-- PropPulse AI — initial schema
-- Run in the Supabase SQL editor (or `supabase db push`).

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type client_status as enum ('LEAD', 'QUALIFIED', 'SITE_VISIT_BOOKED', 'CLOSED_BUYER');
exception when duplicate_object then null; end $$;

do $$ begin
  create type appointment_type as enum ('PHONE_CALL', 'SITE_VISIT');
exception when duplicate_object then null; end $$;

do $$ begin
  create type appointment_status as enum ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW');
exception when duplicate_object then null; end $$;

do $$ begin
  create type installment_status as enum ('PENDING', 'PAID');
exception when duplicate_object then null; end $$;

do $$ begin
  create type property_status as enum ('AVAILABLE', 'RESERVED', 'SOLD_OUT');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- updated_at helper
-- ---------------------------------------------------------------------------
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------------
-- Property inventory
-- ---------------------------------------------------------------------------
create table if not exists properties (
  id                  uuid primary key default gen_random_uuid(),
  name                text not null,
  location            text,
  latitude            double precision,
  longitude           double precision,
  price               numeric(14, 2),
  price_per_sqm       numeric(12, 2),
  bedrooms            integer,
  area_sqm            numeric(10, 2),
  down_payment        text,
  payment_plan        text,
  construction_status text,
  description         text,
  floor_plan_url      text,
  image_url           text,
  status              property_status not null default 'AVAILABLE',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create unique index if not exists properties_name_lower_idx on properties (lower(name));
drop trigger if exists properties_updated_at on properties;
create trigger properties_updated_at before update on properties
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- Client phonebook CRM
-- ---------------------------------------------------------------------------
create table if not exists clients (
  id                     uuid primary key default gen_random_uuid(),
  telegram_chat_id       bigint unique,
  telegram_username      text,
  web_session_id         text unique,
  full_name              text,
  phone                  text,
  email                  text,
  budget_min             numeric(14, 2),
  budget_max             numeric(14, 2),
  preferred_location     text,
  preferred_bedrooms     integer,
  interested_property_id uuid references properties (id) on delete set null,
  status                 client_status not null default 'LEAD',
  notes                  text,
  last_contact_at        timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);
create index if not exists clients_status_idx on clients (status);
drop trigger if exists clients_updated_at on clients;
create trigger clients_updated_at before update on clients
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- Conversation log
-- ---------------------------------------------------------------------------
create table if not exists conversation_messages (
  id         bigint generated always as identity primary key,
  client_id  uuid not null references clients (id) on delete cascade,
  role       text not null check (role in ('user', 'assistant', 'tool', 'system')),
  content    text not null,
  channel    text not null default 'telegram',
  created_at timestamptz not null default now()
);
create index if not exists conversation_messages_client_idx
  on conversation_messages (client_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Appointments (calls & site visits)
-- ---------------------------------------------------------------------------
create table if not exists appointments (
  id                uuid primary key default gen_random_uuid(),
  client_id         uuid not null references clients (id) on delete cascade,
  property_id       uuid references properties (id) on delete set null,
  type              appointment_type not null,
  start_at          timestamptz not null,
  end_at            timestamptz not null,
  calendar_event_id text,
  status            appointment_status not null default 'SCHEDULED',
  notes             text,
  reminder_sent_at  timestamptz,
  created_at        timestamptz not null default now()
);
create index if not exists appointments_start_idx on appointments (start_at);

-- ---------------------------------------------------------------------------
-- Buyer ledger: contracts & installment schedules
-- ---------------------------------------------------------------------------
create table if not exists contracts (
  id                  uuid primary key default gen_random_uuid(),
  client_id           uuid not null references clients (id) on delete cascade,
  property_id         uuid references properties (id) on delete set null,
  contract_number     text not null unique,
  total_price         numeric(14, 2) not null,
  down_payment_amount numeric(14, 2),
  monthly_installment numeric(14, 2) not null,
  bank_details        text,
  signed_at           date not null default current_date,
  created_at          timestamptz not null default now()
);

create table if not exists installments (
  id               uuid primary key default gen_random_uuid(),
  contract_id      uuid not null references contracts (id) on delete cascade,
  sequence_no      integer not null,
  due_date         date not null,
  amount           numeric(14, 2) not null,
  status           installment_status not null default 'PENDING',
  paid_at          timestamptz,
  last_reminded_at timestamptz,
  created_at       timestamptz not null default now(),
  unique (contract_id, sequence_no)
);
create index if not exists installments_due_idx on installments (status, due_date);

-- ---------------------------------------------------------------------------
-- Company announcements (ingestion log)
-- ---------------------------------------------------------------------------
create table if not exists announcements (
  id                 uuid primary key default gen_random_uuid(),
  source             text not null default 'portal',
  raw_text           text not null,
  parsed             jsonb,
  ad_copy            text,
  property_id        uuid references properties (id) on delete set null,
  channel_message_id bigint,
  matched_count      integer not null default 0,
  created_at         timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Agent activity feed (dashboard)
-- ---------------------------------------------------------------------------
create table if not exists agent_activity (
  id         bigint generated always as identity primary key,
  kind       text not null,
  summary    text not null,
  payload    jsonb,
  client_id  uuid references clients (id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists agent_activity_created_idx on agent_activity (created_at desc);

-- ---------------------------------------------------------------------------
-- Row Level Security: the backend uses the service-role key (bypasses RLS).
-- Enabling RLS with no policies blocks access via the public anon key.
-- ---------------------------------------------------------------------------
alter table properties            enable row level security;
alter table clients               enable row level security;
alter table conversation_messages enable row level security;
alter table appointments          enable row level security;
alter table contracts             enable row level security;
alter table installments          enable row level security;
alter table announcements         enable row level security;
alter table agent_activity        enable row level security;
