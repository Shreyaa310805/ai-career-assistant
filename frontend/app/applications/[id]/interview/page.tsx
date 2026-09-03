"use client";

import { useParams } from "next/navigation";
import { Badge, Card, LinkButton } from "@/components/ui";

const PLANNED = [
  "Question sets generated from this job description and your resume",
  "Follow-up probes on the gaps the skill-gap tool found",
  "Answer notes stored against this application",
  "A rehearsal timer with per-question pacing",
];

export default function InterviewPage() {
  const params = useParams<{ id: string }>();

  return (
    <Card className="p-8 text-center">
      <Badge>Coming soon</Badge>
      <h2 className="mt-4 text-xl font-bold tracking-tight">Interview preparation is not built yet</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
        Rather than show generated filler, this tab stays empty until the feature is real. Here is what it will
        do when it ships.
      </p>

      <ul className="mx-auto mt-6 max-w-md space-y-2.5 text-left">
        {PLANNED.map((item) => (
          <li key={item} className="flex gap-2.5 text-sm text-slate-600">
            <span aria-hidden className="mt-0.5 text-slate-300">
              ○
            </span>
            {item}
          </li>
        ))}
      </ul>

      <p className="mt-8 text-sm text-slate-500">In the meantime, the skill gap is the best interview prep.</p>
      <div className="mt-4">
        <LinkButton href={`/applications/${params?.id}/skill-gap`} variant="secondary" size="sm">
          Open skill gap
        </LinkButton>
      </div>
    </Card>
  );
}
