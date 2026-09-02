"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { request, saveSession, type AuthResult } from "@/lib/auth";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter(); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const signup = mode === "signup";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const result = await request<AuthResult>(`/auth/${signup ? "register" : "login"}`, { method: "POST", body: JSON.stringify({ name: data.get("name"), email: data.get("email"), password: data.get("password") }) });
      saveSession(result); router.replace("/dashboard");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to authenticate."); }
    finally { setBusy(false); }
  }
  return <main className="grid min-h-screen place-items-center px-5"><section className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-2xl shadow-indigo-950/30">
    <Link href="/" className="text-sm font-semibold text-indigo-300">← CareerPilot</Link>
    <h1 className="mt-7 text-3xl font-bold">{signup ? "Start building momentum" : "Welcome back"}</h1>
    <p className="mt-2 text-slate-400">{signup ? "Create your free account. Upgrade whenever you need more." : "Sign in to continue to your career workspace."}</p>
    <form className="mt-7 space-y-4" onSubmit={submit}>
      {signup && <label className="block text-sm font-medium">Name<input className="mt-1.5" name="name" required minLength={2} maxLength={120} autoComplete="name" /></label>}
      <label className="block text-sm font-medium">Email<input className="mt-1.5" name="email" type="email" required autoComplete="email" /></label>
      <label className="block text-sm font-medium">Password<input className="mt-1.5" name="password" type="password" required minLength={signup ? 8 : 1} maxLength={72} autoComplete={signup ? "new-password" : "current-password"} /></label>
      {error && <p role="alert" className="rounded-lg bg-red-950/60 p-3 text-sm text-red-300">{error}</p>}
      <button disabled={busy} className="w-full rounded-lg bg-indigo-500 py-3 font-semibold text-white transition hover:bg-indigo-400 disabled:opacity-60">{busy ? "Please wait…" : signup ? "Create account" : "Sign in"}</button>
    </form>
    <p className="mt-6 text-center text-sm text-slate-400">{signup ? "Already have an account?" : "New to CareerPilot?"} <Link className="font-semibold text-indigo-300 hover:text-indigo-200" href={signup ? "/login" : "/signup"}>{signup ? "Sign in" : "Create an account"}</Link></p>
  </section></main>;
}
