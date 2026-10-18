-- PropPulse AI — demo data (safe to re-run; skips rows that already exist).
-- Seeded clients have no Telegram chat id / real email, so they appear in the
-- dashboard but are skipped by broadcasts & reminders. Chat with the bot (or
-- edit a client's email in the Phonebook) to receive real messages.

insert into properties (name, location, latitude, longitude, price, price_per_sqm, bedrooms, area_sqm,
                        down_payment, payment_plan, construction_status, description, image_url, status)
values
  ('Bole Skyline Residences', 'Bole, Addis Ababa', 8.9958, 38.7869, 9800000, 98000, 2, 100,
   '30%', '30% down payment, balance over 36 monthly installments', 'Under construction — 70% complete, handover Q3 2027',
   'Modern 2-bedroom apartments 5 minutes from Bole International Airport with gym, rooftop lounge and 24/7 security.',
   'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80', 'AVAILABLE'),
  ('CMC Garden Villas', 'CMC, Addis Ababa', 9.0198, 38.8467, 21500000, 72000, 4, 300,
   '40%', '40% down payment, balance over 24 monthly installments', 'Completed — ready to move in',
   'Standalone 4-bedroom villas with private gardens in a gated community.',
   'https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=1200&q=80', 'AVAILABLE'),
  ('Ayat Family Apartments', 'Ayat, Addis Ababa', 9.0300, 38.8800, 5600000, 70000, 3, 80,
   '20%', '20% down payment, balance over 48 monthly installments', 'Under construction — 45% complete, handover Q1 2028',
   'Affordable 3-bedroom family apartments near schools and the Ayat light-rail station.',
   'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&w=1200&q=80', 'AVAILABLE'),
  ('Kazanchis Business Lofts', 'Kazanchis, Addis Ababa', 9.0180, 38.7660, 7200000, 120000, 1, 60,
   '50%', '50% down payment, balance over 12 monthly installments', 'Completed — ready to move in',
   'Compact 1-bedroom lofts in the heart of the business district, ideal for professionals and investors.',
   'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1200&q=80', 'AVAILABLE'),
  ('Sarbet Diplomatic Suites', 'Sarbet, Addis Ababa', 8.9960, 38.7320, 14800000, 105000, 3, 141,
   '35%', '35% down payment, balance over 30 monthly installments', 'Under construction — 85% complete, handover Q1 2027',
   'Premium 3-bedroom suites near embassies with underground parking and concierge service.',
   'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80', 'AVAILABLE')
on conflict ((lower(name))) do nothing;

insert into clients (full_name, phone, budget_min, budget_max, preferred_location, preferred_bedrooms, status, notes)
select * from (values
  ('Selam Tesfaye',   '+251911000001', 5000000::numeric,  10000000::numeric, 'Bole',   2, 'QUALIFIED'::client_status, 'Demo lead — prefers move-in within a year'),
  ('Dawit Bekele',    '+251911000002', 4000000::numeric,   6500000::numeric, 'Ayat',   3, 'LEAD'::client_status,      'Demo lead — family of four'),
  ('Hanna Girma',     '+251911000003', 12000000::numeric, 25000000::numeric, 'CMC',    4, 'QUALIFIED'::client_status, 'Demo lead — wants a garden'),
  ('Yonas Alemu',     '+251911000004', 6000000::numeric,   8000000::numeric, 'Kazanchis', 1, 'CLOSED_BUYER'::client_status, 'Demo buyer — Kazanchis loft')
) as v(full_name, phone, budget_min, budget_max, preferred_location, preferred_bedrooms, status, notes)
where not exists (select 1 from clients c where c.phone = v.phone);

-- Demo contract + installment schedule for the seeded buyer (installment #2 is 2 days overdue).
with buyer as (
  select id from clients where phone = '+251911000004'
), prop as (
  select id from properties where lower(name) = lower('Kazanchis Business Lofts')
), contract as (
  insert into contracts (client_id, property_id, contract_number, total_price, down_payment_amount,
                         monthly_installment, bank_details, signed_at)
  select buyer.id, prop.id, 'PP-2026-0001', 7200000, 3600000, 300000,
         'Commercial Bank of Ethiopia — Acc. 1000123456789 — PropPulse Developments PLC',
         current_date - interval '2 months'
  from buyer, prop
  on conflict (contract_number) do nothing
  returning id
)
insert into installments (contract_id, sequence_no, due_date, amount, status, paid_at)
select contract.id, s.n,
       (current_date - interval '2 months' + (s.n || ' months')::interval)::date - 2,
       300000,
       case when s.n = 1 then 'PAID'::installment_status else 'PENDING'::installment_status end,
       case when s.n = 1 then now() - interval '1 month' else null end
from contract, generate_series(1, 12) as s(n);

-- Demo site visit tomorrow for a seeded lead.
insert into appointments (client_id, property_id, type, start_at, end_at, notes)
select c.id, p.id, 'SITE_VISIT', date_trunc('day', now()) + interval '1 day 10 hours',
       date_trunc('day', now()) + interval '1 day 11 hours', 'Demo site visit'
from clients c, properties p
where c.phone = '+251911000001' and lower(p.name) = lower('Bole Skyline Residences')
  and not exists (select 1 from appointments a where a.client_id = c.id);
