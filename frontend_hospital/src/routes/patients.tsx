import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getPatients, type Patient } from "@/lib/hospital-workflow";
import { UserRound, Loader2, AlertCircle, Database } from "lucide-react";

export const Route = createFileRoute("/patients")({
  component: PatientsPage,
});

function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPatients()
      .then(setPatients)
      .catch((err) => {
        console.error(err);
        setError("Could not load patients from server. Make sure the Python backend is running.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Patients Directory</h1>
          <p className="text-sm text-muted-foreground">View registered patients in the hospital database.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-surface border border-border px-3 py-1.5 rounded-lg">
          <Database className="h-3.5 w-3.5 text-primary" />
          SQLite Database
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">Loading patients list...</p>
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
              getPatients()
                .then(setPatients)
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
                  <th className="px-6 py-4">ID</th>
                  <th className="px-6 py-4">Name</th>
                  <th className="px-6 py-4">Age / Gender</th>
                  <th className="px-6 py-4">Medical History / Conditions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {patients.map((p) => (
                  <tr key={p.patient_id} className="hover:bg-muted/40 transition">
                    <td className="px-6 py-4 font-mono text-xs text-primary font-semibold">{p.patient_id}</td>
                    <td className="px-6 py-4 font-medium text-foreground">{p.name}</td>
                    <td className="px-6 py-4 text-muted-foreground">
                      {p.age} yrs · <span className="capitalize">{p.gender}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        {p.medical_history.map((h, idx) => (
                          <span key={idx} className="inline-flex items-center rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                            {h}
                          </span>
                        ))}
                        {p.medical_history.length === 0 && (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
