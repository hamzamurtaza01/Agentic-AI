# Agentic-AI

Practice and learning projects for agentic AI — building agents from the raw SDKs rather than a framework, so the loop, the tools, and the state are all visible.

## Projects

| Project | What it demonstrates | Stack |
| --- | --- | --- |
| [appointment-booking-agent-in-js](agents-sdk/appointment-booking-agent-in-js) | A hand-written agent loop: the model calls tools, the tools hit a real database, results feed back until it answers | Node, OpenAI `gpt-4o-mini`, Supabase (Postgres) |
| [expense-tracker-agent-in-python](agents-sdk/expense-tracker-agent-in-python) | The same idea with the loop handed to a framework: tools are plain functions, the SDK decides when to call them | Python, OpenAI Agents SDK, Supabase (Postgres) |

---

## appointment-booking-agent-in-js

A booking assistant that checks slot availability and books appointments against Postgres. The agent loop is written out by hand — no framework — so each turn of the request → tool call → result → repeat cycle is explicit in `agent.js`.

**Tools the model can call**

- `check_appointment_availability` — is a given date and time free?
- `book_appointment` — reserve a slot

**Data model**

Two tables, deliberately kept separate:

- `availability_slots` — every slot the business offers
- `appointments` — the subset that is booked

A slot is open when it exists in the first and not the second. A composite foreign key stops a slot that was never offered from being booked, and a unique constraint on `(date, time)` prevents double booking even if two runs check availability at the same moment.

### Setup

```bash
cd agents-sdk/appointment-booking-agent-in-js
npm install
```

Create `.env` in that folder:

```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

`SUPABASE_SECRET_KEY` must be the **secret** key (Supabase → Settings → API Keys), not the publishable one. Row level security is enabled with no policies, so a publishable key reads zero rows _without raising an error_ — every slot then looks unavailable. `agent.js` refuses to start on a publishable key rather than let that happen quietly.

Then run `schema.sql` in the Supabase SQL Editor to create the tables and seed three days of slots. It drops and recreates both tables, so it is safe to re-run while the schema is changing — and destructive once there is data worth keeping.

### Run

```bash
npm start
```

The example prompt at the bottom of `agent.js` is in Urdu (`"Main kal 3 baje haircut book karna chahta hoon"`), which exercises both multilingual input and relative-date handling.

### Notes

- `.env` is loaded by `process.loadEnvFile()` (built into Node 20.12+), resolved against the file rather than the working directory — so `node agent.js` works from anywhere. No `dotenv` dependency.
- The current date is injected into the system prompt in **local** time. Using UTC (`toISOString()`) books a day early whenever the local date is already ahead of UTC.
- Dependencies are pinned exactly, not with `^`.

---

## expense-tracker-agent-in-python

A personal spending tracker: record expenses, summarise them by category, list recent ones. Built on the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/), which owns the agent loop — you declare tools and the SDK decides when to call them, runs them, and feeds results back. Worth reading side by side with the JS project above, where that same loop is written by hand.

**Tools the model can call**

- `add_expense` — record an expense
- `get_spending_summary` — totals per category between two dates
- `list_recent_expenses` — the most recent entries

Tools are ordinary Python functions with a `@function_tool` decorator. The SDK builds the JSON schema the model sees from the type hints, and the tool description from the docstring — so the docstring is part of the interface, not a comment.

### Setup

```bash
cd agents-sdk/expense-tracker-agent-in-python
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

Create `.env` in that folder with the same three variables as the JS project (see `.env.example`), then run `schema.sql` in the Supabase SQL Editor.

### Run

```bash
.venv/Scripts/python agent.py
```

The example prompt asks *"How much did I spend on food last month?"* — the model has to resolve "last month" to a date range and then pick the summary tool.

### Notes

- Categories are constrained in the database and re-checked in the tool, so the model cannot invent one and split a report across `food` and `Food`.
- PostgREST has no `GROUP BY`, so the summary groups in Python. Twenty rows do not justify a database function.
- `supabase-py` raises on API errors, unlike `supabase-js` which returns an `{ data, error }` pair. The tools let those propagate; the SDK reports them back to the model.
