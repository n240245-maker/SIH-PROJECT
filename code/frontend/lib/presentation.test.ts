import assert from "node:assert/strict";
import test from "node:test";

import {
  PEER_METRICS,
  FOLLOW_UP_ACTION_LABELS,
  attentionLabel,
  complianceState,
  contributionSum,
  documentStateLabel,
  familyLabel,
  formatFact,
  formatCompactInr,
  formatMetric,
  humanizeNarrative,
  metricLabel,
  peerObservedValue,
  readinessGroup,
} from "./presentation.ts";

test("all served peer metrics have friendly metadata", () => {
  assert.equal(Object.keys(PEER_METRICS).length, 20);
  assert.equal(metricLabel("financial_minus_physical_gap_pct_as_of"), "Financial vs physical progress gap");
  assert.ok(!metricLabel("financial_minus_physical_gap_pct_as_of").includes("_"));
});

test("observed peer value takes precedence over a missing project alias", () => {
  const row = { observed_value: 158.31622176591375, project_value: null };
  assert.equal(peerObservedValue(row), 158.31622176591375);
  assert.equal(formatMetric("expenditure_to_sanction_pct_as_of", peerObservedValue(row)), "158.3%");
});

test("primary values are rounded to one decimal", () => {
  assert.equal(formatMetric("financial_minus_physical_gap_pct_as_of", 129.40000000000003), "129.4 percentage points");
});

test("priority contributions reconcile without changing governed points", () => {
  assert.equal(contributionSum([{ contribution_points: 7.900415 }, { contribution_points: 81.541486 }]), 89.441901);
  assert.equal(familyLabel("PAYMENT_EXECUTION"), "Payment & Progress Gap");
});

test("review, non-compliance, and analytical semantics remain distinct", () => {
  assert.equal(complianceState("REVIEW"), "review");
  assert.equal(complianceState("NON_COMPLIANT"), "strong_issue");
  assert.notEqual(complianceState("REVIEW"), complianceState("NON_COMPLIANT"));
});

test("attention and lifecycle states have centralized officer-facing labels", () => {
  assert.equal(attentionLabel("IMMEDIATE_PRIORITY"), "Immediate Priority");
  assert.equal(attentionLabel("LOW_ATTENTION"), "Low Attention");
  assert.equal(documentStateLabel("EXPECTED_AFTER_COMPLETION"), "Expected after completion");
  assert.equal(documentStateLabel("NON_COMPLIANT"), "Non-Compliant");
});

test("friendly fact formatting avoids false precision", () => {
  assert.equal(formatFact(37.56, "percentage_points"), "37.6 percentage points");
  assert.equal(formatFact(143.878865979, "percent"), "143.9%");
  assert.equal(formatFact("2025-06-24", "date"), "24 June 2025");
  assert.equal(formatFact(94.201658, "score"), "94.2");
  assert.equal(formatCompactInr(637000), "₹6.37 lakh");
  assert.equal(formatCompactInr(925000), "₹9.25 lakh");
});

test("Indian money summaries use readable lakh and crore units", () => {
  assert.equal(formatCompactInr(637000), "₹6.37 lakh");
  assert.equal(formatCompactInr(12_500_000), "₹1.25 crore");
});

test("readiness and corrective actions remain controlled mappings", () => {
  assert.equal(readinessGroup("RECORDED"), "Recorded");
  assert.equal(readinessGroup("NON_COMPLIANT"), "Requires Review");
  assert.equal(readinessGroup("EXPECTED_AFTER_COMPLETION"), "Not Applicable");
  assert.equal(readinessGroup("INSUFFICIENT_DATA"), "Not Recorded");
  assert.equal(FOLLOW_UP_ACTION_LABELS.REVIEW_REVISED_SANCTION, "Review Revised Sanction");
  assert.equal(Object.keys(FOLLOW_UP_ACTION_LABELS).length, 10);
});

test("mocked grounded explanation fields use officer-facing evidence language", () => {
  const grounded = {
    summary: "Review PERSISTENT_FUND_PROGRESS_REVIEW for W-002760.",
    why_flagged: [{ finding: "PAYMENT_AUTH_BEFORE_REQUEST requires source verification." }],
  };
  assert.equal(humanizeNarrative(grounded.summary), "Review Payment & Progress Gap for W-002760.");
  assert.equal(humanizeNarrative(grounded.why_flagged[0].finding), "Payment authorization recorded before request requires source verification.");
});

test("deterministic fallback narrative avoids raw metric identifiers", () => {
  const rendered = humanizeNarrative("financial_minus_physical_gap_pct_as_of is 129.400000 percentage points");
  assert.equal(rendered, "Financial vs physical progress gap is 129.4 percentage points");
  assert.ok(!rendered.includes("_"));
});
