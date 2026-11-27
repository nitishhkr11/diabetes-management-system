import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, LockKeyhole, ShieldAlert, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "About, methodology & privacy" };

const stack = [
  { name: "Next.js App Router & TypeScript", role: "Responsive, accessible web interface with typed API contracts." },
  { name: "FastAPI & Pydantic", role: "Strict server-side input validation, rate limiting, and deterministic rule engines." },
  { name: "Supabase Auth & PostgreSQL RLS", role: "Authenticated user sessions and row-level ownership enforcement." },
  { name: "Recharts & Custom SVG Scales", role: "Clear, real-data-only visual indicators and chronological trends." },
];

export default function AboutPage() {
  return (
    <>
      <PageHeader
        eyebrow="ABOUT · METHODOLOGY · PRIVACY"
        title="How GlucoGuide works"
        description="A clear, evidence-grounded diabetes risk-screening and blood-test literacy platform built for adults in India."
        action={
          <Link className="btn" href="/screening">
            Check Your Risk <ArrowRight size={15} />
          </Link>
        }
      />

      <div className="content-grid" style={{ marginBottom: 18 }}>
        <section className="card content-card">
          <h2>1. What GlucoGuide does</h2>
          <p>
            GlucoGuide helps ordinary adults in India understand their diabetes risk when they do not have a blood test,
            and understand existing laboratory blood-test results when they already have a report. Signed-in users can
            also optionally save assessments and review personal trends over time.
          </p>
        </section>

        <section className="card content-card">
          <h2>2. Why diabetes risk screening matters</h2>
          <p>
            Type 2 diabetes often develops gradually without obvious symptoms. Early risk awareness encourages timely
            preventive check-ups and lifestyle discussions with a qualified healthcare professional before complications
            arise.
          </p>
        </section>

        <section className="card content-card">
          <h2>3. What MDRF-IDRS is</h2>
          <p>
            The <strong>Madras Diabetes Research Foundation Indian Diabetes Risk Score (MDRF-IDRS)</strong> is a
            published, non-laboratory screening score (0–100) using age, sex-specific waist circumference, physical
            activity level, and parental history of diabetes.
          </p>
          <p>
            Scores below 30 indicate low screening risk, 30–50 moderate risk, and 60 or above high risk. It is a
            deterministic clinical scoring table — not a machine-learning prediction.
          </p>
        </section>

        <section className="card content-card">
          <h2>4. Why we use an Indian screening score</h2>
          <p>
            South Asian and Indian adults often develop metabolic risk at lower BMI and waist thresholds than Western
            populations. MDRF-IDRS was evaluated across Indian adults aged 20+ in the published{" "}
            <strong>ICMR-INDIAB</strong> population-based study.
          </p>
          <p>
            GlucoGuide implements the published MDRF-IDRS scoring table directly and does not claim access to or
            training on raw ICMR-INDIAB participant records.
          </p>
        </section>

        <section className="card content-card">
          <h2>5. Why there are two pathways</h2>
          <p>
            People visit with different needs: some have no blood tests yet and need non-invasive screening (Pathway A),
            while others already hold a lab report and want plain-language context for their HbA1c or glucose values
            (Pathway B). Keeping these pathways separate prevents confusion.
          </p>
        </section>

        <section className="card content-card">
          <h2>6. How laboratory interpretation works</h2>
          <p>
            Pathway B evaluates HbA1c (%), Fasting Plasma Glucose, 2-hour OGTT, and Random Plasma Glucose (with `mg/dL`
            and `mmol/L` conversion) against ADA and ICMR/WHO criteria. It enforces pregnancy routing, random-glucose
            symptom checks, and clinical confirmation reminders.
          </p>
        </section>
      </div>

      <section className="card card-pad" style={{ marginBottom: 18 }}>
        <div className="section-title">
          <div>
            <h2>7. What GlucoGuide cannot do</h2>
            <p>Clear boundaries for safe use.</p>
          </div>
          <ShieldAlert size={18} color="var(--warning)" />
        </div>
        <div className="content-copy">
          <ul>
            <li>GlucoGuide is <strong>not</strong> an AI diagnostic system and cannot diagnose or rule out diabetes.</li>
            <li>MDRF-IDRS is not validated for individuals younger than 20 years and does not output a personalised disease probability.</li>
            <li>A single home glucometer reading cannot establish a clinical diagnosis.</li>
            <li>Pregnant users must follow dedicated gestational diabetes clinical testing rather than standard adult cutoffs.</li>
          </ul>
        </div>
      </section>

      <section className="card card-pad" style={{ marginBottom: 18 }}>
        <div className="section-title">
          <div>
            <h2>Architecture &amp; technology stack</h2>
            <p>Clean separation of UI, validation API, and row-level storage.</p>
          </div>
        </div>
        <div className="mini-flow">
          <span>Next.js Frontend</span>
          <span>→</span>
          <span>Same-origin Proxy</span>
          <span>→</span>
          <span>FastAPI Validation &amp; Scoring</span>
          <span>→</span>
          <span>Supabase RLS (Opt-in)</span>
        </div>
        <div className="field-grid" style={{ marginTop: 14 }}>
          {stack.map((item) => (
            <article key={item.name} className="card" style={{ padding: 14 }}>
              <b style={{ display: "block", fontSize: 13.5, marginBottom: 4 }}>{item.name}</b>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: 12.5 }}>{item.role}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card card-pad" id="privacy" style={{ marginBottom: 18 }}>
        <div className="section-title">
          <div>
            <h2>8. Privacy &amp; data handling</h2>
            <p>Opt-in, consent-first, and account-isolated.</p>
          </div>
          <LockKeyhole size={18} color="var(--primary)" />
        </div>
        <div className="content-copy">
          <ul>
            <li>Public screening and blood-test interpretation work without signing in and do not store your entries.</li>
            <li>Signed-in users must explicitly check a consent box to save a screening or lab interpretation to their private account.</li>
            <li>Every read, insert, and delete request is verified against Supabase Auth and enforced by PostgreSQL Row Level Security (`auth.uid() = user_id`), preventing cross-user access.</li>
            <li>You can export your saved history as CSV or delete individual or all records at any time from History or Account Settings.</li>
          </ul>
        </div>
      </section>

      <div className="note">
        <ShieldCheck size={18} />
        <p>
          <b>Medical disclaimer:</b> GlucoGuide provides educational screening and reference-range guidance only. If you
          have symptoms or results outside the normal range, please consult a qualified healthcare professional.
        </p>
      </div>
    </>
  );
}
