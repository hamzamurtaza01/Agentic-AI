-- Expense tracker agent - schema and seed data.
-- Run in the Supabase SQL Editor. Safe to re-run.

-- Drops first so the script is re-runnable while the schema is still
-- changing. Remove this line once there is data worth keeping.
drop table if exists public.expenses;

create table public.expenses (
  id          bigint generated always as identity primary key,
  spent_on    date          not null,
  amount      numeric(10,2) not null,
  category    text          not null,
  description text,
  created_at  timestamptz   not null default now(),

  -- A refund or a typo of zero is never a valid expense.
  constraint expenses_amount_positive check (amount > 0),

  -- Keeps the category list closed, so the agent cannot invent a
  -- category and split a report across "food" and "Food".
  constraint expenses_category_valid check (
    category in ('food', 'transport', 'shopping', 'bills', 'health', 'other')
  )
);

-- Reports always filter by date, and usually by category as well.
create index expenses_spent_on_idx on public.expenses (spent_on, category);

-- No policies are defined, so the table is reachable only via the secret
-- key, which bypasses RLS. That is what the agent uses.
alter table public.expenses enable row level security;

-- Roughly two months of history so summaries have something to report.
insert into public.expenses (spent_on, amount, category, description) values
  (current_date -  1,  850.00, 'food',      'Groceries'),
  (current_date -  1,  320.00, 'transport', 'Fuel'),
  (current_date -  2, 1200.00, 'shopping',  'Running shoes'),
  (current_date -  3,  450.00, 'food',      'Dinner with friends'),
  (current_date -  5, 3400.00, 'bills',     'Electricity'),
  (current_date -  6,  180.00, 'transport', 'Ride hailing'),
  (current_date -  8,  620.00, 'food',      'Groceries'),
  (current_date -  9,  950.00, 'health',    'Pharmacy'),
  (current_date - 12,  275.00, 'food',      'Coffee and snacks'),
  (current_date - 14, 2100.00, 'bills',     'Internet and phone'),
  (current_date - 15,  400.00, 'transport', 'Fuel'),
  (current_date - 18, 5600.00, 'shopping',  'Winter jacket'),
  (current_date - 21,  730.00, 'food',      'Groceries'),
  (current_date - 24, 1500.00, 'health',    'Dentist'),
  (current_date - 28,  260.00, 'other',     'Gift wrapping'),
  (current_date - 33, 3400.00, 'bills',     'Electricity'),
  (current_date - 36,  890.00, 'food',      'Groceries'),
  (current_date - 40,  510.00, 'transport', 'Fuel'),
  (current_date - 45, 1850.00, 'shopping',  'Headphones'),
  (current_date - 52,  340.00, 'food',      'Takeaway');
