"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Alert, Button, Field, Select, Textarea } from "@/components/ui";
import {
  STATUS_LABEL,
  STATUS_ORDER,
  createApplication,
  updateApplication,
  type Application,
} from "@/lib/applications";

export function ApplicationForm({
  application,
  onSaved,
}: {
  application?: Application;
  onSaved?: (application: Application) => void;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");

    const form = new FormData(event.currentTarget);
    const value = (name: string) => String(form.get(name) || "").trim();
    const input = {
      company: value("company"),
      role: value("role"),
      status: value("status") as Application["status"],
      location: value("location") || null,
      job_url: value("job_url") || null,
      job_description: value("job_description") || null,
      applied_at: value("applied_at") || null,
    };

    try {
      const result = application
        ? await updateApplication(application.id, input)
        : await createApplication(input);
      if (onSaved) onSaved(result);
      else router.replace(`/applications/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save this application.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Company">
          <input className="field" name="company" required maxLength={160} defaultValue={application?.company} />
        </Field>

        <Field label="Job role">
          <input className="field" name="role" required maxLength={160} defaultValue={application?.role} />
        </Field>

        <Field label="Status">
          <Select name="status" defaultValue={application?.status ?? "SAVED"}>
            {STATUS_ORDER.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABEL[status]}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Application date">
          <input className="field" name="applied_at" type="date" defaultValue={application?.applied_at ?? ""} />
        </Field>

        <Field label="Location">
          <input
            className="field"
            name="location"
            maxLength={160}
            defaultValue={application?.location ?? ""}
            placeholder="e.g. Remote, Bengaluru"
          />
        </Field>

        <Field label="Job link">
          <input
            className="field"
            name="job_url"
            type="url"
            defaultValue={application?.job_url ?? ""}
            placeholder="https://…"
          />
        </Field>
      </div>

      <Field
        label="Job description"
        hint="Pasting the full posting here means the ATS and skill-gap tools can use it without re-entry."
      >
        <Textarea
          name="job_description"
          rows={8}
          maxLength={20000}
          defaultValue={application?.job_description ?? ""}
          placeholder="Paste the requirements, qualifications and responsibilities."
        />
      </Field>

      {error ? <Alert>{error}</Alert> : null}

      <Button type="submit" disabled={busy}>
        {busy ? "Saving…" : application ? "Save changes" : "Create application"}
      </Button>
    </form>
  );
}
