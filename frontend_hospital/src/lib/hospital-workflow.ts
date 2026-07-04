// Client-side API and streaming workflow caller for the Python LangGraph hospital backend.

export type AgentName =
  | "Supervisor"
  | "PatientInfo"
  | "EmergencyCheck"
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
  patient_info?: any;
  doctor_search_result?: any;
  appointment_result?: any;
  lab_schedule_result?: any;
  lab_report_analysis?: any;
  validation_passed?: boolean;
  validation_feedback?: string;
  errors?: string[];
  waiting_for_confirmation?: boolean;
}

export interface Patient {
  patient_id: string;
  name: string;
  age: number;
  gender: string;
  medical_history: string[];
  phone?: string;
  email?: string;
  blood_group?: string;
  address?: string;
  allergies?: string[];
  insurance_provider?: string;
  insurance_number?: string;
  emergency_contact?: string;
  notes?: string;
}

export interface Doctor {
  doctor_id: string;
  name: string;
  specialization: string;
  experience: number;
  fee: number;
  hospital: string;
  available_slots: string[];
}

export interface Appointment {
  appointment_id: string;
  patient_id: string;
  patient_name?: string;
  doctor_id: string;
  doctor_name?: string;
  doctor_specialization?: string;
  slot: string;
  status: string;
}

export interface LabReport {
  lab_order_id: string;
  patient_id: string;
  patient_name?: string;
  test_name: string;
  status: string;
}

export interface Notification {
  notification_id: string;
  patient_id: string;
  patient_name?: string;
  message: string;
  channel: string;
  status: string;
  sent_at: string;
}

export interface PatientHistory {
  patient: Patient;
  appointments: Appointment[];
  lab_reports: LabReport[];
  notifications: Notification[];
}

const API_BASE = "http://localhost:8000/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error on ${path}: ${response.status} ${response.statusText}. ${text}`);
  }

  return response.json() as Promise<T>;
}

// Patients API
export const getPatients = () => apiFetch<Patient[]>("/patients");
export const getPatientDetail = (id: string) => apiFetch<Patient>(`/patients/${id}`);
export const createPatient = (p: Patient) =>
  apiFetch<Patient>("/patients", {
    method: "POST",
    body: JSON.stringify(p),
  });
export const updatePatient = (id: string, p: Omit<Patient, "patient_id">) =>
  apiFetch<{ message: string }>(`/patients/${id}`, {
    method: "PUT",
    body: JSON.stringify(p),
  });
export const deletePatient = (id: string) =>
  apiFetch<{ message: string }>(`/patients/${id}`, {
    method: "DELETE",
  });
export const getPatientHistory = (id: string) => apiFetch<PatientHistory>(`/patients/${id}/history`);

// Doctors API
export const getDoctors = (specialization?: string) => {
  const query = specialization ? `?specialization=${encodeURIComponent(specialization)}` : "";
  return apiFetch<Doctor[]>(`/doctors${query}`);
};
export const getDoctorDetail = (id: string) => apiFetch<Doctor>(`/doctors/${id}`);
export const createDoctor = (d: Doctor) =>
  apiFetch<Doctor>("/doctors", {
    method: "POST",
    body: JSON.stringify(d),
  });
export const updateDoctor = (id: string, d: Omit<Doctor, "doctor_id">) =>
  apiFetch<{ message: string }>(`/doctors/${id}`, {
    method: "PUT",
    body: JSON.stringify(d),
  });
export const deleteDoctor = (id: string) =>
  apiFetch<{ message: string }>(`/doctors/${id}`, {
    method: "DELETE",
  });

// Appointments API
export const getAppointments = () => apiFetch<Appointment[]>("/appointments");
export const createAppointment = (appt: Omit<Appointment, "appointment_id">) =>
  apiFetch<Appointment>("/appointments", {
    method: "POST",
    body: JSON.stringify(appt),
  });
export const updateAppointment = (id: string, appt: Omit<Appointment, "appointment_id">) =>
  apiFetch<{ message: string }>(`/appointments/${id}`, {
    method: "PUT",
    body: JSON.stringify(appt),
  });
export const deleteAppointment = (id: string) =>
  apiFetch<{ message: string }>(`/appointments/${id}`, {
    method: "DELETE",
  });

// Lab Reports API
export const getLabReports = () => apiFetch<LabReport[]>("/lab-reports");
export const createLabReport = (report: Omit<LabReport, "lab_order_id">) =>
  apiFetch<LabReport>("/lab-reports", {
    method: "POST",
    body: JSON.stringify(report),
  });
export const updateLabReport = (id: string, report: Omit<LabReport, "lab_order_id">) =>
  apiFetch<{ message: string }>(`/lab-reports/${id}`, {
    method: "PUT",
    body: JSON.stringify(report),
  });
export const deleteLabReport = (id: string) =>
  apiFetch<{ message: string }>(`/lab-reports/${id}`, {
    method: "DELETE",
  });

// Fallback sample patients to keep static console working if backend is loading
export const SAMPLE_PATIENTS = [
  { id: "P001", name: "John Doe" },
  { id: "P002", name: "Alice Smith" },
  { id: "P003", name: "Ravi Kumar" },
];

export async function runWorkflow(
  patientId: string,
  userQuery: string,
  onEvent: (ev: AgentEvent) => void,
  debug: boolean = false,
): Promise<WorkflowResult> {
  const response = await fetch("http://localhost:8000/api/workflow", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      patient_id: patientId,
      user_query: userQuery,
      debug,
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

export async function resumeWorkflow(
  patientId: string,
  selectedDoctor: string,
  selectedDate: string,
  selectedTime: string,
  userDecision: string,
  onEvent: (ev: AgentEvent) => void,
  debug: boolean = false,
): Promise<WorkflowResult> {
  const response = await fetch("http://localhost:8000/api/workflow/resume", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      patient_id: patientId,
      selected_doctor: selectedDoctor,
      selected_date: selectedDate,
      selected_time: selectedTime,
      user_decision: userDecision,
      debug,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Workflow resumption request failed: ${response.status} ${response.statusText}. ${errText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No readable stream in workflow resumption response");
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
    throw new Error("Workflow resumption finished without yielding final result summary");
  }

  return result;
}

