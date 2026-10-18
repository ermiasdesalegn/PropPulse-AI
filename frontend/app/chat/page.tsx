"use client";

import {
  Bot,
  Building2,
  CalendarCheck,
  CalendarClock,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  SendHorizonal,
  Sparkles,
  UserCheck,
  UserRound,
  Wrench,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, CardHeader, ErrorNote, PageHeader, cx, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useIntegrations } from "@/lib/hooks";
import type { Client, Message, ToolCall } from "@/lib/types";

type ChatItem =
  | { kind: "user" | "assistant"; text: string }
  | { kind: "tool"; call: Pick<ToolCall, "name" | "args"> & { result?: ToolCall["result"] } };

const SESSION_KEY = "proppulse-chat-session";

const PERSISTENT_CHIPS = [
  "🏢 Show Bole apartments under 15M ETB",
  "💰 What are the installment payment plans?",
  "👤 My name is Dawit, budget 14M ETB, email dawit@gmail.com",
  "📅 Check availability tomorrow at 2:00 PM",
  "✅ Book a site visit for Bole Skyline tomorrow at 2:00 PM",
];

function newSessionId() {
  return `web-${crypto.randomUUID().replaceAll("-", "").slice(0, 20)}`;
}

function loadSessionId(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = newSessionId();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return newSessionId();
  }
}

function messagesToItems(messages: Message[]): ChatItem[] {
  return messages.flatMap<ChatItem>((m) => {
    if (m.role === "user" || m.role === "assistant") return [{ kind: m.role, text: m.content }];
    if (m.role === "tool") {
      try {
        const parsed = JSON.parse(m.content);
        return [{ kind: "tool", call: { name: parsed.tool, args: parsed.args, result: parsed.result } }];
      } catch {
        return [];
      }
    }
    return [];
  });
}

function ToolBadge({
  name,
  args,
  result,
}: {
  name: string;
  args?: Record<string, unknown>;
  result?: unknown;
}) {
  const [open, setOpen] = useState(false);

  const meta: Record<string, { label: string; icon: typeof Building2; color: string; border: string; bg: string }> = {
    search_properties: {
      label: "Search Property Inventory",
      icon: Building2,
      color: "text-sky-600 dark:text-sky-400",
      border: "border-sky-500/25",
      bg: "bg-sky-500/5",
    },
    upsert_client_profile: {
      label: "Update CRM Lead Profile",
      icon: UserCheck,
      color: "text-indigo-600 dark:text-indigo-400",
      border: "border-indigo-500/25",
      bg: "bg-indigo-500/5",
    },
    check_calendar_availability: {
      label: "Check Google Calendar",
      icon: CalendarClock,
      color: "text-amber-600 dark:text-amber-400",
      border: "border-amber-500/25",
      bg: "bg-amber-500/5",
    },
    check_availability: {
      label: "Check Calendar Slots",
      icon: CalendarClock,
      color: "text-amber-600 dark:text-amber-400",
      border: "border-amber-500/25",
      bg: "bg-amber-500/5",
    },
    book_appointment: {
      label: "Book Site Visit / Call",
      icon: CalendarCheck,
      color: "text-emerald-600 dark:text-emerald-400",
      border: "border-emerald-500/25",
      bg: "bg-emerald-500/5",
    },
  };

  const toolMeta = meta[name] ?? {
    label: name,
    icon: Wrench,
    color: "text-brand",
    border: "border-line",
    bg: "bg-subtle/60",
  };
  const Icon = toolMeta.icon;

  const argsEntries = Object.entries(args ?? {});
  const argsSummary = argsEntries
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");

  return (
    <div className="my-1.5 ml-10 max-w-[90%]">
      <div
        className={cx(
          "rounded-xl border transition-all text-xs overflow-hidden shadow-xs",
          toolMeta.border,
          toolMeta.bg,
        )}
      >
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className={cx("grid size-5 shrink-0 place-items-center rounded", toolMeta.color)}>
              <Icon className="size-3.5" />
            </span>
            <span className="font-semibold text-ink truncate">
              {toolMeta.label}
            </span>
            <code className="hidden sm:inline font-mono text-[11px] text-muted rounded bg-black/5 dark:bg-white/5 px-1.5 py-0.5">
              {name}()
            </code>
            {argsSummary && (
              <span className="hidden md:inline truncate text-[11px] text-muted max-w-[200px]">
                ({argsSummary})
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" /> Executed
            </span>
            {open ? <ChevronUp className="size-3.5 text-muted" /> : <ChevronDown className="size-3.5 text-muted" />}
          </div>
        </button>

        {open && (
          <div className="border-t border-line/60 bg-surface/95 p-3 space-y-2.5 text-[11px]">
            {argsEntries.length > 0 && (
              <div>
                <div className="font-semibold text-muted uppercase tracking-wider text-[10px]">Arguments:</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {argsEntries.map(([k, v]) => (
                    <span key={k} className="inline-flex items-center gap-1 rounded bg-subtle px-2 py-0.5 font-mono text-ink">
                      <span className="text-muted">{k}:</span> {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div>
              <div className="font-semibold text-muted uppercase tracking-wider text-[10px]">Result:</div>
              <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-subtle p-2.5 font-mono text-[11px] text-ink leading-relaxed">
                {typeof result === "string" ? result : JSON.stringify(result ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const info = useIntegrations();
  const sessionRef = useRef<string | null>(null);
  const [ready, setReady] = useState(false);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [client, setClient] = useState<Client | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = loadSessionId();
    sessionRef.current = id;
    api<{ client: Client | null; messages: Message[] }>(`api/chat/web/${id}`)
      .then((r) => {
        setItems(messagesToItems(r.messages));
        setClient(r.client);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items, sending]);

  async function send(text: string) {
    const sessionId = sessionRef.current;
    if (!text.trim() || !sessionId || sending) return;
    setInput("");
    setError(null);
    setItems((prev) => [...prev, { kind: "user", text }]);
    setSending(true);
    try {
      const r = await api<{ reply: string; tool_calls: ToolCall[]; client: Client }>("api/chat/web", {
        body: { session_id: sessionId, message: text },
      });
      setItems((prev) => [
        ...prev,
        ...r.tool_calls.map<ChatItem>((call) => ({ kind: "tool", call })),
        { kind: "assistant", text: r.reply },
      ]);
      setClient(r.client);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  function reset() {
    const id = newSessionId();
    try {
      localStorage.setItem(SESSION_KEY, id);
    } catch {}
    sessionRef.current = id;
    setItems([]);
    setClient(null);
  }

  const currency = info?.currency ?? "ETB";
  const profile: [string, string | null | undefined][] = client
    ? [
        ["Name", client.full_name],
        ["Phone", client.phone],
        ["Email", client.email],
        [
          "Budget",
          client.budget_min || client.budget_max
            ? `${money(client.budget_min, currency)} – ${money(client.budget_max, currency)}`
            : null,
        ],
        ["Location", client.preferred_location],
        ["Bedrooms", client.preferred_bedrooms?.toString()],
      ]
    : [];

  return (
    <>
      <PageHeader
        title="Agent Test Chat"
        subtitle="Talk to the same Gemini agent that runs on Telegram. Tool calls hit the live inventory, CRM, calendar and email."
        actions={
          <Button variant="secondary" onClick={reset}>
            <RotateCcw className="size-4" /> New conversation
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="flex h-[calc(100vh-12rem)] min-h-[520px] flex-col lg:col-span-2">
          <div className="flex-1 space-y-3 overflow-y-auto p-5">
            {items.length === 0 && (
              <div className="py-8 text-center">
                <Bot className="mx-auto size-9 text-brand" />
                <h4 className="mt-2 text-sm font-semibold text-ink">Welcome to PropPulse AI Test Console</h4>
                <p className="mt-1 text-xs text-muted max-w-md mx-auto">
                  Experience our 24/7 autonomous sales executive. Send any inquiry or click a quick-action prompt below to watch live Gemini function calling.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {PERSISTENT_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => send(chip)}
                      className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:border-brand hover:text-brand hover:bg-brand-soft/30 transition-all shadow-xs"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {items.map((item, i) =>
              item.kind === "tool" ? (
                <ToolBadge
                  key={i}
                  name={item.call.name}
                  args={item.call.args as Record<string, unknown>}
                  result={item.call.result}
                />
              ) : (
                <div key={i} className={cx("flex gap-2.5", item.kind === "user" && "flex-row-reverse")}>
                  <span
                    className={cx(
                      "grid size-8 shrink-0 place-items-center rounded-full",
                      item.kind === "user" ? "bg-subtle text-muted" : "bg-brand text-white",
                    )}
                  >
                    {item.kind === "user" ? <UserRound className="size-4" /> : <Bot className="size-4" />}
                  </span>
                  <div
                    className={cx(
                      "max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm",
                      item.kind === "user" ? "rounded-tr-sm bg-brand text-white" : "rounded-tl-sm bg-subtle text-ink",
                    )}
                  >
                    {item.text}
                  </div>
                </div>
              ),
            )}
            {sending && (
              <div className="flex items-center gap-2 pl-10 text-xs text-muted">
                <span className="flex gap-1">
                  <span className="size-1.5 animate-bounce rounded-full bg-muted" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted [animation-delay:120ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted [animation-delay:240ms]" />
                </span>
                {info?.agent_name ?? "Agent"} is thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-line p-3">
            {/* Persistent Quick-Action Chips (SRS Section 5.2) */}
            <div className="mb-2.5">
              <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-muted">
                <span className="flex items-center gap-1.5 text-ink font-semibold">
                  <Sparkles className="size-3.5 text-brand" /> Quick-Action Evaluator Prompts
                </span>
                <span className="text-[10px] text-muted">Triggers live Gemini function calling</span>
              </div>
              <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar">
                {PERSISTENT_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => send(chip)}
                    disabled={sending || !ready}
                    className="shrink-0 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:border-brand hover:text-brand hover:bg-brand-soft/30 transition-all disabled:opacity-50 shadow-xs"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            </div>

            <ErrorNote message={error} />
            <form
              className="mt-1 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message as a client…"
                className={inputClass}
                disabled={!ready}
              />
              <Button type="submit" loading={sending} disabled={!input.trim()}>
                <SendHorizonal className="size-4" />
              </Button>
            </form>
          </div>
        </Card>

        <Card className="self-start">
          <CardHeader title="Captured CRM profile" icon={<UserRound className="size-4 text-brand" />} actions={client && <Badge value={client.status} />} />
          {client ? (
            <dl className="divide-y divide-line">
              {profile.map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4 px-5 py-2.5 text-sm">
                  <dt className="text-muted">{label}</dt>
                  <dd className={cx("text-right font-medium", value ? "text-ink" : "text-faint")}>{value || "not yet"}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="px-5 py-6 text-sm text-muted">
              The agent saves details here automatically via <code className="font-mono text-xs">upsert_client_profile</code> as the
              conversation goes.
            </p>
          )}
          {info?.bot_username && (
            <p className="border-t border-line px-5 py-3 text-xs text-muted">
              Prefer Telegram?{" "}
              <a className="font-medium text-brand underline" href={`https://t.me/${info.bot_username}`} target="_blank" rel="noreferrer">
                Chat with @{info.bot_username}
              </a>
            </p>
          )}
        </Card>
      </div>
    </>
  );
}
