import { authedRequest } from "@/lib/auth";

export type PlanDetails = {
  plan: "FREE" | "PREMIUM";
  credits: number;
  credit_limit: number;
  trial_available: boolean;
  pro_until: string | null;
  subscription_id: string | null;
  subscription_status: string | null;
  cancel_at_cycle_end: boolean;
  configured: boolean;
  interval: "monthly" | "yearly";
  trial_question_limit: number;
};
export type BillingInterval = "monthly" | "yearly";
export type Catalog = { trial_question_limit: number; plans: { interval: BillingInterval; available: boolean; credits: number; amount: number | null; currency: string | null }[] };
export const getCatalog = () => authedRequest<Catalog>("/billing/catalog");

type CheckoutResult = {
  already_premium: boolean;
  key_id: string;
  subscription_id: string;
  amount: number;
  currency: string;
};
type Verification = {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
};
type CheckoutOptions = {
  key: string; subscription_id: string; name: string; description: string;
  handler: (response: Verification) => void;
  modal: { ondismiss: () => void };
};
declare global {
  interface Window { Razorpay?: new (options: CheckoutOptions) => { open: () => void; on: (event: string, handler: () => void) => void }; }
}
export const getPlan = () => authedRequest<PlanDetails>("/billing/plan");
export const syncPlan = () => authedRequest<PlanDetails>("/billing/sync", { method: "POST" });
export const cancelSubscription = () => authedRequest<PlanDetails>("/billing/cancel", { method: "POST" });

async function loadCheckout() {
  if (window.Razorpay) return;
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve();
    script.onerror = () => { script.remove(); reject(new Error("Unable to load Razorpay checkout")); };
    document.body.appendChild(script);
  });
}

export async function checkout(interval: BillingInterval = "monthly"): Promise<PlanDetails> {
  await loadCheckout();
  const order = await authedRequest<CheckoutResult>("/billing/checkout", {
    method: "POST", body: JSON.stringify({ plan: "PREMIUM", interval }),
  });
  if (order.already_premium) return getPlan();
  if (!window.Razorpay) throw new Error("Razorpay checkout is unavailable");
  const Razorpay = window.Razorpay;
  return new Promise((resolve, reject) => {
    const modal = new Razorpay({ key: order.key_id, subscription_id: order.subscription_id,
      name: "SkillSync Pro", description: `${formatPrice(order.amount, order.currency)} ${interval} — TEST payment`,
      handler: async (response) => {
        try {
          const plan = await authedRequest<PlanDetails>("/billing/verify", { method: "POST", body: JSON.stringify(response) });
          if (plan.plan !== "PREMIUM") throw new Error("Payment authorization received. Waiting for the paid subscription; refresh your plan shortly.");
          resolve(plan);
        } catch (error) { reject(error); }
      },
      modal: { ondismiss: () => reject(new Error("Checkout closed. Your plan has not changed.")) },
    });
    modal.on("payment.failed", () => reject(new Error("Test payment failed. You can retry checkout.")));
    modal.open();
  });
}

export function formatPrice(amount: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amount / 100);
}
