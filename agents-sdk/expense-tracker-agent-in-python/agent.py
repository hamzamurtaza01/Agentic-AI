"""Expense tracker agent, built on the OpenAI Agents SDK.

The SDK owns the agent loop: it decides when to call a tool, runs it, feeds
the result back, and repeats until the model has an answer. Compare with
../appointment-booking-agent, where that loop is written out by hand.
"""

import asyncio
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
from supabase import Client, create_client

# Resolved against this file, not the working directory, so the agent runs
# the same from anywhere.
load_dotenv(Path(__file__).with_name(".env"))

SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase: Client = create_client(os.environ["SUPABASE_URL"], SUPABASE_SECRET_KEY)

CATEGORIES = ("food", "transport", "shopping", "bills", "health", "other")


# The docstring is not decoration: the SDK turns it into the tool description
# and the per-argument schema the model sees. Type hints become the types.
@function_tool
def add_expense(amount: float, category: str, description: str, spent_on: str) -> str:
    """Record a new expense.

    Args:
        amount: Amount spent, greater than zero.
        category: One of food, transport, shopping, bills, health, other.
        description: Short note about what was bought.
        spent_on: Date of the expense in YYYY-MM-DD format.
    """
    if category not in CATEGORIES:
        return f"Invalid category '{category}'. Valid: {', '.join(CATEGORIES)}."

    row = {
        "amount": amount,
        "category": category,
        "description": description,
        "spent_on": spent_on,
    }
    # supabase-py raises on API errors, so no error tuple to unpack here.
    supabase.table("expenses").insert(row).execute()
    return f"Recorded {amount:.2f} for {category} on {spent_on}."


@function_tool
def get_spending_summary(start_date: str, end_date: str) -> str:
    """Total spending per category between two dates, inclusive.

    Args:
        start_date: Start of the range in YYYY-MM-DD format.
        end_date: End of the range in YYYY-MM-DD format.
    """
    rows = (
        supabase.table("expenses")
        .select("amount, category")
        .gte("spent_on", start_date)
        .lte("spent_on", end_date)
        .execute()
        .data
    )
    if not rows:
        return f"No expenses recorded between {start_date} and {end_date}."

    # PostgREST has no GROUP BY, and twenty rows do not justify a database
    # function, so the grouping happens here.
    totals = defaultdict(float)
    for row in rows:
        totals[row["category"]] += float(row["amount"])

    lines = [f"  {cat}: {amt:.2f}" for cat, amt in sorted(totals.items(), key=lambda kv: -kv[1])]
    return "\n".join(
        [f"Spending from {start_date} to {end_date} (total {sum(totals.values()):.2f}):", *lines]
    )


@function_tool
def list_recent_expenses(limit: int) -> str:
    """List the most recent expenses, newest first.

    Args:
        limit: How many expenses to return, at most 20.
    """
    rows = (
        supabase.table("expenses")
        .select("spent_on, amount, category, description")
        .order("spent_on", desc=True)
        .limit(min(limit, 20))
        .execute()
        .data
    )
    if not rows:
        return "No expenses recorded yet."
    return "\n".join(
        f"  {r['spent_on']}  {float(r['amount']):>8.2f}  {r['category']:<9} {r['description'] or ''}"
        for r in rows
    )


def build_agent() -> Agent:
    # The model has no notion of the current date, and every relative phrase
    # ("last month", "this week") depends on it. Local time, not UTC: using
    # UTC records an expense a day early whenever the local date is ahead.
    today = date.today()
    return Agent(
        name="Expense tracker",
        instructions=(
            "You help the user track personal spending. "
            f"Today is {today.isoformat()} and this month began on "
            f"{today.replace(day=1).isoformat()}. "
            f"Last month ran from "
            f"{(today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()} to "
            f"{(today.replace(day=1) - timedelta(days=1)).isoformat()}. "
            f"Valid categories are {', '.join(CATEGORIES)}; map anything the "
            "user says onto one of these. Amounts are in PKR. "
            "Resolve relative dates yourself before calling a tool."
        ),
        tools=[add_expense, get_spending_summary, list_recent_expenses],
        model="gpt-4o-mini",
    )


async def main() -> None:
    result = await Runner.run(build_agent(), "Give me a summary of my spending last month, and compare it to this month.")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
