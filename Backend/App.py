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
# 1. DUMMY HOSPITAL DATA (in-memory "DB")
# =====================================================================================

DB = {
    "patients": [
        {"patient_id": "P001", "name": "John Doe", "age": 45, "appointments": ["A101"], "lab_reports": ["ECG"]},
        {"patient_id": "P002", "name": "Alice Smith", "age": 32, "appointments": [], "lab_reports": []},
        {"patient_id": "P003", "name": "Ravi Kumar", "age": 58, "appointments": [], "lab_reports": []},
    ],
    "doctors": [
        {
            "doctor_id": "D101", "name": "Dr. Brown", "specialization": "Cardiology",
            "available_slots": ["2026-07-10 09:00", "2026-07-10 11:00"],
        },
        {
            "doctor_id": "D102", "name": "Dr. Green", "specialization": "Orthopedics",
            "available_slots": ["2026-07-11 10:00", "2026-07-11 14:00"],
        },
        {
            "doctor_id": "D103", "name": "Dr. Patel", "specialization": "General Medicine",
            "available_slots": ["2026-07-09 08:30", "2026-07-09 15:00"],
        },
    ],
    "appointments": [
        {"appointment_id": "A101", "patient_id": "P001", "doctor_id": "D101", "slot": "2026-07-10 09:00"},
    ],
    "lab_reports": [
        {"patient_id": "P001", "test_name": "ECG", "status": "Completed"},
        {"patient_id": "P001", "test_name": "Blood Test", "status": "Completed"},
    ],
}

_appt_counter = [102]
_lab_counter = [1]


# =====================================================================================
# 2. TOOLS  (simulate hospital backend / external systems — these are what agents call)
# =====================================================================================

def tool_get_patient(patient_id: str) -> Dict:
    for p in DB["patients"]:
        if p["patient_id"] == patient_id:
            return {"success": True, "data": p}
    return {"success": False, "error": f"Patient {patient_id} not found"}


def tool_search_doctors(specialization: str) -> Dict:
    matches = [d for d in DB["doctors"] if d["specialization"].lower() == specialization.lower()]
    if not matches:
        return {"success": False, "error": f"No doctors found for specialization '{specialization}'"}
    return {"success": True, "data": matches}


def tool_get_earliest_slot(doctor_id: str) -> Dict:
    for d in DB["doctors"]:
        if d["doctor_id"] == doctor_id:
            if not d["available_slots"]:
                return {"success": False, "error": f"No available slots for {d['name']}"}
            earliest = sorted(d["available_slots"], key=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M"))[0]
            return {"success": True, "data": {"doctor_id": doctor_id, "doctor_name": d["name"], "slot": earliest}}
    return {"success": False, "error": f"Doctor {doctor_id} not found"}


def tool_book_appointment(patient_id: str, doctor_id: str, slot: str, simulate_failure: bool = False) -> Dict:
    if simulate_failure:
        return {"success": False, "error": "Booking system temporarily unavailable"}

    doctor = next((d for d in DB["doctors"] if d["doctor_id"] == doctor_id), None)
    if not doctor:
        return {"success": False, "error": f"Doctor {doctor_id} not found"}
    if slot not in doctor["available_slots"]:
        return {"success": False, "error": f"Slot {slot} no longer available"}

    _appt_counter[0] += 1
    appointment_id = f"A{_appt_counter[0]}"

    doctor["available_slots"].remove(slot)
    DB["appointments"].append({
        "appointment_id": appointment_id, "patient_id": patient_id,
        "doctor_id": doctor_id, "slot": slot,
    })
    patient = next((p for p in DB["patients"] if p["patient_id"] == patient_id), None)
    if patient:
        patient["appointments"].append(appointment_id)

    return {"success": True, "data": {
        "appointment_id": appointment_id, "doctor_name": doctor["name"], "slot": slot,
    }}


def tool_check_lab_report(patient_id: str, test_name: str) -> Dict:
    report = next((r for r in DB["lab_reports"]
                    if r["patient_id"] == patient_id and r["test_name"].lower() == test_name.lower()), None)
    if report:
        return {"success": True, "data": {"exists": True, "status": report["status"]}}
    return {"success": True, "data": {"exists": False, "status": None}}


def tool_schedule_lab_test(patient_id: str, test_name: str) -> Dict:
    _lab_counter[0] += 1
    new_report = {"patient_id": patient_id, "test_name": test_name, "status": "Scheduled"}
    DB["lab_reports"].append(new_report)
    patient = next((p for p in DB["patients"] if p["patient_id"] == patient_id), None)
    if patient:
        patient["lab_reports"].append(test_name)
    return {"success": True, "data": {"test_name": test_name, "status": "Scheduled",
                                       "lab_order_id": f"L{_lab_counter[0]}"}}


def tool_send_notification(patient_id: str, message: str, simulate_failure: bool = False) -> Dict:
    if simulate_failure:
        return {"success": False, "error": "Notification service unreachable"}
    return {"success": True, "data": {"channel": "SMS+Email", "message": message,
                                       "sent_at": datetime.now().isoformat()}}


# =====================================================================================
# 3. SHARED STATE (the "message bus" all agents read/write)
# =====================================================================================

class HospitalState(TypedDict):
    patient_id: str
    user_query: str

    messages: Annotated[List[BaseMessage], operator.add]   # inter-agent communication log

    tasks: List[Dict]                # parsed task list from Supervisor
    completed_tasks: List[str]       # task names marked done

    patient_info: Optional[Dict]
    doctor_search_result: Optional[Dict]
    lab_check_result: Optional[Dict]

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


MAX_RETRIES = 2


# =====================================================================================
# 4. AGENT: SUPERVISOR  — understands request, builds task plan
# =====================================================================================

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor Agent in a hospital multi-agent system.
Read the patient's natural-language request and extract a structured task plan.

Return ONLY valid JSON (no markdown fences, no commentary) in this exact shape:
{{
  "specialization_needed": "<medical specialization inferred from symptoms, e.g. Cardiology>",
  "wants_appointment": true/false,
  "lab_test_needed": "<test name if one is mentioned/implied, else null>",
  "wants_notification": true/false,
  "reasoning": "<one sentence explaining the inference>"
}}

Rules:
- Infer specialization from symptoms if not stated explicitly (e.g. chest pain -> Cardiology).
- If the user asks to check for an existing report AND schedule it conditionally, set lab_test_needed to that test's name regardless — downstream agents will decide whether to actually schedule it.
- Be conservative: only set fields true/non-null if the request clearly implies them.
"""

def supervisor_agent(state: HospitalState) -> HospitalState:
    llm = get_llm(temperature=0.0)
    prompt = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Patient ID: {state['patient_id']}\nRequest: {state['user_query']}"),
    ]
    response = llm.invoke(prompt)
    raw = response.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback heuristic plan if the model returns malformed JSON
        plan = {
            "specialization_needed": "Cardiology" if "chest" in state["user_query"].lower() else "General Medicine",
            "wants_appointment": True,
            "lab_test_needed": "ECG" if "ecg" in state["user_query"].lower() else None,
            "wants_notification": "notify" in state["user_query"].lower(),
            "reasoning": "Fallback heuristic used due to parse failure.",
        }

    tasks = []
    if plan.get("wants_appointment"):
        tasks.append({"name": "book_appointment", "specialization": plan.get("specialization_needed", "General Medicine")})
    if plan.get("lab_test_needed"):
        tasks.append({"name": "check_and_schedule_lab", "test_name": plan["lab_test_needed"]})
    if plan.get("wants_notification"):
        tasks.append({"name": "notify_patient"})

    log = AIMessage(content=f"[Supervisor] Plan created: {json.dumps(plan)}")

    return {
        **state,
        "tasks": tasks,
        "completed_tasks": [],
        "messages": [log],
        "retry_counts": {},
        "errors": [],
        "next_step": "gather_context",
    }


# =====================================================================================
# 5. PARALLEL CONTEXT-GATHERING NODE
#    Runs PatientInfoAgent, DoctorSearchAgent, LabReportAgent concurrently
#    (these are independent reads — no reason to serialize them)
# =====================================================================================

def _patient_info_worker(patient_id: str) -> Dict:
    result = tool_get_patient(patient_id)
    return {"agent": "PatientInfoAgent", "result": result}


def _doctor_search_worker(specialization: str) -> Dict:
    search = tool_search_doctors(specialization)
    if not search["success"]:
        return {"agent": "DoctorSearchAgent", "result": search}
    doctor = search["data"][0]  # pick first matching specialist
    slot_result = tool_get_earliest_slot(doctor["doctor_id"])
    if not slot_result["success"]:
        return {"agent": "DoctorSearchAgent", "result": slot_result}
    return {"agent": "DoctorSearchAgent", "result": {"success": True, "data": slot_result["data"]}}


def _lab_check_worker(patient_id: str, test_name: str) -> Dict:
    result = tool_check_lab_report(patient_id, test_name)
    return {"agent": "LabReportAgent", "result": result}


def parallel_context_gathering_node(state: HospitalState) -> HospitalState:
    """Fan-out independent lookups concurrently, fan-in results into shared state."""
    task_names = {t["name"] for t in state["tasks"]}
    needs_doctor = "book_appointment" in task_names
    lab_task = next((t for t in state["tasks"] if t["name"] == "check_and_schedule_lab"), None)

    futures = {}
    new_messages = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures[executor.submit(_patient_info_worker, state["patient_id"])] = "patient_info"
        if needs_doctor:
            spec_task = next(t for t in state["tasks"] if t["name"] == "book_appointment")
            futures[executor.submit(_doctor_search_worker, spec_task["specialization"])] = "doctor_search"
        if lab_task:
            futures[executor.submit(_lab_check_worker, state["patient_id"], lab_task["test_name"])] = "lab_check"

        results = {}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"agent": key, "result": {"success": False, "error": str(e)}}

    patient_info = results.get("patient_info", {}).get("result")
    doctor_search_result = results.get("doctor_search", {}).get("result")
    lab_check_result = results.get("lab_check", {}).get("result")

    new_messages.append(AIMessage(content=f"[PatientInfoAgent] {json.dumps(patient_info)}"))
    if doctor_search_result is not None:
        new_messages.append(AIMessage(content=f"[DoctorSearchAgent] {json.dumps(doctor_search_result)}"))
    if lab_check_result is not None:
        new_messages.append(AIMessage(content=f"[LabReportAgent] {json.dumps(lab_check_result)}"))

    errors = list(state.get("errors", []))
    if patient_info and not patient_info.get("success"):
        errors.append(patient_info.get("error", "Failed to fetch patient info"))
    if doctor_search_result and not doctor_search_result.get("success"):
        errors.append(doctor_search_result.get("error", "Doctor search failed"))

    return {
        **state,
        "patient_info": patient_info,
        "doctor_search_result": doctor_search_result,
        "lab_check_result": lab_check_result,
        "messages": new_messages,
        "errors": errors,
        "next_step": "route_after_context",
    }


# =====================================================================================
# 6. AGENT: APPOINTMENT (multi-step: depends on DoctorSearchAgent output)
# =====================================================================================

def appointment_agent(state: HospitalState) -> HospitalState:
    task_names = {t["name"] for t in state["tasks"]}
    if "book_appointment" not in task_names:
        return {**state, "appointment_status": "not_requested", "next_step": "route_after_appointment"}

    ds = state.get("doctor_search_result")
    retry_counts = dict(state.get("retry_counts", {}))
    errors = list(state.get("errors", []))
    messages = []

    if not ds or not ds.get("success"):
        # Failure recovery: no doctor/slot available at all
        errors.append("No cardiology slot could be found; appointment not booked.")
        messages.append(AIMessage(content="[AppointmentAgent] Cannot book — no doctor/slot available. Escalating to alternative-slot search."))
        return {
            **state,
            "appointment_status": "failed_no_availability",
            "appointment_result": None,
            "messages": messages,
            "errors": errors,
            "next_step": "route_after_appointment",
        }

    doctor_id = ds["data"]["doctor_id"]
    slot = ds["data"]["slot"]

    attempt = retry_counts.get("book_appointment", 0)
    simulate_failure = False  # toggle True to test failure-recovery path
    booking = tool_book_appointment(state["patient_id"], doctor_id, slot, simulate_failure=simulate_failure)

    if booking["success"]:
        messages.append(AIMessage(content=f"[AppointmentAgent] Booked: {json.dumps(booking['data'])}"))
        completed = list(state.get("completed_tasks", [])) + ["book_appointment"]
        return {
            **state,
            "appointment_status": "confirmed",
            "appointment_result": booking["data"],
            "completed_tasks": completed,
            "messages": messages,
            "next_step": "route_after_appointment",
        }

    # --- Failure recovery: retry once by re-fetching an alternative slot ---
    if attempt < MAX_RETRIES:
        retry_counts["book_appointment"] = attempt + 1
        alt_slot_result = tool_get_earliest_slot(doctor_id)
        messages.append(AIMessage(
            content=f"[AppointmentAgent] Booking failed ({booking['error']}). Retrying with alternative slot (attempt {attempt + 1})."
        ))
        if alt_slot_result["success"]:
            booking_retry = tool_book_appointment(state["patient_id"], doctor_id, alt_slot_result["data"]["slot"])
            if booking_retry["success"]:
                completed = list(state.get("completed_tasks", [])) + ["book_appointment"]
                messages.append(AIMessage(content=f"[AppointmentAgent] Retry succeeded: {json.dumps(booking_retry['data'])}"))
                return {
                    **state,
                    "appointment_status": "confirmed_after_retry",
                    "appointment_result": booking_retry["data"],
                    "completed_tasks": completed,
                    "retry_counts": retry_counts,
                    "messages": messages,
                    "next_step": "route_after_appointment",
                }

    errors.append(f"Appointment booking failed after retries: {booking.get('error')}")
    messages.append(AIMessage(content="[AppointmentAgent] All retries exhausted. Marking as failed, workflow continues."))
    return {
        **state,
        "appointment_status": "failed",
        "appointment_result": None,
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

    if not check or not check.get("success"):
        return {
            **state,
            "lab_test_status": "check_failed",
            "errors": state.get("errors", []) + [f"Could not verify existing {test_name} report."],
            "next_step": "route_after_lab",
        }

    if check["data"]["exists"]:
        messages.append(AIMessage(content=f"[LabSchedulingAgent] {test_name} already exists ({check['data']['status']}) — skipping scheduling to avoid duplicate work."))
        completed.append("check_and_schedule_lab")
        return {
            **state,
            "lab_test_status": f"already_exists ({check['data']['status']})",
            "lab_schedule_result": None,
            "completed_tasks": completed,
            "messages": messages,
            "next_step": "route_after_lab",
        }

    # Not present -> dynamically decide to schedule it
    schedule = tool_schedule_lab_test(state["patient_id"], test_name)
    if schedule["success"]:
        completed.append("check_and_schedule_lab")
        messages.append(AIMessage(content=f"[LabSchedulingAgent] Scheduled new {test_name}: {json.dumps(schedule['data'])}"))
        return {
            **state,
            "lab_test_status": "scheduled",
            "lab_schedule_result": schedule["data"],
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
# 8. AGENT: NOTIFICATION (depends on appointment + lab outcomes)
# =====================================================================================

def notification_agent(state: HospitalState) -> HospitalState:
    task_names = {t["name"] for t in state["tasks"]}
    if "notify_patient" not in task_names:
        return {**state, "notification_status": "not_requested", "next_step": "validate"}

    parts = []
    if state.get("appointment_status", "").startswith("confirmed"):
        ar = state["appointment_result"]
        parts.append(f"Your appointment with {ar['doctor_name']} is confirmed for {ar['slot']} (ID: {ar['appointment_id']}).")
    elif state.get("appointment_status") in ("failed", "failed_no_availability"):
        parts.append("We were unable to book your appointment automatically; our staff will follow up shortly.")

    if state.get("lab_test_status", "").startswith("already_exists"):
        parts.append(f"Note: your existing lab report status is {state['lab_test_status'].split('(')[-1].rstrip(')')}.")
    elif state.get("lab_test_status") == "scheduled":
        lr = state["lab_schedule_result"]
        parts.append(f"Your {lr['test_name']} test has been scheduled (Order ID: {lr['lab_order_id']}).")

    message = " ".join(parts) if parts else "Your request has been processed."

    retry_counts = dict(state.get("retry_counts", {}))
    attempt = retry_counts.get("notify_patient", 0)
    simulate_failure = False  # toggle True to test failure-recovery path
    send = tool_send_notification(state["patient_id"], message, simulate_failure=simulate_failure)

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

    # Failure recovery: retry once, then fall back to an alternate channel note
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
# 9. AGENT: VALIDATOR — self-correction / hallucination & completeness check
# =====================================================================================

VALIDATOR_SYSTEM_PROMPT = """You are the Validator Agent. You audit a hospital workflow's outcome
against what was actually requested and what tools actually reported.

You are given:
1. The original task plan (what SHOULD have happened)
2. The actual completed_tasks list
3. The actual tool-derived results for appointment, lab, and notification
4. Any errors logged

Check for:
- Every planned task is either in completed_tasks OR has a legitimate documented failure reason.
- No task appears "done" without a matching tool result (that would be hallucination).
- No redundant/unnecessary actions (e.g. scheduling a lab test that already existed).

Return ONLY valid JSON (no markdown fences):
{{
  "passed": true/false,
  "feedback": "<short explanation, empty string if passed>"
}}
"""

def validator_agent(state: HospitalState) -> HospitalState:
    llm = get_llm(temperature=0.0)

    audit_payload = {
        "planned_tasks": state["tasks"],
        "completed_tasks": state.get("completed_tasks", []),
        "appointment_status": state.get("appointment_status"),
        "appointment_result": state.get("appointment_result"),
        "lab_test_status": state.get("lab_test_status"),
        "lab_schedule_result": state.get("lab_schedule_result"),
        "notification_status": state.get("notification_status"),
        "errors": state.get("errors", []),
    }

    prompt = [
        SystemMessage(content=VALIDATOR_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(audit_payload, indent=2)),
    ]

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip().replace("```json", "").replace("```", "").strip()
        verdict = json.loads(raw)
    except Exception:
        # Deterministic fallback validation if LLM parsing fails
        planned_names = {t["name"] for t in state["tasks"]}
        completed_names = set(state.get("completed_tasks", []))
        unresolved = planned_names - completed_names
        # A task counts as "resolved" even if failed, as long as status/errors document why
        genuinely_missing = [t for t in unresolved if not state.get("errors")]
        verdict = {
            "passed": len(genuinely_missing) == 0,
            "feedback": f"Unresolved without error explanation: {genuinely_missing}" if genuinely_missing else "",
        }

    messages = [AIMessage(content=f"[ValidatorAgent] passed={verdict['passed']} feedback={verdict.get('feedback', '')}")]

    return {
        **state,
        "validation_passed": verdict["passed"],
        "validation_feedback": verdict.get("feedback", ""),
        "messages": messages,
        "next_step": "finalize" if verdict["passed"] else "revise",
    }


# =====================================================================================
# 10. AGENT: SUMMARIZER — final natural-language response, grounded strictly in tool outputs
# =====================================================================================

SUMMARIZER_SYSTEM_PROMPT = """You are the Summary Agent. Write a short, warm, factual summary
for the patient based ONLY on the structured results provided. Do not invent any detail
(times, names, IDs) that is not present in the data. If something failed, say so plainly
and reassure the patient staff will follow up. Keep it to 2-4 sentences."""

def summarizer_agent(state: HospitalState) -> HospitalState:
    llm = get_llm(temperature=0.2)

    grounded_data = {
        "appointment_status": state.get("appointment_status"),
        "appointment_result": state.get("appointment_result"),
        "lab_test_status": state.get("lab_test_status"),
        "lab_schedule_result": state.get("lab_schedule_result"),
        "notification_status": state.get("notification_status"),
        "errors": state.get("errors", []),
    }

    prompt = [
        SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(grounded_data, indent=2)),
    ]

    try:
        response = llm.invoke(prompt)
        summary = response.content.strip()
    except Exception:
        summary = "Your request has been processed; see status fields for details."

    return {
        **state,
        "summary": summary,
        "messages": [AIMessage(content=f"[SummarizerAgent] {summary}")],
        "next_step": "done",
    }


def revision_router_node(state: HospitalState) -> HospitalState:
    """Entered when validator fails — logs feedback and loops back to re-run the
    affected step once before giving up gracefully (bounded self-correction)."""
    revise_attempt = state.get("retry_counts", {}).get("__revision__", 0)
    retry_counts = dict(state.get("retry_counts", {}))
    retry_counts["__revision__"] = revise_attempt + 1

    messages = [AIMessage(content=f"[Supervisor] Validation failed: {state.get('validation_feedback')}. Re-routing (revision {revise_attempt + 1}).")]

    if revise_attempt >= MAX_RETRIES:
        # Give up gracefully — proceed to finalize with whatever we have, errors intact
        return {**state, "retry_counts": retry_counts, "messages": messages, "next_step": "finalize"}

    # Simple, safe re-entry point: re-run notification/summarization since that's
    # almost always where an incomplete/mismatched final response would surface.
    return {**state, "retry_counts": retry_counts, "messages": messages, "next_step": "reroute_notification"}


# =====================================================================================
# 11. ROUTING FUNCTIONS (conditional edges — dynamic, not hardcoded sequence)
# =====================================================================================

def route_after_context(state: HospitalState) -> str:
    task_names = {t["name"] for t in state["tasks"]}
    if "book_appointment" in task_names:
        return "appointment_agent"
    if "check_and_schedule_lab" in task_names:
        return "lab_scheduling_agent"
    return "notification_agent"


def route_after_appointment(state: HospitalState) -> str:
    task_names = {t["name"] for t in state["tasks"]}
    if "check_and_schedule_lab" in task_names:
        return "lab_scheduling_agent"
    return "notification_agent"


def route_after_lab(state: HospitalState) -> str:
    return "notification_agent"


def route_after_validation(state: HospitalState) -> str:
    return "finalize" if state["validation_passed"] else "revise"


def route_after_revision(state: HospitalState) -> str:
    return state["next_step"]  # either "reroute_notification" or "finalize"


# =====================================================================================
# 12. FINALIZE NODE — assembles the exact required output shape
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

def build_graph():
    graph = StateGraph(HospitalState)

    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("gather_context", parallel_context_gathering_node)
    graph.add_node("appointment_agent", appointment_agent)
    graph.add_node("lab_scheduling_agent", lab_scheduling_agent)
    graph.add_node("notification_agent", notification_agent)
    graph.add_node("validator_agent", validator_agent)
    graph.add_node("revision_router", revision_router_node)
    graph.add_node("summarizer_agent", summarizer_agent)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("supervisor")

    graph.add_edge("supervisor", "gather_context")

    graph.add_conditional_edges("gather_context", route_after_context, {
        "appointment_agent": "appointment_agent",
        "lab_scheduling_agent": "lab_scheduling_agent",
        "notification_agent": "notification_agent",
    })

    graph.add_conditional_edges("appointment_agent", route_after_appointment, {
        "lab_scheduling_agent": "lab_scheduling_agent",
        "notification_agent": "notification_agent",
    })

    graph.add_conditional_edges("lab_scheduling_agent", route_after_lab, {
        "notification_agent": "notification_agent",
    })

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

    return graph.compile()


# =====================================================================================
# 14. ENTRY POINT
# =====================================================================================

def run_hospital_workflow(patient_id: str, user_query: str, verbose: bool = True) -> Dict:
    app = build_graph()

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
    }

    final_state = app.invoke(initial_state)

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