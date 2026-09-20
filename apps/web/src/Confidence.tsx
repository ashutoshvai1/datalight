import type { components } from "./generated/api";
import { Badge, EvidenceLinks } from "./components";

type Decision = components["schemas"]["Decision"];

export function ConfidenceLabel({ decision }: { decision: Decision }) {
  if (decision.status !== "Fault Suspected") return null;
  const confidence = decision.confidence;
  return (
    <Badge tone={confidence?.level === "high" ? "amber" : ""}>
      {confidence
        ? `Confidence: ${confidence.level === "high" ? "High" : "Low"}`
        : "Confidence not recorded"}
    </Badge>
  );
}

export default function Confidence({
  decision,
  showEvidence,
}: {
  decision: Decision;
  showEvidence: (id: string) => void;
}) {
  if (decision.status !== "Fault Suspected" || !decision.confidence)
    return null;
  const confidence = decision.confidence;
  return (
    <div className="decision-confidence">
      <p>{confidence.explanation}</p>
      <p className="muted">
        Evidence strength, not fault probability or severity. The initial
        reference is provisional.
      </p>
      <EvidenceLinks
        ids={confidence.evidence_ids}
        showEvidence={showEvidence}
      />
    </div>
  );
}
