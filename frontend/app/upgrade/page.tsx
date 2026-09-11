"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Alert, Button, Card, LinkButton, SectionHeading } from "@/components/ui";
import { cancelSubscription, checkout, formatPrice, getCatalog, getPlan, syncPlan, type Catalog, type PlanDetails } from "@/lib/billing";

export default function UpgradePage() {
  const [plan, setPlan] = useState<PlanDetails | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(action: () => Promise<PlanDetails>) {
    setBusy(true); setError("");
    try { setPlan(await action()); window.dispatchEvent(new Event("plan-changed")); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to update your plan"); }
    finally { setBusy(false); }
  }
  useEffect(() => { getPlan().then(setPlan).catch(e => setError(e.message)); }, []);
  useEffect(() => { getCatalog().then(setCatalog).catch(e => setError(e.message)); }, []);
  return <AppShell><main className="mx-auto max-w-3xl space-y-6 px-5 py-8">
    <SectionHeading eyebrow="Plans" title="SkillSync Pro" description="Interview sessions, premium reports, and the full career toolkit." />
    <Alert tone="info">Razorpay TEST checkout. Use test payment details; no real money is charged. The monthly price is shown in checkout.</Alert>
    {error && <Alert>{error}</Alert>}
    <Card className="space-y-5 p-7">
      <h2 className="text-xl font-semibold">{plan?.plan === "PREMIUM" ? "Pro activated" : "Upgrade to Pro"}</h2>
      <p>One credit starts one interview. Questions and answers within that session use no additional credits. Each successful renewal resets your allowance for the billing period.</p>
      {plan?.plan === "PREMIUM" ? <>
        <p className="text-3xl font-bold">{plan.credits}/{plan.credit_limit} credits</p>
        {plan.pro_until && <p>Access through {new Date(plan.pro_until).toLocaleString()}.</p>}
        <LinkButton href="/interview">Start interview</LinkButton>
        {plan.cancel_at_cycle_end ? <Alert tone="info">Renewal cancelled. Pro stays available until the end of your paid period.</Alert> : plan.subscription_id &&
          <Button disabled={busy} variant="secondary" onClick={() => run(cancelSubscription)}>Cancel renewal</Button>}
      </> : <>
        <p>Free includes one lifetime interview trial with up to {plan?.trial_question_limit ?? catalog?.trial_question_limit ?? "a limited number of"} questions. Trial sessions have no final report.</p>
        {plan && !plan.configured && <Alert>Razorpay TEST settings are not configured on the backend yet.</Alert>}
        {catalog?.plans.map(option => <div key={option.interval} className="rounded-lg border border-line p-4 space-y-3">
          <p className="font-semibold">Pro {option.interval} — {option.credits} interview credits per billing period</p>
          {option.amount !== null && option.currency && <p>{formatPrice(option.amount, option.currency)} / {option.interval === "monthly" ? "month" : "year"}</p>}
          <Button disabled={busy || !option.available} onClick={() => run(() => checkout(option.interval))}>
            {option.available ? `Upgrade ${option.interval} — TEST checkout` : `${option.interval === "yearly" ? "Yearly" : "Monthly"} plan unavailable`}
          </Button>
        </div>)}
        {plan?.subscription_id && <Button variant="secondary" disabled={busy} onClick={() => run(cancelSubscription)}>Cancel unfinished checkout</Button>}
        <LinkButton href="/interview" variant="secondary">Interview practice</LinkButton>
      </>}
      <Button variant="ghost" disabled={busy} onClick={() => run(syncPlan)}>Refresh plan</Button>
    </Card>
  </main></AppShell>;
}
