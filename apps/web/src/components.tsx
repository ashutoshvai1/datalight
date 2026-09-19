import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleHelp, FileSearch, PencilLine, X } from "lucide-react";
import { api, type Evidence, type Finding, type Review } from "./api";

export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <div className="notice danger" role="alert">
      {error instanceof Error ? error.message : "Something went wrong."}
    </div>
  ) : null;
}

export function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <FileSearch size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function EvidenceDrawer({
  id,
  close,
}: {
  id: string;
  close: () => void;
}) {
  const query = useQuery({
    queryKey: ["evidence", id],
    queryFn: () => api<Evidence>(`/evidence/${encodeURIComponent(id)}`),
  });
  return (
    <div className="overlay" onClick={close}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Supporting evidence"
        className="drawer"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">TRACEABLE BY DESIGN</span>
            <h2>Supporting evidence</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close evidence"
            onClick={close}
          >
            <X />
          </button>
        </div>
        <p className="muted">
          Computed locally from the indicated analysis window. Human reviews do
          not modify this record.
        </p>
        <ErrorNotice error={query.error} />
        {query.data ? (
          <>
            <Badge>{query.data.kind}</Badge>
            <p className="mono break">{query.data.id}</p>
            <pre>{JSON.stringify(query.data.details, null, 2)}</pre>
          </>
        ) : (
          <p>Loading evidence…</p>
        )}
      </section>
    </div>
  );
}

function ReviewEditor({ finding }: { finding: Finding }) {
  const client = useQueryClient();
  const [action, setAction] = useState<"accept" | "question" | "override">(
    "accept",
  );
  const [operator, setOperator] = useState("");
  const [reason, setReason] = useState("");
  const [replacement, setReplacement] = useState("");
  const history = useQuery({
    queryKey: ["reviews", finding.id],
    queryFn: () => api<Review[]>(`/findings/${finding.id}/reviews`),
  });
  const save = useMutation({
    mutationFn: () =>
      api<Review>(`/findings/${finding.id}/reviews`, {
        action,
        operator,
        reason,
        replacement: action === "override" ? replacement : null,
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["reviews", finding.id] });
      void client.invalidateQueries({ queryKey: ["audit"] });
      setReason("");
      setReplacement("");
    },
  });
  return (
    <div className="review-editor">
      <p className="muted">
        Your review is added to the history. It does not change the original
        evidence, baseline, or thresholds.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="form-row">
          <label>
            Review action
            <select
              value={action}
              onChange={(e) => {
                setAction(e.target.value as typeof action);
                save.reset();
              }}
            >
              <option value="accept">Accept conclusion</option>
              <option value="question">Question conclusion</option>
              <option value="override">Override conclusion</option>
            </select>
          </label>
          <label>
            Your name
            <input
              value={operator}
              required
              maxLength={100}
              onChange={(e) => setOperator(e.target.value)}
              placeholder="Operator name"
            />
          </label>
        </div>
        <label>
          {action === "question" ? "Question / explanation" : "Explanation"}
          <textarea
            required={action !== "accept"}
            value={reason}
            maxLength={4000}
            onChange={(e) => setReason(e.target.value)}
            placeholder={
              action === "accept"
                ? "Optional context for your acceptance"
                : "Explain the question or correction"
            }
          />
        </label>
        {action === "override" && (
          <label>
            Replacement conclusion
            <textarea
              required
              value={replacement}
              maxLength={4000}
              onChange={(e) => setReplacement(e.target.value)}
            />
          </label>
        )}
        <ErrorNotice error={save.error} />
        <div className="form-actions">
          <button className="primary" disabled={save.isPending} type="submit">
            {save.isPending ? "Saving…" : "Save review"}
          </button>
          {save.isSuccess && (
            <span className="success" role="status">
              Review saved
            </span>
          )}
        </div>
      </form>
      <h4>Review history</h4>
      <ErrorNotice error={history.error} />
      {history.data?.length ? (
        history.data.map((review) => (
          <div className="review-record" key={review.id}>
            <Badge tone={review.action === "override" ? "amber" : ""}>
              {review.action}
            </Badge>
            <strong>{review.operator}</strong>
            <time>{new Date(review.created_at).toLocaleString()}</time>
            <p>{review.reason || "Accepted without an additional note."}</p>
            {review.replacement && (
              <blockquote>{review.replacement}</blockquote>
            )}
          </div>
        ))
      ) : (
        <p className="muted">No human reviews yet.</p>
      )}
    </div>
  );
}

export function FindingCard({
  finding,
  showEvidence,
}: {
  finding: Finding;
  showEvidence: (id: string) => void;
}) {
  const [reviewing, setReviewing] = useState(false);
  return (
    <article className={`finding ${finding.category}`}>
      <div className="finding-top">
        <div className="inline">
          <Badge
            tone={
              finding.category === "quality"
                ? "amber"
                : finding.category === "deviation"
                  ? "red"
                  : ""
            }
          >
            {finding.category}
          </Badge>
          <span className="mono">Batch {finding.batch_index}</span>
        </div>
        <time>{new Date(finding.created_at).toLocaleTimeString()}</time>
      </div>
      <h3>{finding.title}</h3>
      <p>{finding.explanation}</p>
      <div className="finding-meta">
        <span>Basis: {finding.confidence}</span>
        {finding.channel_ids.map((id) => (
          <span className="mono" key={id}>
            {id}
          </span>
        ))}
      </div>
      {!!finding.details.assumptions && (
        <p className="muted">
          Assumptions: {(finding.details.assumptions as string[]).join("; ")}
        </p>
      )}
      <div className="finding-actions">
        <div className="evidence-links">
          {finding.evidence_ids.map((id, index) => (
            <button key={id} onClick={() => showEvidence(id)}>
              <FileSearch size={14} />
              Evidence {index + 1}
            </button>
          ))}
        </div>
        <button className="secondary" onClick={() => setReviewing(!reviewing)}>
          {reviewing ? <X size={15} /> : <PencilLine size={15} />}
          {reviewing ? "Close review" : "Review conclusion"}
        </button>
      </div>
      {reviewing && <ReviewEditor finding={finding} />}
    </article>
  );
}

export const reviewIcons = {
  accept: Check,
  question: CircleHelp,
  override: PencilLine,
};

export function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
