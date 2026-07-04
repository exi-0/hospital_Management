import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
db.init_db()

from app import build_graph, HospitalState


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic Hospital Backend")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WorkflowRequest(BaseModel):
    patient_id: str
    user_query: str
    debug: Optional[bool] = False

def yield_events_for_node(node_name: str, node_output: dict, task_names: set, patient_id: str, debug: bool = False):
    events = []
    
    if node_name == "supervisor":
        plan_msg = ""
        if node_output.get("messages"):
            plan_msg = node_output["messages"][-1].content
            if "Plan created:" in plan_msg:
                plan_msg = plan_msg.split("Plan created:")[-1].strip()
        try:
            plan_detail = json.loads(plan_msg) if plan_msg else {}
        except Exception:
            plan_detail = {}
        events.append(("Supervisor", "success", "Routing Workflow", plan_detail))
        events.append(("PatientInfo", "running", "Fetching Patient..."))
        
    elif node_name == "patient_info_agent":
        patient_info = node_output.get("patient_info")
        if patient_info and patient_info.get("patient_found"):
            inner_info = patient_info.get("patient_info", {})
            name = inner_info.get("name", "Unknown")
            age = inner_info.get("age", "Unknown")
            events.append(("PatientInfo", "success", "Patient Loaded", patient_info))
        else:
            events.append(("PatientInfo", "error", "Patient lookup failed: Register New Patient", patient_info))
        
        events.append(("EmergencyCheck", "running", "Running emergency rules..."))
        
    elif node_name == "emergency_check_agent":
        emergency_detected = node_output.get("emergency_detected")
        if emergency_detected:
            errs = node_output.get("errors", [])
            msg = errs[-1] if errs else "Emergency detected."
            events.append(("EmergencyCheck", "error", "Emergency detected.", {"reason": msg}))
            events.append(("Notification", "running", "Preparing Notification..."))
        else:
            events.append(("EmergencyCheck", "success", "No emergency detected.", {"status": "normal"}))
            if "search_doctors" in task_names or "book_appointment" in task_names:
                events.append(("DoctorSearch", "running", "Searching Doctors..."))
            elif "check_and_schedule_lab" in task_names:
                events.append(("LabScheduling", "running", "Scheduling lab test..."))
            elif "analyze_lab_reports" in task_names:
                events.append(("LabReport", "running", "Analyzing lab report..."))
            else:
                events.append(("Notification", "running", "Preparing Notification..."))
                
    elif node_name == "doctor_search_agent":
        ds = node_output.get("doctor_search_result")
        if debug:
            events.append(("DoctorSearch", "running", "Searching specialization..."))
            events.append(("DoctorSearch", "running", "Ranking..."))
            events.append(("DoctorSearch", "running", "Filtering..."))
            
        if ds and ds.get("recommended_doctors"):
            events.append(("DoctorSearch", "success", "Doctors Found.", ds))
        else:
            events.append(("DoctorSearch", "warning", "No doctors found.", ds))
            
    elif node_name == "wait_for_user_confirmation_node":
        user_decision = node_output.get("user_decision")
        if user_decision is None:
            events.append(("Appointment", "warning", "Waiting for patient confirmation..."))
            
    elif node_name == "appointment_agent":
        appt_status = node_output.get("appointment_status")
        appt_result = node_output.get("appointment_result")
        
        if appt_status == "cancelled":
            events.append(("Appointment", "warning", "Appointment Cancelled", appt_result))
        elif appt_status == "confirmed_after_retry":
            events.append(("Appointment", "success", "Rescheduled", appt_result))
        elif appt_status in ("confirmed", "confirmed_after_retry") and appt_result:
            events.append(("Appointment", "success", "Appointment Confirmed", appt_result))
        else:
            events.append(("Appointment", "error", "Appointment booking failed.", appt_result))
            
        if appt_status != "cancelled":
            if "check_and_schedule_lab" in task_names:
                events.append(("LabScheduling", "running", "Scheduling lab test..."))
            elif "analyze_lab_reports" in task_names:
                events.append(("LabReport", "running", "Analyzing lab report..."))
            else:
                events.append(("Notification", "running", "Preparing Notification..."))
        else:
            events.append(("Notification", "running", "Preparing Notification..."))
            
    elif node_name == "lab_scheduling_agent":
        lab_status = node_output.get("lab_test_status")
        lab_result = node_output.get("lab_schedule_result")
        
        if lab_status == "scheduled":
            events.append(("LabScheduling", "success", "Scheduled new test", lab_result))
        elif lab_status.startswith("already_exists"):
            events.append(("LabScheduling", "warning", "Skipping — test report already exists", lab_result))
        else:
            events.append(("LabScheduling", "error", "Lab scheduling failed.", lab_result))
            
        if "analyze_lab_reports" in task_names and node_output.get("user_decision") != "cancel":
            events.append(("LabReport", "running", "Analyzing lab report..."))
        else:
            events.append(("Notification", "running", "Preparing Notification..."))
            
    elif node_name == "lab_report_agent":
        analysis = node_output.get("lab_report_analysis")
        if analysis:
            events.append(("LabReport", "success", "Report analysis complete", analysis))
        else:
            events.append(("LabReport", "error", "Failed to analyze lab report."))
            
        events.append(("Notification", "running", "Preparing Notification..."))
        
    elif node_name == "notification_agent":
        notif_status = node_output.get("notification_status")
        notif_result = node_output.get("notification_result")
        
        if notif_status in ("sent", "sent_after_retry"):
            events.append(("Notification", "success", "Notification Sent", notif_result))
        else:
            events.append(("Notification", "error", "Notification delivery failed.", notif_result))
            
        events.append(("Validator", "running", "Running Validation..."))
        
    elif node_name == "validator_agent":
        passed = node_output.get("validation_passed")
        if passed:
            events.append(("Validator", "success", "Validation Passed"))
            events.append(("Summarizer", "running", "Generating Final Summary..."))
        else:
            events.append(("Validator", "warning", "Validation Failed"))
            
    elif node_name == "summarizer_agent":
        events.append(("Summarizer", "success", "Summary Generated"))
        
    return events

def generate_workflow_events(patient_id: str, user_query: str, debug: bool = False):
    logger.info(f"Starting workflow for patient {patient_id} with query: {user_query}")
    
    graph = build_graph()
    config = {"configurable": {"thread_id": f"thread_{patient_id}"}}
    
    initial_state = {
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

    def make_event(agent, status, message, detail=None):
        return json.dumps({
            "type": "event",
            "data": {
                "agent": agent,
                "status": status,
                "message": message,
                "detail": detail,
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        }) + "\n"

    yield make_event("Supervisor", "running", "Parsing Request")
    yield make_event("Supervisor", "running", "Building Plan")

    try:
        for update in graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in update.items():
                logger.info(f"Node completed: {node_name}")
                if node_name == "__interrupt__" or not isinstance(node_output, dict):
                    continue
                
                tasks = node_output.get("tasks", [])
                task_names = {t["name"] for t in tasks} if tasks else set()
                if not task_names:
                    state_val = graph.get_state(config).values
                    task_names = {t["name"] for t in state_val.get("tasks", [])}
                
                evs = yield_events_for_node(node_name, node_output, task_names, patient_id, debug)
                for ev in evs:
                    yield make_event(*ev)

        state_info = graph.get_state(config)
        if state_info.next:
            yield json.dumps({
                "type": "result",
                "data": {
                    "waiting_for_confirmation": True,
                    "appointment_status": "waiting_for_confirmation",
                    "lab_test_status": "in_progress",
                    "notification_status": "in_progress",
                    "doctor_search_result": state_info.values.get("doctor_search_result"),
                    "patient_info": state_info.values.get("patient_info"),
                    "errors": state_info.values.get("errors", []),
                }
            }) + "\n"
        else:
            vals = state_info.values
            yield json.dumps({
                "type": "result",
                "data": {
                    "appointment_status": vals.get("appointment_status"),
                    "lab_test_status": vals.get("lab_test_status"),
                    "notification_status": vals.get("notification_status"),
                    "summary": vals.get("summary"),
                    "patient_info": vals.get("patient_info"),
                    "doctor_search_result": vals.get("doctor_search_result"),
                    "appointment_result": vals.get("appointment_result"),
                    "lab_schedule_result": vals.get("lab_schedule_result"),
                    "lab_report_analysis": vals.get("lab_report_analysis"),
                    "validation_passed": vals.get("validation_passed"),
                    "validation_feedback": vals.get("validation_feedback"),
                    "errors": vals.get("errors"),
                }
            }) + "\n"

    except Exception as e:
        logger.exception("Error running workflow graph")
        yield make_event("Supervisor", "error", f"Fatal execution error: {str(e)}")

class ResumeWorkflowRequest(BaseModel):
    patient_id: str
    selected_doctor: str
    selected_date: str
    selected_time: str
    user_decision: str
    debug: Optional[bool] = False

def generate_resume_workflow_events(patient_id: str, selected_doctor: str, selected_date: str, selected_time: str, user_decision: str, debug: bool = False):
    logger.info(f"Resuming workflow for patient {patient_id} with decision: {user_decision}")
    
    graph = build_graph()
    config = {"configurable": {"thread_id": f"thread_{patient_id}"}}
    
    graph.update_state(config, {
        "selected_doctor": selected_doctor if selected_doctor else None,
        "selected_date": selected_date if selected_date else None,
        "selected_time": selected_time if selected_time else None,
        "user_decision": user_decision,
        "waiting_for_confirmation": False
    })

    def make_event(agent, status, message, detail=None):
        return json.dumps({
            "type": "event",
            "data": {
                "agent": agent,
                "status": status,
                "message": message,
                "detail": detail,
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        }) + "\n"

    yield make_event("Appointment", "running", "Booking Appointment...")
        
    try:
        for update in graph.stream(None, config=config, stream_mode="updates"):
            for node_name, node_output in update.items():
                logger.info(f"Resumed node completed: {node_name}")
                if node_name == "__interrupt__" or not isinstance(node_output, dict):
                    continue
                
                state_val = graph.get_state(config).values
                task_names = {t["name"] for t in state_val.get("tasks", [])}
                
                evs = yield_events_for_node(node_name, node_output, task_names, patient_id, debug)
                for ev in evs:
                    yield make_event(*ev)

        state_info = graph.get_state(config)
        vals = state_info.values
        yield json.dumps({
            "type": "result",
            "data": {
                "appointment_status": vals.get("appointment_status"),
                "lab_test_status": vals.get("lab_test_status"),
                "notification_status": vals.get("notification_status"),
                "summary": vals.get("summary"),
                "patient_info": vals.get("patient_info"),
                "doctor_search_result": vals.get("doctor_search_result"),
                "appointment_result": vals.get("appointment_result"),
                "lab_schedule_result": vals.get("lab_schedule_result"),
                "lab_report_analysis": vals.get("lab_report_analysis"),
                "validation_passed": vals.get("validation_passed"),
                "validation_feedback": vals.get("validation_feedback"),
                "errors": vals.get("errors"),
            }
        }) + "\n"
        
    except Exception as e:
        logger.exception("Error resuming workflow graph")
        yield make_event("Supervisor", "error", f"Fatal execution error during resumption: {str(e)}")

@app.post("/api/workflow")
async def run_workflow_api(req: WorkflowRequest):
    return StreamingResponse(
        generate_workflow_events(req.patient_id, req.user_query, req.debug),
        media_type="text/plain"
    )

@app.post("/api/workflow/resume")
async def resume_workflow_api(req: ResumeWorkflowRequest):
    return StreamingResponse(
        generate_resume_workflow_events(req.patient_id, req.selected_doctor, req.selected_date, req.selected_time, req.user_decision, req.debug),
        media_type="text/plain"
    )

@app.get("/api/reports/{appointment_id}")
async def get_patient_report_pdf(appointment_id: str, download: bool = False):
    import os
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    filename = f"patient_report_{appointment_id}.pdf"
    filepath = os.path.join(report_dir, filename)
    
    if not os.path.exists(filepath):
        # Fallback: if appointment_id looks like a patient ID Pxxx and a report matches f"patient_report_{appointment_id}.pdf"
        # wait, the filename fallback check is:
        alt_filename = f"patient_report_A{appointment_id}.pdf"
        alt_filepath = os.path.join(report_dir, alt_filename)
        if os.path.exists(alt_filepath):
            filepath = alt_filepath
            filename = alt_filename
        else:
            # Maybe there's a file called patient_report_{patient_id}.pdf
            alt_filename2 = f"patient_report_{appointment_id}.pdf"
            # It's already the primary check!
            raise HTTPException(status_code=404, detail="Patient report PDF not found")
        
    if download:
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/pdf"
        )
    else:
        return FileResponse(
            path=filepath,
            media_type="application/pdf"
        )

# ----------------- CRUD Pydantic Schemas -----------------

class PatientCreate(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: str
    medical_history: List[str]
    phone: Optional[str] = ""
    email: Optional[str] = ""
    blood_group: Optional[str] = "Unknown"
    address: Optional[str] = ""
    allergies: List[str] = []
    insurance_provider: Optional[str] = ""
    insurance_number: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    notes: Optional[str] = ""

class PatientUpdate(BaseModel):
    name: str
    age: int
    gender: str
    medical_history: List[str]
    phone: Optional[str] = ""
    email: Optional[str] = ""
    blood_group: Optional[str] = "Unknown"
    address: Optional[str] = ""
    allergies: List[str] = []
    insurance_provider: Optional[str] = ""
    insurance_number: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    notes: Optional[str] = ""

class DoctorCreate(BaseModel):
    doctor_id: str
    name: str
    specialization: str
    experience: int
    fee: float
    hospital: str
    available_slots: List[str]

class DoctorUpdate(BaseModel):
    name: str
    specialization: str
    experience: int
    fee: float
    hospital: str
    available_slots: List[str]

class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    slot: str
    status: str

class AppointmentUpdate(BaseModel):
    patient_id: str
    doctor_id: str
    slot: str
    status: str

class LabReportCreate(BaseModel):
    patient_id: str
    test_name: str
    status: str

class LabReportUpdate(BaseModel):
    patient_id: str
    test_name: str
    status: str

# ----------------- Patients CRUD Endpoints -----------------

@app.get("/api/patients")
async def list_patients():
    return db.get_all_patients()

@app.get("/api/patients/{patient_id}")
async def get_patient_detail(patient_id: str):
    p = db.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p

@app.post("/api/patients")
async def create_new_patient(req: PatientCreate):
    pid = req.patient_id.strip()
    if not pid:
        pid = db.get_next_id("patients", "P")
    if db.get_patient(pid):
        raise HTTPException(status_code=400, detail="Patient ID already exists")
    return db.create_patient(
        pid, req.name, req.age, req.gender, req.medical_history,
        phone=req.phone, email=req.email, blood_group=req.blood_group,
        address=req.address, allergies=req.allergies,
        insurance_provider=req.insurance_provider, insurance_number=req.insurance_number,
        emergency_contact=req.emergency_contact, notes=req.notes
    )

@app.put("/api/patients/{patient_id}")
async def update_existing_patient(patient_id: str, req: PatientUpdate):
    if not db.update_patient(
        patient_id, req.name, req.age, req.gender, req.medical_history,
        phone=req.phone, email=req.email, blood_group=req.blood_group,
        address=req.address, allergies=req.allergies,
        insurance_provider=req.insurance_provider, insurance_number=req.insurance_number,
        emergency_contact=req.emergency_contact, notes=req.notes
    ):
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient updated successfully"}

@app.delete("/api/patients/{patient_id}")
async def delete_existing_patient(patient_id: str):
    if not db.delete_patient(patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient deleted successfully"}

@app.get("/api/patients/{patient_id}/history")
async def get_patient_history_endpoint(patient_id: str):
    history = db.get_patient_history(patient_id)
    if not history:
        raise HTTPException(status_code=404, detail="Patient not found")
    return history

# ----------------- Doctors CRUD Endpoints -----------------

@app.get("/api/doctors")
async def list_doctors(specialization: Optional[str] = None):
    return db.get_all_doctors(specialization)

@app.get("/api/doctors/{doctor_id}")
async def get_doctor_detail(doctor_id: str):
    d = db.get_doctor(doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return d

@app.post("/api/doctors")
async def create_new_doctor(req: DoctorCreate):
    if db.get_doctor(req.doctor_id):
        raise HTTPException(status_code=400, detail="Doctor ID already exists")
    return db.create_doctor(req.doctor_id, req.name, req.specialization, req.experience, req.fee, req.hospital, req.available_slots)

@app.put("/api/doctors/{doctor_id}")
async def update_existing_doctor(doctor_id: str, req: DoctorUpdate):
    if not db.update_doctor(doctor_id, req.name, req.specialization, req.experience, req.fee, req.hospital, req.available_slots):
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"message": "Doctor updated successfully"}

@app.delete("/api/doctors/{doctor_id}")
async def delete_existing_doctor(doctor_id: str):
    if not db.delete_doctor(doctor_id):
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"message": "Doctor deleted successfully"}

# ----------------- Appointments CRUD Endpoints -----------------

@app.get("/api/appointments")
async def list_appointments():
    return db.get_all_appointments()

@app.post("/api/appointments")
async def create_new_appointment(req: AppointmentCreate):
    # Auto-generate ID if needed, or get next ID
    appt_id = db.get_next_id("appointments", "A")
    appt = db.create_appointment(appt_id, req.patient_id, req.doctor_id, req.slot, req.status)
    
    # Also remove this slot from the doctor's available slots if confirmed
    doctor = db.get_doctor(req.doctor_id)
    if doctor and req.slot in doctor["available_slots"]:
        slots = list(doctor["available_slots"])
        slots.remove(req.slot)
        db.update_doctor(req.doctor_id, doctor["name"], doctor["specialization"], doctor["experience"], doctor["fee"], doctor["hospital"], slots)
        
    return appt

@app.put("/api/appointments/{appointment_id}")
async def update_existing_appointment(appointment_id: str, req: AppointmentUpdate):
    if not db.update_appointment(appointment_id, req.patient_id, req.doctor_id, req.slot, req.status):
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"message": "Appointment updated successfully"}

@app.delete("/api/appointments/{appointment_id}")
async def delete_existing_appointment(appointment_id: str):
    if not db.delete_appointment(appointment_id):
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"message": "Appointment deleted successfully"}

# ----------------- Lab Reports CRUD Endpoints -----------------

@app.get("/api/lab-reports")
async def list_lab_reports():
    return db.get_all_lab_reports()

@app.post("/api/lab-reports")
async def create_new_lab_report(req: LabReportCreate):
    lab_id = db.get_next_id("lab_reports", "L")
    return db.create_lab_report(lab_id, req.patient_id, req.test_name, req.status)

@app.put("/api/lab-reports/{lab_order_id}")
async def update_existing_lab_report(lab_order_id: str, req: LabReportUpdate):
    if not db.update_lab_report(lab_order_id, req.patient_id, req.test_name, req.status):
        raise HTTPException(status_code=404, detail="Lab report not found")
    return {"message": "Lab report updated successfully"}

@app.delete("/api/lab-reports/{lab_order_id}")
async def delete_existing_lab_report(lab_order_id: str):
    if not db.delete_lab_report(lab_order_id):
        raise HTTPException(status_code=404, detail="Lab report not found")
    return {"message": "Lab report deleted successfully"}

# ----------------- Entry Point -----------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

