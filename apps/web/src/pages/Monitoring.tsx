import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { api, number, type PageProps } from "../api";
import type { components } from "../generated/api";
import { Badge, Empty, ErrorNotice } from "../components";
import { Chart } from "../Chart";
import DecisionCard, { type BatchDecision } from "../DecisionCard";

export default function Monitoring({ run, report, showEvidence }: PageProps) {
  const client = useQueryClient();
  const [selected, setSelected] = useState("");
  const channel = selected || report?.profiles[0]?.id || "";
  const decisions = useQuery({
    queryKey: ["decisions", run.id, "recent"],
    queryFn: () => api<BatchDecision[]>(`/runs/${run.id}/decisions?limit=5`),
    refetchInterval: 2000,
  });
  const trace = useQuery({
    queryKey: ["trace", run.id, channel],
    queryFn: () =>
      api<components["schemas"]["TraceView"]>(
        `/runs/${run.id}/trace?channel_id=${channel}`,
      ),
    enabled: !!channel,
    refetchInterval: 2000,
  });
  const control = useMutation({
    mutationFn: () =>
      api(`/runs/${run.id}/control`, {
        action: run.status === "running" ? "pause" : "resume",
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["system"] });
      void client.invalidateQueries({ queryKey: ["run"] });
    },
  });
  const names = Object.fromEntries(
    report?.profiles.map((p) => [p.id, p.name]) ?? [],
  );
  const latest = decisions.data?.[0];
  const points: {
    row: number;
    value: number | null;
    forecast: number | null;
  }[] = [];
  let sequence: number | undefined;
  for (const p of trace.data?.points ?? []) {
    if (sequence !== undefined && sequence !== p.sequence)
      points.push({ row: p.row - 0.5, value: null, forecast: null });
    points.push(p);
    sequence = p.sequence;
  }
  const option = {
    tooltip: { trigger: "axis", renderMode: "richText" },
    legend: { bottom: 0 },
    grid: { top: 25, left: 70, right: 25, bottom: 70 },
    xAxis: {
      type: "value",
      name: "Sample row",
      min: points[0]?.row,
      max: points.at(-1)?.row,
    },
    yAxis: { type: "value", scale: true },
    series: [
      {
        name: names[channel] ?? "Observed",
        type: "line",
        showSymbol: false,
        data: points.map((p) => [p.row, p.value]),
        lineStyle: { width: 2, color: "#247567" },
        markArea: {
          silent: true,
          itemStyle: { color: "rgba(196, 132, 58, 0.12)" },
          data:
            trace.data?.flagged.map((t) => [
              { xAxis: t.row_start },
              { xAxis: t.row_end },
            ]) ?? [],
        },
      },
      {
        name: "5-step-ahead forecast",
        type: "line",
        showSymbol: false,
        data: points.map((p) => [p.row, p.forecast]),
        lineStyle: { width: 1.5, type: "dashed", color: "#9a794b" },
      },
    ],
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">02 / MONITOR</span>
          <h1>Monitoring</h1>
          <p>
            {number(run.rows_processed, 0)} samples read ·{" "}
            {run.config.batch_rows} per batch · {run.config.interval}s interval
          </p>
        </div>
        <div className="review-actions">
          <Badge>{run.status}</Badge>
          <button
            className="primary"
            disabled={
              !report ||
              !["paused", "running"].includes(run.status) ||
              control.isPending
            }
            onClick={() => control.mutate()}
          >
            {run.status === "running" ? (
              <Pause size={16} />
            ) : (
              <Play size={16} />
            )}
            {run.status === "running" ? "Pause" : "Play"}
          </button>
        </div>
      </div>
      <ErrorNotice error={control.error || trace.error || decisions.error} />
      <section className="panel status-panel">
        <span className="eyebrow">LATEST AUTOMATED DECISION</span>
        <h2
          className={`process-status ${latest?.decision.status === "Fault Suspected" ? "warning-text" : ""}`}
        >
          {latest?.decision.status ?? "Waiting for first batch"}
        </h2>
        <p>
          {latest
            ? latest.decision.explanation
            : "Press Play to begin reading the remaining samples."}
        </p>
        {latest && (
          <>
            <p>
              {latest.decision.coverage.assessed}/
              {latest.decision.coverage.total} channels assessed
            </p>
            {latest.decision.coverage.limited && (
              <div className="notice amber">
                {latest.decision.coverage.message}
              </div>
            )}
            <Badge
              tone={latest.decision.quality_warnings.length ? "amber" : "green"}
            >
              {latest.decision.quality_warnings.length
                ? `Quality warnings: ${latest.decision.quality_warnings.length}`
                : "Data quality checks passed"}
            </Badge>
            {latest.human_assessment && (
              <p>
                Human assessment: <strong>{latest.effective_status}</strong> ·{" "}
                {latest.human_assessment}
              </p>
            )}
          </>
        )}
      </section>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Incoming data</h2>
            <p>
              Latest 1,000 samples · shaded intervals indicate detected changes.
            </p>
          </div>
          <select
            aria-label="Trend channel"
            value={channel}
            onChange={(e) => setSelected(e.target.value)}
          >
            {report?.profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <Chart option={option} label="Incoming channel values and forecast" />
      </section>
      <h2 className="section-title">Recent decisions</h2>
      {latest ? (
        decisions.data?.map((item) => (
          <DecisionCard
            key={item.id}
            item={item}
            names={names}
            showEvidence={showEvidence}
          />
        ))
      ) : (
        <Empty title="No monitoring decisions yet">
          The initial report is ready independently of playback.
        </Empty>
      )}
    </>
  );
}
