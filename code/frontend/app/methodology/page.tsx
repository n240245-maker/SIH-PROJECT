import { Section } from "@/components/ui";

const matrix = [
  ["Works, sanctions, estimates", "Five role-aware dashboards and dossier", "demo-v2 works + annual allocations"],
  ["Expenditure, payments, progress", "Fund flow, chronology and schedule", "separate one-to-many demo-v2 histories"],
  ["Geo-tagged evidence", "IA capture, district verification and location review", "seeded synthetic evidence + append-only local runtime"],
  ["Completion and records", "Lifecycle-aware readiness", "normalized demo-v2 record registry"],
  ["Unusual patterns", "Three lifecycle-specific Isolation Forests", "demo-v2 anomaly scores"],
  ["Duplicate candidates", "MiniLM top-5 retrieval plus corroboration", "local embeddings and candidate index"],
  ["Compliance", "Deterministic records and payment checks", "structured evidence + verified guideline foundation"],
  ["Cost-overrun context", "Observed status separated from early warning", "LR/RF/XGBoost synthetic holdout evaluation"],
  ["Delay context", "Observed schedule condition only", "No fake delay prediction model"],
  ["Review prioritization", "Governed family-capped human-review queue", "REVIEW_PRIORITY_POLICY_V0_1_DEMO_V2"],
  ["Guideline explanation", "Local fallback or explicit Groq request", "bounded structured evidence + guideline excerpts"],
  ["Human review and audit", "Append-only status, action and notes", "Local runtime JSONL"],
];

export default function MethodologyPage() {
  return <><div className="page-title"><div><p className="eyebrow">Governance & coverage</p><h1>Methodology</h1><p>How the prototype maps programme monitoring needs to frozen, traceable intelligence.</p></div></div>
    <div className="notice">All demo-v2 records, coordinates, histories, evidence images, labels and outcomes are synthetic. Their distributions do not represent real MPLADS national prevalence. Review Priority is deterministic decision support, not a probability, finding, or automated decision.</div>
    <Section title="Feature-completeness matrix" subtitle="Core SIH monitoring need → application capability → governed source">
      <div className="table-wrap"><table><thead><tr><th>Monitoring need</th><th>Application capability</th><th>Frozen source</th></tr></thead><tbody>{matrix.map((row) => <tr key={row[0]}>{row.map((value) => <td key={value}>{value}</td>)}</tr>)}</tbody></table></div>
    </Section>
    <div className="grid-2"><Section title="Interpretation guardrails"><ul><li>Unusualness is a within-lifecycle statistical ranking, not a fraud probability.</li><li>A duplicate review candidate is not a confirmed duplicate.</li><li>Compliance REVIEW means evidence needs human verification.</li><li>The cost model has synthetic holdout support only; delay prediction is unavailable.</li><li>Geo-evidence warnings contribute exactly zero Review Priority points.</li><li>Aggregate comparisons never change an individual work score.</li></ul></Section>
      <Section title="Explanation behavior"><ul><li>The deterministic local explanation is always available.</li><li>Groq is contacted only after the user presses the explicit button.</li><li>Provider rate limits, timeouts, absent keys, or invalid output fall back safely.</li><li>Generated text cannot override source evidence or deterministic rules.</li></ul></Section></div>
    <div className="grid-2"><Section title="Prototype geo policy"><ul><li>Execution evidence is due in the first three Monday–Friday working days each month.</li><li>Completion evidence is due within three working days after completion.</li><li>The 500-metre location band is a prototype review threshold, not an MPLADS rule.</li><li>No official State holiday calendar is bundled; this is disclosed in every affected view.</li><li>Image hashes demonstrate storage integrity, not image authenticity.</li></ul></Section><Section title="Map licensing"><p>No external GeoJSON, commercial tiles, or live map API is used. The application renders an accessible scope-aware heat table from clearly synthetic demo coordinates.</p></Section></div>
  </>;
}
