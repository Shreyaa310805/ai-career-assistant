import { AppShell } from "@/components/app-shell";
import { ApplicationForm } from "@/components/application-form";
import { Card, SectionHeading } from "@/components/ui";

export default function NewApplication() {
  return (
    <AppShell>
      <main className="mx-auto max-w-3xl px-5 py-8 sm:px-8">
        <SectionHeading
          eyebrow="New application"
          title="Add an opportunity"
          description="Create a dedicated workspace for this role."
        />
        <Card className="mt-8 p-6 sm:p-8">
          <ApplicationForm />
        </Card>
      </main>
    </AppShell>
  );
}
