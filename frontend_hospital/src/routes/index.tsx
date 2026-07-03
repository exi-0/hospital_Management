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
} from "lucide-react";
import {
  runWorkflow,
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

function HospitalConsole() {
  const [patientId, setPatientId] = useState("P002");
  const [query, setQuery] = useState(SAMPLE_QUERIES[0].query);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [events]);

  async function handleRun() {
    setRunning(true);
    setEvents([]);
    setResult(null);
    try {
      const r = await runWorkflow(patientId.trim(), query.trim(), (ev) => {
        setEvents((prev) => [...prev, ev]);
      });
      setResult(r);
    } finally {
      setRunning(false);
    }
  }

  function loadSample(i: number) {
    const s = SAMPLE_QUERIES[i];
    setPatientId(s.patient);
    setQuery(s.query);
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-surface/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <Workflow className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight">Agentic Hospital Console</h1>
              <p className="text-xs text-muted-foreground">LangGraph · LangChain · Gemini · multi-agent orchestration</p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex h-2 w-2 rounded-full bg-success animate-pulse-ring" />
            Agents online
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8 grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* LEFT — request composer */}
        <section className="space-y-6">
          <div className="rounded-2xl border border-border bg-surface p-5 agent-glow">
            <h2 className="text-sm font-semibold tracking-tight mb-4 flex items-center gap-2">
              <Play className="h-4 w-4 text-primary" /> New patient request
            </h2>

            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Patient ID</label>
            <div className="relative mb-4">
              <select
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                className="w-full appearance-none rounded-lg border border-input bg-background px-3 py-2 pr-9 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {SAMPLE_PATIENTS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id} — {p.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            </div>

            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Natural-language request</label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
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
          <StatusCards result={result} running={running} events={events} />

          <div className="rounded-2xl border border-border bg-surface overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-elevated">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold tracking-tight">Agent communication log</h3>
              </div>
              <span className="text-xs text-muted-foreground">{events.length} events</span>
            </div>

            <div ref={logRef} className="max-h-[540px] overflow-y-auto p-4 space-y-2 font-mono text-xs">
              {events.length === 0 && !running && (
                <div className="text-center py-16 text-muted-foreground">
                  <Workflow className="h-8 w-8 mx-auto mb-3 opacity-40" />
                  <p className="text-sm font-sans">Run a request to see the agents coordinate live.</p>
                </div>
              )}
              {events.map((ev) => (
                <EventRow key={ev.id} ev={ev} />
              ))}
            </div>
          </div>

          {result && (
            <div className="rounded-2xl border border-border bg-gradient-to-br from-primary/5 via-surface to-surface p-5">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold tracking-tight">Patient summary</h3>
              </div>
              <p className="text-sm leading-relaxed text-foreground/90">{result.summary}</p>
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-border mt-12">
        <div className="mx-auto max-w-7xl px-6 py-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-2">
          <span>Frontend for the Agentic Hospital Management System (LangGraph + Gemini)</span>
          <span>UI simulates backend responses — wire <code className="font-mono text-foreground/70">runWorkflow</code> to your Python API to go live.</span>
        </div>
      </footer>
    </div>
  );
}

function EventRow({ ev }: { ev: AgentEvent }) {
  const meta = AGENT_META[ev.agent];
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

  return (
    <div className={`rounded-lg border ${statusStyles} px-3 py-2 flex gap-3 items-start`}>
      <div className={`mt-0.5 ${meta.color}`}>
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
        <p className="font-sans text-xs text-foreground/85 leading-relaxed break-words">{ev.message}</p>
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
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-xs transition ${
                isActive
                  ? "bg-info/10 border border-info/30"
                  : isDone
                    ? "bg-success/5 border border-success/20"
                    : "bg-muted/40 border border-transparent"
              }`}
            >
              <Icon className={`h-4 w-4 ${meta.color}`} />
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
          <div key={c.title} className={`rounded-2xl border p-4 bg-surface ${tone.border}`}>
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
