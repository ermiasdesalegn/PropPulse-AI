"use client";

import { Loader2, X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import type { ClientStatus } from "@/lib/types";

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ className, children, ...rest }: ComponentProps<"div">) {
  return (
    <div className={cx("rounded-xl border border-line bg-surface shadow-sm", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, icon, actions }: { title: string; icon?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3.5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
        {icon}
        {title}
      </h2>
      {actions}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  loading,
  className,
  children,
  disabled,
  ...rest
}: ComponentProps<"button"> & { variant?: ButtonVariant; loading?: boolean }) {
  const styles: Record<ButtonVariant, string> = {
    primary: "bg-brand text-white hover:bg-brand-strong",
    secondary: "border border-line bg-surface text-ink hover:bg-subtle",
    ghost: "text-muted hover:bg-subtle hover:text-ink",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

const STATUS_STYLES: Record<string, string> = {
  LEAD: "bg-slate-100 text-slate-700 ring-slate-200",
  QUALIFIED: "bg-sky-50 text-sky-700 ring-sky-200",
  SITE_VISIT_BOOKED: "bg-violet-50 text-violet-700 ring-violet-200",
  CLOSED_BUYER: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  AVAILABLE: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  RESERVED: "bg-amber-50 text-amber-700 ring-amber-200",
  SOLD_OUT: "bg-slate-100 text-slate-600 ring-slate-200",
  SCHEDULED: "bg-sky-50 text-sky-700 ring-sky-200",
  COMPLETED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  CANCELLED: "bg-slate-100 text-slate-600 ring-slate-200",
  NO_SHOW: "bg-red-50 text-red-700 ring-red-200",
  PAID: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  PENDING: "bg-amber-50 text-amber-700 ring-amber-200",
  OVERDUE: "bg-red-50 text-red-700 ring-red-200",
  sent: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  skipped: "bg-slate-100 text-slate-600 ring-slate-200",
};

export const STATUS_LABELS: Record<ClientStatus, string> = {
  LEAD: "Lead",
  QUALIFIED: "Qualified",
  SITE_VISIT_BOOKED: "Visit booked",
  CLOSED_BUYER: "Buyer",
};

export function Badge({ value, label, className }: { value: string; label?: string; className?: string }) {
  const style = STATUS_STYLES[value] ?? (value.startsWith("error") ? STATUS_STYLES.OVERDUE : STATUS_STYLES.LEAD);
  const text = label ?? STATUS_LABELS[value as ClientStatus] ?? value.replaceAll("_", " ").toLowerCase();
  return (
    <span
      title={value.startsWith("error") ? value : undefined}
      className={cx(
        "inline-flex max-w-full items-center truncate rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset",
        style,
        className,
      )}
    >
      {value.startsWith("error") ? "error" : text}
    </span>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon: ReactNode;
  tone?: "default" | "warn";
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
        <span className={cx("rounded-lg p-1.5", tone === "warn" ? "bg-red-50 text-red-600" : "bg-brand-soft text-brand")}>
          {icon}
        </span>
      </div>
      <div className={cx("mt-2 text-2xl font-semibold tabular-nums", tone === "warn" ? "text-red-600" : "text-ink")}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </Card>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="rounded-full bg-subtle p-3 text-muted">{icon}</div>
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{message}</div>;
}

export function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={cx("flex flex-col gap-1 text-xs font-medium text-muted", className)}>
      {label}
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20";

export function Drawer({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button aria-label="Close" className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-2xl flex-col bg-canvas shadow-2xl">
        <div className="flex items-center justify-between border-b border-line bg-surface px-5 py-4">
          <div className="min-w-0 text-base font-semibold text-ink">{title}</div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-subtle" aria-label="Close panel">
            <X className="size-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>
  );
}

export function DeliveryBadges({ telegram, email }: { telegram: string; email: string }) {
  return (
    <span className="inline-flex gap-1">
      <Badge value={telegram} label={`tg: ${telegram.startsWith("error") ? "error" : telegram}`} />
      <Badge value={email} label={`email: ${email.startsWith("error") ? "error" : email}`} />
    </span>
  );
}
