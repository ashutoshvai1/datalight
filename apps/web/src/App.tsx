import { useState } from "react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, FileText, ListChecks, Plus } from "lucide-react";
import { api, type Report, type Run, type System } from "./api";
import type { components } from "./generated/api";
import { ErrorNotice, EvidenceDrawer } from "./components";
import Understanding from "./pages/Understanding";
import Monitoring from "./pages/Monitoring";
import DecisionLog from "./pages/DecisionLog";

type Choice = components["schemas"]["SourceChoice"];
type Preview = components["schemas"]["SourcePreview"];

function Setup({ done }: { done: (run: Run) => void }) {
  const [path, setPath] = useState<string | null>(null);
  const [initial, setInitial] = useState(500);
  const [batch, setBatch] = useState(100);
  const [interval, setInterval] = useState(10);
  const [limits, setLimits] = useState<
    Record<string, { minimum: string; maximum: string }>
  >({});
  const choices = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Choice[]>("/sources"),
  });
  const selectedPath = path ?? choices.data?.[0]?.path ?? "";
  const preview = useQuery({
    queryKey: ["preview", selectedPath],
    queryFn: () =>
      api<Preview>(`/sources/preview?path=${encodeURIComponent(selectedPath)}`),
    enabled: !!selectedPath,
  });
  const start = useMutation({
    mutationFn: () =>
      api<Run>("/runs", {
        path: selectedPath,
        initial_rows: initial,
        batch_rows: batch,
        interval,
        limits: Object.fromEntries(
          Object.entries(limits)
            .filter(([, v]) => v.minimum !== "" || v.maximum !== "")
            .map(([key, v]) => [
              key,
              {
                minimum: v.minimum === "" ? null : Number(v.minimum),
                maximum: v.maximum === "" ? null : Number(v.maximum),
              },
            ]),
        ),
      }),
    onSuccess: done,
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">START AN ANALYSIS</span>
          <h1>Understand first. Monitor next.</h1>
          <p>Choose a local CSV and set the pace of your demo.</p>
        </div>
      </div>
      <form
        className="panel setup-form"
        onSubmit={(e) => {
          e.preventDefault();
          start.mutate();
        }}
      >
        <label>
          CSV path
          <input
            list="demo-sources"
            value={selectedPath}
            onChange={(e) => {
              setPath(e.target.value);
              setLimits({});
            }}
            required
            placeholder="demo_abrupt.csv"
          />
        </label>
        <datalist id="demo-sources">
          {choices.data?.map((c) => (
            <option key={c.path} value={c.path}>
              {c.name}
            </option>
          ))}
        </datalist>
        <div className="demo-choices">
          {choices.data?.map((c) => (
            <button
              type="button"
              className={selectedPath === c.path ? "primary" : ""}
              key={c.path}
              onClick={() => {
                setPath(c.path);
                setLimits({});
              }}
            >
              {c.name}
            </button>
          ))}
        </div>
        <p>
          Paths are relative to the mounted data directory. Raw observations
          stay local.
        </p>
        <div className="setup-grid">
          <label>
            Initial samples
            <input
              type="number"
              min={32}
              max={10000}
              value={initial}
              onChange={(e) => setInitial(Number(e.target.value))}
              required
            />
          </label>
          <label>
            Samples per batch
            <input
              type="number"
              min={1}
              max={10000}
              value={batch}
              onChange={(e) => setBatch(Number(e.target.value))}
              required
            />
          </label>
          <label>
            Seconds between batches
            <input
              type="number"
              min={0}
              max={3600}
              step="0.1"
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
              required
            />
          </label>
        </div>
        <details>
          <summary>Optional channel limits</summary>
          <p>
            Leave blank when limits are unknown. Observed ranges are not
            physical limits.
          </p>
          <div className="table-scroll limits-table">
            <table>
              <thead>
                <tr>
                  <th>Channel</th>
                  <th>Minimum</th>
                  <th>Maximum</th>
                </tr>
              </thead>
              <tbody>
                {preview.data?.channels.map((name) => (
                  <tr key={name}>
                    <td>{name}</td>
                    {(["minimum", "maximum"] as const).map((bound) => (
                      <td key={bound}>
                        <input
                          aria-label={`${name} ${bound}`}
                          type="number"
                          step="any"
                          value={limits[name]?.[bound] ?? ""}
                          placeholder="Not configured"
                          onChange={(e) =>
                            setLimits({
                              ...limits,
                              [name]: {
                                ...(limits[name] ?? {
                                  minimum: "",
                                  maximum: "",
                                }),
                                [bound]: e.target.value,
                              },
                            })
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        <ErrorNotice error={choices.error || preview.error || start.error} />
        <button
          className="primary"
          disabled={start.isPending || !preview.data || preview.isFetching}
        >
          {" "}
          {start.isPending ? "Starting…" : "Build understanding report"}
        </button>
        <p>Monitoring starts only when you press Play.</p>
      </form>
    </>
  );
}

export default function App() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [setup, setSetup] = useState(false);
  const [evidence, setEvidence] = useState<string | null>(null);
  const selectedRun = params.get("run");
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
  const search = selectedRun ? `?run=${selectedRun}` : "";
  const showingSetup =
    setup ||
    (!run && !!system.data) ||
    (!selectedRun && !!run && run.config.analysis_version !== "monitor-v2");
  const done = (created: Run) => {
    client.setQueryData<System>(["system"], (previous) =>
      previous ? { ...previous, run: created } : previous,
    );
    setSetup(false);
    setParams({});
    void client.invalidateQueries();
    navigate("/understanding");
  };
  const pageProps = run
    ? { run, report: report.data, showEvidence: setEvidence }
    : undefined;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          datalight<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">DATA UNDERSTANDING & MONITORING</div>
        <nav>
          <NavLink
            to={`/understanding${search}`}
            onClick={() => setSetup(false)}
          >
            <FileText size={18} />
            Understanding
          </NavLink>
          <NavLink to={`/monitoring${search}`} onClick={() => setSetup(false)}>
            <Activity size={18} />
            Monitoring
          </NavLink>
          <NavLink to={`/log${search}`} onClick={() => setSetup(false)}>
            <ListChecks size={18} />
            Decision log
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <span className="local-indicator">Local workspace</span>
          <p>Evidence first. Human judgment stays in the loop.</p>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            {showingSetup
              ? "New analysis"
              : selectedRun
                ? "Historical analysis"
                : (run?.config.path ??
                  system.data?.source?.name ??
                  "Datalight")}
          </span>
          <div className="top-actions">
            <select
              aria-label="Analysis history"
              value={selectedRun ?? system.data?.run?.id ?? ""}
              onChange={(e) => {
                setParams({ run: e.target.value });
                setSetup(false);
              }}
            >
              {history.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {new Date(r.created_at).toLocaleString()} · {r.status}
                </option>
              ))}
            </select>
            <button onClick={() => setSetup(true)}>
              <Plus size={16} />
              New analysis
            </button>
          </div>
        </header>
        <main>
          <ErrorNotice
            error={
              system.error ||
              archived.error ||
              report.error ||
              (run?.error ? new Error(run.error) : null)
            }
          />
          {showingSetup ? (
            <Setup done={done} />
          ) : pageProps ? (
            <Routes>
              <Route
                path="/understanding"
                element={
                  <Understanding key={pageProps.run.id} {...pageProps} />
                }
              />
              <Route
                path="/monitoring"
                element={<Monitoring key={pageProps.run.id} {...pageProps} />}
              />
              <Route
                path="/log"
                element={<DecisionLog key={pageProps.run.id} {...pageProps} />}
              />
              <Route
                path="*"
                element={<Navigate to={`/understanding${search}`} replace />}
              />
            </Routes>
          ) : (
            <p>Loading…</p>
          )}
        </main>
      </div>
      {evidence && (
        <EvidenceDrawer id={evidence} close={() => setEvidence(null)} />
      )}
    </div>
  );
}
