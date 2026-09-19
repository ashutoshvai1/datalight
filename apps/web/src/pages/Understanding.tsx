import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { number, type PageProps } from "../api";
import { Badge, Empty } from "../components";
import { Chart } from "../Chart";

export default function Understanding({ report, showEvidence }: PageProps) {
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState("");
  const [params] = useSearchParams();
  if (!report)
    return (
      <Empty title="Building the initial understanding">
        Computing quality checks, statistics, and causal forecasts. Monitoring
        will remain paused.
      </Empty>
    );
  const profile =
    report.profiles.find((p) => p.id === selected) ?? report.profiles[0];
  const names = Object.fromEntries(report.profiles.map((p) => [p.id, p.name]));
  const prediction = profile && report.predictions?.[profile.id];
  const explanation = report.explanations?.find(
    (e) => e.channel_id === profile?.id,
  );
  const checks = report.checks.filter((c) =>
    c.name.endsWith(`:${profile?.id}`),
  );
  const relationships = report.correlations
    .filter((c) => c.coefficient !== null)
    .sort(
      (a, b) => Math.abs(b.coefficient ?? 0) - Math.abs(a.coefficient ?? 0),
    );
  const ids = report.profiles.map((p) => p.id);
  const cells = report.correlations
    .filter((c) => c.coefficient !== null)
    .flatMap((c) => [
      [ids.indexOf(c.left), ids.indexOf(c.right), c.coefficient],
      [ids.indexOf(c.right), ids.indexOf(c.left), c.coefficient],
    ]);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">01 / UNDERSTAND</span>
          <h1>Initial understanding</h1>
          <p>
            Your initial samples define a provisional reference for monitoring.
          </p>
        </div>
        <Link className="button primary" to={`/monitoring?${params}`}>
          Go to monitoring →
        </Link>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>Channel profiles</h2>
          <input
            aria-label="Search channels"
            placeholder="Search channels…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Channel</th>
                <th>Mean</th>
                <th>Std dev</th>
                <th>Observed min / max</th>
                <th>Prediction MAE</th>
                <th>Mean slope / sample</th>
              </tr>
            </thead>
            <tbody>
              {report.profiles
                .filter((p) =>
                  p.name.toLowerCase().includes(filter.toLowerCase()),
                )
                .map((p) => (
                  <tr
                    key={p.id}
                    className={profile?.id === p.id ? "selected" : ""}
                  >
                    <td>
                      <button
                        className="channel-button"
                        onClick={() => setSelected(p.id)}
                      >
                        {p.name}
                      </button>
                    </td>
                    <td>{number(p.mean)}</td>
                    <td>{number(p.std)}</td>
                    <td>
                      {number(p.minimum)} / {number(p.maximum)}
                    </td>
                    <td>{number(report.predictions?.[p.id]?.mae)}</td>
                    <td>{number(report.predictions?.[p.id]?.slope_mean, 6)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
      {profile && (
        <div className="two-column">
          <section className="panel">
            <h2>{profile.name}: quality & prediction</h2>
            <dl className="metric-list">
              <dt>Missing / invalid</dt>
              <dd>
                {profile.missing} / {profile.invalid}
              </dd>
              <dt>Completeness</dt>
              <dd>{number(profile.completeness * 100, 1)}%</dd>
              <dt>Slope variability</dt>
              <dd>{number(prediction?.slope_std, 6)}</dd>
              <dt>Forecast evaluation</dt>
              <dd>
                {prediction
                  ? `${prediction.forecasts} errors · 10-sample lookback · 5-sample horizon`
                  : "Not available in this historical report"}
              </dd>
            </dl>
            {checks.map((c) => (
              <div className="quality-row" key={c.name}>
                <strong>
                  {c.name.startsWith("range") ? "In range" : "Frozen / stuck"}
                </strong>
                <Badge
                  tone={
                    c.status === "fail"
                      ? "amber"
                      : c.status === "pass"
                        ? "green"
                        : ""
                  }
                >
                  {c.status === "unavailable" ? "Not assessed" : c.status}
                </Badge>
                <p>{c.explanation}</p>
              </div>
            ))}
            <button
              className="text-button"
              onClick={() => showEvidence(profile.evidence_id)}
            >
              Inspect evidence
            </button>
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Channel explanation</h2>
              <Badge>{report.interpretation_status}</Badge>
            </div>
            <p className="explanation">
              {explanation?.text ?? report.interpretation_message}
            </p>
            {explanation?.evidence_ids.map((id) => (
              <button
                className="text-button"
                key={id}
                onClick={() => showEvidence(id)}
              >
                Supporting evidence
              </button>
            ))}
            <h3>Strongest relationships</h3>
            {relationships
              .filter((c) => c.left === profile.id || c.right === profile.id)
              .slice(0, 3)
              .map((c) => (
                <div className="quality-row" key={c.evidence_id}>
                  <button
                    className="text-button"
                    onClick={() => showEvidence(c.evidence_id)}
                  >
                    {names[c.left]} ↔ {names[c.right]}
                  </button>
                  <span>
                    r = {number(c.coefficient)} · n = {c.count}
                  </span>
                </div>
              ))}
            <p>Correlation does not establish causation.</p>
          </section>
        </div>
      )}
      {report.checks.some(
        (c) => c.status === "fail" && !c.name.includes(":"),
      ) && (
        <section className="panel">
          <h2>Data quality warnings</h2>
          {report.checks
            .filter((c) => c.status === "fail" && !c.name.includes(":"))
            .map((c) => (
              <p key={c.name}>
                {c.name}: {c.affected}. {c.explanation}
              </p>
            ))}
        </section>
      )}
      <section className="panel">
        <details>
          <summary>Full pairwise correlation matrix</summary>
          <Chart
            label="Channel correlation matrix"
            height={400}
            option={{
              tooltip: { renderMode: "richText" },
              grid: { top: 20, left: 70, bottom: 80, right: 20 },
              xAxis: {
                type: "category",
                data: ids.map((id) => names[id]),
                axisLabel: { hideOverlap: true },
              },
              yAxis: {
                type: "category",
                data: ids.map((id) => names[id]),
                axisLabel: { hideOverlap: true },
              },
              visualMap: {
                min: -1,
                max: 1,
                orient: "horizontal",
                bottom: 0,
                left: "center",
                inRange: { color: ["#b47f61", "#f1f0eb", "#216e63"] },
              },
              series: [{ type: "heatmap", data: cells }],
            }}
          />
        </details>
      </section>
    </>
  );
}
