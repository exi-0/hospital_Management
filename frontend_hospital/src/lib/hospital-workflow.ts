// Client-side simulation of the Python LangGraph hospital multi-agent workflow.
// Mirrors DB, tools, and agent behavior for a live UI demo. Swap runWorkflow's
// internals with a fetch() to your Python backend when ready.

export type AgentName =
  | "Supervisor"
  | "PatientInfo"
  | "DoctorSearch"
  | "LabReport"
  | "Appointment"
  | "LabScheduling"
  | "Notification"
  | "Validator"
  | "Summarizer";

export interface AgentEvent {
  id: string;
  agent: AgentName;
  status: "running" | "success" | "warning" | "error";
  message: string;
  detail?: Record<string, unknown>;
  timestamp: number;
}

export interface WorkflowResult {
  appointment_status: string;
  lab_test_status: string;
  notification_status: string;
  summary: string;
}

interface Patient {
  patient_id: string;
  name: string;
  age: number;
  appointments: string[];
  lab_reports: string[];
}
interface Doctor {
  doctor_id: string;
  name: string;
  specialization: string;
  available_slots: string[];
}

const DB = {
  patients: [
    { patient_id: "P001", name: "John Doe", age: 45, appointments: ["A101"], lab_reports: ["ECG"] },
    { patient_id: "P002", name: "Alice Smith", age: 32, appointments: [], lab_reports: [] },
    { patient_id: "P003", name: "Ravi Kumar", age: 58, appointments: [], lab_reports: [] },
  ] as Patient[],
  doctors: [
    { doctor_id: "D101", name: "Dr. Brown", specialization: "Cardiology", available_slots: ["2026-07-10 09:00", "2026-07-10 11:00"] },
    { doctor_id: "D102", name: "Dr. Green", specialization: "Orthopedics", available_slots: ["2026-07-11 10:00", "2026-07-11 14:00"] },
    { doctor_id: "D103", name: "Dr. Patel", specialization: "General Medicine", available_slots: ["2026-07-09 08:30", "2026-07-09 15:00"] },
  ] as Doctor[],
  lab_reports: [
    { patient_id: "P001", test_name: "ECG", status: "Completed" },
    { patient_id: "P001", test_name: "Blood Test", status: "Completed" },
  ] as { patient_id: string; test_name: string; status: string }[],
};

let apptCounter = 102;
let labCounter = 1;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface Plan {
  specialization_needed: string;
  wants_appointment: boolean;
  lab_test_needed: string | null;
  wants_notification: boolean;
  reasoning: string;
}

function parseQuery(q: string): Plan {
  const lower = q.toLowerCase();
  let spec = "General Medicine";
  if (/chest|heart|cardio|palpitation/.test(lower)) spec = "Cardiology";
  else if (/bone|joint|fracture|ortho|knee|back pain/.test(lower)) spec = "Orthopedics";
  const wantsAppt = /(book|appointment|schedule.*(doctor|visit)|consult)/.test(lower);
  let lab: string | null = null;
  if (/ecg|ekg/.test(lower)) lab = "ECG";
  else if (/blood test|cbc/.test(lower)) lab = "Blood Test";
  else if (/x-?ray/.test(lower)) lab = "X-Ray";
  else if (/mri/.test(lower)) lab = "MRI";
  const wantsNotify = /(notify|inform|let me know|message|sms|email)/.test(lower);
  return {
    specialization_needed: spec,
    wants_appointment: wantsAppt,
    lab_test_needed: lab,
    wants_notification: wantsNotify,
    reasoning: `Inferred ${spec}${lab ? `, lab: ${lab}` : ""}${wantsAppt ? ", appointment" : ""}${wantsNotify ? ", notify" : ""}.`,
  };
}

export async function runWorkflow(
  patientId: string,
  userQuery: string,
  onEvent: (ev: AgentEvent) => void,
): Promise<WorkflowResult> {
  const response = await fetch("http://localhost:8000/api/workflow", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      patient_id: patientId,
      user_query: userQuery,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Workflow request failed: ${response.status} ${response.statusText}. ${errText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No readable stream in workflow response");
  }

  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let result: WorkflowResult | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        try {
          const parsed = JSON.parse(trimmed);
          if (parsed.type === "event") {
            onEvent(parsed.data);
          } else if (parsed.type === "result") {
            result = parsed.data;
          }
        } catch (e) {
          console.warn("Failed to parse streaming line from backend:", trimmed, e);
        }
      }
    }

    // Process remaining buffer
    const finalTrimmed = buffer.trim();
    if (finalTrimmed) {
      try {
        const parsed = JSON.parse(finalTrimmed);
        if (parsed.type === "event") {
          onEvent(parsed.data);
        } else if (parsed.type === "result") {
          result = parsed.data;
        }
      } catch (e) {
        console.warn("Failed to parse remaining buffer line from backend:", finalTrimmed, e);
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (!result) {
    throw new Error("Workflow execution finished without yielding final result summary");
  }

  return result;
}

export const SAMPLE_PATIENTS = DB.patients.map((p) => ({ id: p.patient_id, name: p.name }));
