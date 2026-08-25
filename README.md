# Agentic-AI
Practice projects for agentic AI. Each one is a working agent with real tools against a real database — first written by hand so the loop is visible, then rebuilt on a framework so the difference is obvious.

## Projects

| Project | What it demonstrates | Stack |
| --- | --- | --- |
| [appointment-booking-agent-in-js](agents-sdk/appointment-booking-agent-in-js) | The agent loop written out by hand: call the model, run the tools it asks for, feed results back, repeat | Node, OpenAI `gpt-4o-mini`, Supabase |
| [appointment-booking-agent-in-python](agents-sdk/appointment-booking-agent-in-python) | The same agent with the loop handed to a framework — the direct comparison | Python, OpenAI Agents SDK, Supabase |
| [expense-tracker-agent-in-python](agents-sdk/expense-tracker-agent-in-python) | A different tool shape: aggregating over a date range rather than checking and reserving | Python, OpenAI Agents SDK, Supabase |

## Setup

Every project needs a `.env` in its own folder (see each `.env.example`):

```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

`SUPABASE_SECRET_KEY` must be the **secret** key (Supabase → Settings → API Keys), not the publishable one. RLS is enabled with no policies, so a publishable key reads zero rows _without raising an error_ — the tables look empty instead of forbidden. Every agent here refuses to start on a publishable key rather than let that happen quietly.

Then run that project's `schema.sql` in the Supabase SQL Editor. Each drops and recreates its tables, so re-running is safe while the schema is changing and destructive once it isn't. Both booking projects share the same tables — running either one covers both.

Install and run:

```bash
# Node
cd agents-sdk/appointment-booking-agent-in-js && npm install && npm start

# Python
cd agents-sdk/expense-tracker-agent-in-python
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # .venv/bin/ on macOS/Linux
.venv/Scripts/python agent.py
```

---

## The booking agents

A booking assistant that checks slot availability and reserves appointments. Built twice, on the same two tables, so the JS and Python versions can be read side by side.

**Data model** — `availability_slots` is every slot the business offers; `appointments` is the subset that is booked. A slot is open when it exists in the first and not the second. A composite foreign key stops a slot that was never offered from being booked, and a unique constraint on `(date, time)` prevents double booking even if two runs check availability at the same moment.

**Tools** — check availability, book a slot, and (Python only) list a day's open slots so the agent can offer alternatives instead of just saying no.

### Where the loop went

`agent.js` spells the loop out. In Python it lives inside `Runner.run()` — the model still makes several round trips, choosing each tool based on what the last returned. Asking for a taken slot produces three LLM calls and two chained tool calls. Inspect it with `result.raw_responses` (one entry per LLM call) and `result.new_items` (tool calls and their outputs).

| Hand-written in JS | Inside `Runner.run()` |
| --- | --- |
| `while (true)` | the SDK turn loop |
| `chat.completions.create(...)` | one entry in `result.raw_responses` |
| `if (!message.tool_calls?.length) return` | no tool calls, so the loop ends and `final_output` is set |
| `messages.push({role: "tool", ...})` | a `ToolCallOutputItem` is appended |
| loop guard on an unexpected stop reason | `max_turns` (default 10), raising `MaxTurnsExceeded` |

Tool definitions shrink too: the JS version hand-writes a JSON schema per tool, while `@function_tool` derives it from type hints and the docstring — which makes the docstring part of the interface, not a comment.

---

## expense-tracker-agent-in-python

Record expenses, summarise them by category, list recent ones — the same SDK as above pointed at a different problem, where the model resolves a phrase like "last month" into a date range before choosing a tool.

- Categories are constrained in the database and re-checked in the tool, so the model cannot invent one and split a report across `food` and `Food`.
- PostgREST has no `GROUP BY`, so the summary groups in Python. Twenty rows do not justify a database function.

## Notes worth keeping

- **Dates are injected into the prompt in local time.** The model has no idea what today is, and UTC (`toISOString()`) books a day early whenever the local date is already ahead.
- **`.env` is resolved against the file, not the working directory**, so an agent runs the same from any folder. Node uses the built-in `process.loadEnvFile()`; Python uses `python-dotenv`.
- **`supabase-py` raises on API errors**, while `supabase-js` returns an `{ data, error }` pair that is easy to ignore.
- Dependencies are pinned exactly, not with `^`.
s, unlike `supabase-js` which returns an `{ data, error }` pair. The tools let those propagate; the SDK reports them back to the model.
