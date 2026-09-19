import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Radio } from "lucide-react";
import { api, number, type Batch, type Finding, type PageProps } from "../api";
import { Badge, Empty, ErrorNotice, FindingCard, Stat } from "../components";
import { Chart } from "../Chart";

export default function Monitoring({ run, report, showEvidence }: PageProps) {
  const [channel, setChannel] = useState("c001");
  const batches = useQuery({
    queryKey: ["batches", run.id],
    queryFn: () => api<Batch[]>(`/runs/${run.id}/batches?limit=100`),
  });
  const findings = useQuery({
    queryKey: ["findings", run.id, "monitor"],
    queryFn: () => api<Finding[]>(`/runs/${run.id}/findings?limit=50`),
  });
  const option = useMemo(() => {
    const points: {
      label: string;
      value: number | null;
      low: number | null;
      high: number | null;
    }[] = [];
    let sequence: number | undefined;
    for (const batch of [...(batches.data ?? [])].reverse()) {
      const channels = batch.summary.channels as {
        id: string;
        median: number | null;
        q05: number | null;
        q95: number | null;
      }[];
      const value = channels.find((c) => c.id === channel);
      if (sequence !== undefined && sequence !== batch.sequence)
        points.push({
          label: "Sequence boundary",
          value: null,
          low: null,
          high: null,
        });
      points.push({
        label: `Rows ${batch.row_start}–${batch.row_end}`,
        value: value?.median ?? null,
        low: value?.q05 ?? null,
        high: value?.q95 ?? null,
      });
      sequence = batch.sequence;
    }
    return {
      tooltip: { trigger: "axis", renderMode: "richText" },
      grid: { top: 20, bottom: 55, left: 65, right: 25 },
      xAxis: {
        type: "category",
        data: points.map((p) => p.label),
        axisLabel: { fontSize: 10, hideOverlap: true },
        axisLine: { lineStyle: { color: "#cbd3ce" } },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { color: "#edf0eb" } },
      },
      series: [
        {
          name: "Batch median",
          type: "line",
          showSymbol: points.length < 30,
          data: points.map((p) => p.value),
          lineStyle: { width: 2.5, color: "#247567" },
          itemStyle: { color: "#247567" },
        },
        {
          name: "5th percentile",
          type: "line",
          showSymbol: false,
          data: points.map((p) => p.low),
          lineStyle: { color: "#a3bdb4", type: "dashed" },
          itemStyle: { color: "#a3bdb4" },
        },
        {
          name: "95th percentile",
          type: "line",
          showSymbol: false,
          data: points.map((p) => p.high),
          lineStyle: { color: "#a3bdb4", type: "dashed" },
          itemStyle: { color: "#a3bdb4" },
        },
      ],
    };
  }, [batches.data, channel]);
  const latest = batches.data?.[0];
  const visible = findings.data?.filter((f) =>
    ["quality", "deviation"].includes(f.category),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">02 / MONITOR</span>
          <h1>Watch the evidence evolve.</h1>
          <p>
            Every incoming batch passes quality checks before process analysis.
          </p>
        </div>
        <Badge tone={run.status === "running" ? "green" : ""}>
          <Radio size={13} />
          {run.status}
        </Badge>
      </div>
      <div className="stats">
        <Stat
          label="Observations processed"
          value={number(run.rows_processed, 0)}
          detail="Read progressively from the mounted file"
        />
        <Stat
          label="Committed batches"
          value={number(run.batch_index, 0)}
          detail="Results and cursor saved atomically"
        />
        <Stat
          label="Current sequence"
          value={String(run.sequence + 1)}
          detail="Temporal calculations respect boundaries"
        />
        <Stat
          label="Latest data quality"
          value={String(latest?.summary.trust ?? "Pending")}
          detail="Reliability of the observations"
        />
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Channel trend</h2>
            <p>
              Last 100 batches · median and 5th/95th percentiles · gaps separate
              sequences.
            </p>
          </div>
          <select
            aria-label="Trend channel"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          >
            {report?.profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id})
              </option>
            ))}
          </select>
        </div>
        <ErrorNotice error={batches.error} />
        <Chart option={option} label="Batch channel trend" />
      </section>
      {latest && (
        <section className="panel compact">
          <details>
            <summary>
              Latest batch checks and unsupported detector channels
            </summary>
            <pre>
              {JSON.stringify(
                {
                  checks: latest.summary.checks,
                  unsupported: latest.summary.unsupported,
                },
                null,
                2,
              )}
            </pre>
          </details>
        </section>
      )}
      <div className="section-heading">
        <div>
          <h2>Recent findings</h2>
          <p>
            Quality issues and reference deviations stay separate. Full history
            is in the decision log.
          </p>
        </div>
      </div>
      <ErrorNotice error={findings.error} />
      {visible?.length ? (
        visible.map((f) => (
          <FindingCard key={f.id} finding={f} showEvidence={showEvidence} />
        ))
      ) : (
        <Empty title="No batch findings so far">
          Monitoring continues against the provisional reference. No finding is
          not proof of a healthy process.
        </Empty>
      )}
    </>
  );
}
