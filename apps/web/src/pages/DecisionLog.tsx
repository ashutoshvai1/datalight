import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import {
  api,
  type Audit,
  type Finding,
  type ModelCall,
  type PageProps,
} from "../api";
import { Badge, Empty, ErrorNotice, FindingCard } from "../components";

export default function DecisionLog({ run, showEvidence }: PageProps) {
  const [offset, setOffset] = useState(0);
  const [category, setCategory] = useState("");
  const [before, setBefore] = useState<number | undefined>();
  const findings = useQuery({
    queryKey: ["findings", run.id, "log", offset, category],
    queryFn: () =>
      api<Finding[]>(
        `/runs/${run.id}/findings?offset=${offset}&limit=50&category=${category}`,
      ),
  });
  const audit = useQuery({
    queryKey: ["audit", run.id, before],
    queryFn: () =>
      api<Audit[]>(
        `/runs/${run.id}/audit?limit=50${before ? `&before=${before}` : ""}`,
      ),
  });
  const calls = useQuery({
    queryKey: ["model-calls", run.id],
    queryFn: () => api<ModelCall[]>(`/runs/${run.id}/model-calls`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">03 / REVIEW</span>
          <h1>Every conclusion has a history.</h1>
          <p>
            Inspect the evidence, question an inference, or record a correction.
          </p>
        </div>
        <Badge>Append-only review history</Badge>
      </div>
      <div className="section-heading">
        <div>
          <h2>Conclusions & human review</h2>
          <p>Original findings remain intact after every review.</p>
        </div>
        <select
          aria-label="Finding category"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All categories</option>
          {["assumption", "quality", "deviation", "interpretation"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>
      <ErrorNotice error={findings.error} />
      {findings.data?.length ? (
        findings.data.map((f) => (
          <FindingCard key={f.id} finding={f} showEvidence={showEvidence} />
        ))
      ) : (
        <Empty title="No conclusions in this view">
          The initial reference and subsequent findings appear here as analysis
          progresses.
        </Empty>
      )}
      <div className="pagination">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous
        </button>
        <span>Page {offset / 50 + 1}</span>
        <button
          disabled={findings.data?.length !== 50}
          onClick={() => setOffset(offset + 50)}
        >
          Next
        </button>
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Model data-flow record</h2>
            <p>
              Inspect exactly which derived summaries were sent, to which
              endpoint, and why.
            </p>
          </div>
          <Sparkles size={18} />
        </div>
        <ErrorNotice error={calls.error} />
        {calls.data?.length ? (
          calls.data.map((call) => (
            <details className="model-call" key={call.id}>
              <summary>
                {call.model} <Badge>{call.status}</Badge>
              </summary>
              <p className="break">{call.endpoint}</p>
              <p>
                Purpose: {call.purpose} ·{" "}
                {new Date(call.started_at).toLocaleString()}
              </p>
              {call.error && <div className="notice amber">{call.error}</div>}
              <h4>Outgoing request (authorization omitted)</h4>
              <pre>{JSON.stringify(call.request, null, 2)}</pre>
              <h4>Response</h4>
              <pre>{JSON.stringify(call.response, null, 2)}</pre>
            </details>
          ))
        ) : (
          <p className="muted">
            No model requests have been made for this run. Statistical analysis
            does not require a model connection.
          </p>
        )}
      </section>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Processing ledger</h2>
            <p>
              Durable events link analysis, replay controls, and human reviews.
            </p>
          </div>
        </div>
        <ErrorNotice error={audit.error} />
        <div className="ledger">
          {audit.data?.map((e) => (
            <details key={e.id}>
              <summary>
                <span className="mono">#{e.id}</span>
                <strong>{e.kind}</strong>
                <time>{new Date(e.created_at).toLocaleTimeString()}</time>
              </summary>
              <pre>{JSON.stringify(e.payload, null, 2)}</pre>
            </details>
          ))}
        </div>
        <div className="pagination">
          <button onClick={() => setBefore(undefined)} disabled={!before}>
            Latest
          </button>
          <button
            disabled={audit.data?.length !== 50}
            onClick={() => setBefore(audit.data?.at(-1)?.id)}
          >
            Older events
          </button>
        </div>
      </section>
    </>
  );
}
