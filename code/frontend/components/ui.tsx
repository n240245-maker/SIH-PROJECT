import { AlertCircle, LoaderCircle } from "lucide-react";

export function LoadingState({ label = "Loading governed intelligence…" }: { label?: string }) {
  return <div className="state-box"><LoaderCircle className="spin" size={24} /><p>{label}</p></div>;
}
export function ErrorState({ error }: { error: unknown }) {
  return <div className="state-box error" role="alert"><AlertCircle size={24} /><div><strong>Unable to load this view</strong><p>{error instanceof Error ? error.message : "An unexpected error occurred."}</p></div></div>;
}
export function EmptyState({ label = "No records match the current scope and filters." }: { label?: string }) {
  return <div className="state-box"><p>{label}</p></div>;
}
export function Band({ value }: { value: unknown }) {
  const text = String(value ?? "UNKNOWN"); return <span className={`band band-${text.toLowerCase()}`}>{text}</span>;
}
export function Section({ title, subtitle, children, id }: { title: string; subtitle?: string; children: React.ReactNode; id?: string }) {
  return <section className="panel" id={id}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div></div>{children}</section>;
}
