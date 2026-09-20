import { useState } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { components } from "./generated/api";
import { api, number, type Review } from "./api";
import { Badge, ErrorNotice, EvidenceLinks } from "./components";
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
  const [reason, setReason] = useState("");
  const [question, setQuestion] = useState("");
  const [replacement, setReplacement] = useState("OK");
  const [open, setOpen] = useState(false);
  const reviews = useInfiniteQuery({
    queryKey: ["reviews", item.id],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<Review[]>(
        `/findings/${item.id}/reviews?limit=100&offset=${pageParam}`,
      ),
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === 100 ? allPages.length * 100 : undefined,
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
    mutationFn: (reviewAction: "accept" | "question" | "override") =>
      api(`/findings/${item.id}/reviews`, {
        action: reviewAction,
        reason:
          reviewAction === "question"
            ? question
            : reviewAction === "override"
              ? reason
              : "",
        replacement: reviewAction === "override" ? replacement : null,
      }),
    onSuccess: (_, reviewAction) => {
      setAction(null);
      if (reviewAction === "question") setQuestion("");
      else setReason("");
      setOpen(true);
      void client.invalidateQueries({ queryKey: ["reviews", item.id] });
      void client.invalidateQueries({ queryKey: ["answers", item.id] });
      void client.invalidateQueries({ queryKey: ["decisions"] });
    },
  });
  const history = reviews.data?.pages.flat() ?? [];
  const d = item.decision;
  const pendingQuestion =
    history.some(
      (review) =>
        review.action === "question" &&
        !answers.data?.some((answer) => answer.review_id === review.id),
    ) ||
    answers.data?.some((answer) =>
      ["pending", "queued", "running"].includes(answer.status),
    );
  const ruleMatches = d.rule_matches ?? [];
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
      {ruleMatches.length > 0 && (
        <details open>
          <summary>Custom monitoring rules ({ruleMatches.length})</summary>
          {ruleMatches.map((match, index) => (
            <div className="quality-row" key={`${match.rule_id}:${index}`}>
              <strong>{names[match.channel_id] ?? match.channel_id}</strong>
              <Badge tone="amber">
                {match.effect === "fault"
                  ? "Fault Suspected"
                  : "Quality warning"}
              </Badge>
              <p>
                {match.violation_count} matching observations · samples{" "}
                {match.row_start}–{match.row_end}
              </p>
              <EvidenceLinks
                ids={match.evidence_ids}
                showEvidence={showEvidence}
              />
            </div>
          ))}
        </details>
      )}
      <div className="review-actions">
        {(["accept", "question", "override"] as const).map((a) => (
          <button
            key={a}
            onClick={() => {
              setAction(a);
              if (a === "question") setOpen(true);
              setReplacement(d.status === "OK" ? "Fault Suspected" : "OK");
            }}
          >
            {a.charAt(0).toUpperCase() + a.slice(1)}
          </button>
        ))}
      </div>
      {action && action !== "question" && (
        <form
          className="review-form"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(action);
          }}
        >
          {action !== "accept" && (
            <label>
              Override reason
              <textarea
                required
                maxLength={4000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
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
              {save.isPending ? "Saving…" : "Save review"}
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
        {reviews.hasNextPage && (
          <button
            type="button"
            disabled={reviews.isFetchingNextPage}
            onClick={() => void reviews.fetchNextPage()}
          >
            Load earlier reviews
          </button>
        )}
        {history.length ? (
          [...history]
            .sort(
              (a, b) =>
                a.created_at.localeCompare(b.created_at) ||
                a.id.localeCompare(b.id),
            )
            .map((r) => {
              const answer = answers.data?.find((a) => a.review_id === r.id);
              return (
                <div className="review-history" key={r.id}>
                  <strong>
                    {r.action === "question"
                      ? "You asked"
                      : r.action === "accept"
                        ? "Accepted"
                        : "Overridden"}
                  </strong>
                  <time>{new Date(r.created_at).toLocaleString()}</time>
                  {r.replacement && <p>Human assessment: {r.replacement}</p>}
                  {r.reason && <p>{r.reason}</p>}
                  {r.action === "question" && (
                    <div className="answer">
                      <Badge>{answer?.status ?? "pending"}</Badge>
                      <p>
                        {answer
                          ? display(answer.text)
                          : "Waiting for an answer…"}
                      </p>
                      <EvidenceLinks
                        ids={answer?.evidence_ids ?? []}
                        showEvidence={showEvidence}
                      />
                    </div>
                  )}
                </div>
              );
            })
        ) : (
          <p>No reviews yet.</p>
        )}
        <form
          className="review-form conversation-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!pendingQuestion && question.trim()) save.mutate("question");
          }}
        >
          <label>
            {history.some((review) => review.action === "question")
              ? "Continue the conversation"
              : "Your question"}
            <textarea
              required
              maxLength={4000}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about this decision or its evidence…"
              disabled={!!pendingQuestion}
            />
          </label>
          <p className="muted">
            Computed summaries and your conversation go to the configured model.
            Keep raw data and secrets out of questions.
          </p>
          <div className="review-actions">
            <button
              className="primary"
              disabled={
                save.isPending ||
                !!pendingQuestion ||
                reviews.isLoading ||
                answers.isLoading ||
                !question.trim()
              }
            >
              {pendingQuestion
                ? "Waiting for an answer…"
                : save.isPending
                  ? "Sending…"
                  : "Ask question"}
            </button>
          </div>
          <ErrorNotice error={save.error} />
        </form>
      </details>
    </section>
  );
}
