"use client";

import {
  Building2,
  CalendarClock,
  ExternalLink,
  LayoutDashboard,
  Megaphone,
  MessageSquareText,
  Receipt,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useIntegrations } from "@/lib/hooks";
import { cx } from "./ui";

const NAV = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/chat", label: "Agent Test Chat", icon: MessageSquareText },
  { href: "/phonebook", label: "Phonebook CRM", icon: Users },
  { href: "/ledger", label: "Buyer Ledger", icon: Receipt },
  { href: "/properties", label: "Inventory", icon: Building2 },
  { href: "/composer", label: "Ad & Broadcast", icon: Megaphone },
  { href: "/automations", label: "Automations", icon: CalendarClock },
];

const INTEGRATION_LABELS: Record<string, string> = {
  gemini: "Gemini 2.5 Flash",
  supabase: "Supabase",
  telegram: "Telegram bot",
  telegram_channel: "Telegram channel",
  calendar: "Google Calendar",
  email: "Resend email",
};

export function Sidebar() {
  const pathname = usePathname();
  const info = useIntegrations();

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid size-9 place-items-center rounded-lg bg-brand text-white">
          <Building2 className="size-5" />
        </div>
        <div>
          <div className="text-sm font-semibold text-ink">PropPulse AI</div>
          <div className="text-xs text-muted">{info?.company_name ?? "Sales Command Center"}</div>
        </div>
      </div>

      <nav className="flex flex-col gap-1 px-3 pb-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cx(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-brand-soft text-brand-strong" : "text-muted hover:bg-subtle hover:text-ink",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-3 border-t border-line px-5 py-4">
        {info?.bot_username && (
          <a
            href={`https://t.me/${info.bot_username}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
          >
            Open @{info.bot_username} <ExternalLink className="size-3.5" />
          </a>
        )}
        <ul className="space-y-1.5">
          {Object.entries(INTEGRATION_LABELS).map(([key, label]) => {
            const ok = info?.integrations[key as keyof typeof info.integrations];
            return (
              <li key={key} className="flex items-center justify-between text-xs text-muted">
                {label}
                <span
                  className={cx(
                    "size-2 rounded-full",
                    info === null ? "bg-slate-300" : ok ? "bg-emerald-500" : "bg-red-400",
                  )}
                  title={ok ? "Configured" : "Not configured"}
                />
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
