import { Section } from "@/components/ui";

const matrix = [
  ["Works, sanctions, estimates", "Overview and work profile", "project_features.csv"],
  ["Expenditure, payments, progress", "Financial snapshot and payment section", "project_features + payment/fund evidence"],
  ["Completion and assets", "Lifecycle/profile evidence", "project_features.csv"],
  ["Unusual patterns", "Within-stage unusualness and peers", "anomaly + peer benchmark artifacts"],
  ["Duplicate candidates", "Corroborated review-candidate cards", "Day-4.1 duplicate candidates"],
  ["Compliance", "Eight deterministic rule results", "compliance evidence + guideline references"],
  ["Cost and delay context", "Eligibility-aware predictive section", "predictive scores/explanations"],
  ["Trends and hotspots", "Bounded chart and transparent shares", "trend + hotspot artifacts"],
  ["Review prioritization", "Queue, contribution families, early warnings", "Day-7 fusion artifacts"],
  ["Guideline explanation", "Local fallback or explicit Groq request", "Day-8 explanation context"],
  ["Human review and audit", "Append-only status and notes", "Local runtime JSONL"],
];

export default function MethodologyPage() {
  return <><div className="page-title"><div><p className="eyebrow">Governance & coverage</p><h1>Methodology</h1><p>How the prototype maps programme monitoring needs to frozen, traceable intelligence.</p></div></div>
    <div className="notice">All records are synthetic prototype data unless their source metadata says otherwise. Review Priority is deterministic decision support, not a probability, finding, or automated decision.</div>
    <Section title="Feature-completeness matrix" subtitle="Core SIH monitoring need → application capability → governed source">
      <div className="table-wrap"><table><thead><tr><th>Monitoring need</th><th>Application capability</th><th>Frozen source</th></tr></thead><tbody>{matrix.map((row) => <tr key={row[0]}>{row.map((value) => <td key={value}>{value}</td>)}</tr>)}</tbody></table></div>
    </Section>
    <div className="grid-2"><Section title="Interpretation guardrails"><ul><li>Unusualness is a within-lifecycle statistical ranking, not probability.</li><li>A duplicate review candidate is not a confirmed duplicate.</li><li>Compliance REVIEW means evidence needs human verification.</li><li>The cost model is weak secondary context; delay prediction is unavailable.</li><li>Hotspot shares never change an individual work score.</li></ul></Section>
      <Section title="Explanation behavior"><ul><li>The deterministic local explanation is always available.</li><li>Groq is contacted only after the user presses the explicit button.</li><li>Provider rate limits, timeouts, absent keys, or invalid output fall back safely.</li><li>Generated text cannot override source evidence or deterministic rules.</li></ul></Section></div>
  </>;
}
