"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApplicationForm } from "@/components/application-form";
import { Button, Card, CardHeader, LinkButton, Skeleton } from "@/components/ui";
import { deleteApplication, getApplication, type Application } from "@/lib/applications";

export default function ApplicationOverview() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;
  const [app, setApp] = useState<Application | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (id) getApplication(id).then(setApp).catch(() => setApp(null));
  }, [id]);

  async function remove() {
    if (!id || !confirm("Delete this application? Its resume versions and analyses stay linked to it.")) return;
    await deleteApplication(id);
    router.replace("/applications");
  }

  if (!app) return <Skeleton className="h-72" />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Application details"
          description="Company, role, status and the job description this workspace analyses against."
          action={
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setEditing((value) => !value)}>
                {editing ? "Cancel" : "Edit"}
              </Button>
              <Button variant="danger" size="sm" onClick={remove}>
                Delete
              </Button>
            </div>
          }
        />
        <div className="p-6">
          {editing ? (
            <ApplicationForm
              application={app}
              onSaved={(updated) => {
                setApp(updated);
                setEditing(false);
                router.refresh();
              }}
            />
          ) : (
            <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
              <Detail label="Company" value={app.company} />
              <Detail label="Job role" value={app.role} />
              <Detail label="Location" value={app.location} />
              <Detail
                label="Application date"
                value={app.applied_at ? new Date(app.applied_at).toLocaleDateString() : null}
              />
              <div className="sm:col-span-2">
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">Job link</dt>
                <dd className="mt-1 text-sm">
                  {app.job_url ? (
                    <a
                      href={app.job_url}
                      target="_blank"
                      rel="noreferrer"
                      className="break-all font-medium text-brand-600 hover:text-brand-700"
                    >
                      {app.job_url}
                    </a>
                  ) : (
                    <span className="text-slate-400">Not set</span>
                  )}
                </dd>
              </div>
            </dl>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Job description"
          description="Used by the ATS, skill gap and roadmap tools in this workspace."
          action={
            app.job_description ? undefined : (
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                Add one
              </Button>
            )
          }
        />
        <div className="p-6">
          {app.job_description ? (
            <p className="whitespace-pre-wrap text-sm leading-6 text-slate-600">{app.job_description}</p>
          ) : (
            <p className="text-sm text-slate-500">
              No job description saved yet. Adding it here means you will not have to paste it into each tool.
            </p>
          )}
        </div>
      </Card>

      <Card className="bg-surface-muted/60 p-6">
        <h2 className="text-[15px] font-semibold">Next step</h2>
        <p className="mt-1.5 text-sm text-slate-500">
          Upload a resume and run an ATS analysis — the skill gap, roadmap and what-if tools all build on it.
        </p>
        <LinkButton href={`/applications/${app.id}/ats`} size="sm" className="mt-4">
          Go to Resume &amp; ATS
        </LinkButton>
      </Card>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm text-slate-800">{value || <span className="text-slate-400">Not set</span>}</dd>
    </div>
  );
}
