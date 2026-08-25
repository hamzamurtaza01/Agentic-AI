"""Appointment booking agent, built on the OpenAI Agents SDK.

The SDK owns the agent loop: it decides when to call a tool, runs it, feeds
the result back, and repeats until the model has an answer. Compare with
../appointment-booking-agent-in-js, where that loop is written out by hand.
"""

import asyncio
import os
import datetime
from pathlib import Path

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
from supabase import Client, create_client

# Resolved against this file, not the working directory, so the agent runs
# the same from anywhere.
load_dotenv(Path(__file__).with_name(".env"))

SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase: Client = create_client(os.environ["SUPABASE_URL"], SUPABASE_SECRET_KEY)


# The docstring is not decoration: the SDK turns it into the tool description
# and the per-argument schema the model sees. Type hints become the types.
@function_tool
def check_availability(date: str, time: str) -> str:
    """Check if a time slot is available for booking.

    Args:
        date: Date of the appointment in YYYY-MM-DD format.
        time: Time of the appointment in HH:MM format.
    """
    # Two questions, not one: does the business offer this slot at all, and
    # has someone already taken it? Checking only appointments would report
    # 3am on a closed day as available.
    slot = (
        supabase.table("availability_slots")
        .select("id")
        .eq("date", date)
        .eq("time", time)
        .execute()
        .data
    )
    if not slot:
        return f"The business has no slot at {date} {time}. It is not offered."

    booked = (
        supabase.table("appointments")
        .select("id")
        .eq("date", date)
        .eq("time", time)
        .execute()
        .data
    )
    if booked:
        return f"Sorry, {date} at {time} is already booked."
    return f"{date} at {time} is available for booking."


@function_tool
def book_appointment(date: str, time: str, name: str, service: str) -> str:
    """Book an appointment.

    Args:
        date: Date of the appointment in YYYY-MM-DD format.
        time: Time of the appointment in HH:MM format.
        name: Name of the person booking the appointment.
        service: Type of service requested.
    """
    row = {"date": date, "time": time, "name": name, "service": service}
    # supabase-py raises on API errors, so no error tuple to unpack here.
    # A unique constraint on (date, time) means a slot taken between the
    # availability check and this insert fails here rather than double books.
    supabase.table("appointments").insert(row).execute()
    return f"Appointment booked for {name} on {date} at {time} for {service}."


@function_tool
def list_open_slots(date: str) -> str:
    """List every free slot on a given day, so an alternative can be offered.

    Args:
        date: Date to look at, in YYYY-MM-DD format.
    """
    slots = (
        supabase.table("availability_slots")
        .select("time")
        .eq("date", date)
        .order("time")
        .execute()
        .data
    )
    if not slots:
        return f"The business is not open on {date}."

    booked = (
        supabase.table("appointments").select("time").eq("date", date).execute().data
    )
    taken = {row["time"] for row in booked}
    free = [row["time"] for row in slots if row["time"] not in taken]
    if not free:
        return f"Every slot on {date} is booked."
    return f"Open slots on {date}: {', '.join(free)}"


def build_agent() -> Agent:
    # The model has no notion of the current date, and every relative phrase
    # ("tomorrow", "next Tuesday") depends on it. Local time, not UTC: using
    # UTC books a day early whenever the local date is already ahead.
    today = datetime.date.today()
    return Agent(
        name="Appointment booking agent",
        instructions=(
            "You are an appointment booking assistant. "
            f"Today is {today.isoformat()}, a {today.strftime('%A')}. "
            "Resolve relative dates yourself before calling a tool. "
            "Always check availability before booking. If the slot is taken "
            "or not offered, call list_open_slots and suggest alternatives "
            "rather than booking something the customer did not ask for. "
            "Ask for the customer's name if they have not given one."
        ),
        tools=[check_availability, book_appointment, list_open_slots],
        model="gpt-4o-mini",
    )


async def main() -> None:
    result = await Runner.run(
        build_agent(),
        "Book me a haircut tomorrow at 9:00 AM. My name is Hamza.",
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
