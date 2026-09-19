import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./generated/api";
import { api, number, type Review } from "./api";
import { Badge, ErrorNotice } from "./components";
export type BatchDecision = components["schemas"]["DecisionView"];
type Answer = components["schemas"]["AnswerView"];

export default function DecisionCard({
  item,
  names,
  showEvidence,
}: {
  item: BatchDecision;
  names: Record<string, string>;
  showEvidence: (id: string) => void;
}) {
  const client = useQueryClient();
  const [action, setAction] = useState<
    "accept" | "question" | "override" | null
  >(null);
  const [operator, setOperator] = useState(
    () => localStorage.getItem("datalight-operator") ?? "",
  );
  const [reason, setReason] = useState("");
  const [replacement, setReplacement] = useState("OK");
  const [open, setOpen] = useState(false);
  const reviews = useQuery({
    queryKey: ["reviews", item.id],
    queryFn: () => api<Review[]>(`/findings/${item.id}/reviews`),
    enabled: open || !!action,
    refetchInterval: open ? 3000 : false,
  });
  const answers = useQuery({
    queryKey: ["answers", item.id],
    queryFn: () => api<Answer[]>(`/findings/${item.id}/answers`),
    enabled: open || !!action,
    refetchInterval: open ? 3000 : false,
  });
  const save = useMutation({
    mutationFn: () =>
      api(`/findings/${item.id}/reviews`, {
        action,
        operator,
        reason,
        replacement: action === "override" ? replacement : null,
      }),
    onSuccess: () => {
      localStorage.setItem("datalight-operator", operator);
      setAction(null);
      setReason("");
      setOpen(true);
      void client.invalidateQueries({ queryKey: ["reviews", item.id] });
      void client.invalidateQueries({ queryKey: ["answers", item.id] });
      void client.invalidateQueries({ queryKey: ["decisions"] });
    },
  });
  const d = item.decision;
  const display = (text: string) =>
    text.replace(/\bc\d{3}\b/g, (id) => names[id] ?? id);
  return (
    <section className="panel decision-card">
      <div className="section-heading">
        <h3>
          Samples {d.row_start}–{d.row_end}
        </h3>
        <Badge tone={d.status === "OK" ? "green" : "amber"}>{d.status}</Badge>
      </div>
      <p className="explanation">{d.explanation}</p>
      {item.human_assessment && (
        <p className="human-assessment">
          <strong>Human assessment: {item.effective_status}</strong> ·{" "}
          {item.human_assessment}
        </p>
      )}
      {d.coverage.limited && (
        <div className="notice amber">
          {d.coverage.message} · {d.coverage.assessed}/{d.coverage.total}{" "}
          channels assessed
        </div>
      )}
      {d.quality_warnings.length > 0 && (
        <details>
          <summary>Data quality warnings ({d.quality_warnings.length})</summary>
          {d.quality_warnings.map((q, i) => (
            <p key={i}>{display(q)}</p>
          ))}
        </details>
      )}
      <details>
        <summary>
          Evidence metrics ({d.triggers.length} change intervals)
        </summary>
        {d.triggers.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Channel / rule</th>
                  <th>Value</th>
                  <th>Reference</th>
                  <th>Scale</th>
                  <th>Score / threshold</th>
                  <th>Samples</th>
                </tr>
              </thead>
              <tbody>
                {d.triggers.map((t, i) => (
                  <tr key={i}>
                    <td>
                      <button
                        className="text-button"
                        onClick={() =>
                          t.evidence_ids?.[0] && showEvidence(t.evidence_ids[0])
                        }
                      >
                        {names[t.channel_id] ?? t.channel_id} · {t.kind}
                      </button>
                    </td>
                    <td>{number(t.value, 6)}</td>
                    <td>{number(t.reference, 6)}</td>
                    <td>{number(t.scale, 6)}</td>
                    <td>
                      {number(t.score)} / {t.threshold}
                    </td>
                    <td>
                      {t.row_start}–{t.row_end}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>
            No process-change threshold exceeded. {d.coverage.assessed}/
            {d.coverage.total} channels assessed.
          </p>
        )}
        {Object.keys(d.forecast_errors ?? {}).length > 0 && (
          <>
            <h4>Forecast error in this batch</h4>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Channel</th>
                    <th>Mean absolute error</th>
                    <th>Scored predictions</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(d.forecast_errors ?? {}).map(
                    ([id, metric]) => (
                      <tr key={id}>
                        <td>{names[id] ?? id}</td>
                        <td>{number(metric.mae)}</td>
                        <td>{metric.forecast_errors}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </details>
      <div className="review-actions">
        {(["accept", "question", "override"] as const).map((a) => (
          <button
            key={a}
            onClick={() => {
              setOperator(
                localStorage.getItem("datalight-operator") ?? operator,
              );
              setAction(a);
              setReplacement(d.status === "OK" ? "Fault Suspected" : "OK");
            }}
          >
            {a.charAt(0).toUpperCase() + a.slice(1)}
          </button>
        ))}
      </div>
      {action && (
        <form
          className="review-form"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <label>
            Your name
            <input
              required
              maxLength={100}
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
            />
          </label>
          {action !== "accept" && (
            <label>
              {action === "question" ? "Your question" : "Override reason"}
              <textarea
                required
                maxLength={4000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
          )}
          {action === "question" && (
            <p>
              Your question and computed summaries go to the configured LLM. Do
              not paste raw data or secrets.
            </p>
          )}
          {action === "override" && (
            <label>
              Human assessment
              <select
                aria-label="Human assessment"
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
              >
                <option>OK</option>
                <option>Fault Suspected</option>
              </select>
            </label>
          )}
          <div className="review-actions">
            <button className="primary" disabled={save.isPending}>
              {save.isPending
                ? "Saving…"
                : action === "question"
                  ? "Ask question"
                  : "Save review"}
            </button>
            <button type="button" onClick={() => setAction(null)}>
              Cancel
            </button>
          </div>
          <ErrorNotice error={save.error} />
        </form>
      )}
      <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary>Review history & questions</summary>
        <ErrorNotice error={reviews.error || answers.error} />
        {reviews.data?.length ? (
          reviews.data.map((r) => {
            const answer = answers.data?.find((a) => a.review_id === r.id);
            return (
              <div className="review-history" key={r.id}>
                <strong>
                  {r.operator} · {r.action}
                </strong>
                <time>{new Date(r.created_at).toLocaleString()}</time>
                {r.replacement && <p>Human assessment: {r.replacement}</p>}
                {r.reason && <p>{r.reason}</p>}
                {r.action === "question" && (
                  <div className="answer">
                    <Badge>{answer?.status ?? "pending"}</Badge>
                    <p>
                      {answer ? display(answer.text) : "Waiting for an answer…"}
                    </p>
                    {answer?.evidence_ids.map((id) => (
                      <button
                        className="text-button"
                        key={id}
                        onClick={() => showEvidence(id)}
                      >
                        Evidence
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <p>No reviews yet.</p>
        )}
      </details>
    </section>
  );
}
