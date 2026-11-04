import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { extractCalendar, type CalendarResultT } from "@/lib/calendar.functions";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Mess Calendar - set your meal booking days" },
      { name: "description", content: "Upload or paste your college calendar and AI finds working days and holidays for your SpaceBasic meal agent." },
      { property: "og:title", content: "Mess Calendar - set your meal booking days" },
      { property: "og:description", content: "Turn your college calendar into a meal booking schedule in seconds." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
type Row = { date: string; name: string; keep: boolean };

function toBase64(f: File) {
  return new Promise<string>((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1] ?? "");
    r.onerror = rej;
    r.readAsDataURL(f);
  });
}

function Index() {
  const extract = useServerFn(extractCalendar);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [weekdays, setWeekdays] = useState<number[] | null>(null);
  const [holidays, setHolidays] = useState<Row[]>([]);
  const [extra, setExtra] = useState<Row[]>([]);
  const [notes, setNotes] = useState("");
  const [copied, setCopied] = useState(false);

  async function run() {
    setBusy(true);
    setError("");
    try {
      let filePayload = null;
      if (file) {
        if (!(file.type.startsWith("text/") || /\.(txt|csv|ics|md)$/i.test(file.name))) {
          filePayload = { name: file.name, mediaType: file.type || "application/pdf", base64: await toBase64(file) };
        }
      }
      const fileText = file && !filePayload ? await file.text() : "";
      const res = await extract({ data: { text: [text, fileText].filter(Boolean).join("\n\n"), file: filePayload, year: new Date().getFullYear() } });
      if (!res.ok) return setError(res.error);
      const r: CalendarResultT = res.result;
      setWeekdays(r.working_weekdays);
      setHolidays(r.holidays.map((h) => ({ ...h, keep: true })));
      setExtra(r.extra_working_days.map((h) => ({ ...h, keep: true })));
      setNotes(r.notes);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const schedule = useMemo(
    () =>
      weekdays && {
        working_weekdays: [...weekdays].sort(),
        holidays: holidays.filter((h) => h.keep).map((h) => h.date),
        extra_working_days: extra.filter((h) => h.keep).map((h) => h.date),
      },
    [weekdays, holidays, extra],
  );

  function download() {
    const blob = new Blob([JSON.stringify(schedule, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "schedule.json";
    a.click();
  }

  return (
    <main className="min-h-screen bg-background text-foreground font-sans">
      <div className="mx-auto max-w-3xl px-5 py-12">
        <p className="text-sm font-bold uppercase tracking-widest text-primary">SpaceBasic meal agent</p>
        <h1 className="mt-2 font-display text-4xl font-extrabold leading-tight md:text-5xl">
          Tell the agent when college is on.
        </h1>
        <p className="mt-3 max-w-xl text-muted-foreground">
          Upload a photo or PDF of your academic calendar, or paste it. AI picks out working days and holidays. Check them, then give the result to your agent.
        </p>

        <section className="mt-8 rounded-2xl border border-border bg-card p-5 shadow-sm">
          <label className="block text-sm font-bold">Upload calendar (photo, PDF or text)</label>
          <input
            type="file"
            accept="image/*,application/pdf,.txt,.csv,.ics"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-2 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-2 file:font-bold file:text-accent-foreground"
          />
          <label className="mt-5 block text-sm font-bold">…or paste it</label>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} placeholder={"e.g.\n14 Nov - Children's Day (holiday)\n20-27 Dec - Winter break\n2nd & 4th Saturdays are holidays"} className="mt-2" />
          <Button onClick={run} disabled={busy || (!text.trim() && !file)} className="mt-4 w-full md:w-auto">
            {busy ? "Reading your calendar…" : "Find working days & holidays"}
          </Button>
          {error && <p className="mt-3 text-sm font-medium text-destructive">{error}</p>}
        </section>

        {weekdays && (
          <section className="mt-8 space-y-6">
            <div>
              <h2 className="font-display text-2xl font-bold">Review</h2>
              {notes && <p className="mt-1 text-sm text-muted-foreground">{notes}</p>}
            </div>
            <div>
              <h3 className="text-sm font-bold">Class days each week</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {DAYS.map((d, i) => {
                  const on = weekdays.includes(i);
                  return (
                    <button key={d} onClick={() => setWeekdays(on ? weekdays.filter((x) => x !== i) : [...weekdays, i])}
                      className={`rounded-full border px-4 py-1.5 text-sm font-bold ${on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground"}`}>
                      {d}
                    </button>
                  );
                })}
              </div>
            </div>
            <DateList title={`Holidays - no booking (${holidays.filter((h) => h.keep).length})`} rows={holidays} setRows={setHolidays} />
            {extra.length > 0 && <DateList title="Extra working days - book anyway" rows={extra} setRows={setExtra} />}
            <div className="rounded-2xl bg-secondary p-5 text-secondary-foreground">
              <p className="text-sm">Download this and put it in your agent folder (next to <b>meal_agent.py</b>). Or copy these lines into <b>config.json</b>.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={download}>Download schedule</Button>
                <Button variant="outline" onClick={async () => { await navigator.clipboard.writeText(JSON.stringify(schedule, null, 2).slice(1, -2) + ","); setCopied(true); }}>
                  {copied ? "Copied!" : "Copy for config.json"}
                </Button>
              </div>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function DateList({ title, rows, setRows }: { title: string; rows: Row[]; setRows: (r: Row[]) => void }) {
  const [d, setD] = useState("");
  return (
    <div>
      <h3 className="text-sm font-bold">{title}</h3>
      <ul className="mt-2 divide-y divide-border rounded-xl border border-border bg-card">
        {rows.map((r, i) => (
          <li key={r.date + i} className="flex items-center gap-3 px-4 py-2 text-sm">
            <input type="checkbox" checked={r.keep} onChange={() => setRows(rows.map((x, j) => (j === i ? { ...x, keep: !x.keep } : x)))} className="accent-primary" />
            <span className={`w-28 font-mono ${r.keep ? "" : "line-through text-muted-foreground"}`}>{r.date}</span>
            <span className="text-muted-foreground">{r.name}</span>
          </li>
        ))}
        <li className="flex items-center gap-2 px-4 py-2">
          <input type="date" value={d} onChange={(e) => setD(e.target.value)} className="rounded-md border border-input bg-background px-2 py-1 text-sm" />
          <Button size="sm" variant="ghost" disabled={!d} onClick={() => { setRows([...rows, { date: d, name: "Added by you", keep: true }].sort((a, b) => a.date.localeCompare(b.date))); setD(""); }}>Add date</Button>
        </li>
      </ul>
    </div>
  );
}
