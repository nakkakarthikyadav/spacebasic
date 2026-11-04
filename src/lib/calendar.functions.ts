import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

const Input = z.object({
  text: z.string().max(60000).default(""),
  file: z
    .object({ name: z.string(), mediaType: z.string(), base64: z.string().max(14_000_000) })
    .nullable()
    .default(null),
  year: z.number().int().min(2020).max(2100),
});

export const CalendarResult = z.object({
  working_weekdays: z.array(z.number().int().min(0).max(6)),
  holidays: z.array(z.object({ date: z.string(), name: z.string() })),
  extra_working_days: z.array(z.object({ date: z.string(), name: z.string() })),
  notes: z.string(),
});
export type CalendarResultT = z.infer<typeof CalendarResult>;

export const extractCalendar = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => Input.parse(d))
  .handler(async ({ data }) => {
    const { runExtraction } = await import("./calendar.server");
    return runExtraction(data);
  });
