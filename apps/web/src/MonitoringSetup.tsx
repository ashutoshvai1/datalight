import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Report, type Run, type System } from "./api";
import type { components } from "./generated/api";
import { Badge, ErrorNotice } from "./components";

type Rule = components["schemas"]["MonitoringRule"];
type Proposal = components["schemas"]["RuleProposalView"];

function describeRule(rule: Rule, names: Record<string, string>) {
  const channel = names[rule.channel_id] ?? rule.channel_id;
  const effect =
    rule.effect === "fault"
      ? "Flag Fault Suspected"
      : "Show a data quality warning";
  const operators = { gt: ">", gte: "≥", lt: "<", lte: "≤" };
  const condition =
    rule.operator === "missing"
      ? `${channel} is missing`
      : rule.operator === "outside"
        ? `${channel} is outside [${rule.minimum}, ${rule.maximum}]`
        : `${channel} ${operators[rule.operator]} ${rule.threshold}`;
  return `${effect} when ${condition}.`;
}

export default function MonitoringSetup({
  run,
  report,
}: {
  run: Run;
  report: Report;
}) {
  const client = useQueryClient();
  const [draftExcluded, setDraftExcluded] = useState<string[] | null>(null);
  const [draftRules, setDraftRules] = useState<string[] | null>(null);
  const [request, setRequest] = useState("");
  const [proposalId, setProposalId] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [search, setSearch] = useState("");
  const excluded = draftExcluded ?? run.config.excluded_channel_ids ?? [];
  const rules = run.config.rules ?? [];
  const ruleIds = draftRules ?? rules.map((rule) => rule.id);
  const locked = !!run.config.monitoring_locked || run.batch_index > 1;
  const editable = !locked && run.status === "paused";
  const dirty =
    JSON.stringify([...excluded].sort()) !==
      JSON.stringify([...(run.config.excluded_channel_ids ?? [])].sort()) ||
    JSON.stringify([...ruleIds].sort()) !==
      JSON.stringify(rules.map((rule) => rule.id).sort());
  const names = Object.fromEntries(
    report.profiles.map((profile) => [profile.id, profile.name]),
  );
  const base = `/runs/${run.id}`;
  const updateRun = (updated: Run) => {
    client.setQueryData(["run", run.id], updated);
    client.setQueryData<System>(["system"], (previous) =>
      previous?.run?.id === run.id ? { ...previous, run: updated } : previous,
    );
    void client.invalidateQueries({ queryKey: ["runs"] });
  };
  const save = useMutation({
    mutationFn: () =>
      api<Run>(`${base}/monitoring-config`, {
        excluded_channel_ids: excluded,
        rule_ids: ruleIds,
      }),
    onSuccess: (updated) => {
      updateRun(updated);
      setDraftExcluded(null);
      setDraftRules(null);
      setSaved(true);
      setProposalId(null);
    },
  });
  const propose = useMutation({
    mutationFn: () => api<Proposal>(`${base}/rule-proposals`, { request }),
    onSuccess: (proposal) => {
      client.setQueryData(["rule-proposal", run.id, proposal.id], proposal);
      setProposalId(proposal.id);
    },
  });
  const proposal = useQuery({
    queryKey: ["rule-proposal", run.id, proposalId],
    queryFn: () => api<Proposal>(`${base}/rule-proposals/${proposalId}`),
    enabled: !!proposalId,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ? 1500 : false,
  });
  const apply = useMutation({
    mutationFn: () =>
      api<Run>(`${base}/rule-proposals/${proposalId}/apply`, {}),
    onSuccess: (updated) => {
      updateRun(updated);
      setProposalId(null);
      setRequest("");
      setSaved(true);
    },
  });
  const pending = propose.isPending || proposal.data?.status === "pending";
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    const navigate = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest?.("a[href]");
      if (
        anchor &&
        !window.confirm(
          "You have unsaved monitoring settings. Leave without saving?",
        )
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    const internal = (event: Event) => {
      if (
        !window.confirm(
          "You have unsaved monitoring settings. Leave without saving?",
        )
      )
        event.preventDefault();
    };
    window.addEventListener("datalight:navigate", internal);
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", navigate, true);
    return () => {
      window.removeEventListener("datalight:navigate", internal);
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", navigate, true);
    };
  }, [dirty]);

  return (
    <section className="panel monitoring-setup" aria-label="Monitoring setup">
      <div className="section-heading">
        <h2>Monitoring setup</h2>
        <Badge>
          {locked ? "Fixed for this analysis" : "Before first Play"}
        </Badge>
      </div>
      {run.status === "completed" && run.batch_index <= 1 && (
        <p className="notice">
          All observations are in the understanding report. There are no
          remaining samples to monitor.
        </p>
      )}
      <h3>Channels to exclude from monitoring</h3>
      <div className="channel-selection-heading">
        <p>
          {report.profiles.length - excluded.length} numeric channels selected
          for monitoring
        </p>
        <input
          aria-label="Filter monitoring channels"
          placeholder="Find a channel…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <div className="channel-selection">
        {report.columns
          .filter((column) =>
            column.name.toLowerCase().includes(search.toLowerCase()),
          )
          .map((column) => {
            const profile = report.profiles.find(
              (profile) => profile.name === column.name,
            );
            return (
              <label className="channel-option" key={column.name}>
                <input
                  type="checkbox"
                  checked={!profile || excluded.includes(profile.id)}
                  disabled={
                    !profile || !editable || save.isPending || apply.isPending
                  }
                  onChange={(event) => {
                    if (!profile) return;
                    setDraftExcluded(
                      event.target.checked
                        ? [...excluded, profile.id]
                        : excluded.filter((id) => id !== profile.id),
                    );
                    setSaved(false);
                    setProposalId(null);
                  }}
                />
                <span>
                  <strong>{column.name}</strong>
                  {!profile && <small>{column.reason}</small>}
                </span>
              </label>
            );
          })}
      </div>
      <h3>Additional monitoring rules</h3>
      {rules.filter((rule) => ruleIds.includes(rule.id)).length > 0 && (
        <ul className="applied-rules">
          {rules
            .filter((rule) => ruleIds.includes(rule.id))
            .map((rule) => (
              <li key={rule.id}>
                <span>{describeRule(rule, names)}</span>
                {editable && (
                  <button
                    type="button"
                    className="text-button"
                    disabled={apply.isPending || save.isPending}
                    onClick={() => {
                      setDraftRules(ruleIds.filter((id) => id !== rule.id));
                      setSaved(false);
                    }}
                    aria-label={`Remove rule for ${names[rule.channel_id]}`}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
        </ul>
      )}
      {editable && (
        <>
          <div className="rule-label">
            <label htmlFor="monitoring-rule">Describe a simple rule</label>
            <span className="help-tip">
              <button
                type="button"
                aria-label="Example monitoring rule"
                aria-describedby="rule-example"
              >
                ?
              </button>
              <span role="tooltip" id="rule-example">
                Flag fault if channel{" "}
                {report.profiles.find(
                  (profile) => !excluded.includes(profile.id),
                )?.name ?? "xyz"}{" "}
                exceeds 80. You can also request a quality warning for missing
                values or values outside a range.
              </span>
            </span>
          </div>
          <textarea
            id="monitoring-rule"
            placeholder="Flag fault if channel xyz exceeds 80"
            value={request}
            maxLength={2000}
            disabled={pending || apply.isPending}
            onChange={(event) => {
              setRequest(event.target.value);
              setProposalId(null);
            }}
          />
          <div className="review-actions">
            <button
              type="button"
              disabled={!request.trim() || dirty || pending || apply.isPending}
              onClick={() => propose.mutate()}
            >
              {pending ? "Interpreting rule…" : "Propose rule"}
            </button>
            {dirty && (
              <span className="muted">
                Save your channel and rule changes before proposing another
                rule.
              </span>
            )}
          </div>
          {proposal.data && (
            <div className="rule-proposal" aria-live="polite">
              {proposal.data.rule && proposal.data.status === "succeeded" ? (
                <>
                  <strong>Proposed rule</strong>
                  <p>{describeRule(proposal.data.rule, names)}</p>
                  <div className="review-actions">
                    <button
                      className="primary"
                      type="button"
                      disabled={dirty || apply.isPending || save.isPending}
                      onClick={() => apply.mutate()}
                    >
                      Apply rule
                    </button>
                    <button
                      type="button"
                      disabled={apply.isPending || save.isPending}
                      onClick={() => setProposalId(null)}
                    >
                      Discard
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p>
                    {proposal.data.message ||
                      (pending
                        ? "Preparing a rule for your review…"
                        : "No rule was applied.")}
                  </p>
                  {!pending && (
                    <button type="button" onClick={() => propose.mutate()}>
                      Retry proposal
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
      <ErrorNotice
        error={save.error || propose.error || proposal.error || apply.error}
      />
      {editable && (
        <div className="review-actions setup-save">
          <button
            className="primary"
            type="button"
            disabled={
              !dirty ||
              save.isPending ||
              apply.isPending ||
              excluded.length >= report.profiles.length
            }
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Save monitoring setup"}
          </button>
          <span role="status">
            {excluded.length >= report.profiles.length
              ? "Keep at least one numeric channel."
              : dirty
                ? "Unsaved changes"
                : saved
                  ? "Monitoring setup saved"
                  : "Ready to monitor"}
          </span>
        </div>
      )}
    </section>
  );
}
