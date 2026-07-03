import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from App import build_graph, HospitalState

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

def generate_workflow_events(patient_id: str, user_query: str):
    logger.info(f"Starting workflow for patient {patient_id} with query: {user_query}")
    
    # Initialize the graph
    graph = build_graph()
    
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
    }

    # Helper function to format UI events
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

    # Emit Supervisor running
    yield make_event("Supervisor", "running", "Parsing request and building task plan...")

    # We track which agents have been notified as "running" so we don't emit duplicates or conflict
    notified_running = set()

    try:
        # Run graph updates stream
        for update in graph.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in update.items():
                logger.info(f"Node completed: {node_name}")
                
                if node_name == "supervisor":
                    # Supervisor completed
                    tasks = node_output.get("tasks", [])
                    plan_msg = ""
                    if node_output.get("messages"):
                        plan_msg = node_output["messages"][-1].content
                        if "Plan created:" in plan_msg:
                            plan_msg = plan_msg.split("Plan created:")[-1].strip()
                    
                    try:
                        plan_detail = json.loads(plan_msg) if plan_msg else {}
                    except Exception:
                        plan_detail = {}
                        
                    yield make_event("Supervisor", "success", f"Plan created: {plan_msg or 'Tasks identified.'}", plan_detail)

                    # Mark next agents as running
                    yield make_event("PatientInfo", "running", f"Fetching patient {patient_id}...")
                    notified_running.add("PatientInfo")
                    
                    task_names = {t["name"] for t in tasks}
                    if "book_appointment" in task_names:
                        spec = next((t["specialization"] for t in tasks if t["name"] == "book_appointment"), "General Medicine")
                        yield make_event("DoctorSearch", "running", f"Searching {spec} specialists...")
                        notified_running.add("DoctorSearch")
                    
                    if "check_and_schedule_lab" in task_names:
                        test_name = next((t["test_name"] for t in tasks if t["name"] == "check_and_schedule_lab"), "ECG")
                        yield make_event("LabReport", "running", f"Checking existing {test_name} reports...")
                        notified_running.add("LabReport")

                elif node_name == "gather_context":
                    # Parallel context gathering completed
                    patient_info = node_output.get("patient_info")
                    doctor_search = node_output.get("doctor_search_result")
                    lab_check = node_output.get("lab_check_result")
                    
                    if patient_info:
                        if patient_info.get("success"):
                            yield make_event("PatientInfo", "success", f"Loaded {patient_info['data']['name']} (age {patient_info['data']['age']})", patient_info["data"])
                        else:
                            yield make_event("PatientInfo", "error", patient_info.get("error", "Failed to load patient info"))
                    
                    if doctor_search is not None:
                        if doctor_search.get("success"):
                            yield make_event("DoctorSearch", "success", f"Found {doctor_search['data']['doctor_name']} — earliest slot {doctor_search['data']['slot']}", doctor_search["data"])
                        else:
                            yield make_event("DoctorSearch", "error", doctor_search.get("error", "Doctor search failed"))
                            
                    if lab_check is not None:
                        if lab_check.get("success"):
                            exists = lab_check["data"]["exists"]
                            status = lab_check["data"]["status"]
                            tasks = node_output.get("tasks", [])
                            lab_task = next((t for t in tasks if t["name"] == "check_and_schedule_lab"), None)
                            test_name = lab_task["test_name"] if lab_task else "ECG"
                            msg = f"{test_name} already exists ({status})" if exists else f"No prior {test_name} on file"
                            yield make_event("LabReport", "success", msg, lab_check["data"])
                        else:
                            yield make_event("LabReport", "error", lab_check.get("error", "Failed to check lab report"))

                    # Next agent is routed. Trigger running notification.
                    tasks = node_output.get("tasks", [])
                    task_names = {t["name"] for t in tasks}
                    if "book_appointment" in task_names:
                        yield make_event("Appointment", "running", "Booking appointment...")
                        notified_running.add("Appointment")
                    elif "check_and_schedule_lab" in task_names:
                        yield make_event("LabScheduling", "running", "Deciding on lab scheduling...")
                        notified_running.add("LabScheduling")
                    elif "notify_patient" in task_names:
                        yield make_event("Notification", "running", "Sending confirmation...")
                        notified_running.add("Notification")

                elif node_name == "appointment_agent":
                    appt_status = node_output.get("appointment_status")
                    appt_result = node_output.get("appointment_result")
                    
                    if appt_status in ("confirmed", "confirmed_after_retry"):
                        yield make_event("Appointment", "success", f"Confirmed appointment with {appt_result['doctor_name']} @ {appt_result['slot']} (ID: {appt_result['appointment_id']})", appt_result)
                    else:
                        yield make_event("Appointment", "error", "Appointment booking failed. Staff will follow up.")
                        
                    # Route to next
                    tasks = node_output.get("tasks", [])
                    task_names = {t["name"] for t in tasks}
                    if "check_and_schedule_lab" in task_names:
                        yield make_event("LabScheduling", "running", "Deciding on lab scheduling...")
                        notified_running.add("LabScheduling")
                    elif "notify_patient" in task_names:
                        yield make_event("Notification", "running", "Sending confirmation...")
                        notified_running.add("Notification")

                elif node_name == "lab_scheduling_agent":
                    lab_status = node_output.get("lab_test_status")
                    lab_result = node_output.get("lab_schedule_result")
                    tasks = node_output.get("tasks", [])
                    lab_task = next((t for t in tasks if t["name"] == "check_and_schedule_lab"), None)
                    test_name = lab_task["test_name"] if lab_task else "ECG"
                    
                    if lab_status == "scheduled":
                        yield make_event("LabScheduling", "success", f"Scheduled new {test_name} test — Order ID: {lab_result['lab_order_id']}", lab_result)
                    elif lab_status.startswith("already_exists"):
                        exists_status = lab_status.split("(")[-1].rstrip(")")
                        yield make_event("LabScheduling", "warning", f"Skipping — {test_name} already exists ({exists_status})")
                    else:
                        yield make_event("LabScheduling", "error", f"Lab scheduling failed.")
                        
                    # Route to next
                    if "notify_patient" in {t["name"] for t in tasks}:
                        yield make_event("Notification", "running", "Sending confirmation...")
                        notified_running.add("Notification")

                elif node_name == "notification_agent":
                    notif_status = node_output.get("notification_status")
                    notif_result = node_output.get("notification_result")
                    
                    if notif_status in ("sent", "sent_after_retry"):
                        yield make_event("Notification", "success", f"Notification sent: \"{notif_result.get('message', '')}\"", notif_result)
                    else:
                        yield make_event("Notification", "error", "Notification delivery failed.")
                        
                    # Route to Validator
                    yield make_event("Validator", "running", "Auditing completeness & grounding...")
                    notified_running.add("Validator")

                elif node_name == "validator_agent":
                    passed = node_output.get("validation_passed")
                    feedback = node_output.get("validation_feedback", "")
                    
                    if passed:
                        yield make_event("Validator", "success", "All planned tasks reconciled against tool outputs. No hallucination detected.")
                        yield make_event("Summarizer", "running", "Composing patient-facing summary...")
                        notified_running.add("Summarizer")
                    else:
                        yield make_event("Validator", "warning", f"Validation check failed: {feedback or 'Inconsistencies detected.'}. Initiating revision route.")

                elif node_name == "revision_router":
                    yield make_event("Supervisor", "warning", "Re-routing workflow to resolve validation feedback.")

                elif node_name == "summarizer_agent":
                    summary = node_output.get("summary", "")
                    yield make_event("Summarizer", "success", summary)

                elif node_name == "finalize":
                    # Send final result metadata
                    yield json.dumps({
                        "type": "result",
                        "data": {
                            "appointment_status": node_output.get("appointment_status"),
                            "lab_test_status": node_output.get("lab_test_status"),
                            "notification_status": node_output.get("notification_status"),
                            "summary": node_output.get("summary"),
                        }
                    }) + "\n"
                    
    except Exception as e:
        logger.exception("Error running workflow graph")
        yield make_event("Supervisor", "error", f"Fatal execution error: {str(e)}")

@app.post("/api/workflow")
async def run_workflow_api(req: WorkflowRequest):
    return StreamingResponse(
        generate_workflow_events(req.patient_id, req.user_query),
        media_type="text/plain"  # Plain text makes stream parsing easy on the frontend
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
