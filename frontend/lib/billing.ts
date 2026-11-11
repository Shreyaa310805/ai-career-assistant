import { authedRequest, type User } from "@/lib/auth";

export type BillingInterval = "monthly" | "yearly";
export type Payment = {
  id: string;
  plan: "PREMIUM";
  amount_cents: number;
  currency: string;
  provider: string;
  status: "SUCCEEDED" | "FAILED" | "PENDING";
  created_at: string;
};
export type PlanDetails = {
  plan: "FREE" | "PREMIUM";
  premium_since: string | null;
  payments: Payment[];
  credits: number;
  credit_limit: number;
  trial_available: boolean;
  trial_question_limit: number;
  interval: BillingInterval;
  pro_until: string | null;
  subscription_id: string | null;
  subscription_status: string | null;
  cancel_at_cycle_end: boolean;
  webhook_configured: boolean;
  test_mode: boolean;
  configured: boolean;
  provider: "razorpay" | "simulated";
};
export type PlanOption = {
  interval: BillingInterval;
  available: boolean;
  credits: number;
  amount: number | null;
  currency: string | null;
};
export type PlanCatalog = { plans: PlanOption[]; trial_question_limit: number };
export type CheckoutResult = {
  already_premium: boolean;
  user?: User;
  key_id?: string;
  subscription_id?: string;
  amount?: number;
  currency?: string;
};
export type CheckoutVerification = {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
};

const jsonPost = (body?: unknown): RequestInit => ({
  method: "POST",
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const getPlan = () => authedRequest<PlanDetails>("/billing/plan");
export const getCatalog = () => authedRequest<PlanCatalog>("/billing/catalog");
export const checkout = (interval: BillingInterval) =>
  authedRequest<CheckoutResult>("/billing/checkout", jsonPost({ plan: "PREMIUM", interval }));
export const verifyCheckout = (details: CheckoutVerification) =>
  authedRequest<PlanDetails>("/billing/verify", jsonPost(details));
export const syncPlan = () => authedRequest<PlanDetails>("/billing/sync", jsonPost());
export const cancelSubscription = () => authedRequest<PlanDetails>("/billing/cancel", jsonPost());

export function formatPrice(amount: number | null | undefined, currency: string | null | undefined) {
  if (amount == null || !currency) return "Price unavailable";
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(amount / 100);
}
