-- Appointment booking agent — schema and seed data.
-- Run in the Supabase SQL Editor. Safe to re-run.
--
-- availability_slots = every slot the business offers.
-- appointments       = the subset of those slots that are booked.
-- A slot is open when it exists in the first table and not the second.

-- Drops first so the script is re-runnable while the schema is still
-- changing. Remove these two lines once there is data worth keeping.
drop table if exists public.appointments;
drop table if exists public.availability_slots;

create table public.availability_slots (
  id   bigint generated always as identity primary key,
  date date not null,
  time time not null,

  -- Needed as a unique key so appointments can reference it below.
  constraint availability_slots_unique unique (date, time)
);

create table public.appointments (
  id         bigint generated always as identity primary key,
  name       text        not null,
  date       date        not null,
  time       time        not null,
  service    text        not null,
  created_at timestamptz not null default now(),

  -- Only a slot the business actually offers can be booked.
  constraint appointments_slot_fk foreign key (date, time)
    references public.availability_slots (date, time),

  -- One booking per slot. The agent checks before inserting, but two
  -- concurrent runs can both pass that check, so the database is what
  -- actually prevents a double booking.
  constraint appointments_slot_unique unique (date, time)
);

-- No policies are defined, so both tables are reachable only via the
-- secret key, which bypasses RLS. That is what the agent uses.
alter table public.availability_slots enable row level security;
alter table public.appointments       enable row level security;

-- Offer every half hour from 09:00 to 17:00, for the next three days.
insert into public.availability_slots (date, time)
select d::date, t::time
from generate_series(current_date, current_date + 2, interval '1 day') d,
     generate_series(
       timestamp '2000-01-01 09:00',
       timestamp '2000-01-01 17:00',
       interval '30 minutes'
     ) t
on conflict (date, time) do nothing;

-- Booked slots only. Tomorrow 15:00 is deliberately left unbooked: it is
-- the slot the example prompt in agent.py asks for.
insert into public.appointments (name, date, time, service) values
  ('Ayesha Khan',   current_date,     '10:00', 'haircut'),
  ('Bilal Ahmed',   current_date,     '14:30', 'beard trim'),
  ('Fatima Sheikh', current_date + 1, '11:00', 'hair colour'),
  ('Usman Tariq',   current_date + 1, '16:00', 'haircut'),
  ('Zara Malik',    current_date + 2, '09:30', 'haircut'),
  ('Hassan Raza',   current_date + 2, '15:00', 'shave')
on conflict (date, time) do nothing;
