"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Alert, Badge, Button, Card, LinkButton, SectionHeading } from "@/components/ui";
import {
  cancelSubscription,
  checkout,
  formatPrice,
  getCatalog,
  getPlan,
  syncPlan,
  verifyCheckout,
  type BillingInterval,
  type PlanCatalog,
  type PlanDetails,
} from "@/lib/billing";
import { getCurrentUser, type User } from "@/lib/auth";

type RazorpaySuccess = {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
};
type RazorpayOptions = {
  key: string;
  subscription_id: string;
  name: string;
  description: string;
  notes?: { user_id: string };
  prefill?: { name?: string; email?: string };
  theme: { color: string };
  handler: (response: RazorpaySuccess) => void | Promise<void>;
  modal: { ondismiss: () => void };
};
type RazorpayInstance = {
  open: () => void;
  on: (event: "payment.failed", callback: (response: { error?: { description?: string; reason?: string } }) => void) => void;
};
const razorpayConstructor = () =>
  (window as Window & { Razorpay?: new (options: RazorpayOptions) => RazorpayInstance }).Razorpay;

const PREMIUM_FEATURES = [
  "Unlimited tracked applications with company, role, dates and status",
  "A dedicated workspace per role",
  "Resume versions, comparison and best-version selection",
  "Skill gap analysis with ranked priorities",
  "Career roadmap and curated learning resources",
  "What-if simulation of your match score",
  "Role-specific interview preparation and reports",
];

async function loadRazorpay() {
  if (razorpayConstructor()) return;
  await new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[src="https://checkout.razorpay.com/v1/checkout.js"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Could not load Razorpay Checkout.")), { once: true });
      if (razorpayConstructor()) resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not load Razorpay Checkout."));
    document.body.appendChild(script);
  });
  if (!razorpayConstructor()) throw new Error("Razorpay Checkout did not initialize.");
}

export default function UpgradePage() {
  const [plan, setPlan] = useState<PlanDetails | null>(null);
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [interval, setInterval] = useState<BillingInterval>("monthly");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    const [currentPlan, currentCatalog] = await Promise.all([getPlan(), getCatalog()]);
    setPlan(currentPlan);
    setCatalog(currentCatalog);
    return currentPlan;
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([getPlan(), getCatalog(), getCurrentUser()])
      .then(([currentPlan, currentCatalog, currentUser]) => {
        if (!active) return;
        setPlan(currentPlan);
        setCatalog(currentCatalog);
        setUser(currentUser);
        if (currentPlan.subscription_status && currentPlan.interval) setInterval(currentPlan.interval);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load billing details.");
      });
    return () => { active = false; };
  }, []);

  const selected = catalog?.plans.find((item) => item.interval === interval);
  const price = formatPrice(selected?.amount, selected?.currency);
  const isPremium = plan?.plan === "PREMIUM";

  async function pay() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (plan?.provider === "simulated") {
        await checkout(interval);
        const updated = await refresh();
        setPlan(updated);
        setNotice("Simulated payment recorded. Premium is active for this account; no real payment was made.");
        return;
      }
      await loadRazorpay();
      const result = await checkout(interval);
      if (result.already_premium) {
        await refresh();
        setNotice("Premium is already active on your account.");
        return;
      }
      if (!result.key_id || !result.subscription_id) {
        throw new Error("Razorpay checkout is not configured for this plan. Check the server billing settings.");
      }
      const Razorpay = razorpayConstructor();
      if (!Razorpay) throw new Error("Razorpay Checkout is unavailable. Please reload and try again.");
      const checkoutModal = new Razorpay({
        key: result.key_id,
        subscription_id: result.subscription_id,
        name: "SkillSync",
        description: `${interval === "monthly" ? "Monthly" : "Yearly"} Premium subscription`,
        notes: user?.id ? { user_id: user.id } : undefined,
        prefill: user ? { name: user.name, email: user.email } : undefined,
        theme: { color: "#4f46e5" },
        handler: async (response) => {
          setBusy(true);
          setError("");
          try {
            if (response.razorpay_subscription_id !== result.subscription_id) {
              throw new Error("The returned subscription did not match this checkout.");
            }
            const updated = await verifyCheckout(response);
            setPlan(updated);
            if (updated.plan === "PREMIUM") {
              setNotice("Payment verified. Premium is active on your account.");
            } else {
              setNotice("Payment received. Razorpay is confirming the subscription; check the status in a moment.");
            }
          } catch (err) {
            setError(err instanceof Error ? err.message : "Payment verification is still pending.");
            setNotice("Your checkout completed, but the server has not confirmed access yet. Use Check status below.");
          } finally {
            setBusy(false);
          }
        },
        modal: { ondismiss: () => setBusy(false) },
      });
      checkoutModal.on("payment.failed", (response) => {
        setError(response.error?.description || response.error?.reason || "Payment failed. Please try another method.");
        setBusy(false);
      });
      checkoutModal.open();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start checkout.");
      setBusy(false);
    }
  }

  async function checkStatus() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await syncPlan();
      setPlan(updated);
      setNotice(updated.plan === "PREMIUM" ? "Premium is active." : "No completed payment was found yet. If you just paid, wait briefly and check again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh payment status.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setPlan(await cancelSubscription());
      setNotice("Subscription cancellation updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the subscription.");
    } finally {
      setBusy(false);
    }
  }

  const unfinishedStatuses = ["created", "authenticated", "active", "pending", "halted"];
  const pending = Boolean(plan?.subscription_status && unfinishedStatuses.includes(plan.subscription_status) && !isPremium);
  const intervalMismatch = Boolean(pending && plan?.interval !== interval);
  const planStatus = plan?.subscription_status;

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl px-5 py-8 sm:px-8">
        <div className="mb-6">
          <SectionHeading eyebrow="Plans" title={isPremium ? "Your Premium plan" : "Upgrade to Premium"}
            description={plan?.provider === "simulated" ? "Preview the Premium upgrade using the local simulated checkout." : "Choose a subscription and complete payment securely with Razorpay."} />
        </div>

        {plan?.provider === "simulated" ? <div className="mb-5"><Alert tone="info"><b>Simulated checkout.</b> This records a mock payment and activates Premium locally. No real payment is processed.</Alert></div> : null}
        {plan?.test_mode && plan.provider === "razorpay" ? <div className="mb-5"><Alert tone="warning"><b>Razorpay test mode.</b> Use Razorpay test credentials and test payment methods. No real charge will be made.</Alert></div> : null}
        {plan?.provider === "razorpay" ? <div className="mb-5"><Alert tone="info">Razorpay Checkout displays the payment methods available to your account. On desktop, supported UPI Autopay checkouts can show a QR code to scan with a UPI app.</Alert></div> : null}
        {error ? <div className="mb-5"><Alert>{error}</Alert></div> : null}
        {notice ? <div className="mb-5"><Alert tone="info">{notice}</Alert></div> : null}

        <div className="grid gap-6 md:grid-cols-[1.15fr_1fr]">
          <Card className="p-7">
              <div className="flex items-start justify-between gap-4">
              <div><h2 className="text-lg font-semibold">Premium</h2><p className="mt-1 text-sm text-slate-500">{plan?.provider === "simulated" ? "Local simulated upgrade for this account." : "Recurring subscription, managed securely by Razorpay."}</p></div>
              <Badge tone={isPremium ? "success" : "brand"}>{isPremium ? "Active" : "Premium"}</Badge>
            </div>
            <p className="mt-6 text-4xl font-bold tracking-tight">{price}<span className="text-base font-medium text-slate-500"> / {interval === "monthly" ? "month" : "year"}</span></p>
            <ul className="mt-6 space-y-2.5">{PREMIUM_FEATURES.map((feature) => <li key={feature} className="flex gap-2.5 text-sm text-slate-700"><span aria-hidden className="mt-0.5 text-emerald-600">✓</span>{feature}</li>)}</ul>
          </Card>

          <Card className="h-fit p-7">
            {isPremium ? <div>
              <h2 className="text-lg font-semibold">Premium is active</h2>
              <p className="mt-2 text-sm text-slate-500">Subscription status: {planStatus || "active"}{plan?.pro_until ? ` · access through ${new Date(plan.pro_until).toLocaleDateString()}` : ""}</p>
              {plan?.cancel_at_cycle_end ? <p className="mt-3 text-sm text-amber-800">Cancellation is scheduled at the end of the current billing period.</p> : <Button variant="secondary" onClick={cancel} disabled={busy} className="mt-5 w-full">{busy ? "Updating…" : "Cancel subscription"}</Button>}
              <LinkButton href="/applications" className="mt-3 w-full">Go to applications</LinkButton>
            </div> : <>
              <h2 className="text-lg font-semibold">Checkout</h2>
              {pending ? <div className="mt-4"><Alert tone="warning">An unfinished subscription ({planStatus}) already exists for the {plan?.interval} plan. {intervalMismatch ? "Select that billing interval to resume checkout, or cancel the existing subscription first." : "Continue to Razorpay to resume its checkout."}</Alert></div> : null}
              {plan?.provider === "razorpay" ? <div className="mt-5 grid grid-cols-2 gap-2" role="group" aria-label="Billing interval">
                {(["monthly", "yearly"] as const).map((item) => <button key={item} type="button" onClick={() => setInterval(item)} className={`rounded-lg border px-3 py-2.5 text-sm font-semibold capitalize ${interval === item ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line text-slate-600"}`}>{item}</button>)}
              </div> : null}
              <dl className="mt-5 space-y-2.5 text-sm">
                <div className="flex justify-between"><dt className="text-slate-500">Payment mode</dt><dd className="font-medium">{plan?.provider === "simulated" ? "Simulated" : `Razorpay · ${interval}`}</dd></div>
                <div className="flex justify-between border-t border-line pt-2.5"><dt className="font-semibold">Due now</dt><dd className="font-semibold tabular-nums">{price}</dd></div>
              </dl>
              {plan && !plan.configured ? <div className="mt-5"><Alert>Razorpay is not configured yet. Add the test key and plan IDs to the backend environment, then restart the backend.</Alert></div> : null}
              {plan?.provider === "razorpay" && selected && !selected.available ? <div className="mt-5"><Alert tone="warning">{interval === "monthly" ? "The Razorpay monthly plan must be priced at ₹250 INR. Create that plan in Razorpay and set its plan ID in .env." : "No matching Razorpay yearly plan is configured."}</Alert></div> : null}
              <Button size="lg" onClick={pay} disabled={!plan || busy || (plan.provider === "razorpay" && (!selected?.available || intervalMismatch || !plan.configured))} className="mt-6 w-full">{busy ? (plan?.provider === "simulated" ? "Processing…" : "Opening secure checkout…") : plan?.provider === "simulated" ? `Pay ${price} · simulated` : `Continue to Razorpay · ${price}`}</Button>
              {pending ? <><Button variant="secondary" onClick={checkStatus} disabled={busy} className="mt-3 w-full">Check payment status</Button><Button variant="ghost" onClick={cancel} disabled={busy} className="mt-2 w-full">Cancel unfinished subscription</Button></> : null}
              <p className="mt-3 text-center text-xs text-slate-500">{plan?.provider === "simulated" ? "No card or payment details are collected." : "Card and supported UPI payment options appear in Razorpay Checkout. Subscription renewals follow the plan schedule."}</p>
            </>}
          </Card>
        </div>
      </main>
    </AppShell>
  );
}
