import { createOpenAI } from "@ai-sdk/openai";
import { Output, streamText, type ModelMessage } from "ai";
import { CalendarResult, type CalendarResultT } from "./calendar.functions";

const INSTRUCTIONS = `You read Indian college academic calendars and extract the schedule for a hostel mess-booking agent.
Return:
- working_weekdays: weekday numbers that are normally class days (0=Mon ... 6=Sun).
- holidays: every date (YYYY-MM-DD) with no classes that falls on a normal working weekday: public holidays, festivals, vacations/breaks (expand ranges into each date), exam-free/study days marked as holidays.
- extra_working_days: dates that are normally off (e.g. a Sunday or second Saturday) but declared working.
- notes: short notes about anything ambiguous (e.g. "2nd & 4th Saturdays off" - also list those Saturdays as holidays).
Use the given year when the calendar omits it. Never invent dates that are not in the calendar.`;

type In = { text: string; file: { name: string; mediaType: string; base64: string } | null; year: number };

export async function runExtraction(data: In): Promise<{ ok: true; result: CalendarResultT } | { ok: false; error: string }> {
  const apiKey = process.env["LOVABLE_API_KEY"];
  if (!apiKey) return { ok: false, error: "AI is not configured." };
  if (!data.text.trim() && !data.file) return { ok: false, error: "Paste the calendar or upload a file first." };

  const content: Exclude<ModelMessage["content"], string> = [
    { type: "text", text: `Default year: ${data.year}.\n\n${data.text || "(calendar attached as file)"}` },
  ] as never;
  if (data.file) {
    const isImage = data.file.mediaType.startsWith("image/");
    (content as unknown[]).push(
      isImage
        ? { type: "image", image: data.file.base64, mediaType: data.file.mediaType }
        : { type: "file", data: data.file.base64, mediaType: data.file.mediaType, filename: data.file.name },
    );
  }

  const provider = createOpenAI({
    baseURL: "https://ai.gateway.lovable.dev/v1",
    apiKey,
    headers: { "Lovable-API-Key": apiKey, "X-Lovable-AIG-SDK": "vercel-ai-sdk" },
  });
  try {
    let streamError: unknown = null;
    const result = streamText({
      model: provider.responses("openai/gpt-6-astra"),
      instructions: INSTRUCTIONS,
      messages: [{ role: "user", content } as ModelMessage],
      output: Output.object({ schema: CalendarResult }),
      maxRetries: 1,
      onError: ({ error }) => {
        streamError = error;
      },
      providerOptions: {
        openai: {
          forceReasoning: true,
          reasoningEffort: "low",
          reasoningSummary: "auto",
          store: false,
          include: ["reasoning.encrypted_content"],
        },
      },
    });
    const out = await result.output;
    if (streamError) throw streamError;
    out.holidays.sort((a, b) => a.date.localeCompare(b.date));
    return { ok: true, result: out };
  } catch (e) {
    const status = (e as { statusCode?: number }).statusCode;
    if (status === 402) return { ok: false, error: "AI credits have run out. Add credits to keep using this." };
    if (status === 429) return { ok: false, error: "Too many requests right now. Try again in a minute." };
    console.error("calendar extraction failed", e);
    return { ok: false, error: "Couldn't read that calendar. Try a clearer photo or paste the text." };
  }
}
