import { useEffect, useState } from "react";
import {
  Navigate,
  NavLink,
  Route,
  Routes,
  useSearchParams,
} from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Database,
  FileText,
  Layers3,
  ListChecks,
  Pause,
  Play,
  RotateCcw,
  Zap,
} from "lucide-react";
import {
  api,
  number,
  type Control,
  type Report,
  type Run,
  type System,
} from "./api";
import { Badge, Empty, ErrorNotice, EvidenceDrawer } from "./components";
import Understanding from "./pages/Understanding";
import Monitoring from "./pages/Monitoring";
import DecisionLog from "./pages/DecisionLog";

export default function App() {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const selectedRun = params.get("run");
  const [evidence, setEvidence] = useState<string | null>(null);
  const [initialRows, setInitialRows] = useState(500);
  const [newAnalysis, setNewAnalysis] = useState(false);
  const system = useQuery({
    queryKey: ["system"],
    queryFn: () => api<System>("/system"),
    refetchInterval: 2000,
  });
  const history = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("/runs"),
    refetchInterval: 5000,
  });
  const archived = useQuery({
    queryKey: ["run", selectedRun],
    queryFn: () => api<Run>(`/runs/${selectedRun}`),
    enabled: !!selectedRun,
    refetchInterval: 2000,
  });
  const run = selectedRun ? archived.data : system.data?.run;
  const report = useQuery({
    queryKey: ["report", run?.id],
    queryFn: () => api<Report>(`/runs/${run?.id}/report`),
    enabled: !!run && run.batch_index > 0,
    refetchInterval: 3000,
  });
  const control = useMutation({
    mutationFn: (action: Control["action"]) =>
      api(`/runs/${run?.id}/control`, { action }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["system"] });
      void client.invalidateQueries({ queryKey: ["run"] });
    },
  });
  const start = useMutation({
    mutationFn: () =>
      api<Run>("/runs", {
        initial_rows: initialRows,
        batch_rows: run?.config.batch_rows ?? 100,
        interval: run?.config.interval ?? 1,
        threshold: run?.config.threshold ?? 6,
      }),
    onSuccess: () => {
      setParams({});
      setNewAnalysis(false);
      void client.invalidateQueries();
    },
  });
  useEffect(() => {
    if (!run?.id) return;
    const stream = new EventSource(`/api/v1/runs/${run.id}/events`);
    let timer: ReturnType<typeof setTimeout> | undefined;
    stream.onmessage = () => {
      if (!timer)
        timer = setTimeout(() => {
          for (const key of [
            "batches",
            "findings",
            "audit",
            "model-calls",
            "report",
          ])
            void client.invalidateQueries({ queryKey: [key, run.id] });
          timer = undefined;
        }, 750);
    };
    return () => {
      stream.close();
      clearTimeout(timer);
    };
  }, [run?.id, client]);
  const active =
    !!run && ["initializing", "running", "paused"].includes(run.status);
  const search = selectedRun ? `?run=${selectedRun}` : "";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          datalight<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">PROCESS INTELLIGENCE</div>
        <nav>
          <NavLink to={`/understanding${search}`}>
            <Layers3 size={18} />
            Understanding
          </NavLink>
          <NavLink to={`/monitoring${search}`}>
            <Activity size={18} />
            Monitoring
          </NavLink>
          <NavLink to={`/log${search}`}>
            <ListChecks size={18} />
            Decision log
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="local-indicator">
            <span /> Local workspace
          </div>
          <p>
            Evidence first.
            <br />
            Human judgment, always.
          </p>
          <span className="version">FOUNDATION · V0.1</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="source">
            <Database size={16} />
            <strong>{system.data?.source?.name ?? "Mounted CSV"}</strong>
            <span className="divider">/</span>
            <span>
              {run
                ? `${number(run.rows_processed, 0)} observations`
                : "Connecting…"}
            </span>
          </div>
          <div className="inline">
            <Badge tone={active ? "green" : ""}>
              <span className={`status-dot ${active ? "live" : ""}`} />
              {run?.status ?? "Starting"}
            </Badge>
            <button
              className="secondary"
              onClick={() => setNewAnalysis(!newAnalysis)}
            >
              <RotateCcw size={14} />
              New analysis
            </button>
          </div>
        </header>
        <main>
          <div className="run-bar">
            <label className="run-selector">
              Analysis
              <select
                aria-label="Select analysis"
                value={selectedRun ?? ""}
                onChange={(e) =>
                  setParams(e.target.value ? { run: e.target.value } : {})
                }
              >
                <option value="">Current analysis</option>
                {history.data
                  ?.filter((r) => r.id !== system.data?.run?.id)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {new Date(r.created_at).toLocaleString()} · {r.status}
                    </option>
                  ))}
              </select>
            </label>
            <div className="playback">
              <span>
                {run?.fast_forward || run?.config.interval === 0
                  ? "Full-speed replay"
                  : `${run?.config.batch_rows ?? 100} rows / ${run?.config.interval ?? 1}s`}
              </span>
              <button
                disabled={!active || control.isPending}
                onClick={() =>
                  control.mutate(run?.status === "paused" ? "resume" : "pause")
                }
              >
                {run?.status === "paused" ? (
                  <Play size={14} />
                ) : (
                  <Pause size={14} />
                )}
                {run?.status === "paused" ? "Resume" : "Pause"}
              </button>
              <button
                className={run?.fast_forward ? "engaged" : ""}
                disabled={!active || control.isPending}
                onClick={() =>
                  control.mutate(
                    run?.fast_forward ? "normal_speed" : "fast_forward",
                  )
                }
              >
                <Zap size={14} />
                {run?.fast_forward ? "Normal speed" : "Fast-forward"}
              </button>
            </div>
          </div>
          {newAnalysis && (
            <form
              className="new-analysis panel"
              onSubmit={(e) => {
                e.preventDefault();
                start.mutate();
              }}
            >
              <div>
                <h3>Start a fresh analysis</h3>
                <p>
                  The active replay stops. Previous reports and reviews remain
                  available.
                </p>
              </div>
              <label>
                Initial observations
                <input
                  aria-label="Initial observations"
                  type="number"
                  min={32}
                  max={10000}
                  required
                  value={initialRows}
                  onChange={(e) => setInitialRows(Number(e.target.value))}
                />
              </label>
              <button
                type="submit"
                className="primary"
                disabled={start.isPending}
              >
                Analyze & monitor <ArrowRight size={15} />
              </button>
            </form>
          )}
          <ErrorNotice
            error={
              system.error ||
              archived.error ||
              report.error ||
              control.error ||
              start.error
            }
          />
          {system.data?.source_error && (
            <div className="notice danger" role="alert">
              {system.data.source_error}
            </div>
          )}
          {run?.error && (
            <div className="notice danger" role="alert">
              {run.error}
            </div>
          )}
          {run ? (
            <Routes>
              <Route
                path="/understanding"
                element={
                  <Understanding
                    key={run.id}
                    run={run}
                    report={report.data}
                    showEvidence={setEvidence}
                  />
                }
              />
              <Route
                path="/monitoring"
                element={
                  <Monitoring
                    key={run.id}
                    run={run}
                    report={report.data}
                    showEvidence={setEvidence}
                  />
                }
              />
              <Route
                path="/log"
                element={
                  <DecisionLog
                    key={run.id}
                    run={run}
                    report={report.data}
                    showEvidence={setEvidence}
                  />
                }
              />
              <Route
                path="*"
                element={<Navigate to={`/understanding${search}`} replace />}
              />
            </Routes>
          ) : (
            <Empty title="Preparing your local workspace">
              The worker will register the mounted CSV and start its initial
              analysis automatically. If this persists, check the source and
              worker status.
            </Empty>
          )}
          <footer>
            <FileText size={13} /> Datalight foundation{" "}
            <span>
              Raw observations stay in your environment. Only derived summaries
              may reach the configured model.
            </span>
          </footer>
        </main>
      </div>
      {evidence && (
        <EvidenceDrawer id={evidence} close={() => setEvidence(null)} />
      )}
    </div>
  );
}
