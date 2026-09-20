"""Versioned evidence-strength policy, independent of detection and model output."""

from .schemas import ConfidenceBasis, DecisionConfidence

PERSISTENCE = 10
REFERENCE_COUNT = 50


def qualifies(basis: ConfidenceBasis) -> bool:
    return basis.observed_persistence >= basis.required_persistence and (
        basis.kind == "rule"
        or (basis.reference_usable is True and (basis.reference_count or 0) >= REFERENCE_COUNT)
    )


def retain(facts: list[ConfidenceBasis], candidate: ConfidenceBasis):
    """Keep one strongest observation per source, not an unbounded sample history."""
    key = (candidate.channel_id, candidate.kind, candidate.rule_id)
    # Evaluation visits one channel/rule at a time; its entries are at the end.
    for index in range(len(facts) - 1, -1, -1):
        prior = facts[index]
        if (prior.channel_id, prior.kind, prior.rule_id) == key:
            if candidate.observed_persistence > prior.observed_persistence:
                facts[index] = candidate
            return
    facts.append(candidate)


def assess(facts: list[ConfidenceBasis]) -> DecisionConfidence | None:
    if not facts:
        return None
    # Stable ties follow detector/channel/rule evaluation order.
    basis = max(
        facts,
        key=lambda f: (qualifies(f), f.observed_persistence / f.required_persistence),
    )
    high = qualifies(basis)
    label = "Applied fault rule" if basis.kind == "rule" else f"{basis.kind.capitalize()} change"
    unit = (
        "observations"
        if basis.kind == "rule"
        else "checks"
        if basis.kind == "drift"
        else "evaluations"
    )
    explanation = (
        f"{label} persisted for {basis.observed_persistence} consecutive {unit} "
        f"({basis.required_persistence} required)."
    )
    if basis.kind != "rule":
        explanation += (
            " Sufficient reference data."
            if basis.reference_usable and (basis.reference_count or 0) >= REFERENCE_COUNT
            else f" Limited reference: a usable initial profile and {REFERENCE_COUNT} reference measurements are required."
        )
    return DecisionConfidence(
        level="high" if high else "low",
        explanation=explanation,
        evidence_ids=basis.evidence_ids,
        basis=basis,
    )
