"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Alert, Badge, Button, Card, LinkButton, SectionHeading } from "@/components/ui";
import { checkout, formatPrice, getPlan, type PlanDetails } from "@/lib/billing";

const PREMIUM_FEATURES = [
  "Unlimited tracked applications with company, role, dates and status",
  "A dedicated workspace per role",
  "Resume versions, comparison and best-version selection",
  "Skill gap analysis with ranked priorities",
  "Career roadmap and curated learning resources",
  "What-if simulation of your match score",
];

export default function UpgradePage() {
  const router = useRouter();
  const [plan, setPlan] = useState<PlanDetails | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getPlan().then(setPlan).catch(() => setPlan(null));
  }, []);

  async function pay() {
    setBusy(true);
    setError("");
    try {
      const result = await checkout();
      setDone(true);
      setPlan((current) => (current ? { ...current, plan: result.user.plan } : current));
      // Let the confirmation register before moving on.
      setTimeout(() => router.push("/applications"), 1400);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to complete the upgrade.");
    } finally {
      setBusy(false);
    }
  }

  const isPremium = plan?.plan === "PREMIUM";
  const price = plan ? formatPrice(plan.price_cents, plan.currency) : "$19";

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl px-5 py-8 sm:px-8">
        <div className="mb-6">
          <SectionHeading
            eyebrow="Plans"
            title="Upgrade to Premium"
            description="Unlock the application tracker and every role-specific analysis tool."
          />
        </div>

        <Alert tone="info">
          <b>Simulated checkout.</b> This build has no payment processor connected. Selecting
          &ldquo;Pay&rdquo; records a mock transaction and switches your account to Premium immediately.
          No card details are requested, sent or stored.
        </Alert>

        <div className="mt-6 grid gap-6 md:grid-cols-[1.15fr_1fr]">
          <Card className="p-7">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Premium</h2>
                <p className="mt-1 text-sm text-slate-500">One-time upgrade for this account.</p>
              </div>
              <Badge tone={isPremium ? "success" : "brand"}>{isPremium ? "Active" : "Recommended"}</Badge>
            </div>

            <p className="mt-6 text-4xl font-bold tracking-tight">
              {price}
              <span className="text-base font-medium text-slate-500"> one-time</span>
            </p>

            <ul className="mt-6 space-y-2.5">
              {PREMIUM_FEATURES.map((feature) => (
                <li key={feature} className="flex gap-2.5 text-sm text-slate-700">
                  <span aria-hidden className="mt-0.5 text-emerald-600">✓</span>
                  {feature}
                </li>
              ))}
            </ul>
          </Card>

          <Card className="h-fit p-7">
            {isPremium || done ? (
              <div className="text-center">
                <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-emerald-50 text-xl text-emerald-600">
                  ✓
                </div>
                <h2 className="mt-4 text-lg font-semibold">You are on Premium</h2>
                <p className="mt-2 text-sm text-slate-500">
                  The application tracker and every workspace tool are unlocked.
                </p>
                <LinkButton href="/applications" className="mt-6 w-full">
                  Go to applications
                </LinkButton>
              </div>
            ) : (
              <>
                <h2 className="text-lg font-semibold">Checkout</h2>
                <dl className="mt-5 space-y-2.5 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Premium plan</dt>
                    <dd className="font-medium tabular-nums">{price}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Payment method</dt>
                    <dd className="font-medium">Simulated</dd>
                  </div>
                  <div className="flex justify-between border-t border-line pt-2.5">
                    <dt className="font-semibold">Total</dt>
                    <dd className="font-semibold tabular-nums">{price}</dd>
                  </div>
                </dl>

                {error ? (
                  <div className="mt-5">
                    <Alert>{error}</Alert>
                  </div>
                ) : null}

                <Button size="lg" onClick={pay} disabled={busy} className="mt-6 w-full">
                  {busy ? "Processing…" : `Pay ${price} — simulated`}
                </Button>
                <p className="mt-3 text-center text-xs text-slate-500">
                  No card is required and none is collected.
                </p>
              </>
            )}
          </Card>
        </div>
      </main>
    </AppShell>
  );
}
