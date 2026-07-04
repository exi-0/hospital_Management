import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getAppointments, type Appointment } from "@/lib/hospital-workflow";
import { Calendar, Loader2, AlertCircle, Database } from "lucide-react";

export const Route = createFileRoute("/appointments")({
  component: AppointmentsPage,
});

function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const loadAppointments = () => {
      getAppointments()
        .then((data) => {
          if (active) {
            setAppointments(data);
            setError(null);
          }
        })
        .catch((err) => {
          console.error(err);
          if (active) {
            setError("Could not load appointments from server. Make sure the Python backend is running.");
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    };

    loadAppointments();

    const interval = setInterval(loadAppointments, 3000); // Polling every 3 seconds

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Appointments Ledger</h1>
          <p className="text-sm text-muted-foreground">Monitor booked consultation slots and status in real-time.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-surface border border-border px-3 py-1.5 rounded-lg">
          <Database className="h-3.5 w-3.5 text-primary" />
          SQLite Database
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">Loading appointments...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-6 text-center max-w-xl mx-auto my-12">
          <AlertCircle className="h-10 w-10 text-destructive mx-auto mb-4" />
          <h3 className="font-semibold text-foreground mb-1">Server Connection Error</h3>
          <p className="text-sm text-muted-foreground mb-4">{error}</p>
          <button 
            onClick={() => {
              setLoading(true);
              setError(null);
              getAppointments()
                .then(setAppointments)
                .catch(() => setError("Backend system is offline."))
                .finally(() => setLoading(false));
            }}
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition"
          >
            Retry Connection
          </button>
        </div>
      ) : (
        <div className="rounded-2xl border border-border bg-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-surface-elevated border-b border-border text-xs font-medium text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-4">Appointment ID</th>
                  <th className="px-6 py-4">Patient ID</th>
                  <th className="px-6 py-4">Doctor ID</th>
                  <th className="px-6 py-4">Slot Date & Time</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {appointments.map((a) => (
                  <tr key={a.appointment_id} className="hover:bg-muted/40 transition">
                    <td className="px-6 py-4 font-mono text-xs text-primary font-semibold">{a.appointment_id}</td>
                    <td className="px-6 py-4 font-medium text-foreground">{a.patient_name || a.patient_id}</td>
                    <td className="px-6 py-4 text-foreground">{a.doctor_name || a.doctor_id}</td>
                    <td className="px-6 py-4 text-muted-foreground font-medium">{a.slot}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize border ${
                        a.status === "confirmed" 
                          ? "bg-success/5 border-success/30 text-success" 
                          : "bg-warning/5 border-warning/30 text-warning"
                      }`}>
                        {a.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {appointments.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center text-muted-foreground italic">
                      No appointments registered. Use the Agentic Console to book one.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
