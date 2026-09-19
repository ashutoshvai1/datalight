import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Finding, type Review, type PageProps } from "../api";
import { Empty, ErrorNotice } from "../components";
import DecisionCard, { type BatchDecision } from "../DecisionCard";

function HistoricalFinding({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  const reviews = useQuery({
    queryKey: ["reviews", finding.id],
    queryFn: () => api<Review[]>(`/findings/${finding.id}/reviews`),
    enabled: open,
  });
  return (
    <section className="panel">
      <h3>{finding.title}</h3>
      <p>{finding.explanation}</p>
      <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary>Original review history</summary>
        <ErrorNotice error={reviews.error} />
        {reviews.data?.length ? (
          reviews.data.map((r) => (
            <div className="review-history" key={r.id}>
              <strong>
                {r.operator} · {r.action}
              </strong>
              <time>{new Date(r.created_at).toLocaleString()}</time>
              <p>{r.reason}</p>
              {r.replacement && <p>Human assessment: {r.replacement}</p>}
            </div>
          ))
        ) : (
          <p>No reviews recorded.</p>
        )}
      </details>
    </section>
  );
}

export default function DecisionLog({ run, report, showEvidence }: PageProps) {
  const [offset, setOffset] = useState(0);
  const legacy = run.config.analysis_version !== "monitor-v2";
  const oldFindings = useQuery({
    queryKey: ["historical-findings", run.id, offset],
    queryFn: () =>
      api<Finding[]>(`/runs/${run.id}/findings?offset=${offset}&limit=20`),
    enabled: legacy,
  });
  const query = useQuery({
    queryKey: ["decisions", run.id, offset],
    queryFn: () =>
      api<BatchDecision[]>(
        `/runs/${run.id}/decisions?offset=${offset}&limit=20`,
      ),
    refetchInterval: 3000,
    enabled: !legacy,
  });
  const names = Object.fromEntries(
    report?.profiles.map((p) => [p.id, p.name]) ?? [],
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">03 / REVIEW</span>
          <h1>Decision log</h1>
          <p>
            Automated decisions, supporting evidence, and your review history.
          </p>
        </div>
      </div>
      <ErrorNotice error={query.error || oldFindings.error} />
      {legacy && (
        <>
          <p>
            Historical findings and reviews are read-only. Start a new analysis
            for batch decisions.
          </p>
          {oldFindings.data?.map((finding) => (
            <HistoricalFinding key={finding.id} finding={finding} />
          ))}
        </>
      )}
      {!legacy &&
        (query.data?.length ? (
          query.data.map((item) => (
            <DecisionCard
              key={item.id}
              item={item}
              names={names}
              showEvidence={showEvidence}
            />
          ))
        ) : (
          <Empty title="No batch decisions">
            New monitoring decisions appear here. Historical reports remain
            available in Understanding.
          </Empty>
        ))}
      <div className="pagination">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Previous
        </button>
        <span>Page {offset / 20 + 1}</span>
        <button
          disabled={
            (legacy ? oldFindings.data?.length : query.data?.length) !== 20
          }
          onClick={() => setOffset(offset + 20)}
        >
          Next
        </button>
      </div>
    </>
  );
}
