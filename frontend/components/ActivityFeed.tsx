"use client";

import {
  AlertTriangle,
  BellRing,
  Building2,
  CalendarCheck,
  FileSignature,
  Megaphone,
  MessageSquare,
  Receipt,
  Send,
  Timer,
  UserCog,
  UserPlus,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { timeAgo } from "@/lib/format";
import type { Activity } from "@/lib/types";
import { cx } from "./ui";

const KIND: Record<string, { icon: LucideIcon; tone: string; label: string }> = {
  conversation: { icon: MessageSquare, tone: "bg-sky-50 text-sky-600", label: "Chat" },
  tool_call: { icon: Wrench, tone: "bg-slate-100 text-slate-600", label: "Tool call" },
  crm_update: { icon: UserCog, tone: "bg-indigo-50 text-indigo-600", label: "CRM" },
  new_lead: { icon: UserPlus, tone: "bg-emerald-50 text-emerald-600", label: "New lead" },
  appointment_booked: { icon: CalendarCheck, tone: "bg-violet-50 text-violet-600", label: "Booking" },
  appointment_reminder: { icon: BellRing, tone: "bg-amber-50 text-amber-600", label: "Reminder" },
  installment_reminder: { icon: Receipt, tone: "bg-amber-50 text-amber-700", label: "Payment" },
  ad_posted: { icon: Megaphone, tone: "bg-teal-50 text-teal-600", label: "Ad" },
  lead_broadcast: { icon: Send, tone: "bg-teal-50 text-teal-700", label: "Broadcast" },
  inventory_update: { icon: Building2, tone: "bg-cyan-50 text-cyan-700", label: "Inventory" },
  cron_run: { icon: Timer, tone: "bg-orange-50 text-orange-600", label: "Cron" },
  contract_created: { icon: FileSignature, tone: "bg-emerald-50 text-emerald-700", label: "Contract" },
  error: { icon: AlertTriangle, tone: "bg-red-50 text-red-600", label: "Error" },
};

export function ActivityFeed({ items }: { items: Activity[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <ul className="divide-y divide-line">
      {items.map((item) => {
        const meta = KIND[item.kind] ?? KIND.tool_call;
        const Icon = meta.icon;
        return (
          <li key={item.id} className="px-5 py-3">
            <button className="flex w-full items-start gap-3 text-left" onClick={() => setOpen(open === item.id ? null : item.id)}>
              <span className={cx("mt-0.5 rounded-lg p-1.5", meta.tone)}>
                <Icon className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-ink [overflow-wrap:anywhere]">{item.summary}</span>
                <span className="mt-0.5 block text-xs text-muted">
                  {meta.label} · {timeAgo(item.created_at)}
                </span>
              </span>
            </button>
            {open === item.id && item.payload && (
              <pre className="mt-2 ml-10 max-h-72 overflow-auto rounded-lg bg-subtle p-3 font-mono text-xs text-ink">
                {JSON.stringify(item.payload, null, 2)}
              </pre>
            )}
          </li>
        );
      })}
    </ul>
  );
}
