import OpenAI from "openai";
import { createClient } from "@supabase/supabase-js";
import { fileURLToPath } from "node:url";

// Load the shared .env resolved against this file, not the working
// directory, so the agent runs the same from any cwd.
process.loadEnvFile(fileURLToPath(new URL("../.env", import.meta.url)));

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Server-side client. The secret key bypasses RLS, so it is loaded from
// the environment and must never reach the browser.
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SECRET_KEY,
);

const tools = [
  {
    type: "function",
    function: {
      name: "check_appointment_availability",
      description: "Check if a time slot is available for booking",
      parameters: {
        type: "object",
        properties: {
          date: { type: "string", description: "Date in YYYY-MM-DD format" },
          time: { type: "string", description: "Time in HH:MM format" },
        },
        required: ["date", "time"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "book_appointment",
      description: "Book an appointment slot",
      parameters: {
        type: "object",
        properties: {
          name: { type: "string" },
          date: { type: "string" },
          time: { type: "string" },
          service: { type: "string" },
        },
        required: ["name", "date", "time", "service"],
      },
    },
  },
];

async function executeTool(toolName, toolInput) {
  if (toolName === "check_appointment_availability") {
    // Ask both tables at once: does the slot exist, and is it taken?
    // supabase-js resolves with { data, error } rather than throwing,
    // so the errors have to be checked explicitly.
    const [slot, booked] = await Promise.all([
      supabase
        .from("availability_slots")
        .select("id")
        .eq("date", toolInput.date)
        .eq("time", toolInput.time),
      supabase
        .from("appointments")
        .select("id")
        .eq("date", toolInput.date)
        .eq("time", toolInput.time),
    ]);
    if (slot.error) throw new Error(slot.error.message);
    if (booked.error) throw new Error(booked.error.message);

    if (slot.data.length === 0)
      return "Not offered - the business has no slot at that date and time";
    return booked.data.length === 0 ? "Available" : "Booked";
  }

  if (toolName === "book_appointment") {
    const { error } = await supabase.from("appointments").insert([toolInput]);
    if (error) throw new Error(error.message);
    return `Appointment booked for ${toolInput.name}`;
  }

  throw new Error(`Unknown tool: ${toolName}`);
}

async function runAgent(userMessage) {
  const messages = [
    // The model has no notion of the current date. Supplying it lets
    // relative dates such as "tomorrow" resolve correctly.
    {
      role: "system",
      content: `You are an appointment booking assistant. Today is ${
        new Date().toISOString().split("T")[0]
      }. Always check availability before booking.`,
    },
    { role: "user", content: userMessage },
  ];

  while (true) {
    const response = await client.chat.completions.create({
      model: "gpt-4o-mini",
      messages,
      tools,
    });

    const message = response.choices[0].message;

    // No tool calls means the model has produced its final answer.
    if (!message.tool_calls?.length) return message.content ?? "";

    messages.push(message);

    // A single turn may contain several tool calls. Each one requires its
    // own "tool" message in the reply, keyed by tool_call_id.
    for (const call of message.tool_calls) {
      let content;
      try {
        // `arguments` arrives as a JSON string, not an object.
        content = await executeTool(
          call.function.name,
          JSON.parse(call.function.arguments),
        );
      } catch (err) {
        // Report failures back to the model. Omitting a response for a
        // pending tool call causes the next request to fail with a 400.
        content = `Error: ${err.message}`;
      }
      messages.push({ role: "tool", tool_call_id: call.id, content });
    }
  }
}

// Example run
const result = await runAgent("I wanna book an appointment for a head massage today at 3:30pm. My name is John Doe.");
console.log(result);
