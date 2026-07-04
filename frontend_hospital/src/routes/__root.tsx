import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { Workflow, UserRound, Stethoscope, Calendar, FlaskConical } from "lucide-react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Agentic Hospital Management System" },
      { name: "description", content: "Agentic Hospital Management System using LangGraph and SQLite" },
      { name: "author", content: "Antigravity Agent" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-background flex flex-col font-sans">
        {/* Navigation Header */}
        <header className="border-b border-border bg-surface/60 backdrop-blur-sm sticky top-0 z-50">
          <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
            <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition">
              <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                <Workflow className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-base font-semibold tracking-tight text-foreground">Agentic HIS</h1>
                <p className="text-xs text-muted-foreground">LangGraph · Gemini · SQLite</p>
              </div>
            </Link>

            <nav className="hidden md:flex items-center gap-1">
              <Link
                to="/"
                activeProps={{ className: "bg-primary/10 text-primary font-medium" }}
                inactiveProps={{ className: "text-muted-foreground hover:text-foreground hover:bg-accent" }}
                className="px-3.5 py-2 text-sm rounded-lg transition"
              >
                Console
              </Link>
              <Link
                to="/patients"
                activeProps={{ className: "bg-primary/10 text-primary font-medium" }}
                inactiveProps={{ className: "text-muted-foreground hover:text-foreground hover:bg-accent" }}
                className="px-3.5 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
              >
                <UserRound className="h-4 w-4" /> Patients
              </Link>
              <Link
                to="/doctors"
                activeProps={{ className: "bg-primary/10 text-primary font-medium" }}
                inactiveProps={{ className: "text-muted-foreground hover:text-foreground hover:bg-accent" }}
                className="px-3.5 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
              >
                <Stethoscope className="h-4 w-4" /> Doctors
              </Link>
              <Link
                to="/appointments"
                activeProps={{ className: "bg-primary/10 text-primary font-medium" }}
                inactiveProps={{ className: "text-muted-foreground hover:text-foreground hover:bg-accent" }}
                className="px-3.5 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
              >
                <Calendar className="h-4 w-4" /> Appointments
              </Link>
              <Link
                to="/lab-reports"
                activeProps={{ className: "bg-primary/10 text-primary font-medium" }}
                inactiveProps={{ className: "text-muted-foreground hover:text-foreground hover:bg-accent" }}
                className="px-3.5 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
              >
                <FlaskConical className="h-4 w-4" /> Lab Reports
              </Link>
            </nav>

            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex h-2 w-2 rounded-full bg-success animate-pulse-ring" />
              Connected
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1">
          <Outlet />
        </main>

        {/* Global Footer */}
        <footer className="border-t border-border mt-12 bg-surface/30">
          <div className="mx-auto max-w-7xl px-6 py-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-2">
            <span>Agentic Hospital Information System (LangGraph + Gemini + SQLite)</span>
            <span>Persistent Database & Admin Dashboard</span>
          </div>
        </footer>
      </div>
    </QueryClientProvider>
  );
}

