import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getDoctors, type Doctor } from "@/lib/hospital-workflow";
import { Stethoscope, Loader2, AlertCircle, Database, Calendar } from "lucide-react";

export const Route = createFileRoute("/doctors")({
  component: DoctorsPage,
});

function DoctorsPage() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDoctors()
      .then(setDoctors)
      .catch((err) => {
        console.error(err);
        setError("Could not load doctors from server. Make sure the Python backend is running.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Doctors Directory</h1>
          <p className="text-sm text-muted-foreground">View medical specialists, consultation fees, and available slots.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-surface border border-border px-3 py-1.5 rounded-lg">
          <Database className="h-3.5 w-3.5 text-primary" />
          SQLite Database
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">Loading doctors list...</p>
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
              getDoctors()
                .then(setDoctors)
                .catch(() => setError("Backend system is offline."))
                .finally(() => setLoading(false));
            }}
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition"
          >
            Retry Connection
          </button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {doctors.map((d) => (
            <div key={d.doctor_id} className="rounded-2xl border border-border bg-surface p-5 hover:shadow-md transition">
              <div className="flex items-start gap-4">
                <div className="h-12 w-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
                  <Stethoscope className="h-6 w-6" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-base font-semibold text-foreground truncate">{d.name}</h3>
                  <p className="text-xs text-primary font-medium">{d.specialization}</p>
                  <p className="text-xs text-muted-foreground mt-1">{d.hospital}</p>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-muted-foreground block">Experience</span>
                  <span className="font-medium text-foreground">{d.experience} Years</span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Consultation Fee</span>
                  <span className="font-medium text-foreground">${d.fee}</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-border">
                <span className="text-xs font-medium text-muted-foreground mb-2 block flex items-center gap-1">
                  <Calendar className="h-3 w-3" /> Available Slots
                </span>
                <div className="flex flex-wrap gap-1">
                  {d.available_slots.map((s, idx) => (
                    <span key={idx} className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground border border-border">
                      {s.split(" ")[1]} ({s.split(" ")[0].slice(5)})
                    </span>
                  ))}
                  {d.available_slots.length === 0 && (
                    <span className="text-xs text-muted-foreground italic">No slots available</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
