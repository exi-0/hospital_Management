import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  Bell,
  Brain,
  Calendar,
  CheckCircle2,
  ChevronDown,
  FlaskConical,
  Loader2,
  Play,
  Stethoscope,
  UserRound,
  ShieldCheck,
  Sparkles,
  Workflow,
  FileText,
  ShieldAlert,
  ChevronUp,
  Copy,
  Check,
  Share2,
} from "lucide-react";
import {
  runWorkflow,
  resumeWorkflow,
  getPatients,
  createPatient,
  type AgentEvent,
  type AgentName,
  type WorkflowResult,
  SAMPLE_PATIENTS,
} from "@/lib/hospital-workflow";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Agentic Hospital Management System" },
      { name: "description", content: "Multi-agent healthcare workflow orchestration powered by LangGraph, LangChain and Gemini — live agent activity, task routing, and validated outcomes." },
      { property: "og:title", content: "Agentic Hospital Management System" },
      { property: "og:description", content: "Watch a supervisor, doctor-search, lab, and notification agents coordinate a hospital workflow in real time." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: HospitalConsole,
});

const AGENT_META: Record<AgentName, { icon: typeof Activity; label: string; color: string }> = {
  Supervisor: { icon: Brain, label: "Supervisor Agent", color: "text-info" },
  PatientInfo: { icon: UserRound, label: "Patient Info Agent", color: "text-primary" },
  EmergencyCheck: { icon: ShieldAlert, label: "Emergency Check Agent", color: "text-destructive" },
  DoctorSearch: { icon: Stethoscope, label: "Doctor Search Agent", color: "text-primary" },
  LabReport: { icon: FlaskConical, label: "Lab Report Agent", color: "text-primary" },
  Appointment: { icon: Calendar, label: "Appointment Agent", color: "text-info" },
  LabScheduling: { icon: FlaskConical, label: "Lab Scheduling Agent", color: "text-info" },
  Notification: { icon: Bell, label: "Notification Agent", color: "text-info" },
  Validator: { icon: ShieldCheck, label: "Validator Agent", color: "text-warning" },
  Summarizer: { icon: Sparkles, label: "Summarizer Agent", color: "text-success" },
};

const SAMPLE_QUERIES = [
  {
    label: "Chest pain — new patient",
    patient: "P002",
    query:
      "I have chest pain. Book the earliest appointment with a cardiologist. Check whether I already have an ECG report. If not, schedule an ECG test. Finally notify me with all the details.",
  },
  {
    label: "Recurring cardiac patient",
    patient: "P001",
    query:
      "I've been experiencing chest pain for two days. Book the earliest cardiologist appointment. Check whether I already have an ECG. If not, schedule one. Notify me after everything is done.",
  },
  {
    label: "Ortho consult",
    patient: "P003",
    query:
      "My knee has been hurting after a fall. Book an orthopedics appointment and schedule an X-Ray if I don't already have one. Notify me over SMS.",
  },
];

interface ConsoleCache {
  patientId: string;
  query: string;
  events: AgentEvent[];
  result: WorkflowResult | null;
  debug: boolean;
  waitingForConfirmation: boolean;
  availableDoctors: any[];
  selectedDoctorId: string;
  selectedDate: string;
  selectedTime: string;
}

let consoleCache: ConsoleCache = {
  patientId: "P002",
  query: "I have chest pain. Book the earliest appointment with a cardiologist. Check whether I already have an ECG report. If not, schedule an ECG test. Finally notify me with all the details.",
  events: [],
  result: null,
  debug: false,
  waitingForConfirmation: false,
  availableDoctors: [],
  selectedDoctorId: "",
  selectedDate: "",
  selectedTime: "",
};

function HospitalConsole() {
  const [patientId, setPatientIdState] = useState(consoleCache.patientId);
  const [query, setQueryState] = useState(consoleCache.query);
  const [events, setEventsState] = useState<AgentEvent[]>(consoleCache.events);
  const [running, setRunning] = useState(false);
  const [result, setResultState] = useState<WorkflowResult | null>(consoleCache.result);
  const [patientsList, setPatientsList] = useState<{ id: string; name: string; phone?: string }[]>([]);
  const [debug, setDebugState] = useState(consoleCache.debug);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  
  // Human-in-the-loop State
  const [waitingForConfirmation, setWaitingForConfirmationState] = useState(consoleCache.waitingForConfirmation);
  const [availableDoctors, setAvailableDoctorsState] = useState<any[]>(consoleCache.availableDoctors);
  const [selectedDoctorId, setSelectedDoctorIdState] = useState(consoleCache.selectedDoctorId);
  const [selectedDate, setSelectedDateState] = useState(consoleCache.selectedDate);
  const [selectedTime, setSelectedTimeState] = useState(consoleCache.selectedTime);

  // Synced setters
  const setPatientId = (val: string | ((prev: string) => string)) => {
    setPatientIdState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.patientId = next;
      return next;
    });
  };
  const setQuery = (val: string | ((prev: string) => string)) => {
    setQueryState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.query = next;
      return next;
    });
  };
  const setEvents = (val: AgentEvent[] | ((prev: AgentEvent[]) => AgentEvent[])) => {
    setEventsState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.events = next;
      return next;
    });
  };
  const setResult = (val: WorkflowResult | null | ((prev: WorkflowResult | null) => WorkflowResult | null)) => {
    setResultState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.result = next;
      return next;
    });
  };
  const setDebug = (val: boolean | ((prev: boolean) => boolean)) => {
    setDebugState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.debug = next;
      return next;
    });
  };
  const setWaitingForConfirmation = (val: boolean | ((prev: boolean) => boolean)) => {
    setWaitingForConfirmationState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.waitingForConfirmation = next;
      return next;
    });
  };
  const setAvailableDoctors = (val: any[] | ((prev: any[]) => any[])) => {
    setAvailableDoctorsState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.availableDoctors = next;
      return next;
    });
  };
  const setSelectedDoctorId = (val: string | ((prev: string) => string)) => {
    setSelectedDoctorIdState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.selectedDoctorId = next;
      return next;
    });
  };
  const setSelectedDate = (val: string | ((prev: string) => string)) => {
    setSelectedDateState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.selectedDate = next;
      return next;
    });
  };
  const setSelectedTime = (val: string | ((prev: string) => string)) => {
    setSelectedTimeState((prev) => {
      const next = typeof val === "function" ? val(prev) : val;
      consoleCache.selectedTime = next;
      return next;
    });
  };
  
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getPatients()
      .then((data) => {
        setPatientsList(data.map((p) => ({ id: p.patient_id, name: p.name, phone: p.phone })));
      })
      .catch((err) => {
        console.warn("Could not load patients dynamically, using fallbacks:", err);
        setPatientsList(SAMPLE_PATIENTS);
      });

    // Request HTML5 native notification permission on load
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [events]);

  function triggerRealNotification(message: string) {
    if ("Notification" in window) {
      if (Notification.permission === "granted") {
        new Notification("Hospital Notification Agent", {
          body: message,
          tag: "hospital-notification-alert",
        });
      } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then((permission) => {
          if (permission === "granted") {
            new Notification("Hospital Notification Agent", {
              body: message,
              tag: "hospital-notification-alert",
            });
          }
        });
      }
    }
  }

  function handleAgentEvent(ev: AgentEvent) {
    setEvents((prev) => [...prev, ev]);
    if (ev.agent === "Notification" && ev.status === "success") {
      triggerRealNotification(ev.message);
    }
  }

  async function handleRun() {
    setRunning(true);
    setEvents([]);
    setResult(null);
    setWaitingForConfirmation(false);
    setAvailableDoctors([]);
    setSelectedDoctorId("");
    setSelectedDate("");
    setSelectedTime("");
    setErrorText(null);
    try {
      const r = await runWorkflow(patientId.trim(), query.trim(), handleAgentEvent, debug);
      if (r.waiting_for_confirmation) {
        setResult(r);
        setWaitingForConfirmation(true);
        const docs = r.doctor_search_result?.recommended_doctors || [];
        setAvailableDoctors(docs);
        if (docs.length > 0) {
          const firstDoc = docs[0];
          setSelectedDoctorId(firstDoc.doctor_id);
          if (firstDoc.available_slots && firstDoc.available_slots.length > 0) {
            const firstSlot = firstDoc.available_slots[0];
            const parts = firstSlot.split(" ");
            setSelectedDate(parts[0]);
            setSelectedTime(parts[1] || "09:00");
          }
        }
      } else {
        setResult(r);
      }
    } catch (err: any) {
      console.error("Error executing workflow:", err);
      setErrorText(err.message || "Failed to execute workflow.");
    } finally {
      setRunning(false);
    }
  }

  async function handleConfirm() {
    if (!selectedDoctorId || !selectedDate || !selectedTime) return;
    setRunning(true);
    setWaitingForConfirmation(false);
    setErrorText(null);
    try {
      const r = await resumeWorkflow(
        patientId.trim(),
        selectedDoctorId,
        selectedDate,
        selectedTime,
        "confirm",
        handleAgentEvent,
        debug
      );
      setResult(r);
    } catch (err: any) {
      console.error("Error confirming slot:", err);
      setErrorText(err.message || "Failed to confirm appointment slot.");
    } finally {
      setRunning(false);
    }
  }

  async function handleCancel() {
    setRunning(true);
    setWaitingForConfirmation(false);
    setErrorText(null);
    try {
      const r = await resumeWorkflow(
        patientId.trim(),
        "",
        "",
        "",
        "cancel",
        handleAgentEvent,
        debug
      );
      setResult(r);
    } catch (err: any) {
      console.error("Error cancelling request:", err);
      setErrorText(err.message || "Failed to cancel transaction.");
    } finally {
      setRunning(false);
    }
  }

  function resetWorkflowState() {
    setEvents([]);
    setResult(null);
    setWaitingForConfirmation(false);
    setAvailableDoctors([]);
    setSelectedDoctorId("");
    setSelectedDate("");
    setSelectedTime("");
    setErrorText(null);
  }

  function loadSample(i: number) {
    const s = SAMPLE_QUERIES[i];
    setPatientId(s.patient);
    setQuery(s.query);
    resetWorkflowState();
  }

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto max-w-7xl px-6 py-8 grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* LEFT — request composer */}
        <section className="space-y-6">
          <div className="rounded-2xl border border-border bg-surface p-5 agent-glow">
            <h2 className="text-sm font-semibold tracking-tight mb-4 flex items-center gap-2">
              <Play className="h-4 w-4 text-primary" /> New patient request
            </h2>

            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Patient ID</label>
            <PatientSelector
              patients={patientsList}
              selectedId={patientId}
              onChange={(id) => {
                setPatientId(id);
                resetWorkflowState();
              }}
              onAddNewClick={() => setShowRegisterModal(true)}
            />

            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Natural-language request</label>
            <textarea
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (waitingForConfirmation || result) {
                  resetWorkflowState();
                }
              }}
              rows={6}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring resize-none leading-relaxed"
              placeholder="e.g. I have chest pain. Book a cardiologist and schedule an ECG if I don't have one."
            />

            <button
              onClick={handleRun}
              disabled={running || !patientId.trim() || !query.trim()}
              className="mt-4 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {running ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Agents working…
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" /> Run workflow
                </>
              )}
            </button>



            <div className="mt-5 pt-4 border-t border-border">
              <p className="text-xs font-medium text-muted-foreground mb-2">Try a sample</p>
              <div className="space-y-1.5">
                {SAMPLE_QUERIES.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => loadSample(i)}
                    disabled={running}
                    className="w-full text-left rounded-md px-3 py-2 text-xs bg-muted hover:bg-accent transition disabled:opacity-50"
                  >
                    <span className="font-medium">{s.label}</span>
                    <span className="text-muted-foreground"> · {s.patient}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <AgentRoster events={events} running={running} />
        </section>

        {/* RIGHT — live agent activity + results */}
        <section className="space-y-6 min-w-0">
          {errorText && (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-xs font-sans text-destructive flex items-start gap-3 border-l-4 border-l-destructive shadow-sm animate-fade-in">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <span className="font-bold block mb-0.5 text-[13px]">Workflow Execution Error</span>
                <p className="text-foreground/80 leading-relaxed font-sans">{errorText}</p>
              </div>
            </div>
          )}

          <StatusCards result={result} running={running} events={events} />

          {waitingForConfirmation && (
            <div className="rounded-2xl border border-warning/30 bg-surface p-6 shadow-md space-y-6 animate-fade-in border-l-4 border-l-warning">
              <div className="flex items-center gap-3 border-b border-border/50 pb-3">
                <div className="h-10 w-10 rounded-xl bg-warning/10 text-warning flex items-center justify-center flex-shrink-0 animate-pulse">
                  <Workflow className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground">Human-in-the-Loop Confirmation</h3>
                  <p className="text-xs text-muted-foreground">Select a doctor and available slot to proceed with booking.</p>
                </div>
              </div>

              {/* Doctor Cards */}
              <div className="space-y-3">
                <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider">Choose Doctor</label>
                <div className="grid gap-3 sm:grid-cols-2">
                  {availableDoctors.length === 0 ? (
                    <div className="sm:col-span-2 p-5 rounded-xl bg-muted/20 border border-border text-center text-xs text-muted-foreground italic font-sans flex flex-col items-center justify-center gap-1.5 py-8">
                      <Workflow className="h-6 w-6 text-muted-foreground/45 mb-1" />
                      <span>No matching doctors with available slots found for this specialization.</span>
                    </div>
                  ) : (
                    availableDoctors.map((doc) => {
                      const isSelected = doc.doctor_id === selectedDoctorId;
                      return (
                        <button
                          key={doc.doctor_id}
                          onClick={() => {
                            setSelectedDoctorId(doc.doctor_id);
                            if (doc.available_slots && doc.available_slots.length > 0) {
                              setSelectedDate(doc.available_slots[0].split(" ")[0]);
                              setSelectedTime(doc.available_slots[0].split(" ")[1] || "09:00");
                            }
                          }}
                          className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                            isSelected
                              ? "border-primary bg-primary/5 ring-1 ring-primary"
                              : "border-border bg-background hover:border-border/60"
                          }`}
                        >
                          <div>
                            <span className="font-semibold text-foreground block text-sm">{doc.name}</span>
                            <span className="text-[11px] text-muted-foreground block">{doc.specialization} · {doc.experience} yrs exp</span>
                            <span className="text-[11px] text-muted-foreground block font-mono">{doc.hospital}</span>
                          </div>
                          <div className="mt-3 flex items-center justify-between w-full text-xs">
                            <span className="font-semibold text-primary font-mono">${doc.fee} Fee</span>
                            <span className="text-warning-foreground font-semibold">★ {doc.rating} Rating</span>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Calendar / Slots selection */}
              {selectedDoctorId && (
                <div className="grid gap-4 sm:grid-cols-2 pt-3 border-t border-border/50">
                  <div>
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Available Dates</label>
                    <div className="relative">
                      <select
                        value={selectedDate}
                        onChange={(e) => {
                          const newDate = e.target.value;
                          setSelectedDate(newDate);
                          const doc = availableDoctors.find(d => d.doctor_id === selectedDoctorId);
                          const firstTime = doc?.available_slots
                            .filter((s: string) => s.split(" ")[0] === newDate)
                            .map((s: string) => s.split(" ")[1] || "09:00")[0] || "09:00";
                          setSelectedTime(firstTime);
                        }}
                        className="w-full appearance-none rounded-lg border border-input bg-background px-3 py-2 pr-9 text-xs outline-none focus:ring-2 focus:ring-ring"
                      >
                        {Array.from(new Set((availableDoctors.find(d => d.doctor_id === selectedDoctorId)?.available_slots || []).map((s: string) => s.split(" ")[0]))).map((d: any) => (
                          <option key={d} value={d}>
                            {d}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Available Time Slots</label>
                    <div className="relative">
                      <select
                        value={selectedTime}
                        onChange={(e) => setSelectedTime(e.target.value)}
                        className="w-full appearance-none rounded-lg border border-input bg-background px-3 py-2 pr-9 text-xs outline-none focus:ring-2 focus:ring-ring"
                      >
                        {(availableDoctors.find(d => d.doctor_id === selectedDoctorId)?.available_slots || [])
                          .filter((s: string) => s.split(" ")[0] === selectedDate)
                          .map((s: string) => s.split(" ")[1] || "09:00")
                          .map((t: string) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    </div>
                  </div>
                </div>
              )}

              {/* Buttons */}
              <div className="flex flex-wrap gap-3 pt-4 border-t border-border/50">
                <button
                  onClick={handleConfirm}
                  disabled={running || !selectedDoctorId || !selectedDate || !selectedTime}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition"
                >
                  <CheckCircle2 className="h-4 w-4" /> Confirm Booking
                </button>
                <button
                  onClick={handleCancel}
                  disabled={running}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-input bg-background px-4 py-2 text-xs font-semibold text-foreground hover:bg-accent disabled:opacity-50 transition"
                >
                  <AlertCircle className="h-4 w-4 text-destructive" /> Cancel Booking
                </button>
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-border bg-surface overflow-hidden shadow-sm">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-elevated">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold tracking-tight">Agent communication log</h3>
              </div>
              <span className="text-xs text-muted-foreground">{events.length} events</span>
            </div>

            <div ref={logRef} className="max-h-[450px] overflow-y-auto p-4 space-y-3">
              {events.length === 0 && !running ? (
                <div className="text-center py-16 text-muted-foreground font-mono text-xs">
                  <Workflow className="h-8 w-8 mx-auto mb-3 opacity-40" />
                  <p className="text-sm font-sans">Run a request to see the agents coordinate live.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {(["Supervisor", "PatientInfo", "EmergencyCheck", "DoctorSearch", "Appointment", "LabScheduling", "LabReport", "Notification", "Validator", "Summarizer"] as AgentName[]).map((agent) => {
                    const agentEvents = events.filter((e) => e.agent === agent);
                    return (
                      <AgentGroupCard
                        key={agent}
                        agent={agent}
                        events={agentEvents}
                        isWorkflowRunning={running || waitingForConfirmation}
                        isWorkflowFinished={result !== null && !waitingForConfirmation}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {result && (
            <div className="space-y-6">
              <SummarySection result={result} />
              <DetailsGrid result={result} />
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-border mt-12">
        <div className="mx-auto max-w-7xl px-6 py-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-2">
          <span>Frontend for the Agentic Hospital Management System (LangGraph + Gemini)</span>
          <span>Live API Connection to the local FastAPI Backend.</span>
        </div>
      </footer>

      {showRegisterModal && (
        <PatientFormModal
          onClose={() => setShowRegisterModal(false)}
          onSaveSuccess={(newPatient) => {
            setPatientsList((prev) => [
              ...prev,
              {
                id: newPatient.patient_id,
                name: `${newPatient.name} ⭐ (new)`,
                phone: newPatient.phone,
              },
            ]);
            setPatientId(newPatient.patient_id);
            resetWorkflowState();
            setShowRegisterModal(false);
          }}
        />
      )}
    </div>
  );
}

function SummarySection({ result }: { result: WorkflowResult }) {
  const [activeTab, setActiveTab] = useState<"patient" | "admin">("patient");
  
  let patientSummary = "";
  let adminSummary = "";
  
  try {
    const parsed = JSON.parse(result.summary);
    patientSummary = parsed.patient_summary || "";
    adminSummary = parsed.admin_summary || "";
  } catch (e) {
    patientSummary = result.summary;
    adminSummary = "Workflow completed successfully. Operations ledger successfully reconciled.";
  }

  return (
    <div className="rounded-2xl border border-border bg-surface overflow-hidden shadow-sm">
      <div className="flex border-b border-border bg-surface-elevated">
        <button
          onClick={() => setActiveTab("patient")}
          className={`flex-1 py-3 text-xs font-semibold tracking-tight transition flex items-center justify-center gap-2 border-b-2 outline-none ${
            activeTab === "patient"
              ? "border-primary text-primary bg-background/30"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" /> Patient Summary
        </button>
        <button
          onClick={() => setActiveTab("admin")}
          className={`flex-1 py-3 text-xs font-semibold tracking-tight transition flex items-center justify-center gap-2 border-b-2 outline-none ${
            activeTab === "admin"
              ? "border-primary text-primary bg-background/30"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="h-3.5 w-3.5" /> Administrative Plan
        </button>
      </div>
      
      <div className="p-5">
        {activeTab === "patient" ? (
          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success">
              <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              Patient Care Directive
            </div>
            <p className="text-sm leading-relaxed text-foreground/90 font-medium">
              {patientSummary}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-info/10 px-2.5 py-0.5 text-xs font-medium text-info">
              <span className="h-1.5 w-1.5 rounded-full bg-info animate-pulse" />
              System Operations Summary
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground font-mono bg-muted/40 p-3 rounded-lg border border-border whitespace-pre-wrap animate-fade-in">
              {adminSummary}
            </p>
          </div>
        )}
      </div>

      <div className="border-t border-border bg-surface-elevated/40 px-5 py-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs text-foreground/90 font-medium font-sans">
          <span className="text-success text-base">✅</span>
          <span>Report Generated Successfully</span>
        </div>
        
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <a
            href={`http://localhost:8000/api/reports/${result.appointment_result?.appointment_id || `A${result.patient_info?.patient_info?.patient_id || result.patient_info?.patient_id || "P001"}`}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 sm:flex-initial text-center rounded-lg border border-input bg-background hover:bg-accent px-3.5 py-2 text-xs font-semibold text-foreground transition cursor-pointer"
          >
            View Report
          </a>
          
          <a
            href={`http://localhost:8000/api/reports/${result.appointment_result?.appointment_id || `A${result.patient_info?.patient_info?.patient_id || result.patient_info?.patient_id || "P001"}`}?download=true`}
            className="flex-1 sm:flex-initial text-center rounded-lg bg-primary hover:bg-primary/90 px-3.5 py-2 text-xs font-semibold text-primary-foreground transition cursor-pointer"
          >
            Download PDF
          </a>
          
          <button
            type="button"
            onClick={() => {
              const url = `http://localhost:8000/api/reports/${result.appointment_result?.appointment_id || `A${result.patient_info?.patient_info?.patient_id || result.patient_info?.patient_id || "P001"}`}`;
              if (navigator.share) {
                navigator.share({
                  title: 'Patient Care Report',
                  text: 'SACRED HEART GENERAL HOSPITAL - Patient Care Report Summary',
                  url: url
                }).catch(console.error);
              } else {
                navigator.clipboard.writeText(url);
                alert("Report link copied to clipboard!");
              }
            }}
            className="rounded-lg border border-input bg-background hover:bg-accent p-2 text-foreground transition cursor-pointer"
            title="Share Report"
          >
            <Share2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailsGrid({ result }: { result: WorkflowResult }) {
  const p = result.patient_info;
  const appt = result.appointment_result;
  const lab = result.lab_schedule_result;
  const analysis = result.lab_report_analysis;

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Patient Profile Card */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 hover:border-primary/30 transition">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
            <UserRound className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">Patient Profile Record</h4>
            <p className="text-[10px] text-muted-foreground">Demographics & Diagnosed History</p>
          </div>
        </div>
        {p ? (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 border-b border-border/50 pb-2">
              <div>
                <span className="text-muted-foreground block text-[10px]">Full Name</span>
                <span className="font-semibold text-foreground">{p.patient_info?.name || "Unknown"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Age / Gender</span>
                <span className="font-semibold text-foreground">
                  {p.patient_info?.age} yrs · <span className="capitalize">{p.patient_info?.gender}</span>
                </span>
              </div>
            </div>
            <div>
              <span className="text-muted-foreground block text-[10px] mb-1">Diagnosed Conditions</span>
              <div className="flex flex-wrap gap-1.5">
                {(p.medical_history || []).map((h: string, i: number) => (
                  <span key={i} className="inline-flex items-center rounded-md bg-primary/5 border border-primary/20 px-2 py-0.5 text-[10px] font-medium text-primary">
                    {h}
                  </span>
                ))}
                {(p.medical_history || []).length === 0 && (
                  <span className="text-muted-foreground italic text-[11px]">None documented</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">Patient info was not loaded.</p>
        )}
      </div>

      {/* Appointment Detail Card */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 hover:border-info/30 transition">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-info/10 text-info flex items-center justify-center flex-shrink-0">
            <Stethoscope className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">Consultation Booking</h4>
            <p className="text-[10px] text-muted-foreground">Specialist slot reservation</p>
          </div>
        </div>
        {appt && appt.appointment_status !== "failed" ? (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 border-b border-border/50 pb-2">
              <div>
                <span className="text-muted-foreground block text-[10px]">Doctor Assigned</span>
                <span className="font-semibold text-foreground">{appt.doctor_name || appt.doctor || "Assigned Specialist"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Booking Code</span>
                <span className="font-mono font-semibold text-primary">{appt.appointment_id || "N/A"}</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-muted-foreground block text-[10px]">Reserved Slot</span>
                <span className="font-semibold text-foreground">{appt.slot || `${appt.date || ''} ${appt.time || ''}`.trim() || "N/A"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Status</span>
                <span className="inline-flex items-center rounded-full bg-success/5 border border-success/30 px-2 py-0.5 text-[9px] font-semibold text-success uppercase">
                  {appt.appointment_status}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground space-y-2">
            <p className="italic">No active appointment booked during this run.</p>
            {appt?.next_available?.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border">
                <span className="text-[10px] text-muted-foreground block mb-1">Suggested Slots:</span>
                <div className="flex flex-wrap gap-1">
                  {appt.next_available.map((s: string, i: number) => (
                    <span key={i} className="bg-muted px-1.5 py-0.5 rounded text-[10px] border border-border">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Lab Order Card */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 hover:border-info/30 transition">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-info/10 text-info flex items-center justify-center flex-shrink-0">
            <FlaskConical className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">Diagnostic Lab Scheduling</h4>
            <p className="text-[10px] text-muted-foreground">Technical and resource allocation</p>
          </div>
        </div>
        {lab ? (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 border-b border-border/50 pb-2">
              <div>
                <span className="text-muted-foreground block text-[10px]">Lab Booking ID</span>
                <span className="font-mono font-semibold text-primary">{lab.lab_booking_id || "N/A"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Scheduled Tests</span>
                <span className="font-semibold text-foreground">{(lab.tests || []).join(", ") || "None"}</span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-muted-foreground block text-[10px]">Lab Date & Time</span>
                <span className="font-semibold text-foreground">{lab.lab_date} at {lab.lab_time}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Workflow Action</span>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase border ${
                  lab.lab_booking_id?.startsWith("EXISTING") 
                    ? "bg-warning/5 border-warning/30 text-warning" 
                    : "bg-success/5 border-success/30 text-success"
                }`}>
                  {lab.lab_booking_id?.startsWith("EXISTING") ? "Reused Report" : "Scheduled New"}
                </span>
              </div>
            </div>

            {lab.instructions && lab.instructions.length > 0 && (
              <div className="pt-2 border-t border-border/50">
                <span className="text-[10px] text-muted-foreground block mb-1">Pre-Test Instructions & Allocation</span>
                <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-muted-foreground">
                  {lab.instructions.map((ins: string, i: number) => (
                    <li key={i}>{ins}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">No lab schedule result.</p>
        )}
      </div>

      {/* AI Diagnostic Review Card */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 hover:border-success/30 transition">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-success/10 text-success flex items-center justify-center flex-shrink-0">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">AI Lab Diagnostic Review</h4>
            <p className="text-[10px] text-muted-foreground">Automated pathology parameter auditing</p>
          </div>
        </div>
        {analysis ? (
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-border/50 pb-2 gap-2">
              <p className="text-[11px] font-medium text-foreground/90 leading-normal">{analysis.summary}</p>
              <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold flex-shrink-0 border uppercase ${
                analysis.risk_level === "High" 
                  ? "bg-destructive/5 text-destructive border-destructive/20" 
                  : analysis.risk_level === "Moderate"
                    ? "bg-warning/5 text-warning-foreground border-warning/20"
                    : "bg-success/5 text-success border-success/20"
              }`}>
                {analysis.risk_level} Risk
              </span>
            </div>

            {analysis.abnormal_results && analysis.abnormal_results.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold text-destructive block mb-1">Abnormal Findings</span>
                <div className="space-y-1">
                  {analysis.abnormal_results.map((r: any, i: number) => (
                    <div key={i} className="flex justify-between bg-destructive/5 border border-destructive/10 rounded p-1.5 text-[10px]">
                      <span className="font-medium text-foreground">{r.parameter}</span>
                      <span className="text-destructive font-semibold">{r.value} (Normal: {r.normal_range})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analysis.normal_results && analysis.normal_results.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold text-success block mb-1">Normal Parameters</span>
                <div className="grid grid-cols-2 gap-1.5">
                  {analysis.normal_results.map((r: any, i: number) => (
                    <div key={i} className="flex justify-between bg-muted/30 border border-border/50 rounded px-1.5 py-1 text-[10px] text-muted-foreground">
                      <span className="truncate mr-1">{r.parameter}</span>
                      <span className="font-semibold text-foreground flex-shrink-0">{r.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analysis.recommendation && (
              <div className="pt-2 border-t border-border/50 text-[11px]">
                <span className="font-semibold text-foreground">Recommendation: </span>
                <span className="text-muted-foreground">{analysis.recommendation}</span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">No lab report analysis was executed for this request.</p>
        )}
      </div>

      {/* Validator Audits Card */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 hover:border-warning/30 transition md:col-span-2">
        <div className="flex items-center justify-between border-b border-border/50 pb-3 gap-2 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-warning/10 text-warning flex items-center justify-center flex-shrink-0">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-foreground">Self-Correction & Graph Validator</h4>
              <p className="text-[10px] text-muted-foreground">Workflow reconciliation audit trail</p>
            </div>
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase border ${
            result.validation_passed 
              ? "bg-success/5 border-success/30 text-success" 
              : "bg-destructive/5 border-destructive/30 text-destructive"
          }`}>
            {result.validation_passed ? "Audit Passed" : "Audit Failed"}
          </span>
        </div>
        
        <div className="grid gap-4 sm:grid-cols-2 text-xs">
          <div className="space-y-1.5">
            <span className="text-[10px] text-muted-foreground block">Validator Audit Feedback</span>
            <p className="font-mono text-xs bg-muted/40 border border-border p-2.5 rounded-lg text-foreground/90 whitespace-pre-wrap leading-relaxed">
              {result.validation_feedback || "All planned tasks successfully reconciled against database records. Final outcome validated."}
            </p>
          </div>
          
          <div className="space-y-2">
            <div>
              <span className="text-[10px] text-muted-foreground block mb-1">Errors Logged</span>
              {result.errors && result.errors.length > 0 ? (
                <div className="space-y-1">
                  {result.errors.map((err, i) => (
                    <div key={i} className="flex items-start gap-1.5 bg-destructive/5 text-destructive p-1.5 rounded text-[11px] border border-destructive/10">
                      <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                      <span>{err}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="font-semibold text-success block mt-0.5">None. Core system services responded with 100% SLA.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AgentGroupCard({
  agent,
  events,
  isWorkflowRunning,
  isWorkflowFinished,
}: {
  agent: AgentName;
  events: AgentEvent[];
  isWorkflowRunning: boolean;
  isWorkflowFinished: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const meta = AGENT_META[agent];
  if (!meta) return null;
  const Icon = meta.icon;

  let status: "idle" | "pending" | "running" | "success" | "warning" | "error" | "skipped" = "idle";
  if (events.length === 0) {
    if (isWorkflowFinished) {
      status = "skipped";
    } else if (isWorkflowRunning) {
      status = "pending";
    } else {
      status = "idle";
    }
  } else {
    const hasError = events.some((e) => e.status === "error");
    const hasWarning = events.some((e) => e.status === "warning");
    const hasRunning = events.some((e) => e.status === "running");
    
    if (hasError) {
      status = "error";
    } else if (hasWarning) {
      status = "warning";
    } else if (hasRunning && events[events.length - 1].status === "running") {
      status = "running";
    } else {
      status = "success";
    }
  }

  useEffect(() => {
    if (status === "running") {
      setExpanded(true);
    }
  }, [status]);

  if (status === "idle") return null;

  const statusStyles = {
    idle: "border-border/40 bg-muted/10 opacity-50",
    pending: "border-border bg-muted/20 opacity-70",
    running: "border-info/40 bg-info/5 ring-1 ring-info/30 shadow-info/5 shadow-lg",
    success: "border-success/30 bg-success/5 hover:border-success/50",
    warning: "border-warning/30 bg-warning/5 hover:border-warning/50",
    error: "border-destructive/30 bg-destructive/5 hover:border-destructive/50",
    skipped: "border-border/30 bg-muted/5 opacity-60 border-dashed",
  }[status];

  const statusColor = {
    idle: "text-muted-foreground",
    pending: "text-muted-foreground animate-pulse",
    running: "text-info",
    success: "text-success",
    warning: "text-warning",
    error: "text-destructive",
    skipped: "text-muted-foreground",
  }[status];

  const statusText = {
    idle: "Idle",
    pending: "🟡 Pending",
    running: "🌀 Active",
    success: "✔ Completed",
    warning: "🟡 Waiting",
    error: "✖ Failed",
    skipped: "⏭ Skipped",
  }[status];

  let durationStr = "";
  if (events.length >= 2) {
    const start = events[0].timestamp;
    const end = events[events.length - 1].timestamp;
    const diff = end - start;
    durationStr = diff < 1000 ? `${diff}ms` : `${(diff / 1000).toFixed(2)}s`;
  } else if (events.length === 1 && status === "running") {
    durationStr = "running...";
  }

  const toolOutput = events.find((e) => e.detail !== undefined && e.detail !== null)?.detail;

  const handleCopy = () => {
    if (!toolOutput) return;
    navigator.clipboard.writeText(JSON.stringify(toolOutput, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`rounded-xl border ${statusStyles} transition-all duration-300 overflow-hidden shadow-sm`}>
      <div
        onClick={() => status !== "skipped" && status !== "pending" && setExpanded(!expanded)}
        className={`px-4 py-3 flex items-center justify-between gap-3 select-none ${
          status !== "skipped" && status !== "pending" ? "cursor-pointer hover:bg-black/5 dark:hover:bg-white/5" : ""
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`${meta.color} flex-shrink-0`}>
            <Icon className="h-4 w-4" />
          </div>
          <span className="font-sans font-bold text-xs text-foreground truncate">{meta.label}</span>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {durationStr && (
            <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {durationStr}
            </span>
          )}
          <span className={`text-[10px] font-sans font-semibold uppercase tracking-wider ${statusColor}`}>
            {statusText}
          </span>
          {status !== "skipped" && status !== "pending" && (
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-300 ${
                expanded ? "rotate-180" : ""
              }`}
            />
          )}
        </div>
      </div>

      {expanded && (status !== "skipped" && status !== "pending") && (
        <div className="border-t border-border bg-muted/10 p-4 space-y-4">
          <div className="relative pl-4 space-y-3.5 before:absolute before:left-[5px] before:top-[8px] before:bottom-[8px] before:w-[1.5px] before:bg-border/60">
            {events.map((ev, i) => {
              const itemStatusStyles = {
                running: "bg-info ring-4 ring-info/10",
                success: "bg-success ring-4 ring-success/10",
                warning: "bg-warning ring-4 ring-warning/10",
                error: "bg-destructive ring-4 ring-destructive/10",
              }[ev.status];

              let displayMessage = ev.message;
              if (ev.agent === "Summarizer" && ev.status === "success") {
                try {
                  const parsed = JSON.parse(ev.message);
                  displayMessage = parsed.patient_summary || ev.message;
                } catch {
                }
              }

              return (
                <div key={ev.id || i} className="relative flex flex-col gap-1">
                  <span className={`absolute -left-[14.5px] top-[4px] h-[7px] w-[7px] rounded-full ${itemStatusStyles}`} />
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-sans text-[11px] font-medium text-foreground/90">{displayMessage}</span>
                    <span className="text-[9px] text-muted-foreground font-mono">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {toolOutput && (
            <div className="mt-3 rounded-lg border border-border bg-background overflow-hidden">
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-muted/30">
                <span className="text-[10px] font-sans font-bold text-muted-foreground uppercase tracking-wider">
                  Tool Output / Payload
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCopy();
                  }}
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition flex items-center gap-1 text-[9px] font-sans font-medium"
                  title="Copy tool output JSON"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-success" /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" /> Copy JSON
                    </>
                  )}
                </button>
              </div>
              <pre className="p-3 text-[10px] font-mono text-foreground/80 overflow-x-auto max-h-[180px] bg-background/50">
                {JSON.stringify(toolOutput, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PatientSelector({
  patients,
  selectedId,
  onChange,
  onAddNewClick,
}: {
  patients: { id: string; name: string; phone?: string }[];
  selectedId: string;
  onChange: (id: string) => void;
  onAddNewClick: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedPatient = patients.find((p) => p.id === selectedId);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredPatients = patients.filter((p) => {
    const s = search.toLowerCase().trim();
    if (!s) return true;
    return (
      p.id.toLowerCase().includes(s) ||
      p.name.toLowerCase().includes(s) ||
      (p.phone && p.phone.toLowerCase().includes(s))
    );
  });

  return (
    <div className="relative mb-4 flex gap-2 items-center" ref={dropdownRef}>
      <div className="relative flex-1">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="w-full text-left appearance-none rounded-lg border border-input bg-background px-3 py-2 pr-9 text-sm outline-none focus:ring-2 focus:ring-ring flex items-center justify-between cursor-pointer"
        >
          <span className="truncate">
            {selectedPatient ? `${selectedPatient.id} — ${selectedPatient.name}` : "Select Patient..."}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground pointer-events-none" />
        </button>

        {open && (
          <div className="absolute left-0 right-0 mt-1 z-50 rounded-lg border border-border bg-surface p-2 shadow-lg max-h-[300px] overflow-y-auto space-y-2 animate-in fade-in slide-in-from-top-1 duration-150">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ID, name, phone..."
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-ring mb-1"
              onClick={(e) => e.stopPropagation()}
            />

            <div className="space-y-0.5 max-h-[200px] overflow-y-auto">
              {filteredPatients.length === 0 ? (
                <div className="text-center py-4 text-xs text-muted-foreground font-sans">
                  No patients found
                </div>
              ) : (
                filteredPatients.map((p) => {
                  const isSelected = p.id === selectedId;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        onChange(p.id);
                        setOpen(false);
                        setSearch("");
                      }}
                      className={`w-full text-left rounded-md px-2.5 py-1.5 text-xs transition flex justify-between items-center ${
                        isSelected
                          ? "bg-primary/10 text-primary font-semibold"
                          : "hover:bg-accent text-foreground"
                      }`}
                    >
                      <span className="truncate font-sans">{p.id} — {p.name}</span>
                      {p.phone && <span className="text-[10px] text-muted-foreground font-mono">{p.phone}</span>}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onAddNewClick}
        className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background hover:bg-accent px-3 py-2 text-sm font-medium text-foreground transition cursor-pointer flex-shrink-0"
        title="Add New Patient"
      >
        ➕ <span className="hidden sm:inline">Add</span>
      </button>
    </div>
  );
}

interface PatientFormModalProps {
  onClose: () => void;
  onSaveSuccess: (newPatient: Patient) => void;
}

function PatientFormModal({ onClose, onSaveSuccess }: PatientFormModalProps) {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [bloodGroup, setBloodGroup] = useState("Unknown");
  const [address, setAddress] = useState("");
  const [emergencyContact, setEmergencyContact] = useState("");
  const [insuranceProvider, setInsuranceProvider] = useState("");
  const [insuranceNumber, setInsuranceNumber] = useState("");
  const [notes, setNotes] = useState("");

  const [allergies, setAllergies] = useState<string[]>([]);
  const [customAllergy, setCustomAllergy] = useState("");
  const [conditions, setConditions] = useState<string[]>([]);
  const [customCondition, setCustomCondition] = useState("");

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const presetAllergies = ["Penicillin", "Dust", "Milk", "Peanuts", "None"];
  const presetConditions = ["Diabetes", "Hypertension", "Asthma", "Heart Disease", "None"];

  const handleAllergyClick = (allergy: string) => {
    if (allergy === "None") {
      setAllergies(["None"]);
    } else {
      setAllergies((prev) => {
        const filtered = prev.filter((a) => a !== "None");
        if (filtered.includes(allergy)) {
          return filtered.filter((a) => a !== allergy);
        } else {
          return [...filtered, allergy];
        }
      });
    }
  };

  const handleConditionClick = (condition: string) => {
    if (condition === "None") {
      setConditions(["None"]);
    } else {
      setConditions((prev) => {
        const filtered = prev.filter((c) => c !== "None");
        if (filtered.includes(condition)) {
          return filtered.filter((c) => c !== condition);
        } else {
          return [...filtered, condition];
        }
      });
    }
  };

  const addCustomAllergy = () => {
    const val = customAllergy.trim();
    if (val && !allergies.includes(val)) {
      setAllergies((prev) => [...prev.filter((a) => a !== "None"), val]);
      setCustomAllergy("");
    }
  };

  const addCustomCondition = () => {
    const val = customCondition.trim();
    if (val && !conditions.includes(val)) {
      setConditions((prev) => [...prev.filter((c) => c !== "None"), val]);
      setCustomCondition("");
    }
  };

  const handleClear = () => {
    setName("");
    setAge("");
    setGender("");
    setPhone("");
    setEmail("");
    setBloodGroup("Unknown");
    setAddress("");
    setEmergencyContact("");
    setInsuranceProvider("");
    setInsuranceNumber("");
    setNotes("");
    setAllergies([]);
    setConditions([]);
    setErrors({});
  };

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!name.trim()) nextErrors.name = "Patient Name is required";
    
    if (!age) {
      nextErrors.age = "Age is required";
    } else {
      const ageNum = parseInt(age);
      if (isNaN(ageNum) || ageNum <= 0) {
        nextErrors.age = "Age must be a positive integer";
      }
    }

    if (!gender) nextErrors.gender = "Gender is required";

    if (phone.trim()) {
      const phoneRegex = /^\+?[0-9\s\-()]{7,15}$/;
      if (!phoneRegex.test(phone.trim())) {
        nextErrors.phone = "Invalid phone number format";
      }
    }

    if (email.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email.trim())) {
        nextErrors.email = "Invalid email format";
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setSaving(true);
    try {
      const payload: Patient = {
        patient_id: "",
        name: name.trim(),
        age: parseInt(age),
        gender,
        medical_history: conditions,
        allergies,
        phone: phone.trim(),
        email: email.trim(),
        blood_group: bloodGroup,
        address: address.trim(),
        insurance_provider: insuranceProvider.trim(),
        insurance_number: insuranceNumber.trim(),
        emergency_contact: emergencyContact.trim(),
        notes: notes.trim(),
      };

      const result = await createPatient(payload);
      setSuccess(true);
      setTimeout(() => {
        onSaveSuccess(result);
      }, 1500);
    } catch (err: any) {
      console.error(err);
      setErrors({ api: err.message || "Failed to save patient record" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-surface rounded-2xl border border-border shadow-xl flex flex-col animate-in zoom-in-95 duration-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-border bg-surface-elevated flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground">New Patient Registration</h3>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition text-xs font-sans cursor-pointer"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSave} className="flex-1 overflow-y-auto p-6 space-y-6 font-sans">
          {success ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <span className="h-16 w-16 bg-success/10 text-success rounded-full flex items-center justify-center text-3xl animate-bounce">
                ✅
              </span>
              <h4 className="text-sm font-bold text-foreground">Patient Registered Successfully</h4>
              <p className="text-xs text-muted-foreground">Adding patient profile and closing form...</p>
            </div>
          ) : (
            <>
              {errors.api && (
                <div className="p-3 bg-destructive/10 text-destructive text-xs rounded-lg border border-destructive/20 font-sans">
                  {errors.api}
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Patient Name *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="e.g. Mukesh Kumar"
                  />
                  {errors.name && <p className="text-[10px] text-destructive font-sans">{errors.name}</p>}
                </div>

                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Age *
                  </label>
                  <input
                    type="number"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="e.g. 28"
                  />
                  {errors.age && <p className="text-[10px] text-destructive font-sans">{errors.age}</p>}
                </div>

                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Gender *
                  </label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                  >
                    <option value="" className="text-foreground">Select Gender</option>
                    <option value="Male" className="text-foreground">Male</option>
                    <option value="Female" className="text-foreground">Female</option>
                    <option value="Other" className="text-foreground">Other</option>
                  </select>
                  {errors.gender && <p className="text-[10px] text-destructive font-sans">{errors.gender}</p>}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="+91 9876543210"
                  />
                  {errors.phone && <p className="text-[10px] text-destructive font-sans">{errors.phone}</p>}
                </div>

                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Email
                  </label>
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="example@hospital.com"
                  />
                  {errors.email && <p className="text-[10px] text-destructive font-sans">{errors.email}</p>}
                </div>

                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Blood Group
                  </label>
                  <select
                    value={bloodGroup}
                    onChange={(e) => setBloodGroup(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                  >
                    <option value="Unknown" className="text-foreground">Unknown</option>
                    <option value="A+" className="text-foreground">A+</option>
                    <option value="A-" className="text-foreground">A-</option>
                    <option value="B+" className="text-foreground">B+</option>
                    <option value="B-" className="text-foreground">B-</option>
                    <option value="AB+" className="text-foreground">AB+</option>
                    <option value="AB-" className="text-foreground">AB-</option>
                    <option value="O+" className="text-foreground">O+</option>
                    <option value="O-" className="text-foreground">O-</option>
                  </select>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Address
                  </label>
                  <input
                    type="text"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="Street, City, Zip"
                  />
                </div>

                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Emergency Contact
                  </label>
                  <input
                    type="text"
                    value={emergencyContact}
                    onChange={(e) => setEmergencyContact(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="Name - Phone"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Known Allergies
                </label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {presetAllergies.map((allergy) => {
                    const isSelected = allergies.includes(allergy);
                    return (
                      <button
                        key={allergy}
                        type="button"
                        onClick={() => handleAllergyClick(allergy)}
                        className={`px-3 py-1 rounded-full text-xs font-sans transition border cursor-pointer ${
                          isSelected
                            ? "bg-destructive/10 border-destructive text-destructive font-semibold"
                            : "bg-muted/40 border-transparent text-foreground hover:bg-muted"
                        }`}
                      >
                        {allergy}
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-2 max-w-sm">
                  <input
                    type="text"
                    value={customAllergy}
                    onChange={(e) => setCustomAllergy(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomAllergy())}
                    className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="Add custom allergy..."
                  />
                  <button
                    type="button"
                    onClick={addCustomAllergy}
                    className="rounded-lg bg-muted px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-accent transition cursor-pointer"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {allergies.filter((a) => !presetAllergies.includes(a)).map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 bg-destructive/10 text-destructive border border-destructive/20 rounded-md px-2 py-0.5 text-xs"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => setAllergies((prev) => prev.filter((a) => a !== tag))}
                        className="text-[9px] hover:text-foreground font-sans font-bold cursor-pointer ml-1"
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Existing Medical Conditions
                </label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {presetConditions.map((condition) => {
                    const isSelected = conditions.includes(condition);
                    return (
                      <button
                        key={condition}
                        type="button"
                        onClick={() => handleConditionClick(condition)}
                        className={`px-3 py-1 rounded-full text-xs font-sans transition border cursor-pointer ${
                          isSelected
                            ? "bg-primary/10 border-primary text-primary font-semibold"
                            : "bg-muted/40 border-transparent text-foreground hover:bg-muted"
                        }`}
                      >
                        {condition}
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-2 max-w-sm">
                  <input
                    type="text"
                    value={customCondition}
                    onChange={(e) => setCustomCondition(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomCondition())}
                    className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="Add custom condition..."
                  />
                  <button
                    type="button"
                    onClick={addCustomCondition}
                    className="rounded-lg bg-muted px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-accent transition cursor-pointer"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {conditions.filter((c) => !presetConditions.includes(c)).map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 bg-primary/10 text-primary border border-primary/20 rounded-md px-2 py-0.5 text-xs"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => setConditions((prev) => prev.filter((c) => c !== tag))}
                        className="text-[9px] hover:text-foreground font-sans font-bold cursor-pointer ml-1"
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Insurance Provider
                  </label>
                  <input
                    type="text"
                    value={insuranceProvider}
                    onChange={(e) => setInsuranceProvider(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="e.g. Star Health"
                  />
                </div>

                <div className="space-y-1">
                  <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Insurance Number
                  </label>
                  <input
                    type="text"
                    value={insuranceNumber}
                    onChange={(e) => setInsuranceNumber(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring text-foreground"
                    placeholder="e.g. IN-987-123"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring resize-none text-foreground"
                  placeholder="Additional patient notes..."
                />
              </div>
            </>
          )}
        </form>

        {!success && (
          <div className="px-6 py-4 border-t border-border bg-surface-elevated flex items-center justify-between flex-wrap gap-2">
            <button
              type="button"
              onClick={handleClear}
              className="px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground bg-muted rounded-lg transition cursor-pointer"
            >
              Clear
            </button>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted border border-input rounded-lg transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 text-xs font-semibold text-primary-foreground bg-primary hover:bg-primary/95 rounded-lg transition flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save Patient
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function EventRow({ ev }: { ev: AgentEvent }) {
  const meta = AGENT_META[ev.agent];
  if (!meta) return null;
  const Icon = meta.icon;
  const statusStyles = {
    running: "border-info/40 bg-info/5",
    success: "border-success/40 bg-success/5",
    warning: "border-warning/40 bg-warning/5",
    error: "border-destructive/40 bg-destructive/5",
  }[ev.status];
  const StatusIcon = {
    running: Loader2,
    success: CheckCircle2,
    warning: AlertCircle,
    error: AlertCircle,
  }[ev.status];
  const statusColor = {
    running: "text-info",
    success: "text-success",
    warning: "text-warning",
    error: "text-destructive",
  }[ev.status];

  // Try to parse JSON message for summarizer agent display
  let displayMessage = ev.message;
  if (ev.agent === "Summarizer" && ev.status === "success") {
    try {
      const parsed = JSON.parse(ev.message);
      displayMessage = parsed.patient_summary || ev.message;
    } catch {
      // Fallback
    }
  }

  return (
    <div className={`rounded-lg border ${statusStyles} px-3 py-2 flex gap-3 items-start`}>
      <div className={`mt-0.5 ${meta.color} flex-shrink-0`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="font-sans font-semibold text-[11px] text-foreground">{meta.label}</span>
          <StatusIcon className={`h-3 w-3 ${statusColor} ${ev.status === "running" ? "animate-spin" : ""}`} />
          <span className="ml-auto text-[10px] text-muted-foreground font-sans">
            {new Date(ev.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <p className="font-sans text-xs text-foreground/85 leading-relaxed break-words">{displayMessage}</p>
        {ev.detail && (
          <details className="mt-1.5">
            <summary className="cursor-pointer text-[10px] text-muted-foreground font-sans hover:text-foreground">
              tool output
            </summary>
            <pre className="mt-1 rounded bg-background/60 border border-border p-2 text-[10px] overflow-x-auto">
              {JSON.stringify(ev.detail, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

function AgentRoster({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const activeAgents = new Set(
    events.filter((e) => e.status === "running").map((e) => e.agent),
  );
  const completedAgents = new Set(
    events.filter((e) => e.status === "success" || e.status === "warning").map((e) => e.agent),
  );

  const agents: AgentName[] = [
    "Supervisor",
    "PatientInfo",
    "EmergencyCheck",
    "DoctorSearch",
    "LabReport",
    "Appointment",
    "LabScheduling",
    "Notification",
    "Validator",
    "Summarizer",
  ];

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold tracking-tight mb-3 flex items-center gap-2">
        <Brain className="h-4 w-4 text-primary" /> Agent roster
      </h2>
      <div className="space-y-1.5">
        {agents.map((a) => {
          const meta = AGENT_META[a];
          const Icon = meta.icon;
          const isActive = activeAgents.has(a);
          const isDone = completedAgents.has(a);
          return (
            <div
              key={a}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-xs transition border ${
                isActive
                  ? "bg-info/10 border-info/30"
                  : isDone
                    ? "bg-success/5 border-success/20"
                    : "bg-muted/40 border-transparent"
              }`}
            >
              <Icon className={`h-4 w-4 ${meta.color} flex-shrink-0`} />
              <span className="flex-1 font-medium text-foreground/90">{meta.label}</span>
              {isActive && <Loader2 className="h-3 w-3 animate-spin text-info" />}
              {!isActive && isDone && <CheckCircle2 className="h-3 w-3 text-success" />}
              {!isActive && !isDone && running && <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatusCards({
  result,
  running,
  events,
}: {
  result: WorkflowResult | null;
  running: boolean;
  events: AgentEvent[];
}) {
  const anyProgress = running || events.length > 0;

  const cards = [
    {
      title: "Appointment",
      icon: Calendar,
      value: result?.appointment_status ?? (anyProgress ? "in_progress" : "—"),
    },
    {
      title: "Lab Test",
      icon: FlaskConical,
      value: result?.lab_test_status ?? (anyProgress ? "in_progress" : "—"),
    },
    {
      title: "Notification",
      icon: Bell,
      value: result?.notification_status ?? (anyProgress ? "in_progress" : "—"),
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {cards.map((c) => {
        const Icon = c.icon;
        const tone = statusTone(c.value);
        return (
          <div key={c.title} className={`rounded-2xl border p-4 bg-surface ${tone.border} transition`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground">{c.title}</span>
              <Icon className={`h-4 w-4 ${tone.icon}`} />
            </div>
            <div className={`text-sm font-semibold ${tone.text} break-words`}>{formatStatus(c.value)}</div>
          </div>
        );
      })}
    </div>
  );
}

function formatStatus(v: string) {
  if (!v || v === "—") return "—";
  return v.replace(/_/g, " ");
}

function statusTone(v: string) {
  if (v.startsWith("confirmed") || v === "sent" || v === "scheduled") {
    return { border: "border-success/30", text: "text-success", icon: "text-success" };
  }
  if (v.startsWith("already_exists")) {
    return { border: "border-warning/30", text: "text-warning-foreground", icon: "text-warning" };
  }
  if (v.startsWith("failed") || v === "check_failed") {
    return { border: "border-destructive/30", text: "text-destructive", icon: "text-destructive" };
  }
  if (v === "in_progress") {
    return { border: "border-info/30", text: "text-info", icon: "text-info" };
  }
  return { border: "border-border", text: "text-muted-foreground", icon: "text-muted-foreground" };
}
