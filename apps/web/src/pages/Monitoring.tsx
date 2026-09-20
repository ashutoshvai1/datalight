import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { api, number, type PageProps } from "../api";
import type { components } from "../generated/api";
import { Badge, Empty, ErrorNotice } from "../components";
import { Chart } from "../Chart";
import DecisionCard, { type BatchDecision } from "../DecisionCard";
import Confidence, { ConfidenceLabel } from "../Confidence";

type TraceWindow = components["schemas"]["TraceView"];

export default function Monitoring({ run, report, showEvidence }: PageProps) {
  const client = useQueryClient();
  const [selected, setSelected] = useState("");
  const [endBatch, setEndBatch] = useState<number | null>(null);
  const excluded = run.config.excluded_channel_ids ?? [];
  const channels =
    report?.profiles.filter((p) => !excluded.includes(p.id)) ?? [];
  const channel =
    channels.find((p) => p.id === selected)?.id || channels[0]?.id || "";
  const decisions = useQuery({
    queryKey: ["decisions", run.id, "recent"],
    queryFn: () => api<BatchDecision[]>(`/runs/${run.id}/decisions?limit=5`),
    refetchInterval: 2000,
  });
  const trace = useQuery({
    queryKey: ["trace", run.id, channel, endBatch],
    queryFn: () =>
      api<TraceWindow>(
        `/runs/${run.id}/trace?channel_id=${channel}&batch_window=3${endBatch === null ? "" : `&end_batch=${endBatch}`}`,
      ),
    enabled: !!channel,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === channel ? previous : undefined,
    refetchInterval: 2000,
  });
  const latestBatch = Math.max(
    trace.data?.latest_batch ?? 0,
    run.batch_index - 1,
    0,
  );
  const oldestEnd = Math.min(2, latestBatch);
  const visibleEnd = endBatch ?? latestBatch;
  const scrollHistory = (delta: number) => {
    if (!delta) return;
    setEndBatch((current) => {
      const value = Math.max(
        oldestEnd,
        Math.min(latestBatch, (current ?? latestBatch) + Math.sign(delta)),
      );
      return value === latestBatch ? null : value;
    });
  };
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
    animation: false,
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
        <div className="decision-status">
          <h2
            className={`process-status ${latest?.decision.status === "Fault Suspected" ? "warning-text" : ""}`}
          >
            {latest?.decision.status ?? "Waiting for first batch"}
          </h2>
          {latest && <ConfidenceLabel decision={latest.decision} />}
        </div>
        {latest && (
          <Confidence decision={latest.decision} showEvidence={showEvidence} />
        )}
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
              {trace.data?.points.length
                ? `Samples ${trace.data.row_start}–${trace.data.row_end} · `
                : ""}
              {endBatch === null ? "Current batch" : "Selected batch"} and up to
              two previous batches. Shading marks detected changes.
            </p>
          </div>
          <select
            aria-label="Trend channel"
            value={channel}
            onChange={(e) => setSelected(e.target.value)}
          >
            {channels.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div
          id="monitoring-trace"
          onWheel={(event) => scrollHistory(event.deltaX)}
        >
          <Chart option={option} label="Incoming channel values and forecast" />
        </div>
        <div className="history-controls">
          <span className="muted">
            Drag or scroll horizontally for earlier batches
          </span>
          <button
            disabled={endBatch === null}
            onClick={() => setEndBatch(null)}
          >
            Latest
          </button>
        </div>
        <input
          type="range"
          className="history-scroll"
          role="scrollbar"
          aria-label="Monitoring history"
          aria-controls="monitoring-trace"
          aria-orientation="horizontal"
          aria-valuemin={oldestEnd}
          aria-valuemax={latestBatch}
          aria-valuenow={visibleEnd}
          aria-valuetext={`Through batch ${visibleEnd}`}
          min={oldestEnd}
          max={latestBatch}
          step={1}
          value={visibleEnd}
          disabled={latestBatch <= oldestEnd}
          onChange={(event) => {
            const value = Number(event.target.value);
            setEndBatch(value === latestBatch ? null : value);
          }}
          onWheel={(event) => scrollHistory(event.deltaX)}
        />
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
