"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, BellRing, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { number } from "@/lib/format";
import { useScope } from "@/lib/scope";

const CATEGORY_ORDER = [
  "Financial", "Progress", "Schedule", "Payments", "Compliance",
  "Duplicate Review", "Completion / Asset", "Analytical Signals",
];

export default function AlertCenterPage() {
  const { scope } = useScope();
  const query = useQuery({ queryKey: ["alert-center", scope], queryFn: () => api.alerts(scope) });
  if (query.isLoading) return <LoadingState label="Loading governed alert summary…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;

  const grouped = new Map<string, typeof query.data.summary>();
  query.data.summary.forEach((item) => {
    const category = item.category === "Completion / Asset" ? item.category : item.category;
    grouped.set(category, [...(grouped.get(category) ?? []), item]);
  });
  const categories = CATEGORY_ORDER.filter((category) => grouped.has(category));

  return <>
    <div className="page-title"><div><p className="eyebrow">Governed officer workflow</p><h1>Alert center</h1><p>Actionable review conditions remain separate from statistical and operational context.</p></div><div className="alert-total"><BellRing size={18} /><strong>{number.format(query.data.total)}</strong><span>governed alert records</span></div></div>
    <div className="alert-guidance"><ShieldAlert size={18} /><p><strong>Requires Review</strong> identifies a current governed condition for officer verification. <strong>Analytical context</strong> supports prioritization but is not itself an actionable finding.</p></div>
    {!categories.length ? <EmptyState label="No alerts are available for this authority scope." /> : <div className="alert-category-list">
      {categories.map((category) => <section className="alert-category" key={category} aria-labelledby={`alert-${category.replaceAll(" ", "-")}`}>
        <div className="alert-category-heading"><BarChart3 size={17} /><h2 id={`alert-${category.replaceAll(" ", "-")}`}>{category}</h2></div>
        <div className="compact-row-list">{grouped.get(category)?.map((item) => <Link className="compact-row alert-row" href={`/review-queue?alert_type=${encodeURIComponent(item.alert_type)}`} key={item.alert_type} aria-label={`Open ${item.label} in the review queue`}>
          <span className={`state-pill ${item.actionable ? "state-review" : "state-analytical"}`}>{item.actionable ? <ShieldAlert size={12} /> : <BarChart3 size={12} />}{item.status}</span>
          <span className="compact-row-main"><strong>{item.label}</strong><small>{item.short_explanation}</small></span>
          <span className="alert-count"><strong>{number.format(item.work_count)}</strong><small>works</small></span>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>)}</div>
      </section>)}
    </div>}
    <p className="section-note">Counts summarize the current frozen alert artifact within the selected authority scope. They do not alter Review Priority or multiply urgency.</p>
  </>;
}
