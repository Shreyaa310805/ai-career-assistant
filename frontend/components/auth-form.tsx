"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Alert, Button, Field } from "@/components/ui";
import { request, saveSession, type AuthResult } from "@/lib/auth";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const signup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const result = await request<AuthResult>(`/auth/${signup ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          email: data.get("email"),
          password: data.get("password"),
        }),
      });
      saveSession(result);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to authenticate.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-surface-muted px-5 py-12">
      <section className="w-full max-w-md">
        <Link href="/" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
          ← SkillSync
        </Link>

        <div className="mt-5 rounded-card border border-line bg-white p-8 shadow-sm">
          <h1 className="text-2xl font-bold tracking-tight">
            {signup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {signup
              ? "Free ATS scoring, no card required. Upgrade later if you need the full workspace."
              : "Sign in to continue to your workspace."}
          </p>

          <form className="mt-7 space-y-4" onSubmit={submit}>
            {signup ? (
              <Field label="Name">
                <input className="field" name="name" required minLength={2} maxLength={120} autoComplete="name" />
              </Field>
            ) : null}

            <Field label="Email">
              <input className="field" name="email" type="email" required autoComplete="email" />
            </Field>

            <Field label="Password" hint={signup ? "At least 8 characters." : undefined}>
              <input
                className="field"
                name="password"
                type="password"
                required
                minLength={signup ? 8 : 1}
                maxLength={72}
                autoComplete={signup ? "new-password" : "current-password"}
              />
            </Field>

            {error ? <Alert>{error}</Alert> : null}

            <Button type="submit" size="lg" disabled={busy} className="w-full">
              {busy ? "Please wait…" : signup ? "Create account" : "Sign in"}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-slate-500">
          {signup ? "Already have an account?" : "New to SkillSync?"}{" "}
          <Link className="font-semibold text-brand-600 hover:text-brand-700" href={signup ? "/login" : "/signup"}>
            {signup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
