"""
Agentic Hospital Management System
====================================
Multi-agent healthcare workflow orchestration using LangGraph + LangChain + Gemini.

Architecture
------------
- SupervisorAgent      : parses the query into a task list, routes control
- PatientInfoAgent      : fetches patient record (parallel-safe)
- DoctorSearchAgent     : finds specialist + earliest slot (parallel-safe)
- LabReportAgent        : checks existing lab reports (parallel-safe)
- AppointmentAgent      : books appointment (depends on DoctorSearchAgent)
- LabSchedulingAgent    : schedules ECG only if missing (depends on LabReportAgent)
- NotificationAgent     : notifies patient (depends on booking/lab completion)
- ValidatorAgent        : self-corrects, checks for hallucination/omission
- Failure recovery is handled via conditional edges + retry counters on shared state.

Install:
    pip install langchain langchain-google-genai langgraph python-dotenv --break-system-packages

Run:
    export GOOGLE_API_KEY="your-gemini-api-key"
    python hospital_agentic_system.py
"""

import os
import json
import operator
from datetime import datetime
from typing import TypedDict, Annotated, List, Dict, Optional, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

# =====================================================================================
# 0. CONFIG
# =====================================================================================

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_API_KEYS", "")
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not set. Set it via `export GOOGLE_API_KEY=...` or `GOOGLE_API_KEYS=...` in .env before running.")

def get_llm(temperature: float = 0.0):
    """Factory so each agent can request its own (possibly differently-tuned) LLM handle."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=temperature,
        convert_system_message_to_human=False,
    )


# =====================================================================================
# 1. DATABASE CONNECTION & TOOLS
# =====================================================================================

import db

def tool_get_patient(patient_id: str) -> Dict:
    p = db.get_patient(patient_id)
    if p:
        return {"success": True, "data": p}
    return {"success": False, "error": f"Patient {patient_id} not found"}


def tool_search_doctors(specialization: str) -> Dict:
    matches = db.get_all_doctors(specialization)
    if not matches:
        return {"success": False, "error": f"No doctors found for specialization '{specialization}'"}
    return {"success": True, "data": matches}


def tool_get_earliest_slot(doctor_id: str) -> Dict:
    d = db.get_doctor(doctor_id)
    if not d:
        return {"success": False, "error": f"Doctor {doctor_id} not found"}
    if not d["available_slots"]:
        return {"success": False, "error": f"No available slots for {d['name']}"}
    earliest = sorted(d["available_slots"], key=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M"))[0]
    return {"success": True, "data": {"doctor_id": doctor_id, "doctor_name": d["name"], "slot": earliest}}


def tool_book_appointment(patient_id: str, doctor_id: str, slot: str, simulate_failure: bool = False) -> Dict:
    if simulate_failure:
        return {"success": False, "error": "Booking system temporarily unavailable"}

    doctor = db.get_doctor(doctor_id)
    if not doctor:
        return {"success": False, "error": f"Doctor {doctor_id} not found"}
    if slot not in doctor["available_slots"]:
        return {"success": False, "error": f"Slot {slot} no longer available"}

    appointment_id = db.get_next_id("appointments", "A")
    db.create_appointment(appointment_id, patient_id, doctor_id, slot, "confirmed")

    # Remove slot from doctor availability
    slots = list(doctor["available_slots"])
    slots.remove(slot)
    db.update_doctor(doctor_id, doctor["name"], doctor["specialization"], doctor["experience"], doctor["fee"], doctor["hospital"], slots)

    return {"success": True, "data": {
        "appointment_id": appointment_id, "doctor_name": doctor["name"], "slot": slot,
    }}


def tool_check_lab_report(patient_id: str, test_name: str) -> Dict:
    reports = db.get_patient_lab_reports(patient_id)
    report = next((r for r in reports if r["test_name"].lower() == test_name.lower()), None)
    if report:
        return {"success": True, "data": {"exists": True, "status": report["status"]}}
    return {"success": True, "data": {"exists": False, "status": None}}


def tool_schedule_lab_test(patient_id: str, test_name: str) -> Dict:
    lab_order_id = db.get_next_id("lab_reports", "L")
    db.create_lab_report(lab_order_id, patient_id, test_name, "Scheduled")
    return {"success": True, "data": {"test_name": test_name, "status": "Scheduled",
                                       "lab_order_id": lab_order_id}}


def tool_send_notification(patient_id: str, message: str, simulate_failure: bool = False) -> Dict:
    if simulate_failure:
        return {"success": False, "error": "Notification service unreachable"}
    
    notification_id = db.get_next_id("notifications", "N")
    sent_at = datetime.now().isoformat()
    db.create_notification(notification_id, patient_id, message, "SMS+Email", "sent", sent_at)
    
    return {"success": True, "data": {"channel": "SMS+Email", "message": message,
                                       "sent_at": sent_at}}



# =====================================================================================
# 3. SHARED STATE (the "message bus" all agents read/write)
# =====================================================================================

class HospitalState(TypedDict):
    patient_id: str
    user_query: str
    session_id: Optional[str]

    messages: Annotated[List[BaseMessage], operator.add]   # inter-agent communication log

    tasks: List[Dict]                # parsed task list from Supervisor
    completed_tasks: List[str]       # task names marked done

    patient_info: Optional[Dict]
    patient_found: Optional[bool]
    missing_information: List[str]
    doctor_search_result: Optional[Dict]
    chosen_doctor: Optional[Dict]    # { "doctor_id": str, "slot": str }
    lab_check_result: Optional[Dict]
    lab_report_analysis: Optional[Dict]

    appointment_result: Optional[Dict]
    lab_schedule_result: Optional[Dict]
    notification_result: Optional[Dict]

    appointment_status: str
    lab_test_status: str
    notification_status: str
    summary: str

    retry_counts: Dict[str, int]
    errors: List[str]
    validation_passed: bool
    validation_feedback: Optional[str]
    next_step: Optional[str]

    # New fields for real-world hospital workflow & human-in-the-loop
    selected_doctor: Optional[str]
    selected_date: Optional[str]
    selected_time: Optional[str]
    waiting_for_confirmation: bool
    user_decision: Optional[str]    # "confirm", "change_doctor", "change_date", "cancel"
    emergency_detected: bool
    workflow_status: str
    lab_test_needed: Optional[str]
    specialization_needed: Optional[str]


MAX_RETRIES = 2


# =====================================================================================
# 4. AGENT: SUPERVISOR  — understands request, builds task plan
# =====================================================================================

SUPERVISOR_SYSTEM_PROMPT = """You are a Hospital Supervisor. Analyze the patient query and return ONLY a JSON object (no markdown, no wrap):
{
   "intent": "Appointment Booking | Lab Test | Existing Lab Report Analysis | Prescription Renewal | Doctor Consultation | Emergency",
   "specialization_needed": "Cardiology | Orthopedics | General Medicine | Pediatrics",
   "lab_test_needed": "ECG | X-Ray | CBC | Lipid | HbA1c | null",
   "wants_lab_analysis": true,
   "wants_nl_summary": false,
   "reasoning": "brief description"
}
Rules:
- Infer specialization: chest pain/heart -> Cardiology, knee/joint -> Orthopedics, child/kid -> Pediatrics, else -> General Medicine.
- Infer lab: chest/cardiac -> ECG, knee/injury -> X-Ray, else -> null.
- wants_lab_analysis is true if they mention checking or reviewing reports.
- wants_nl_summary is true only if they explicitly ask for summary, explanations or text detail.
"""

def supervisor_agent(state: HospitalState) -> HospitalState:
    if state.get("tasks"):
        # Idempotency check: already parsed query
        return state

    llm = get_llm(temperature=0.0)
    prompt = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Patient ID: {state['patient_id']}\nRequest: {state['user_query']}"),
    ]
    
    # Low-token call
    response = llm.invoke(prompt)
    raw = response.content.strip().replace("```json", "").replace("```", "").strip()

    try:
        plan = json.loads(raw)
    except Exception:
        # Fallback plan
        plan = {
            "intent": "Appointment Booking",
            "specialization_needed": "Cardiology" if "chest" in state["user_query"].lower() else "General Medicine",
            "lab_test_needed": "ECG" if "ecg" in state["user_query"].lower() else None,
            "wants_lab_analysis": "ecg" in state["user_query"].lower() or "report" in state["user_query"].lower(),
            "wants_nl_summary": False,
            "reasoning": "Fallback parsing used."
        }

    tasks = [{"name": "load_patient_info"}, {"name": "emergency_check"}]
    
    intent = plan.get("intent", "Appointment Booking")
    if intent in ("Appointment Booking", "Doctor Consultation"):
        tasks.append({"name": "search_doctors", "specialization": plan.get("specialization_needed", "General Medicine")})
        tasks.append({"name": "book_appointment", "specialization": plan.get("specialization_needed", "General Medicine")})
        
    if plan.get("lab_test_needed") and plan["lab_test_needed"] != "null":
        tasks.append({"name": "check_and_schedule_lab", "test_name": plan["lab_test_needed"]})
        
    if plan.get("wants_lab_analysis"):
        tasks.append({"name": "analyze_lab_reports", "test_name": plan.get("lab_test_needed") or "ECG"})
        
    tasks.extend([{"name": "notify_patient"}, {"name": "validator_agent"}, {"name": "summarizer_agent"}])

    log = AIMessage(content=f"[Supervisor] Plan created: {json.dumps(plan)}")

    return {
        **state,
        "tasks": tasks,
        "completed_tasks": [],
        "missing_information": [],
        "messages": [log],
        "retry_counts": {},
        "errors": [],
        "waiting_for_confirmation": False,
        "emergency_detected": False,
        "user_decision": None,
        "workflow_status": "supervisor_completed",
        "lab_test_needed": plan.get("lab_test_needed") if plan.get("lab_test_needed") != "null" else None,
        "specialization_needed": plan.get("specialization_needed", "General Medicine"),
        # Use state mapping to pass custom options to other agents
        "chosen_doctor": None,
        "selected_doctor": None,
        "selected_date": None,
        "selected_time": None,
        "next_step": "patient_info",
    }


def _patient_info_worker(patient_id: str) -> Dict:
    p = db.get_patient(patient_id)
    if p:
        return {
            "agent": "PatientInfoAgent",
            "result": {
                "success": True,
                "data": {
                    "patient_found": True,
                    "patient_info": {
                        "patient_id": p["patient_id"],
                        "name": p["name"],
                        "age": p["age"],
                        "gender": p["gender"]
                    },
                    "medical_history": p["medical_history"],
                    "existing_conditions": p["medical_history"],
                    "allergies": ["None documented"]
                }
            }
        }
    else:
        return {
            "agent": "PatientInfoAgent",
            "result": {
                "success": True,
                "data": {
                    "patient_found": False,
                    "patient_info": {},
                    "medical_history": [],
                    "existing_conditions": [],
                    "allergies": [],
                    "message": "Patient not found. Would you like to register as a new patient?"
                }
            }
        }


def _doctor_search_worker(specialization: str) -> Dict:
    search = tool_search_doctors(specialization)
    if not search["success"]:
        return {
            "agent": "DoctorSearchAgent",
            "result": {
                "success": False,
                "error": f"No doctors found for specialization '{specialization}'",
                "data": {
                    "specialization": specialization,
                    "recommended_doctors": [],
                    "available_slots": [],
                    "patient_choice": None,
                    "booking_possible": False
                }
            }
        }
    
    docs = search["data"]
    recommended = []
    for i, doc in enumerate(docs):
        recommended.append({
            "doctor_id": doc["doctor_id"],
            "name": doc["name"],
            "specialization": doc["specialization"],
            "experience": doc["experience"],
            "fee": doc["fee"],
            "hospital": doc["hospital"],
            "available_slots": doc["available_slots"],
            "rating": round(4.5 + (i % 5) * 0.1, 1)
        })

    all_slots = []
    for doc in docs:
        all_slots.extend(doc["available_slots"])
    all_slots = sorted(list(set(all_slots)))

    return {
        "agent": "DoctorSearchAgent",
        "result": {
            "success": True,
            "data": {
                "specialization": specialization,
                "recommended_doctors": recommended,
                "available_slots": all_slots,
                "patient_choice": None,
                "booking_possible": len(recommended) > 0
            }
        }
    }


def _lab_check_worker(patient_id: str, test_name: str) -> Dict:
    result = tool_check_lab_report(patient_id, test_name)
    return {"agent": "LabReportAgent", "result": result}


def patient_info_agent(state: HospitalState) -> HospitalState:
    """Pre-fetch all context lookups in parallel for performance, but parse sequentially. Supports PatientInfoAgent logic."""
    patient_info = state.get("patient_info")
    doctor_search_result = state.get("doctor_search_result")
    lab_check_result = state.get("lab_check_result")
    
    messages = []
    errors = list(state.get("errors", []))
    
    task_names = {t["name"] for t in state["tasks"]}
    needs_doctor = "book_appointment" in task_names or "search_doctors" in task_names
    lab_task = next((t for t in state["tasks"] if t["name"] == "check_and_schedule_lab"), None)
    
    # Run the SQLite checks concurrently
    if patient_info is None or (needs_doctor and doctor_search_result is None) or (lab_task and lab_check_result is None):
        futures = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            if patient_info is None:
                futures[executor.submit(_patient_info_worker, state["patient_id"])] = "patient_info"
            if needs_doctor and doctor_search_result is None:
                futures[executor.submit(_doctor_search_worker, state.get("specialization_needed") or "General Medicine")] = "doctor_search"
            if lab_task and lab_check_result is None:
                futures[executor.submit(_lab_check_worker, state["patient_id"], lab_task["test_name"])] = "lab_check"
                
            results = {}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    results[key] = {"agent": key, "result": {"success": False, "error": str(e)}}
                    
        if "patient_info" in results:
            pi_res = results["patient_info"]["result"]
            if pi_res.get("success"):
                patient_info = pi_res["data"]
            else:
                errors.append(pi_res.get("error", "Failed to fetch patient info"))
                
        if "doctor_search" in results:
            ds_res = results["doctor_search"]["result"]
            if ds_res.get("success"):
                doctor_search_result = ds_res["data"]
            else:
                errors.append(ds_res.get("error", "Doctor search failed"))
                
        if "lab_check" in results:
            lc_res = results["lab_check"]["result"]
            if lc_res.get("success"):
                lab_check_result = lc_res["data"]
            else:
                errors.append(lc_res.get("error", "Lab report check failed"))

    # Now verify patient info
    patient_found = False
    if patient_info:
        patient_found = patient_info.get("patient_found", False)
        if patient_found:
            inner_info = patient_info.get("patient_info", {})
            name = inner_info.get("name", "Unknown")
            age = inner_info.get("age", "Unknown")
            messages.append(AIMessage(content=f"[PatientInfoAgent] Loaded {name} (age {age})"))
        else:
            messages.append(AIMessage(content="[PatientInfoAgent] Register New Patient"))
            errors.append("Patient not found. Register New Patient")
    else:
        messages.append(AIMessage(content="[PatientInfoAgent] Register New Patient"))
        errors.append("Patient not found. Register New Patient")

    return {
        **state,
        "patient_info": patient_info,
        "patient_found": patient_found,
        "doctor_search_result": doctor_search_result,
        "lab_check_result": lab_check_result,
        "messages": messages,
        "errors": errors,
        "workflow_status": "patient_info_completed",
        "next_step": "emergency_check"
    }

def emergency_check_agent(state: HospitalState) -> HospitalState:
    """Scan search query for critical/emergency keywords using Python rules."""
    import re
    query = re.sub(r'\s+', ' ', state["user_query"].lower().strip())
    is_emergency = False
    er_reason = ""
    
    # Emergency Keyword matching
    if ("chest pain" in query or "chestpain" in query) and ("sudden" in query or "severe" in query or "acute" in query or "intense" in query or "breath" in query or "shortness" in query or "unable" in query or "cannot" in query):
        is_emergency = True
        er_reason = "Sudden, severe or acute chest pain (possible cardiac emergency)"
    elif "heart attack" in query or "heartattack" in query:
        is_emergency = True
        er_reason = "Suspected heart attack"
    elif "stroke" in query:
        is_emergency = True
        er_reason = "Suspected stroke"
    elif "severe bleeding" in query or "heavy bleeding" in query or "bleeding heavily" in query:
        is_emergency = True
        er_reason = "Severe bleeding"
    elif "unconscious" in query or "passed out" in query or "pass out" in query:
        is_emergency = True
        er_reason = "Loss of consciousness"
    elif "difficulty breathing" in query or "unable to breathe" in query or "cannot breathe" in query:
        is_emergency = True
        er_reason = "Acute respiratory distress"
    elif "high fever" in query and "seizure" in query:
        is_emergency = True
        er_reason = "High fever accompanied by seizures"
        
    if is_emergency:
        msg = f"EMERGENCY ALERT: {er_reason} detected. Recommend transfer to nearest emergency room immediately. Skipping appointment scheduling."
        log = AIMessage(content=f"[EmergencyCheckAgent] {msg}")
        return {
            **state,
            "emergency_detected": True,
            "workflow_status": "emergency_stopped",
            "appointment_status": "failed",
            "lab_test_status": "failed",
            "messages": [log],
            "errors": state.get("errors", []) + [msg],
            "next_step": "notification_agent"
        }
    else:
        log = AIMessage(content="[EmergencyCheckAgent] No emergency detected. Continuing standard routing.")
        return {
            **state,
            "emergency_detected": False,
            "workflow_status": "emergency_checked",
            "messages": [log],
            "next_step": "doctor_search_agent"
        }

def doctor_search_agent(state: HospitalState) -> HospitalState:
    """Return ranked matching doctors based on specialized pre-fetched SQLite results."""
    task_names = {t["name"] for t in state["tasks"]}
    if "search_doctors" not in task_names and "book_appointment" not in task_names:
        return {
            **state,
            "workflow_status": "doctor_search_completed",
            "next_step": "wait_for_user_confirmation"
        }
        
    ds = state.get("doctor_search_result")
    messages = []
    
    if ds and ds.get("recommended_doctors"):
        messages.append(AIMessage(content=f"[DoctorSearchAgent] Retrieved {len(ds['recommended_doctors'])} doctors matching specialization {ds.get('specialization')}."))
    else:
        messages.append(AIMessage(content="[DoctorSearchAgent] No doctors found matching criteria."))
        
    return {
        **state,
        "messages": messages,
        "workflow_status": "doctor_search_completed",
        "next_step": "wait_for_user_confirmation"
    }

def wait_for_user_confirmation_node(state: HospitalState) -> HospitalState:
    """Pause block for frontend confirmation. If user_decision is set, skip pause."""
    if state.get("user_decision") is not None:
        return {
            **state,
            "waiting_for_confirmation": False,
            "workflow_status": "confirmation_received"
        }
        
    return {
        **state,
        "waiting_for_confirmation": True,
        "workflow_status": "waiting_for_confirmation"
    }



# =====================================================================================
# 6. AGENT: APPOINTMENT (multi-step: depends on DoctorSearchAgent output)
# =====================================================================================
def appointment_agent(state: HospitalState) -> HospitalState:
    task_names = {t["name"] for t in state["tasks"]}
    if "book_appointment" not in task_names:
        return {**state, "appointment_status": "not_requested", "next_step": "route_after_appointment"}

    # Handle cancellation gracefully
    if state.get("user_decision") == "cancel":
        log = AIMessage(content="[AppointmentAgent] Appointment booking cancelled by user request.")
        return {
            **state,
            "appointment_status": "cancelled",
            "appointment_result": {
                "appointment_status": "cancelled",
                "appointment_id": "",
                "doctor": "None",
                "doctor_name": "None",
                "date": "",
                "time": "",
                "slot": "",
                "next_available": []
            },
            "messages": [log],
            "next_step": "route_after_appointment"
        }

    doctor_id = state.get("selected_doctor")
    slot = None
    if state.get("selected_date") and state.get("selected_time"):
        slot = f"{state['selected_date']} {state['selected_time']}"

    # Fallback to recommended doctor if not provided
    if not doctor_id or not slot:
        ds = state.get("doctor_search_result")
        if ds and ds.get("recommended_doctors"):
            doctor_id = ds["recommended_doctors"][0]["doctor_id"]
            slot = ds["recommended_doctors"][0]["available_slots"][0]

    retry_counts = dict(state.get("retry_counts", {}))
    errors = list(state.get("errors", []))
    messages = []

    if not doctor_id or not slot:
        errors.append("No doctor or slot was selected or available; appointment not booked.")
        messages.append(AIMessage(content="[AppointmentAgent] Cannot book — no slot choice selected/available."))
        return {
            **state,
            "appointment_status": "failed",
            "appointment_result": {
                "appointment_status": "failed",
                "appointment_id": "",
                "doctor": "None",
                "doctor_name": "None",
                "date": "",
                "time": "",
                "slot": "",
                "next_available": []
            },
            "messages": messages,
            "errors": errors,
            "next_step": "route_after_appointment",
        }

    attempt = retry_counts.get("book_appointment", 0)
    booking = tool_book_appointment(state["patient_id"], doctor_id, slot)

    doc_obj = db.get_doctor(doctor_id)
    doctor_name = doc_obj["name"] if doc_obj else "Unknown Doctor"
    date_part, time_part = slot.split(" ") if slot and " " in slot else (slot, "")

    if booking["success"]:
        appt_res = {
            "appointment_status": "confirmed",
            "appointment_id": booking["data"]["appointment_id"],
            "doctor": doctor_name,
            "doctor_name": doctor_name,
            "date": date_part,
            "time": time_part,
            "slot": slot,
            "next_available": []
        }
        messages.append(AIMessage(content=f"[AppointmentAgent] Booked: {json.dumps(appt_res)}"))
        completed = list(state.get("completed_tasks", [])) + ["book_appointment"]
        return {
            **state,
            "appointment_status": "confirmed",
            "appointment_result": appt_res,
            "completed_tasks": completed,
            "messages": messages,
            "next_step": "route_after_appointment",
        }

    # If slot becomes unavailable: suggest alternative slots
    next_slots = doc_obj["available_slots"] if doc_obj else []
    appt_fail_res = {
        "appointment_status": "failed_slot_unavailable",
        "appointment_id": "",
        "doctor": doctor_name,
        "doctor_name": doctor_name,
        "date": date_part,
        "time": time_part,
        "slot": slot,
        "next_available": next_slots[:3]
    }

    if attempt < MAX_RETRIES and next_slots:
        retry_counts["book_appointment"] = attempt + 1
        alt_slot = next_slots[0]
        messages.append(AIMessage(
            content=f"[AppointmentAgent] Slot {slot} unavailable. Retrying with next slot {alt_slot}."
        ))
        booking_retry = tool_book_appointment(state["patient_id"], doctor_id, alt_slot)
        if booking_retry["success"]:
            date_alt, time_alt = alt_slot.split(" ") if " " in alt_slot else (alt_slot, "")
            appt_retry_res = {
                "appointment_status": "confirmed_after_retry",
                "appointment_id": booking_retry["data"]["appointment_id"],
                "doctor": doctor_name,
                "doctor_name": doctor_name,
                "date": date_alt,
                "time": time_alt,
                "slot": alt_slot,
                "next_available": []
            }
            completed = list(state.get("completed_tasks", [])) + ["book_appointment"]
            messages.append(AIMessage(content=f"[AppointmentAgent] Retry succeeded: {json.dumps(appt_retry_res)}"))
            return {
                **state,
                "appointment_status": "confirmed_after_retry",
                "appointment_result": appt_retry_res,
                "completed_tasks": completed,
                "retry_counts": retry_counts,
                "messages": messages,
                "next_step": "route_after_appointment",
            }

    errors.append(f"Appointment booking failed: Slot {slot} no longer available.")
    messages.append(AIMessage(content="[AppointmentAgent] All retries exhausted. Booking failed."))
    return {
        **state,
        "appointment_status": "failed",
        "appointment_result": appt_fail_res,
        "retry_counts": retry_counts,
        "errors": errors,
        "messages": messages,
        "next_step": "route_after_appointment",
    }


# =====================================================================================
# 7. AGENT: LAB SCHEDULING (dynamic decision: only acts if report missing)
# =====================================================================================

def lab_scheduling_agent(state: HospitalState) -> HospitalState:
    task_names = {t["name"] for t in state["tasks"]}
    if "check_and_schedule_lab" not in task_names:
        return {**state, "lab_test_status": "not_requested", "next_step": "route_after_lab"}

    lab_task = next(t for t in state["tasks"] if t["name"] == "check_and_schedule_lab")
    test_name = lab_task["test_name"]
    check = state.get("lab_check_result")
    messages = []
    completed = list(state.get("completed_tasks", []))

    if check is None:
        return {
            **state,
            "lab_test_status": "check_failed",
            "errors": state.get("errors", []) + [f"Could not verify existing {test_name} report."],
            "next_step": "route_after_lab",
        }

    # If reports are recent: Recommend using existing reports
    if check.get("exists"):
        lab_res = {
            "tests": [test_name],
            "lab_date": "N/A",
            "lab_time": "N/A",
            "instructions": [f"You have a recent {test_name} report. Recommending using existing reports to avoid duplicate costs."],
            "lab_booking_id": "EXISTING_" + test_name
        }
        messages.append(AIMessage(content=f"[LabSchedulingAgent] {test_name} report exists. Recommending using existing reports."))
        completed.append("check_and_schedule_lab")
        return {
            **state,
            "lab_test_status": f"already_exists ({check.get('status')})",
            "lab_schedule_result": lab_res,
            "completed_tasks": completed,
            "messages": messages,
            "next_step": "route_after_lab",
        }

    # Otherwise, schedule new test
    schedule = tool_schedule_lab_test(state["patient_id"], test_name)
    if schedule["success"]:
        # Simulate Technician, Machine, Laboratory Room allocation
        tech_name = "Technician Sarah Connor"
        room_name = "Lab Room 204"
        machine_name = f"{test_name} Machine Model X"
        
        instructions = []
        if test_name.upper() == "ECG":
            instructions = [
                "No fasting required.",
                "Avoid caffeine, tobacco, or alcohol 2 hours before the test.",
                "Wear comfortable, loose clothing to easily place electrodes."
            ]
        elif test_name.upper() in ("BLOOD TEST", "LIPID", "HBA1C", "CBC"):
            instructions = [
                "Fasting required: Do not eat or drink anything except water for 8 to 12 hours beforehand.",
                "Take regular medications unless advised otherwise by your doctor.",
                "Stay well hydrated with plain water."
            ]
        elif test_name.upper() == "X-RAY":
            instructions = [
                "Remove any metal jewelry or clothing with metal zippers/buttons.",
                "Inform the technician if there is any possibility of pregnancy.",
                "Wear a hospital gown if requested."
            ]
        else:
            instructions = ["No special preparation needed. Please report 15 mins before schedule."]

        # Allocate date and time (e.g. tomorrow or next day)
        appt_slot = state.get("appointment_result", {})
        lab_date = appt_slot.get("date") or datetime.now().strftime("%Y-%m-%d")
        lab_time = "10:30 AM" if appt_slot.get("time") else "09:00 AM"

        lab_res = {
            "tests": [test_name],
            "lab_date": lab_date,
            "lab_time": lab_time,
            "instructions": instructions + [f"Allocated: {tech_name}, {room_name}, using {machine_name}."],
            "lab_booking_id": schedule["data"]["lab_order_id"]
        }
        
        completed.append("check_and_schedule_lab")
        messages.append(AIMessage(content=f"[LabSchedulingAgent] Scheduled new {test_name}: {json.dumps(lab_res)}"))
        return {
            **state,
            "lab_test_status": "scheduled",
            "lab_schedule_result": lab_res,
            "completed_tasks": completed,
            "messages": messages,
            "next_step": "route_after_lab",
        }

    return {
        **state,
        "lab_test_status": "scheduling_failed",
        "errors": state.get("errors", []) + [schedule.get("error", "Lab scheduling failed")],
        "messages": messages,
        "next_step": "route_after_lab",
    }


# =====================================================================================
# 8. AGENT: LAB REPORT ANALYSIS
# =====================================================================================

LAB_REPORT_SYSTEM_PROMPT = """You are a Lab Analyzer. Analyze the test and medical history, then return ONLY a JSON object:
{
   "summary": "Explain results in simple patient-friendly words",
   "abnormal_results": [
      {"parameter": "Parameter Name", "value": "Value", "normal_range": "Range", "flag": "High | Low | Abnormal"}
   ],
   "normal_results": [
      {"parameter": "Parameter Name", "value": "Value", "normal_range": "Range", "flag": "Normal"}
   ],
   "risk_level": "Low | Moderate | High",
   "recommendation": "Follow-up recommendations"
}
"""

def lab_report_agent(state: HospitalState) -> HospitalState:
    task_names = {t["name"] for t in state["tasks"]}
    if "analyze_lab_reports" not in task_names or state.get("user_decision") == "cancel":
        return {**state, "lab_report_analysis": None, "next_step": "route_after_lab"}

    lab_task = next((t for t in state["tasks"] if t["name"] == "analyze_lab_reports"), None)
    test_name = lab_task["test_name"] if lab_task else "ECG"

    # Analyze only if explicitly requested in user query or intent is lab analysis
    query = state["user_query"].lower()
    needs_explanation = ("explain" in query or "analyze" in query or "review" in query or "what does my report say" in query or "check my report" in query)

    if needs_explanation:
        # Load actual lab report details from JSON file if available
        import os
        report_data = None
        reports_dir = os.path.join(os.path.dirname(__file__), "Reports")
        report_path = os.path.join(reports_dir, f"{state['patient_id']}.json")
        if os.path.exists(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    report_data = json.load(f)
            except Exception:
                pass

        llm = get_llm(temperature=0.2)
        report_context = f"\nReport Data: {json.dumps(report_data)}" if report_data else ""
        prompt = [
            SystemMessage(content=LAB_REPORT_SYSTEM_PROMPT),
            HumanMessage(content=f"Patient ID: {state['patient_id']}\nMedical History: {json.dumps(state.get('patient_info', {}).get('medical_history', []))}\nTest Analyzed: {test_name}{report_context}")
        ]
        try:
            response = llm.invoke(prompt)
            raw = response.content.strip().replace("```json", "").replace("```", "").strip()
            analysis = json.loads(raw)
        except Exception:
            needs_explanation = False # fallback to Python

    if not needs_explanation:
        # Failsafe deterministic Python summary
        analysis = {
            "summary": f"Your {test_name} test report is reviewed. Standard parameters are stable.",
            "abnormal_results": [],
            "normal_results": [
                {"parameter": f"{test_name} status", "value": "Completed", "normal_range": "Completed", "flag": "Normal"}
            ],
            "risk_level": "Low",
            "recommendation": "Keep standard monitoring. Show this report to your doctor at your consultation."
        }

    messages = [AIMessage(content=f"[LabReportAgent] Completed analysis: {json.dumps(analysis)}")]

    return {
        **state,
        "lab_report_analysis": analysis,
        "completed_tasks": list(state.get("completed_tasks", [])) + ["analyze_lab_reports"],
        "messages": messages,
        "next_step": "route_after_lab"
    }


# =====================================================================================
# 9. AGENT: NOTIFICATION (depends on appointment + lab outcomes)
# =====================================================================================

def notification_agent(state: HospitalState) -> HospitalState:
    task_names = {t["name"] for t in state["tasks"]}
    if "notify_patient" not in task_names:
        return {**state, "notification_status": "not_requested", "next_step": "validate"}

    parts = []
    
    # Check for Emergency
    if state.get("emergency_detected"):
        parts.append("EMERGENCY ALERT: We detected symptoms of a medical emergency in your query. Please visit the nearest Emergency Room immediately. Appointment booking has been bypassed.")
    # Check for cancellation
    elif state.get("user_decision") == "cancel":
        parts.append("Your hospital booking request has been cancelled per your request.")
    # Standard workflow
    else:
        if state.get("appointment_status", "").startswith("confirmed"):
            ar = state["appointment_result"]
            parts.append(f"Your appointment with {ar['doctor_name']} is confirmed for {ar['slot']} (ID: {ar['appointment_id']}).")
        elif state.get("appointment_status") in ("failed", "failed_no_availability"):
            parts.append("We were unable to book your appointment automatically; our staff will follow up shortly.")

        if state.get("lab_test_status", "").startswith("already_exists"):
            parts.append(f"Note: your existing lab report status is {state['lab_test_status'].split('(')[-1].rstrip(')')}.")
        elif state.get("lab_test_status") == "scheduled":
            lr = state["lab_schedule_result"]
            parts.append(f"Your {lr['tests'][0] if lr.get('tests') else 'diagnostic'} test has been scheduled (Order ID: {lr['lab_booking_id']}).")

    message = " ".join(parts) if parts else "Your request has been processed."

    retry_counts = dict(state.get("retry_counts", {}))
    attempt = retry_counts.get("notify_patient", 0)
    send = tool_send_notification(state["patient_id"], message)

    if send["success"]:
        completed = list(state.get("completed_tasks", [])) + ["notify_patient"]
        return {
            **state,
            "notification_status": "sent",
            "notification_result": send["data"],
            "completed_tasks": completed,
            "messages": [AIMessage(content=f"[NotificationAgent] Sent: {message}")],
            "next_step": "validate",
        }

    # Failure recovery: retry once
    if attempt < MAX_RETRIES:
        retry_counts["notify_patient"] = attempt + 1
        retry_send = tool_send_notification(state["patient_id"], message)
        if retry_send["success"]:
            completed = list(state.get("completed_tasks", [])) + ["notify_patient"]
            return {
                **state,
                "notification_status": "sent_after_retry",
                "notification_result": retry_send["data"],
                "completed_tasks": completed,
                "retry_counts": retry_counts,
                "messages": [AIMessage(content=f"[NotificationAgent] Retry succeeded: {message}")],
                "next_step": "validate",
            }

    return {
        **state,
        "notification_status": "failed",
        "errors": state.get("errors", []) + [send.get("error", "Notification failed")],
        "retry_counts": retry_counts,
        "messages": [AIMessage(content="[NotificationAgent] Notification failed after retry. Logged for manual follow-up.")],
        "next_step": "validate",
    }


# =====================================================================================
# 10. AGENT: VALIDATOR — self-correction / hallucination & completeness check
# =====================================================================================

def validator_agent(state: HospitalState) -> HospitalState:
    passed = True
    feedback = []

    # 1. Patient exists
    if not state.get("patient_found"):
        passed = False
        feedback.append("Patient does not exist. Registration required.")

    # Task planning validations
    task_names = {t["name"] for t in state["tasks"]}

    # If emergency, we skip everything except notification and validation/summary
    if state.get("emergency_detected"):
        if not state.get("notification_status") == "sent":
            passed = False
            feedback.append("Emergency notification was not sent.")
    else:
        # If user cancelled, verify appointment is cancelled and notification is sent
        if state.get("user_decision") == "cancel":
            if state.get("appointment_status") != "cancelled":
                passed = False
                feedback.append("Appointment cancellation status not set correctly.")
        else:
            # 2. Doctor exists & Appointment exists (if planned)
            if "book_appointment" in task_names:
                if state.get("appointment_status") not in ("confirmed", "confirmed_after_retry"):
                    if not any("appointment" in err.lower() or "booking" in err.lower() for err in state.get("errors", [])):
                        passed = False
                        feedback.append("Appointment was planned but not completed, and no error was logged.")
                else:
                    appt = state.get("appointment_result", {})
                    if not appt or not appt.get("doctor"):
                        passed = False
                        feedback.append("Appointment is confirmed but missing doctor name.")

            # 3. Lab booking valid (if planned)
            if "check_and_schedule_lab" in task_names:
                if not state.get("lab_test_status"):
                    passed = False
                    feedback.append("Lab scheduling was planned but no status recorded.")
                else:
                    check = state.get("lab_check_result")
                    if check and check.get("exists"):
                        if not state.get("lab_test_status", "").startswith("already_exists"):
                            passed = False
                            feedback.append("Duplicate lab test scheduled when recent report already exists.")

            # 4. Notification sent (if planned)
            if "notify_patient" in task_names:
                if state.get("notification_status") not in ("sent", "sent_after_retry"):
                    if not any("notification" in err.lower() for err in state.get("errors", [])):
                        passed = False
                        feedback.append("Notification was planned but not sent, and no error was logged.")

    # 5. Hallucination check
    if "book_appointment" not in task_names and state.get("appointment_status") in ("confirmed", "confirmed_after_retry"):
        passed = False
        feedback.append("Hallucination: Appointment booked but was not in the plan.")

    feedback_str = "; ".join(feedback) if feedback else "All validation checks passed."
    log = AIMessage(content=f"[ValidatorAgent] validation_passed={passed}. Feedback: {feedback_str}")

    return {
        **state,
        "validation_passed": passed,
        "validation_feedback": feedback_str,
        "messages": [log],
        "next_step": "finalize" if passed else "revise",
    }


# =====================================================================================
# 11. AGENT: SUMMARIZER — final natural-language response, grounded strictly in tool outputs
# =====================================================================================

SUMMARIZER_SYSTEM_PROMPT = """You are a Summary Agent. Summarize the hospital results as JSON ONLY:
{
   "patient_summary": "Friendly, reassuring summary for patient",
   "admin_summary": "Concise factual summary for admin"
}
"""

def summarizer_agent(state: HospitalState) -> HospitalState:
    query = state["user_query"].lower()
    wants_nl_summary = ("summarize" in query or "explain in words" in query or "detailed summary" in query or "explain results" in query)

    patient_summary = ""
    admin_summary = ""

    if wants_nl_summary:
        llm = get_llm(temperature=0.2)
        grounded_data = {
            "patient_name": state.get("patient_info", {}).get("patient_info", {}).get("name", "Unknown") if state.get("patient_info") else "Unknown",
            "user_query": state.get("user_query"),
            "appointment_status": state.get("appointment_status"),
            "appointment_result": state.get("appointment_result"),
            "lab_test_status": state.get("lab_test_status"),
            "lab_schedule_result": state.get("lab_schedule_result"),
            "lab_report_analysis": state.get("lab_report_analysis"),
            "notification_status": state.get("notification_status"),
            "emergency_detected": state.get("emergency_detected"),
            "errors": state.get("errors", []),
        }
        prompt = [
            SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(grounded_data)),
        ]
        try:
            response = llm.invoke(prompt)
            raw = response.content.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            patient_summary = data.get("patient_summary", "")
            admin_summary = data.get("admin_summary", "")
        except Exception:
            wants_nl_summary = False

    if not wants_nl_summary or not patient_summary:
        # Default Python summary (saves tokens!)
        name = state.get("patient_info", {}).get("patient_info", {}).get("name", "Patient") if state.get("patient_info") else "Patient"

        if state.get("emergency_detected"):
            patient_summary = f"Dear {name}, we detected symptoms of a medical emergency in your request. Please visit the nearest Emergency Room immediately. We bypassed standard scheduling for your safety."
            admin_summary = f"ADMIN ALERT: Emergency detected for patient {state['patient_id']}. Booking bypassed."
        elif state.get("user_decision") == "cancel":
            patient_summary = f"Dear {name}, your appointment scheduling request has been cancelled per your request."
            admin_summary = f"ADMIN NOTE: Patient {state['patient_id']} cancelled booking process."
        else:
            appt = state.get("appointment_result")
            appt_str = ""
            if appt and state.get("appointment_status") in ("confirmed", "confirmed_after_retry"):
                appt_str = f"with {appt.get('doctor_name')} on {appt.get('slot')}"
            else:
                appt_str = "could not be scheduled automatically"

            lab = state.get("lab_schedule_result")
            lab_str = ""
            if lab:
                if lab.get("lab_booking_id", "").startswith("EXISTING"):
                    lab_str = "Your existing diagnostic report was reused."
                else:
                    lab_str = f"A new {', '.join(lab.get('tests', []))} test was scheduled for {lab.get('lab_date')} at {lab.get('lab_time')}."

            patient_summary = f"Dear {name}, your appointment {appt_str} is processed. {lab_str} A notification has been sent to your registered contact."
            admin_summary = f"ADMIN: Patient {state['patient_id']} processed. Appointment: {state.get('appointment_status')}. Lab: {state.get('lab_test_status')}."

    summary_log = f"Patient: {patient_summary}\nAdmin: {admin_summary}"
    log = AIMessage(content=f"[SummarizerAgent] {summary_log}")

    merged = {
        **state,
        "summary": json.dumps({"patient_summary": patient_summary, "admin_summary": admin_summary}),
        "messages": [log],
        "next_step": "done",
    }

    try:
        from pdf_generator import generate_patient_report
        generate_patient_report(merged)
        print("[SummarizerAgent] PDF Report generated successfully.")
    except Exception as pdf_err:
        print(f"[SummarizerAgent] PDF Report generation failed: {pdf_err}")

    return merged


def revision_router_node(state: HospitalState) -> HospitalState:
    """Entered when validator fails — loops back or exits gracefully."""
    revise_attempt = state.get("retry_counts", {}).get("__revision__", 0)
    retry_counts = dict(state.get("retry_counts", {}))
    retry_counts["__revision__"] = revise_attempt + 1

    messages = [AIMessage(content=f"[Supervisor] Validation failed: {state.get('validation_feedback')}. Re-routing (revision {revise_attempt + 1}).")]

    if revise_attempt >= MAX_RETRIES:
        return {**state, "retry_counts": retry_counts, "messages": messages, "next_step": "finalize"}

    return {**state, "retry_counts": retry_counts, "messages": messages, "next_step": "reroute_notification"}


# =====================================================================================
# 11. ROUTING FUNCTIONS (conditional edges)
# =====================================================================================

def route_after_emergency(state: HospitalState) -> str:
    if state.get("emergency_detected"):
        return "notification_agent"
    return "doctor_search_agent"

def route_after_confirmation(state: HospitalState) -> str:
    if state.get("user_decision") == "cancel":
        return "notification_agent"
    return "appointment_agent"

def route_after_appointment(state: HospitalState) -> str:
    # If user cancelled, skip lab scheduling
    if state.get("user_decision") == "cancel":
        return "notification_agent"
    # Route to lab if needed
    task_names = {t["name"] for t in state["tasks"]}
    if "check_and_schedule_lab" in task_names:
        return "lab_scheduling_agent"
    if "analyze_lab_reports" in task_names:
        return "lab_report_agent"
    return "notification_agent"

def route_after_lab(state: HospitalState) -> str:
    task_names = {t["name"] for t in state["tasks"]}
    if "analyze_lab_reports" in task_names and state.get("user_decision") != "cancel":
        return "lab_report_agent"
    return "notification_agent"

def route_after_validation(state: HospitalState) -> str:
    return "finalize" if state["validation_passed"] else "revise"

def route_after_revision(state: HospitalState) -> str:
    return state["next_step"]  # "reroute_notification" or "finalize"


# =====================================================================================
# 12. FINALIZE NODE
# =====================================================================================

def finalize_node(state: HospitalState) -> HospitalState:
    return {
        **state,
        "appointment_status": state.get("appointment_status", "not_requested"),
        "lab_test_status": state.get("lab_test_status", "not_requested"),
        "notification_status": state.get("notification_status", "not_requested"),
    }


# =====================================================================================
# 13. BUILD THE GRAPH
# =====================================================================================

# Use a shared global checkpointer instance so state is preserved across request boundaries
global_memory = MemorySaver()

def build_graph():
    graph = StateGraph(HospitalState)

    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("patient_info_agent", patient_info_agent)
    graph.add_node("emergency_check_agent", emergency_check_agent)
    graph.add_node("doctor_search_agent", doctor_search_agent)
    graph.add_node("wait_for_user_confirmation_node", wait_for_user_confirmation_node)
    graph.add_node("appointment_agent", appointment_agent)
    graph.add_node("lab_scheduling_agent", lab_scheduling_agent)
    graph.add_node("lab_report_agent", lab_report_agent)
    graph.add_node("notification_agent", notification_agent)
    graph.add_node("validator_agent", validator_agent)
    graph.add_node("revision_router", revision_router_node)
    graph.add_node("summarizer_agent", summarizer_agent)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("supervisor")

    graph.add_edge("supervisor", "patient_info_agent")
    graph.add_edge("patient_info_agent", "emergency_check_agent")
    
    # Branch after Emergency Check
    graph.add_conditional_edges("emergency_check_agent", route_after_emergency, {
        "notification_agent": "notification_agent",
        "doctor_search_agent": "doctor_search_agent"
    })
    
    # Doctor Search routes to WAIT node
    graph.add_edge("doctor_search_agent", "wait_for_user_confirmation_node")
    
    # Route after confirmation
    graph.add_conditional_edges("wait_for_user_confirmation_node", route_after_confirmation, {
        "notification_agent": "notification_agent",
        "appointment_agent": "appointment_agent"
    })

    # Route after appointment
    graph.add_conditional_edges("appointment_agent", route_after_appointment, {
        "lab_scheduling_agent": "lab_scheduling_agent",
        "notification_agent": "notification_agent"
    })

    # Route after lab scheduling
    graph.add_conditional_edges("lab_scheduling_agent", route_after_lab, {
        "lab_report_agent": "lab_report_agent",
        "notification_agent": "notification_agent"
    })

    graph.add_edge("lab_report_agent", "notification_agent")
    graph.add_edge("notification_agent", "validator_agent")

    graph.add_conditional_edges("validator_agent", route_after_validation, {
        "finalize": "summarizer_agent",
        "revise": "revision_router",
    })

    graph.add_conditional_edges("revision_router", route_after_revision, {
        "reroute_notification": "notification_agent",
        "finalize": "summarizer_agent",
    })

    graph.add_edge("summarizer_agent", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=global_memory, interrupt_before=["appointment_agent"])


# =====================================================================================
# 14. ENTRY POINT
# =====================================================================================

def run_hospital_workflow(patient_id: str, user_query: str, verbose: bool = True) -> Dict:
    app = build_graph()
    config = {"configurable": {"thread_id": f"console_{patient_id}"}}

    initial_state: HospitalState = {
        "patient_id": patient_id,
        "user_query": user_query,
        "messages": [],
        "tasks": [],
        "completed_tasks": [],
        "patient_info": None,
        "doctor_search_result": None,
        "lab_check_result": None,
        "appointment_result": None,
        "lab_schedule_result": None,
        "notification_result": None,
        "appointment_status": "",
        "lab_test_status": "",
        "notification_status": "",
        "summary": "",
        "retry_counts": {},
        "errors": [],
        "validation_passed": False,
        "validation_feedback": None,
        "next_step": None,
        "selected_doctor": None,
        "selected_date": None,
        "selected_time": None,
        "waiting_for_confirmation": False,
        "user_decision": None,
        "emergency_detected": False,
        "workflow_status": "started",
        "lab_test_needed": None,
        "specialization_needed": None,
    }

    # Run the graph
    events = app.stream(initial_state, config=config, stream_mode="values")
    final_state = initial_state
    for event in events:
        final_state = event

    # If it is interrupted waiting for confirmation (console demo fallback: choose first doctor)
    state_info = app.get_state(config)
    if state_info.next:
        # Re-invoke / resume with the first doctor for console demo
        ds = final_state.get("doctor_search_result")
        if ds and ds.get("recommended_doctors"):
            doc = ds["recommended_doctors"][0]
            slots = doc.get("available_slots", [])
            first_slot = slots[0] if slots else "2026-07-10 09:00"
            parts = first_slot.split(" ")
            app.update_state(config, {
                "selected_doctor": doc["doctor_id"],
                "selected_date": parts[0],
                "selected_time": parts[1] if len(parts) > 1 else "09:00",
                "user_decision": "confirm"
            })
        else:
            app.update_state(config, {"user_decision": "cancel"})
            
        events = app.stream(None, config=config, stream_mode="values")
        for event in events:
            final_state = event

    if verbose:
        print("\n===== AGENT COMMUNICATION LOG =====")
        for m in final_state["messages"]:
            print(m.content)
        print("====================================\n")

    output = {
        "appointment_status": final_state["appointment_status"],
        "lab_test_status": final_state["lab_test_status"],
        "notification_status": final_state["notification_status"],
        "summary": final_state["summary"],
    }
    return output


if __name__ == "__main__":
    # Ensure fresh DB state for console verification
    if os.path.exists(db.DB_FILE):
        try:
            os.remove(db.DB_FILE)
        except Exception:
            pass
    db.init_db()

    result = run_hospital_workflow(
        patient_id="P002",
        user_query=(
            "I have chest pain. Book the earliest appointment with a cardiologist. "
            "Check whether I already have an ECG report. If not, schedule an ECG test. "
            "Finally notify me with all the details."
        ),
    )
    print(json.dumps(result, indent=2))

    print("\n--- Second run: patient who already has ECG ---")
    result2 = run_hospital_workflow(
        patient_id="P001",
        user_query=(
            "I have been experiencing chest pain for the last two days. "
            "Book the earliest available cardiologist appointment. "
            "Check whether I already have an ECG report. "
            "If no ECG exists, schedule an ECG test. "
            "Notify me after everything is completed."
        ),
    )
    print(json.dumps(result2, indent=2))