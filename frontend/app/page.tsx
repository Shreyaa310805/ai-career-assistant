import Link from "next/link";
import { AppPreview } from "@/components/landing/preview";
import { Badge, Card, LinkButton } from "@/components/ui";

const FEATURES = [
  {
    title: "Real ATS scoring",
    body: "Your resume is parsed the way an applicant tracking system reads it, then scored on six named checks — contact details, section coverage, skills, quantified impact, length and work-history structure. You see every component, not just a number.",
  },
  {
    title: "Job-description matching",
    body: "Paste or upload the posting. We extract what the role actually asks for, including technologies no fixed keyword list would know, and show exactly which requirements your resume evidences.",
  },
  {
    title: "Skill gap, at a glance",
    body: "Missing skills ranked by how much each one moves the needle for this specific role — as chips and priority bars, not paragraphs.",
  },
  {
    title: "Application workspace",
    body: "Every role gets its own space: resume versions, ATS history, skill gap, roadmap, what-if and learning, all bound to that application.",
  },
  {
    title: "What-if planning",
    body: "Pick a missing skill, set a target proficiency, and see the estimated effect on your match score before you spend a weekend on it.",
  },
  {
    title: "Your data stays yours",
    body: "Contact details extracted from your resume never leave the server, and raw resume text is never returned by the API. Uploads live in private storage with no public link.",
  },
];

const COMING_SOON = [
  { title: "Interview preparation", body: "Role-specific question sets generated from the job description and your resume gaps." },
];

const FREE_PLAN = ["Resume upload (PDF or DOCX)", "Job description upload or paste", "Full ATS score with breakdown", "Skill match against the role", "Improvement suggestions"];
const PREMIUM_PLAN = ["Everything in Free", "Unlimited tracked applications", "Resume versions and comparison", "Skill gap analysis and priorities", "Career roadmap and learning plan", "What-if score simulation"];

const FAQ = [
  {
    q: "Is the ATS score just a random number?",
    a: "No. Your file is parsed with a real PDF/DOCX text extractor, and the score is the sum of six sub-components that are all shown to you. Two different resumes produce genuinely different results, and the same resume always produces the same one.",
  },
  {
    q: "What happens to my resume?",
    a: "It is stored in private server-side storage with no public URL. The API never returns your name, email address, phone number or raw resume text — only skills, experience, work history and education.",
  },
  {
    q: "Do I need to pay to see my ATS score?",
    a: "No. Uploading a resume, uploading a job description and getting the full scored breakdown is free, and does not need a tracked application.",
  },
  {
    q: "How does payment work right now?",
    a: "Checkout is simulated for this build. Clicking upgrade flips your account to Premium immediately and records a mock transaction. No card details are requested, sent or stored.",
  },
];

export default function Home() {
  return (
    <main className="bg-white text-slate-900">
      <header className="sticky top-0 z-40 border-b border-line bg-white/85 backdrop-blur">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Career<span className="text-brand-600">Pilot</span>
          </Link>
          <div className="hidden gap-7 text-sm font-medium text-slate-600 md:flex">
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#pricing" className="hover:text-slate-900">Pricing</a>
            <a href="#roadmap" className="hover:text-slate-900">Roadmap</a>
            <a href="#faq" className="hover:text-slate-900">FAQ</a>
          </div>
          <div className="flex items-center gap-2">
            <LinkButton href="/login" variant="ghost" size="sm">Sign in</LinkButton>
            <LinkButton href="/signup" size="sm">Get started</LinkButton>
          </div>
        </nav>
      </header>

      {/* Hero ------------------------------------------------------------- */}
      <section className="mx-auto max-w-6xl px-6 pb-16 pt-20 text-center sm:pt-24">
        <Badge tone="brand">Free ATS scoring — no card required</Badge>
        <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
          Find out why your resume is being filtered out.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-600">
          Upload your resume and the job description. CareerPilot scores what an applicant tracking system
          would see, shows which requirements you are missing, and turns the gap into a plan.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <LinkButton href="/signup" size="lg">Score my resume free</LinkButton>
          <LinkButton href="#features" variant="secondary" size="lg">See how it works</LinkButton>
        </div>
      </section>

      {/* Product preview -------------------------------------------------- */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <AppPreview />
      </section>

      {/* Features --------------------------------------------------------- */}
      <section id="features" className="border-y border-line bg-surface-muted py-20">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-600">What you get</p>
          <h2 className="mt-2 max-w-2xl text-3xl font-bold tracking-tight">
            Everything is derived from your actual documents.
          </h2>
          <div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <Card key={feature.title} className="p-6">
                <h3 className="font-semibold">{feature.title}</h3>
                <p className="mt-2.5 text-sm leading-6 text-slate-600">{feature.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing ---------------------------------------------------------- */}
      <section id="pricing" className="py-20">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-600">Pricing</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight">Start free. Upgrade when you are tracking more than one role.</h2>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <Card className="p-7">
              <h3 className="text-lg font-semibold">Free</h3>
              <p className="mt-1 text-sm text-slate-500">Everything you need to fix one resume.</p>
              <p className="mt-5 text-4xl font-bold tracking-tight">$0</p>
              <ul className="mt-6 space-y-2.5">
                {FREE_PLAN.map((item) => (
                  <li key={item} className="flex gap-2.5 text-sm text-slate-700">
                    <span aria-hidden className="mt-0.5 text-emerald-600">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
              <LinkButton href="/signup" variant="secondary" className="mt-7 w-full">Create free account</LinkButton>
            </Card>

            <Card className="relative border-brand-200 p-7 shadow-md">
              <Badge tone="brand" className="absolute -top-3 left-7">Most useful</Badge>
              <h3 className="text-lg font-semibold">Premium</h3>
              <p className="mt-1 text-sm text-slate-500">For an active search across many companies.</p>
              <p className="mt-5 text-4xl font-bold tracking-tight">
                $19<span className="text-base font-medium text-slate-500"> one-time</span>
              </p>
              <ul className="mt-6 space-y-2.5">
                {PREMIUM_PLAN.map((item) => (
                  <li key={item} className="flex gap-2.5 text-sm text-slate-700">
                    <span aria-hidden className="mt-0.5 text-emerald-600">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
              <LinkButton href="/signup" className="mt-7 w-full">Get started</LinkButton>
              <p className="mt-3 text-center text-xs text-slate-500">Checkout is simulated in this build.</p>
            </Card>
          </div>
        </div>
      </section>

      {/* Coming soon ------------------------------------------------------ */}
      <section id="roadmap" className="border-y border-line bg-surface-muted py-20">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-600">On the roadmap</p>
          <h2 className="mt-2 max-w-2xl text-3xl font-bold tracking-tight">Not built yet — and we will not pretend otherwise.</h2>
          <p className="mt-3 max-w-2xl text-slate-600">
            These appear in the product as clearly marked placeholders. Nothing here generates results today.
          </p>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {COMING_SOON.map((item) => (
              <Card key={item.title} className="border-dashed bg-white/60 p-6">
                <Badge>Coming soon</Badge>
                <h3 className="mt-3 font-semibold text-slate-700">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">{item.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ -------------------------------------------------------------- */}
      <section id="faq" className="py-20">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-3xl font-bold tracking-tight">Questions</h2>
          <dl className="mt-8 divide-y divide-line border-y border-line">
            {FAQ.map((item) => (
              <div key={item.q} className="py-6">
                <dt className="font-semibold">{item.q}</dt>
                <dd className="mt-2 text-sm leading-6 text-slate-600">{item.a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* CTA + footer ----------------------------------------------------- */}
      <section className="mx-auto max-w-5xl px-6 pb-20">
        <div className="rounded-2xl bg-surface-inverse px-8 py-14 text-center text-white">
          <h2 className="text-3xl font-bold tracking-tight">See your score in about a minute.</h2>
          <p className="mx-auto mt-3 max-w-xl text-slate-300">
            Upload a resume, paste a job description, and get the full breakdown — free.
          </p>
          <LinkButton href="/signup" size="lg" className="mt-8">Score my resume</LinkButton>
        </div>
      </section>

      <footer className="border-t border-line py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 text-sm text-slate-500">
          <span className="font-semibold text-slate-900">Career<span className="text-brand-600">Pilot</span></span>
          <span>Resume and ATS analysis for your job search.</span>
        </div>
      </footer>
    </main>
  );
}
