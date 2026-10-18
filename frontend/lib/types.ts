export type ClientStatus = "LEAD" | "QUALIFIED" | "SITE_VISIT_BOOKED" | "CLOSED_BUYER";

export interface Client {
  id: string;
  telegram_chat_id: number | null;
  telegram_username: string | null;
  web_session_id: string | null;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  budget_min: number | null;
  budget_max: number | null;
  preferred_location: string | null;
  preferred_bedrooms: number | null;
  interested_property_id: string | null;
  status: ClientStatus;
  notes: string | null;
  last_contact_at: string | null;
  created_at: string;
  updated_at: string;
  properties?: { name: string } | null;
}

export interface Property {
  id: string;
  name: string;
  location: string | null;
  latitude: number | null;
  longitude: number | null;
  price: number | null;
  price_per_sqm: number | null;
  bedrooms: number | null;
  area_sqm: number | null;
  down_payment: string | null;
  payment_plan: string | null;
  construction_status: string | null;
  description: string | null;
  floor_plan_url: string | null;
  image_url: string | null;
  status: "AVAILABLE" | "RESERVED" | "SOLD_OUT";
  updated_at: string;
}

export interface Message {
  id: number;
  client_id: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  channel: string;
  created_at: string;
}

export interface Appointment {
  id: string;
  client_id: string;
  property_id: string | null;
  type: "PHONE_CALL" | "SITE_VISIT";
  start_at: string;
  end_at: string;
  calendar_event_id: string | null;
  status: "SCHEDULED" | "COMPLETED" | "CANCELLED" | "NO_SHOW";
  notes: string | null;
  reminder_sent_at: string | null;
  clients?: Client | null;
  properties?: Property | null;
}

export interface Installment {
  id: string;
  contract_id: string;
  sequence_no: number;
  due_date: string;
  amount: number;
  status: "PENDING" | "PAID";
  paid_at: string | null;
  last_reminded_at: string | null;
}

export interface Contract {
  id: string;
  client_id: string;
  property_id: string | null;
  contract_number: string;
  total_price: number;
  down_payment_amount: number | null;
  monthly_installment: number;
  bank_details: string | null;
  signed_at: string;
  clients?: Client | null;
  properties?: Property | null;
  installments: Installment[];
}

export interface Activity {
  id: number;
  kind: string;
  summary: string;
  payload: Record<string, unknown> | null;
  client_id: string | null;
  created_at: string;
  clients?: { full_name: string | null; telegram_username: string | null } | null;
}

export interface Integrations {
  integrations: Record<"gemini" | "supabase" | "telegram" | "telegram_channel" | "calendar" | "email", boolean>;
  bot_username: string | null;
  channel_id: string | null;
  company_name: string;
  agent_name: string;
  timezone: string;
  currency: string;
  channel_link?: string | null;
}

export interface Stats {
  clients_total: number;
  clients_by_status: Record<ClientStatus, number>;
  properties_available: number;
  appointments_next_7_days: number;
  installments_due_soon: number;
  installments_overdue: number;
  overdue_amount: number;
  announcements_total: number;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface Delivery {
  telegram: string;
  email: string;
  [key: string]: unknown;
}

export interface CronSummary {
  ran_at: string;
  trigger: string;
  appointment_reminders: (Delivery & {
    appointment_id: string;
    client: string | null;
    when: string;
    error?: string;
    preview_text?: string;
    preview_email_subject?: string;
    preview_email_html?: string;
  })[];
  installment_reminders: (Delivery & {
    installment_id: string;
    client: string | null;
    contract: string;
    amount: number;
    due_date: string;
    status: string;
    error?: string;
    preview_text?: string;
    preview_email_subject?: string;
    preview_email_html?: string;
  })[];
}
