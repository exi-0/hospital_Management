import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getLabReports, type LabReport } from "@/lib/hospital-workflow";
import { FlaskConical, Loader2, AlertCircle, Database } from "lucide-react";

export const Route = createFileRoute("/lab-reports")({
  component: LabReportsPage,
});

function LabReportsPage() {
  const [reports, setReports] = useState<LabReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLabReports()
      .then(setReports)
      .catch((err) => {
        console.error(err);
        setError("Could not load lab reports from server. Make sure the Python backend is running.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Lab Reports Log</h1>
          <p className="text-sm text-muted-foreground">Check status of diagnostic reports and laboratory orders.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-surface border border-border px-3 py-1.5 rounded-lg">
          <Database className="h-3.5 w-3.5 text-primary" />
          SQLite Database
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">Loading lab reports...</p>
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
              getLabReports()
                .then(setReports)
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
                  <th className="px-6 py-4">Lab Order ID</th>
                  <th className="px-6 py-4">Patient ID</th>
                  <th className="px-6 py-4">Test Name</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {reports.map((r) => (
                  <tr key={r.lab_order_id} className="hover:bg-muted/40 transition">
                    <td className="px-6 py-4 font-mono text-xs text-primary font-semibold">{r.lab_order_id}</td>
                    <td className="px-6 py-4 font-medium text-foreground">{r.patient_name || r.patient_id}</td>
                    <td className="px-6 py-4 text-foreground font-medium">{r.test_name}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize border ${
                        r.status === "Completed" || r.status === "completed"
                          ? "bg-success/5 border-success/30 text-success" 
                          : "bg-warning/5 border-warning/30 text-warning"
                      }`}>
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {reports.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-muted-foreground italic">
                      No lab reports on file. Use the Agentic Console to request one.
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
