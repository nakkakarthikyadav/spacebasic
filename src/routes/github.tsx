import { createFileRoute, Link } from "@tanstack/react-router";
import { queryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listIssues } from "@/lib/github.functions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type State = "open" | "closed" | "all";
const issuesQuery = (state: State) =>
  queryOptions({ queryKey: ["gh-issues", state], queryFn: () => listIssues({ data: { state } }) });

export const Route = createFileRoute("/github")({
  head: () => ({
    meta: [
      { title: "GitHub Issues - spacebasic repo" },
      { name: "description", content: "Read-only view of issues in the spacebasic GitHub repository." },
      { property: "og:title", content: "GitHub Issues - spacebasic repo" },
      { property: "og:description", content: "See open and closed issues from the spacebasic repository." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  loader: ({ context }) => context.queryClient.ensureQueryData(issuesQuery("open")),
  component: GithubPage,
});

function GithubPage() {
  const [state, setState] = useState<State>("open");
  return (
    <main className="mx-auto max-w-3xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">GitHub issues</h1>
        <Link to="/" className="text-sm underline text-muted-foreground">Back to calendar</Link>
      </div>
      <div className="flex gap-2">
        {(["open", "closed", "all"] as State[]).map((s) => (
          <Button key={s} size="sm" variant={s === state ? "default" : "outline"} onClick={() => setState(s)}>
            {s}
          </Button>
        ))}
      </div>
      <IssueList state={state} />
    </main>
  );
}

function IssueList({ state }: { state: State }) {
  const { data } = useSuspenseQuery(issuesQuery(state));
  if (data.error) return <p className="text-destructive">{data.error}</p>;
  if (!data.issues.length) return <p className="text-muted-foreground">No {state} issues in {data.repo}.</p>;
  return (
    <ul className="divide-y rounded-lg border">
      {data.issues.map((i) => (
        <li key={i.number} className="p-3 space-y-1">
          <a href={i.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
            #{i.number} {i.title}
          </a>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground items-center">
            <Badge variant={i.state === "open" ? "default" : "secondary"}>{i.state}</Badge>
            <span>by {i.user}</span>
            <span>{i.comments} comments</span>
            <span>updated {new Date(i.updated_at).toLocaleDateString()}</span>
            {i.labels.map((l) => <Badge key={l} variant="outline">{l}</Badge>)}
          </div>
        </li>
      ))}
    </ul>
  );
}
