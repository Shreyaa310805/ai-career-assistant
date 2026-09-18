import { authedRequest, type User } from "@/lib/auth";

export type PaymentStatus = "SUCCEEDED" | "FAILED";

export type Payment = {
  id: string;
  plan: "FREE" | "PREMIUM";
  amount_cents: number;
  currency: string;
  provider: string;
  status: PaymentStatus;
  created_at: string;
};

export type PlanDetails = {
  plan: "FREE" | "PREMIUM";
  premium_since: string | null;
  price_cents: number;
  currency: string;
  provider: string;
  payments: Payment[];
};

export type CheckoutResult = {
  user: User;
  payment: Payment | null;
  already_premium: boolean;
};

export const getPlan = () => authedRequest<PlanDetails>("/billing/plan");

/** Simulated purchase. The server owns the price and the resulting plan. */
export const checkout = () =>
  authedRequest<CheckoutResult>("/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ plan: "PREMIUM" }),
  });

export function formatPrice(cents: number, currency: string) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(
    cents / 100,
  );
}
