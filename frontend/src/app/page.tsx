import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BookOpen,
  ClipboardCheck,
  FileSpreadsheet,
  HeartPulse,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { GlucoseIllustration } from "@/components/glucose-illustration";

function HeroArt() {
  return (
    <svg viewBox="0 0 420 290" aria-hidden="true">
      <defs>
        <linearGradient id="heroGlow" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="var(--primary-soft)" />
          <stop offset="1" stopColor="var(--surface)" />
        </linearGradient>
      </defs>
      <circle cx="220" cy="145" r="122" fill="url(#heroGlow)" />
      <circle cx="220" cy="145" r="95" fill="none" stroke="var(--border)" strokeDasharray="4 7" />
      <rect x="64" y="66" width="150" height="74" rx="14" fill="var(--surface)" stroke="var(--border)" />
      <text x="82" y="94" fill="var(--primary)" fontSize="10" fontWeight="800">PATHWAY A · NO LABS</text>
      <text x="82" y="114" fill="var(--text)" fontSize="13" fontWeight="700">MDRF-IDRS</text>
      <text x="82" y="129" fill="var(--muted)" fontSize="10">0–100 Risk Score</text>

      <rect x="196" y="152" width="164" height="78" rx="14" fill="var(--surface)" stroke="var(--primary)" strokeWidth="1.8" />
      <text x="214" y="180" fill="var(--secondary)" fontSize="10" fontWeight="800">PATHWAY B · LAB REPORT</text>
      <text x="214" y="200" fill="var(--text)" fontSize="13" fontWeight="700">HbA1c &amp; Glucose</text>
      <text x="214" y="216" fill="var(--muted)" fontSize="10">ADA / ICMR-WHO Ranges</text>

      <path d="M160 140 C160 165 182 184 196 184" fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeDasharray="4 4" />
      <circle cx="312" cy="84" r="22" fill="var(--primary-soft)" stroke="var(--primary)" strokeWidth="1.5" />
      <path d="M303 84 h6 l4 -9 l5 17 l4 -8 h6" fill="none" stroke="var(--primary)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function HomePage() {
  return (
    <>
      <section className="hero-card">
        <div className="hero-copy">
          <div className="eyebrow">INDIAN DIABETES SCREENING &amp; LAB GUIDANCE</div>
          <h1>
            Understand Your Diabetes Risk. <em>Take a Step Towards Better Health.</em>
          </h1>
          <p>
            GlucoGuide helps adults in India understand their diabetes risk through an established Indian screening
            score or interpret existing blood-test results with clear, educational guidance.
          </p>
          <div className="hero-actions">
            <Link className="btn" href="/screening?mode=idrs">
              Check Your Risk <ArrowRight size={16} />
            </Link>
            <Link className="btn btn-secondary" href="/screening?mode=lab">
              Understand My Test Results
            </Link>
          </div>
          <div className="hero-safe">
            <ShieldCheck size={16} />
            <span>Educational screening &amp; guidance only · Not a clinical diagnosis</span>
          </div>
        </div>
        <div className="hero-art">
          <HeroArt />
        </div>
      </section>

      <div className="section-title">
        <div>
          <h2>Choose how you want to start</h2>
          <p>Two separate, clear pathways based on whether you have a blood-test report.</p>
        </div>
        <Link className="text-link" href="/screening">
          Open screening tool <ArrowRight size={14} />
        </Link>
      </div>

      <section className="split-grid" style={{ marginBottom: 28 }}>
        <Link href="/screening?mode=idrs" className="pathway-card">
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <span className="feature-icon" style={{ marginBottom: 0 }}>
                <ClipboardCheck size={20} />
              </span>
              <span className="status-badge badge-neutral">Option 1 · No blood test needed</span>
            </div>
            <h3 style={{ margin: "0 0 8px", fontSize: 19 }}>I don&apos;t have a blood test</h3>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
              I want to assess my diabetes risk using basic health and lifestyle information (age, waist circumference,
              physical activity, and family history) with the published <strong>MDRF-IDRS</strong> score.
            </p>
          </div>
          <span className="text-link">
            Start MDRF-IDRS screening <ArrowRight size={14} />
          </span>
        </Link>

        <Link href="/screening?mode=lab" className="pathway-card">
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <span className="feature-icon" style={{ marginBottom: 0 }}>
                <FileSpreadsheet size={20} />
              </span>
              <span className="status-badge badge-neutral">Option 2 · Have lab values</span>
            </div>
            <h3 style={{ margin: "0 0 8px", fontSize: 19 }}>I already have a blood-test report</h3>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
              I want to understand what my <strong>HbA1c</strong>, <strong>Fasting Glucose</strong>,{" "}
              <strong>2-hour OGTT</strong>, or <strong>Random Glucose</strong> results mean against ADA and ICMR/WHO
              reference ranges.
            </p>
          </div>
          <span className="text-link">
            Interpret blood-test results <ArrowRight size={14} />
          </span>
        </Link>
      </section>

      <div className="section-title">
        <div>
          <h2>How GlucoGuide works</h2>
          <p>Simple, transparent steps with clear medical safeguards.</p>
        </div>
        <Link className="text-link" href="/about">
          Methodology &amp; privacy <ArrowRight size={14} />
        </Link>
      </div>

      <section className="feature-grid">
        <article className="card feature-card">
          <span className="feature-icon"><HeartPulse size={18} /></span>
          <h3>1. Pick your pathway</h3>
          <p>Start with everyday lifestyle and waist measurements, or enter numbers directly from your pathology report.</p>
        </article>
        <article className="card feature-card">
          <span className="feature-icon"><Stethoscope size={18} /></span>
          <h3>2. Review clear guidance</h3>
          <p>See your score or reference band with plain-language explanations, contributing factors, and safety notes.</p>
        </article>
        <article className="card feature-card">
          <span className="feature-icon"><LockKeyhole size={18} /></span>
          <h3>3. Save only if you consent</h3>
          <p>Nothing is saved without sign-in and explicit consent. Signed-in users can track trends on their private dashboard.</p>
        </article>
      </section>

      <section className="split-grid" style={{ marginBottom: 28 }}>
        <article className="card content-card">
          <div className="eyebrow" style={{ marginBottom: 6 }}>INDIAN SCREENING STANDARD</div>
          <h2>About MDRF-IDRS</h2>
          <p>
            The <strong>Madras Diabetes Research Foundation Indian Diabetes Risk Score (MDRF-IDRS)</strong> is a
            validated, non-invasive screening tool evaluated across Indian adults aged 20+ in the ICMR-INDIAB
            population-based study.
          </p>
          <ul>
            <li>Uses four simple inputs: age, sex-specific waist circumference, physical activity, and parental diabetes history.</li>
            <li>Scores range from <strong>0 to 100</strong>: Below 30 (Low risk), 30–50 (Moderate risk), and 60 or above (High risk).</li>
            <li>It is a screening score — <strong>not a medical diagnosis</strong> and not a personalised disease probability.</li>
          </ul>
          <p style={{ marginTop: 10, fontSize: 12.5 }}>
            Note: GlucoGuide implements the published MDRF-IDRS scoring table and does not possess or train on raw
            ICMR-INDIAB participant data.
          </p>
        </article>

        <article className="card content-card">
          <div className="eyebrow" style={{ marginBottom: 6 }}>CLINICAL REFERENCE RANGES</div>
          <h2>About Blood-Test Interpretation</h2>
          <p>
            If you already have laboratory values, GlucoGuide compares them against established <strong>ADA</strong> and{" "}
            <strong>ICMR/WHO</strong> thresholds and explains where guidelines differ (for example, ADA vs. WHO/ICMR
            impaired fasting glucose cutoffs).
          </p>
          <ul>
            <li>Supports HbA1c (%), Fasting Plasma Glucose, 2-hour OGTT, and Random Plasma Glucose (`mg/dL` or `mmol/L`).</li>
            <li>Routes pregnant users to a separate gestational diabetes clinical pathway.</li>
            <li>Requires symptom context for random glucose and advises clinical confirmation for unconfirmed diabetes-range values.</li>
          </ul>
        </article>
      </section>

      <section className="split-grid" style={{ marginBottom: 28 }}>
        <article className="card content-card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <LockKeyhole size={18} color="var(--primary)" />
            <h2 style={{ margin: 0 }}>Privacy &amp; Data Protection</h2>
          </div>
          <p>
            Public screening and lab interpretation work without an account and do not store your inputs. If you sign in
            with Supabase Authentication and explicitly check the consent box, your records are protected by PostgreSQL
            Row Level Security (RLS) so only your account can view, export, or delete them.
          </p>
          <Link className="text-link" href="/about#privacy">
            Read privacy details <ArrowRight size={14} />
          </Link>
        </article>

        <article className="card content-card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <ShieldAlert size={18} color="var(--warning)" />
            <h2 style={{ margin: 0 }}>Medical Limitations &amp; Disclaimers</h2>
          </div>
          <p>
            GlucoGuide is an educational risk-screening and lab-literacy tool. It cannot diagnose diabetes, prescribe
            treatment, replace a clinician, or interpret a single home glucometer reading as a clinical diagnosis. Always
            consult a qualified doctor for medical evaluation.
          </p>
          <Link className="text-link" href="/learn">
            <BookOpen size={14} /> Learn about diabetes &amp; testing
          </Link>
        </article>
      </section>

      <div className="section-title">
        <div>
          <h2>Learn how glucose and insulin work</h2>
          <p>An interactive visual overview for everyday understanding.</p>
        </div>
        <Link className="text-link" href="/simulation">
          Open full view <Activity size={14} />
        </Link>
      </div>
      <GlucoseIllustration compact />
    </>
  );
}
