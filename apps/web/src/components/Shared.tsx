import { AlertTriangle, Check, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="state-panel">
      <LoaderCircle className="spin" size={24} />
      <span>Reconstructing financial evidence…</span>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-panel error">
      <AlertTriangle size={22} />
      <div>
        <strong>Could not load workspace</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function StatusBadge({
  status,
}: {
  status: string;
}) {
  const safe = ["pass", "ready", "auto_approved", "exact", "composite"].includes(
    status,
  );
  return (
    <span className={`status-badge ${safe ? "safe" : "risk"}`}>
      {safe && <Check size={12} />}
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function Metric({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "good" | "risk";
}) {
  return (
    <article className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}
