import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Layers3,
  ListChecks,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api, number, type Finding, type PageProps } from "../api";
import { Badge, Empty, ErrorNotice, FindingCard, Stat } from "../components";
import { Chart } from "../Chart";

export default function Understanding({
  run,
  report,
  showEvidence,
}: PageProps) {
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState("c001");
  const hypotheses = useQuery({
    queryKey: ["findings", run.id, "interpretation"],
    queryFn: () =>
      api<Finding[]>(`/runs/${run.id}/findings?category=interpretation`),
  });
  const heatmap = useMemo(() => {
    if (!report) return {};
    const ids = report.profiles.map((p) => p.id);
    const cells = report.correlations
      .filter((c) => c.coefficient !== null)
      .flatMap((c) => {
        const x = ids.indexOf(c.left),
          y = ids.indexOf(c.right);
        return [
          [x, y, c.coefficient],
          [y, x, c.coefficient],
        ];
      });
    ids.forEach((_, i) => {
      if (report.profiles[i].std) cells.push([i, i, 1]);
    });
    return {
      tooltip: { position: "top", renderMode: "richText" },
      grid: { top: 12, right: 20, bottom: 75, left: 50 },
      xAxis: {
        type: "category",
        data: ids,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { fontSize: 10 },
      },
      yAxis: {
        type: "category",
        data: ids,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { fontSize: 10 },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: 5,
        inRange: { color: ["#b47f61", "#f1f0eb", "#216e63"] },
      },
      series: [
        {
          type: "heatmap",
          data: cells,
          emphasis: { itemStyle: { borderColor: "#182e2b", borderWidth: 1 } },
        },
      ],
    };
  }, [report]);
  if (!report)
    return (
      <Empty title="Building the initial understanding">
        Reading a bounded window and computing channel profiles. This page
        updates automatically.
      </Empty>
    );
  const profile =
    report.profiles.find((p) => p.id === selected) ?? report.profiles[0];
  const failed = report.checks.filter((c) => c.status === "fail").length;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">01 / UNDERSTAND</span>
          <h1>A clearer picture of your data.</h1>
          <p>Start with what we can measure. Make assumptions visible.</p>
        </div>
        <Badge tone="green">
          <ShieldCheck size={13} /> Raw data stays local
        </Badge>
      </div>
      <div className="stats">
        <Stat
          label="Numeric channels"
          value={String(report.profiles.length)}
          detail="Inferred from the initial window"
        />
        <Stat
          label="Reference window"
          value={number(report.profiles[0]?.count ?? 0, 0)}
          detail="Observations · provisional baseline"
        />
        <Stat
          label="Quality findings"
          value={String(failed)}
          detail={
            failed
              ? "Review before interpreting changes"
              : "Implemented checks passed"
          }
        />
        <Stat
          label="Relationships"
          value={String(
            report.correlations.filter((c) => c.coefficient !== null).length,
          )}
          detail="Valid pairwise correlations"
        />
      </div>
      <div className="notice">
        <ShieldCheck size={20} />
        <div>
          <strong>A reference, not a guarantee of healthy operation.</strong>
          <p>
            The initial window establishes a comparison point. Its assumptions
            and every subsequent conclusion can be reviewed.
          </p>
        </div>
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>
              Channel profiles{" "}
              <span className="count">{report.profiles.length}</span>
            </h2>
            <p>Distributions, missingness, and temporal behavior.</p>
          </div>
          <input
            className="search"
            aria-label="Search channels"
            placeholder="Search channels…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="profile-layout">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Channel</th>
                  <th>Valid</th>
                  <th>Median</th>
                  <th>Variability σ</th>
                  <th>Quality</th>
                </tr>
              </thead>
              <tbody>
                {report.profiles
                  .filter((p) =>
                    `${p.name} ${p.id}`
                      .toLowerCase()
                      .includes(filter.toLowerCase()),
                  )
                  .map((p) => (
                    <tr
                      className={profile?.id === p.id ? "selected" : ""}
                      key={p.id}
                    >
                      <td>
                        <button
                          className="channel-button"
                          onClick={() => setSelected(p.id)}
                        >
                          <strong>{p.name}</strong>
                          <span>{p.id}</span>
                        </button>
                      </td>
                      <td>{number(p.completeness * 100, 1)}%</td>
                      <td className="mono">{number(p.median)}</td>
                      <td className="mono">{number(p.std)}</td>
                      <td>
                        <Badge tone={p.usable ? "green" : "amber"}>
                          {p.usable ? "Usable" : "Limited"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {profile && (
            <aside className="channel-detail">
              <span className="eyebrow">CHANNEL DETAIL</span>
              <h3>{profile.name}</h3>
              <span className="mono muted">{profile.id}</span>
              <dl>
                <dt>5th / 95th percentile</dt>
                <dd>
                  {number(profile.q05)} / {number(profile.q95)}
                </dd>
                <dt>Median absolute deviation</dt>
                <dd>{number(profile.mad)}</dd>
                <dt>Successive-difference σ</dt>
                <dd>{number(profile.difference_std)}</dd>
                <dt>Lag-1 correlation</dt>
                <dd>{number(profile.lag1)}</dd>
                <dt>Median hold length</dt>
                <dd>{number(profile.hold_median)} samples</dd>
                <dt>Missing / invalid</dt>
                <dd>
                  {profile.missing} / {profile.invalid}
                </dd>
              </dl>
              <button
                className="text-button"
                onClick={() => showEvidence(profile.evidence_id)}
              >
                Inspect evidence <ArrowUpRight size={15} />
              </button>
            </aside>
          )}
        </div>
      </section>
      <div className="two-column">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Channel relationships</h2>
              <p>
                Pearson correlation · association does not establish causation.
              </p>
            </div>
            <Layers3 size={19} />
          </div>
          {report.profiles.length > 1 ? (
            <Chart
              option={heatmap}
              label="Channel correlation matrix"
              height={340}
            />
          ) : (
            <Empty title="Not enough channels">
              Relationships require at least two numeric channels.
            </Empty>
          )}
          <div className="relationship-list">
            {[...report.correlations]
              .filter((c) => c.coefficient !== null)
              .sort(
                (a, b) =>
                  Math.abs(b.coefficient ?? 0) - Math.abs(a.coefficient ?? 0),
              )
              .slice(0, 3)
              .map((c) => (
                <button
                  key={c.evidence_id}
                  onClick={() => showEvidence(c.evidence_id)}
                >
                  <span>
                    {c.left} ↔ {c.right}
                  </span>
                  <span className="mono">
                    r {number(c.coefficient)} · n {c.count}
                  </span>
                  <ArrowUpRight size={14} />
                </button>
              ))}
          </div>
        </section>
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Data quality</h2>
              <p>Check the observations before interpreting the process.</p>
            </div>
            <ListChecks size={19} />
          </div>
          <div className="check-list">
            {report.checks.map((c) => (
              <button key={c.name} onClick={() => showEvidence(c.evidence_id)}>
                <span>{c.name.replaceAll("_", " ")}</span>
                <Badge
                  tone={
                    c.status === "pass"
                      ? "green"
                      : c.status === "fail"
                        ? "amber"
                        : ""
                  }
                >
                  {c.status === "unavailable" ? "Not assessed" : c.status}
                </Badge>
              </button>
            ))}
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>
              <Sparkles size={18} /> Role hypotheses
            </h2>
            <p>
              Model interpretations are tentative and cite statistical evidence.
            </p>
          </div>
          <Badge>{report.interpretation_status}</Badge>
        </div>
        <ErrorNotice error={hypotheses.error} />
        {hypotheses.data?.some((f) => f.batch_index === 0) ? (
          hypotheses.data
            .filter((f) => f.batch_index === 0)
            .map((f) => (
              <FindingCard key={f.id} finding={f} showEvidence={showEvidence} />
            ))
        ) : (
          <p className="muted">{report.interpretation_message}</p>
        )}
      </section>
      <section className="panel compact">
        <details>
          <summary>Analysis boundaries & column classification</summary>
          <ul className="limitations">
            {report.limitations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <table>
            <thead>
              <tr>
                <th>Column</th>
                <th>Role</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {report.columns.map((c) => (
                <tr key={c.name}>
                  <td>{c.name}</td>
                  <td>{c.role}</td>
                  <td>{c.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>
    </>
  );
}
