import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ExternalLink, HeartHandshake, Stethoscope } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Understand diabetes" };

const sources = [
  {
    title: "Evaluation of MDRF-IDRS in detecting undiagnosed diabetes in the Indian population (ICMR-INDIAB)",
    publisher: "Indian Journal of Medical Research (IJMR)",
    date: "Published research reference",
    url: "https://ijmr.org.in/evaluation-of-madras-diabetes-risk-score-in-detecting-undiagnosed-diabetes-in-the-indian-population-results-from-the-indian-council-of-medical-research-india-diabetes-population-based-study/",
  },
  {
    title: "Diabetes — Questions and answers",
    publisher: "World Health Organization",
    date: "WHO Reference",
    url: "https://www.who.int/news-room/questions-and-answers/item/diabetes",
  },
  {
    title: "Diabetes — Fact sheet",
    publisher: "World Health Organization",
    date: "WHO Reference",
    url: "https://www.who.int/news-room/fact-sheets/detail/diabetes",
  },
  {
    title: "Diabetes Tests & Diagnosis",
    publisher: "National Institute of Diabetes and Digestive and Kidney Diseases",
    date: "NIDDK Reference",
    url: "https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis",
  },
  {
    title: "Symptoms of Diabetes",
    publisher: "US Centers for Disease Control and Prevention",
    date: "CDC Reference",
    url: "https://www.cdc.gov/diabetes/signs-symptoms/",
  },
];

export default function LearnPage() {
  return (
    <>
      <PageHeader
        eyebrow="LEARN · HEALTH EDUCATION"
        title="Diabetes, explained with care"
        description="Understand the basics of glucose and insulin, the different types of diabetes, how clinical diagnosis works, and why screening matters in India. Educational only — not personal medical advice."
        action={
          <Link className="btn" href="/screening">
            Check Your Risk <ArrowRight size={15} />
          </Link>
        }
      />

      <section className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="section-title">
          <div>
            <h2>Glucose and insulin: the short version</h2>
            <p>Two key parts of how the body uses energy.</p>
          </div>
        </div>
        <div className="content-copy">
          <p>
            Glucose is a sugar that circulates in the blood and fuels your body&apos;s cells. Insulin is a hormone made by
            the pancreas that helps glucose move from the bloodstream into cells. Diabetes refers to conditions in which
            blood glucose regulation is affected because the body makes too little insulin, cannot use insulin
            effectively, or both. Persistently high blood glucose can harm organs and blood vessels over time.
          </p>
          <p>
            Diabetes is not one single condition. Type 1, Type 2, and gestational diabetes have different causes,
            diagnostic thresholds, and care pathways.
          </p>
        </div>
      </section>

      <section className="content-grid" style={{ marginBottom: 16 }}>
        <article className="card content-card type-card">
          <h3><span>01</span> Type 1 diabetes</h3>
          <p>
            Type 1 is an autoimmune condition in which the immune system attacks insulin-producing beta cells. The body
            makes little or no insulin. It can appear at any age and is not caused by diet or lifestyle.
          </p>
          <p>Qualified clinicians use specific medical assessments and tests to diagnose and manage it.</p>
        </article>
        <article className="card content-card type-card">
          <h3><span>02</span> Type 2 diabetes</h3>
          <p>
            Type 2 involves the body not using insulin effectively (insulin resistance) and, over time, not producing
            enough insulin. Genetics, age, abdominal adiposity, and lifestyle factors all influence risk.
          </p>
          <p>Early screening with tools like MDRF-IDRS helps identify adults who may benefit from a blood test.</p>
        </article>
        <article className="card content-card type-card">
          <h3><span>03</span> Gestational diabetes</h3>
          <p>
            Gestational diabetes is high blood glucose first recognized during pregnancy. Pregnancy uses dedicated
            screening thresholds (such as DIPSI / IADPSG / WHO criteria) rather than standard adult cutoffs.
          </p>
          <p>Testing and follow-up must be guided by maternity-care professionals.</p>
        </article>
        <article className="card content-card type-card">
          <h3><span>i</span> Other forms</h3>
          <p>
            Less common forms include monogenic diabetes and diabetes related to other medical conditions or
            medications. Classification always requires clinician evaluation.
          </p>
        </article>
      </section>

      <div className="split-grid" style={{ marginBottom: 16 }}>
        <section className="card content-card">
          <h2>Common signs and symptoms</h2>
          <p>
            Many adults with early Type 2 diabetes or prediabetes have no noticeable symptoms. When symptoms occur, they
            may include frequent urination, increased thirst or hunger, unexplained weight loss, fatigue, or blurred
            vision.
          </p>
          <div className="note">
            <HeartHandshake size={17} />
            <p>
              If you notice these symptoms, consult a qualified healthcare professional for laboratory testing. Do not
              rely on a screening score alone to rule out diabetes.
            </p>
          </div>
        </section>

        <section className="card content-card">
          <h2>How clinical diagnosis is made</h2>
          <p>
            Doctors diagnose diabetes using standardized laboratory blood tests — such as <strong>HbA1c</strong>,{" "}
            <strong>Fasting Plasma Glucose</strong>, or a <strong>2-hour Oral Glucose Tolerance Test (OGTT)</strong> —
            together with your medical history.
          </p>
          <p>
            In the absence of classic symptoms of hyperglycemia, a single abnormal test is generally repeated on a
            subsequent day for clinical confirmation. A single home glucometer reading does not establish a diagnosis.
          </p>
          <Link className="text-link" href="/screening?mode=lab">
            Interpret an existing lab report <ArrowRight size={13} />
          </Link>
        </section>
      </div>

      <section className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="section-title">
          <div>
            <h2>General Type 2 risk-reduction information</h2>
            <p>Broad preventive principles — not a personal treatment plan.</p>
          </div>
          <Stethoscope size={18} color="var(--primary)" />
        </div>
        <div className="content-grid">
          <div className="content-copy">
            <h3>Practical habits that may support metabolic health</h3>
            <ul>
              <li>Choose a balanced, sustainable eating pattern rich in fibre and whole foods.</li>
              <li>Include regular moderate or vigorous physical activity suited to your ability.</li>
              <li>Monitor waist circumference and blood pressure during routine check-ups.</li>
              <li>Discuss periodic blood-glucose screening with a doctor if you have a family history of diabetes.</li>
            </ul>
          </div>
          <div className="content-copy">
            <h3>When to seek medical care</h3>
            <p>
              If your MDRF-IDRS score is in the moderate or high risk band, or if a blood test falls in the prediabetes
              or diabetes range, schedule an appointment with a qualified clinician for confirmatory testing and
              personalized advice.
            </p>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="section-title">
          <div>
            <h2>Myth &amp; fact</h2>
            <p>Four helpful reminders.</p>
          </div>
        </div>
        <div className="content-grid faq-list">
          <details open>
            <summary>&ldquo;Type 1 is caused by eating too much sugar.&rdquo;</summary>
            <p>False. Type 1 is an autoimmune condition; diet and lifestyle habits do not cause it.</p>
          </details>
          <details>
            <summary>&ldquo;A screening risk score is the same as a diagnosis.&rdquo;</summary>
            <p>No. MDRF-IDRS estimates screening risk to help decide who should get a blood test; only a clinician with lab tests can diagnose diabetes.</p>
          </details>
          <details>
            <summary>&ldquo;One home glucometer reading confirms diabetes.&rdquo;</summary>
            <p>No. Standardized venous laboratory tests and clinical confirmation are required for diagnosis.</p>
          </details>
          <details>
            <summary>&ldquo;Pregnancy uses the same blood sugar cutoffs.&rdquo;</summary>
            <p>No. Gestational diabetes uses separate pregnancy-specific clinical thresholds.</p>
          </details>
        </div>
      </section>

      <section className="card card-pad" id="sources">
        <div className="section-title">
          <div>
            <h2>Authoritative references</h2>
            <p>Public-health and peer-reviewed sources used in GlucoGuide.</p>
          </div>
        </div>
        <div className="source-list">
          {sources.map((source) => (
            <article className="source-item" key={source.title}>
              <div>
                <strong>{source.title}</strong>
                <small>{source.publisher} · {source.date}</small>
              </div>
              <a href={source.url} target="_blank" rel="noreferrer">
                Open source <ExternalLink size={12} />
              </a>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
