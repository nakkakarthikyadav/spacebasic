import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

// Read-only on purpose: the app has no login, so it never writes to GitHub.
const REPO = "nakkakarthikyadav/spacebasic";

export type IssueT = {
  number: number;
  title: string;
  state: string;
  url: string;
  user: string;
  labels: string[];
  comments: number;
  updated_at: string;
};

export const listIssues = createServerFn({ method: "GET" })
  .inputValidator((d: unknown) => z.object({ state: z.enum(["open", "closed", "all"]) }).parse(d))
  .handler(async ({ data }): Promise<{ repo: string; issues: IssueT[]; error?: string }> => {
    const lk = process.env["LOVABLE_API_KEY"];
    const gk = process.env["GITHUB_API_KEY"];
    if (!lk || !gk) return { repo: REPO, issues: [], error: "GitHub is not connected." };
    const res = await fetch(
      `https://connector-gateway.lovable.dev/github/repos/${REPO}/issues?state=${data.state}&per_page=50`,
      { headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${lk}`, "X-Connection-Api-Key": gk } },
    );
    if (!res.ok) {
      const body = await res.text();
      console.error(`GitHub issues failed [${res.status}]: ${body}`);
      return { repo: REPO, issues: [], error: `GitHub returned ${res.status}` };
    }
    const json = (await res.json()) as any[];
    return {
      repo: REPO,
      issues: json
        .filter((i) => !i.pull_request)
        .map((i) => ({
          number: i.number,
          title: i.title,
          state: i.state,
          url: i.html_url,
          user: i.user?.login ?? "",
          labels: (i.labels ?? []).map((l: any) => l.name),
          comments: i.comments,
          updated_at: i.updated_at,
        })),
    };
  });
