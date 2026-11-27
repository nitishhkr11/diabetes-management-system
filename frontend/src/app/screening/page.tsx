"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, AlertTriangle, ArrowRight, CheckCircle, FlaskConical, Save, ShieldCheck } from "lucide-react";
import { createClient } from "@/lib/supabase/browser";

type Pathway = "idrs" | "lab";

interface IdrsResult {
  score: number;
  max_score: number;
  risk_category: "low" | "moderate" | "high";
  risk_label: string;
  guideline_version: string;
  source_url: string;
  breakdown: {
    age_points: number;
    waist_points: number;
    activity_points: number;
    family_history_points: number;
  };
  next_steps: string;
  disclaimer: string;
}

interface LabResult {
  guideline_version: string;
  pregnancy_pathway: boolean;
  overall_category: string;
  overall_label: string;
  confirmation_required: boolean;
  results: Array<{ test: string; value_display: string; category: string; label: string }>;
  guidance: string;
  guideline_notes: string[];
  disclaimer: string;
}

export default function ScreeningPage() {
  const [pathway, setPathway] = useState<Pathway>("idrs");
  const [userEmail, setUserEmail] = useState<string | null>(null);

  // MDRF-IDRS state
  const [age, setAge] = useState("35");
  const [sex, setSex] = useState<"female" | "male">("male");
  const [waist, setWaist] = useState("92");
  const [waistUnit, setWaistUnit] = useState<"cm" | "in">("cm");
  const [activity, setActivity] = useState<"vigorous" | "moderate" | "mild" | "sedentary">("moderate");
  const [familyHx, setFamilyHx] = useState<"none" | "one_parent" | "both_parents">("none");
  const [idrsLoading, setIdrsLoading] = useState(false);
  const [idrsError, setIdrsError] = useState<string | null>(null);
  const [idrsResult, setIdrsResult] = useState<IdrsResult | null>(null);

  // Lab interpretation state
  const [isPregnant, setIsPregnant] = useState(false);
  const [hba1c, setHba1c] = useState("");
  const [fasting, setFasting] = useState("");
  const [fastingUnit, setFastingUnit] = useState<"mg/dL" | "mmol/L">("mg/dL");
  const [ogtt, setOgtt] = useState("");
  const [ogttUnit, setOgttUnit] = useState<"mg/dL" | "mmol/L">("mg/dL");
  const [randomGlc, setRandomGlc] = useState("");
  const [randomUnit, setRandomUnit] = useState<"mg/dL" | "mmol/L">("mg/dL");
  const [hasSymptoms, setHasSymptoms] = useState(false);
  const [labLoading, setLabLoading] = useState(false);
  const [labError, setLabError] = useState<string | null>(null);
  const [labResult, setLabResult] = useState<LabResult | null>(null);

  // Save history state
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (data?.user?.email) setUserEmail(data.user.email);
    }).catch(() => {});
  }, []);

  async function submitIdrs(e: React.FormEvent) {
    e.preventDefault();
    setIdrsError(null);
    setSavedMsg(null);
    setSaveErr(null);
    setIdrsLoading(true);
    try {
      const res = await fetch("/api/dms/api/v1/india-risk/idrs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age_years: parseFloat(age),
          sex,
          waist_value: parseFloat(waist),
          waist_unit: waistUnit,
          physical_activity: activity,
          family_history: familyHx,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Invalid IDRS input.");
      setIdrsResult(body);
    } catch (err: unknown) {
      setIdrsError(err instanceof Error ? err.message : "Could not calculate MDRF-IDRS.");
    } finally {
      setIdrsLoading(false);
    }
  }

  async function submitLab(e: React.FormEvent) {
    e.preventDefault();
    setLabError(null);
    setSavedMsg(null);
    setSaveErr(null);
    setLabLoading(true);
    try {
      const payload = {
        is_pregnant: isPregnant,
        hba1c_pct: hba1c.trim() ? parseFloat(hba1c) : null,
        fasting_glucose: fasting.trim() ? parseFloat(fasting) : null,
        fasting_unit: fastingUnit,
        ogtt_2h_glucose: ogtt.trim() ? parseFloat(ogtt) : null,
        ogtt_unit: ogttUnit,
        random_glucose: randomGlc.trim() ? parseFloat(randomGlc) : null,
        random_unit: randomUnit,
        has_classic_symptoms: hasSymptoms,
      };
      const res = await fetch("/api/dms/api/v1/india-risk/lab-interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Invalid lab input.");
      setLabResult(body);
    } catch (err: unknown) {
      setLabError(err instanceof Error ? err.message : "Could not interpret lab values.");
    } finally {
      setLabLoading(false);
    }
  }

  async function saveAssessment(type: "mdrf_idrs" | "lab_interpretation") {
    setSaving(true);
    setSavedMsg(null);
    setSaveErr(null);
    try {
      const sb = createClient();
      const { data: { session } } = await sb.auth.getSession();
      if (!session) throw new Error("Sign in to save assessments.");
      if (!consent) throw new Error("Please tick the consent box before saving.");

      const payload = type === "mdrf_idrs"
        ? {
            consent: true,
            assessment_type: "mdrf_idrs",
            idrs_inputs: {
              age_years: parseFloat(age),
              sex,
              waist_value: parseFloat(waist),
              waist_unit: waistUnit,
              physical_activity: activity,
              family_history: familyHx,
            },
          }
        : {
            consent: true,
            assessment_type: "lab_interpretation",
            lab_inputs: {
              is_pregnant: isPregnant,
              hba1c_pct: hba1c.trim() ? parseFloat(hba1c) : null,
              fasting_glucose: fasting.trim() ? parseFloat(fasting) : null,
              fasting_unit: fastingUnit,
              ogtt_2h_glucose: ogtt.trim() ? parseFloat(ogtt) : null,
              ogtt_unit: ogttUnit,
              random_glucose: randomGlc.trim() ? parseFloat(randomGlc) : null,
              random_unit: randomUnit,
              has_classic_symptoms: hasSymptoms,
            },
          };

      const res = await fetch("/api/dms/api/v1/india-risk/history", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(typeof b.detail === "string" ? b.detail : "Could not save assessment.");
      }
      setSavedMsg("Saved to your personal history.");
    } catch (err: unknown) {
      setSaveErr(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">INDIA DIABETES SCREENING &amp; LAB GUIDANCE</div>
          <h1>Check Your Diabetes Risk</h1>
          <p>
            Choose whether you want a non-laboratory Indian risk score (MDRF-IDRS) or an
            educational interpretation of your blood test report. No login required.
          </p>
        </div>
        <Link href="/research" className="btn btn-secondary">
          ML Research Benchmarks <ArrowRight size={15} />
        </Link>
      </div>

      {/* Two clear pathway choices */}
      <div className="split-grid" style={{ gap: 16, marginBottom: 24 }}>
        <button
          type="button"
          onClick={() => setPathway("idrs")}
          className="card card-pad"
          style={{
            textAlign: "left",
            cursor: "pointer",
            borderColor: pathway === "idrs" ? "var(--primary)" : "var(--border)",
            borderWidth: pathway === "idrs" ? 2 : 1,
            background: pathway === "idrs" ? "var(--surface-soft)" : "var(--surface)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <Activity size={18} color="var(--primary)" />
            <strong style={{ fontSize: 16 }}>A. I do not have a blood test</strong>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
            Use the published <strong>MDRF Indian Diabetes Risk Score (MDRF-IDRS)</strong> for
            adults aged 20+ using age, waist circumference, physical activity, and parental history.
          </p>
        </button>

        <button
          type="button"
          onClick={() => setPathway("lab")}
          className="card card-pad"
          style={{
            textAlign: "left",
            cursor: "pointer",
            borderColor: pathway === "lab" ? "var(--primary)" : "var(--border)",
            borderWidth: pathway === "lab" ? 2 : 1,
            background: pathway === "lab" ? "var(--surface-soft)" : "var(--surface)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <FlaskConical size={18} color="var(--secondary)" />
            <strong style={{ fontSize: 16 }}>B. I have a blood test report</strong>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
            Interpret <strong>HbA1c, Fasting Plasma Glucose, 2-hour OGTT, or Random Glucose</strong>{" "}
            against ADA and ICMR/WHO reference ranges, with pregnancy and confirmation safeguards.
          </p>
        </button>
      </div>

      {/* PATHWAY A: MDRF-IDRS */}
      {pathway === "idrs" && (
        <div className="split-grid" style={{ gap: 24, alignItems: "start" }}>
          <form onSubmit={submitIdrs} className="card card-pad">
            <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>MDRF Indian Diabetes Risk Score (MDRF-IDRS)</h2>
            <p style={{ margin: "0 0 18px", fontSize: 13, color: "var(--muted)" }}>
              Evaluated in ICMR-INDIAB for Indian adults aged 20 and above. Not validated for age &lt; 20.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label htmlFor="idrs-age" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Age (years, 20+) *
              </label>
              <input id="idrs-age" type="number" min={20} max={120} step={1} value={age} onChange={(e) => setAge(e.target.value)} className="form-input" required />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label htmlFor="idrs-sex" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Sex (for waist threshold) *
              </label>
              <select id="idrs-sex" value={sex} onChange={(e) => setSex(e.target.value as "female" | "male")} className="form-input">
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label htmlFor="idrs-waist" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Waist circumference *
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 100px", gap: 8 }}>
                <input id="idrs-waist" type="number" min={15} max={200} step={0.1} value={waist} onChange={(e) => setWaist(e.target.value)} className="form-input" required />
                <select aria-label="Waist unit" value={waistUnit} onChange={(e) => setWaistUnit(e.target.value as "cm" | "in")} className="form-input">
                  <option value="cm">cm</option>
                  <option value="in">inches</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label htmlFor="idrs-activity" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Physical activity *
              </label>
              <select id="idrs-activity" value={activity} onChange={(e) => setActivity(e.target.value as typeof activity)} className="form-input">
                <option value="vigorous">Regular vigorous exercise or strenuous manual work (0 pts)</option>
                <option value="moderate">Regular moderate exercise or moderate physical activity (10 pts)</option>
                <option value="mild">Regular mild exercise or mild physical activity (20 pts)</option>
                <option value="sedentary">No exercise and sedentary activities (30 pts)</option>
              </select>
            </div>

            <div style={{ marginBottom: 18 }}>
              <label htmlFor="idrs-family" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Family history of diabetes in parents *
              </label>
              <select id="idrs-family" value={familyHx} onChange={(e) => setFamilyHx(e.target.value as typeof familyHx)} className="form-input">
                <option value="none">Neither parent has diabetes (0 pts)</option>
                <option value="one_parent">One parent has diabetes (10 pts)</option>
                <option value="both_parents">Both parents have diabetes (20 pts)</option>
              </select>
            </div>

            {idrsError && (
              <div className="note note-warn" style={{ marginBottom: 14 }}>
                <AlertTriangle size={16} /><p>{idrsError}</p>
              </div>
            )}

            <button type="submit" className="btn" disabled={idrsLoading}>
              {idrsLoading ? "Calculating…" : "Calculate MDRF-IDRS"} <ArrowRight size={15} />
            </button>
          </form>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {idrsResult ? (
              <div className="card card-pad">
                <div className="eyebrow">{idrsResult.guideline_version}</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 12, margin: "8px 0" }}>
                  <span style={{ fontSize: 40, fontWeight: 800 }}>{idrsResult.score}</span>
                  <span style={{ color: "var(--muted)", fontSize: 14 }}>/ {idrsResult.max_score} · <strong>{idrsResult.risk_label}</strong></span>
                </div>
                <p style={{ margin: "0 0 12px", fontSize: 13, lineHeight: 1.6 }}>{idrsResult.next_steps}</p>

                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 14 }}>
                  <tbody>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}><td style={{ padding: "6px 0", color: "var(--muted)" }}>Age points</td><td style={{ textAlign: "right", fontWeight: 700 }}>{idrsResult.breakdown.age_points}</td></tr>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}><td style={{ padding: "6px 0", color: "var(--muted)" }}>Waist points</td><td style={{ textAlign: "right", fontWeight: 700 }}>{idrsResult.breakdown.waist_points}</td></tr>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}><td style={{ padding: "6px 0", color: "var(--muted)" }}>Physical activity points</td><td style={{ textAlign: "right", fontWeight: 700 }}>{idrsResult.breakdown.activity_points}</td></tr>
                    <tr><td style={{ padding: "6px 0", color: "var(--muted)" }}>Parental family history points</td><td style={{ textAlign: "right", fontWeight: 700 }}>{idrsResult.breakdown.family_history_points}</td></tr>
                  </tbody>
                </table>

                <div className="note" style={{ marginBottom: 12 }}>
                  <ShieldCheck size={16} />
                  <p style={{ margin: 0, fontSize: 12 }}>{idrsResult.disclaimer}</p>
                </div>

                {userEmail ? (
                  <div style={{ padding: 12, borderRadius: 10, background: "var(--surface-soft)", border: "1px solid var(--border)" }}>
                    <label style={{ display: "flex", gap: 8, fontSize: 12, marginBottom: 10 }}>
                      <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                      I consent to saving this MDRF-IDRS screening score to my account history.
                    </label>
                    <button type="button" className="btn btn-quiet" onClick={() => saveAssessment("mdrf_idrs")} disabled={saving}>
                      <Save size={14} /> {saving ? "Saving…" : "Save to my history"}
                    </button>
                    {savedMsg && <p style={{ color: "var(--success)", fontSize: 12, margin: "8px 0 0" }}>{savedMsg}</p>}
                    {saveErr && <p style={{ color: "var(--warning)", fontSize: 12, margin: "8px 0 0" }}>{saveErr}</p>}
                  </div>
                ) : (
                  <p style={{ fontSize: 12, color: "var(--muted)", margin: 0 }}>
                    <Link href="/auth/login" className="text-link">Sign in</Link> to optionally save your screening history.
                  </p>
                )}
              </div>
            ) : (
              <div className="card card-pad">
                <div className="eyebrow" style={{ marginBottom: 8 }}>About MDRF-IDRS</div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--muted)", lineHeight: 1.7 }}>
                  <li>Total score ranges from 0 to 100 (&lt;30 Low, 30–50 Moderate, ≥60 High risk).</li>
                  <li>Risk-screening score only — not a diabetes diagnosis or personalised probability.</li>
                  <li>GlucoGuide does not possess ICMR-INDIAB raw participant data; this implements the published scoring table.</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* PATHWAY B: LAB TEST RESULT INTERPRETATION */}
      {pathway === "lab" && (
        <div className="split-grid" style={{ gap: 24, alignItems: "start" }}>
          <form onSubmit={submitLab} className="card card-pad">
            <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>Blood Test Result Interpretation</h2>
            <p style={{ margin: "0 0 18px", fontSize: 13, color: "var(--muted)" }}>
              Enter one or more laboratory values from your report. A single home glucometer reading does not establish a diagnosis.
            </p>

            <label style={{ display: "flex", gap: 8, padding: 12, borderRadius: 10, background: "var(--warning-bg)", marginBottom: 16, fontSize: 13, fontWeight: 650 }}>
              <input type="checkbox" checked={isPregnant} onChange={(e) => setIsPregnant(e.target.checked)} />
              Currently pregnant (uses separate gestational diabetes pathway)
            </label>

            <div style={{ marginBottom: 14 }}>
              <label htmlFor="lab-hba1c" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                HbA1c (%)
              </label>
              <input id="lab-hba1c" type="number" min={3} max={20} step={0.1} placeholder="e.g. 5.8" value={hba1c} onChange={(e) => setHba1c(e.target.value)} className="form-input" disabled={isPregnant} />
            </div>

            <div style={{ marginBottom: 14 }}>
              <label htmlFor="lab-fpg" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Fasting plasma glucose
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 110px", gap: 8 }}>
                <input id="lab-fpg" type="number" step={0.1} placeholder="e.g. 108" value={fasting} onChange={(e) => setFasting(e.target.value)} className="form-input" disabled={isPregnant} />
                <select aria-label="Fasting glucose unit" value={fastingUnit} onChange={(e) => setFastingUnit(e.target.value as "mg/dL" | "mmol/L")} className="form-input" disabled={isPregnant}>
                  <option value="mg/dL">mg/dL</option>
                  <option value="mmol/L">mmol/L</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label htmlFor="lab-ogtt" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                2-hour OGTT glucose
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 110px", gap: 8 }}>
                <input id="lab-ogtt" type="number" step={0.1} placeholder="e.g. 155" value={ogtt} onChange={(e) => setOgtt(e.target.value)} className="form-input" disabled={isPregnant} />
                <select aria-label="OGTT unit" value={ogttUnit} onChange={(e) => setOgttUnit(e.target.value as "mg/dL" | "mmol/L")} className="form-input" disabled={isPregnant}>
                  <option value="mg/dL">mg/dL</option>
                  <option value="mmol/L">mmol/L</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label htmlFor="lab-random" style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                Random plasma glucose
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 110px", gap: 8 }}>
                <input id="lab-random" type="number" step={0.1} placeholder="e.g. 210" value={randomGlc} onChange={(e) => setRandomGlc(e.target.value)} className="form-input" disabled={isPregnant} />
                <select aria-label="Random glucose unit" value={randomUnit} onChange={(e) => setRandomUnit(e.target.value as "mg/dL" | "mmol/L")} className="form-input" disabled={isPregnant}>
                  <option value="mg/dL">mg/dL</option>
                  <option value="mmol/L">mmol/L</option>
                </select>
              </div>
              <label style={{ display: "flex", gap: 8, fontSize: 12, color: "var(--muted)", marginTop: 8 }}>
                <input type="checkbox" checked={hasSymptoms} onChange={(e) => setHasSymptoms(e.target.checked)} disabled={isPregnant} />
                Classic hyperglycaemia symptoms present (excessive thirst, frequent urination, unexplained weight loss)
              </label>
            </div>

            {labError && (
              <div className="note note-warn" style={{ marginBottom: 14 }}>
                <AlertTriangle size={16} /><p>{labError}</p>
              </div>
            )}

            <button type="submit" className="btn" disabled={labLoading}>
              {labLoading ? "Interpreting…" : "Interpret Lab Results"} <ArrowRight size={15} />
            </button>
          </form>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {labResult ? (
              <div className="card card-pad">
                <div className="eyebrow">{labResult.guideline_version}</div>
                <h3 style={{ margin: "6px 0 10px", fontSize: 18 }}>{labResult.overall_label}</h3>
                <p style={{ margin: "0 0 14px", fontSize: 13, lineHeight: 1.6 }}>{labResult.guidance}</p>

                {labResult.results.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
                    {labResult.results.map((r) => (
                      <div key={r.test} style={{ padding: 10, borderRadius: 8, background: "var(--surface-soft)", border: "1px solid var(--border)", fontSize: 13 }}>
                        <strong>{r.test}:</strong> {r.value_display} — <span>{r.label}</span>
                      </div>
                    ))}
                  </div>
                )}

                <ul style={{ margin: "0 0 14px", paddingLeft: 18, fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
                  {labResult.guideline_notes.map((n, i) => <li key={i}>{n}</li>)}
                </ul>

                <div className="note" style={{ marginBottom: 12 }}>
                  <CheckCircle size={16} />
                  <p style={{ margin: 0, fontSize: 12 }}>{labResult.disclaimer}</p>
                </div>

                {userEmail && !labResult.pregnancy_pathway && (
                  <div style={{ padding: 12, borderRadius: 10, background: "var(--surface-soft)", border: "1px solid var(--border)" }}>
                    <label style={{ display: "flex", gap: 8, fontSize: 12, marginBottom: 10 }}>
                      <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                      I consent to saving this lab interpretation to my account history.
                    </label>
                    <button type="button" className="btn btn-quiet" onClick={() => saveAssessment("lab_interpretation")} disabled={saving}>
                      <Save size={14} /> {saving ? "Saving…" : "Save to my history"}
                    </button>
                    {savedMsg && <p style={{ color: "var(--success)", fontSize: 12, margin: "8px 0 0" }}>{savedMsg}</p>}
                    {saveErr && <p style={{ color: "var(--warning)", fontSize: 12, margin: "8px 0 0" }}>{saveErr}</p>}
                  </div>
                )}
              </div>
            ) : (
              <div className="card card-pad">
                <div className="eyebrow" style={{ marginBottom: 8 }}>Reference Cutoffs (Non-Pregnant Adults)</div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--muted)", lineHeight: 1.7 }}>
                  <li><strong>HbA1c:</strong> &lt;5.7% Normal · 5.7–6.4% Prediabetes · ≥6.5% Diabetes range</li>
                  <li><strong>Fasting Plasma Glucose:</strong> &lt;100 Normal · 100–125 Prediabetes (ADA) · ≥126 mg/dL Diabetes range (WHO/ICMR IFG starts at 110 mg/dL)</li>
                  <li><strong>2-hour OGTT:</strong> &lt;140 Normal · 140–199 Prediabetes · ≥200 mg/dL Diabetes range</li>
                  <li><strong>Random Glucose:</strong> ≥200 mg/dL requires classic symptoms to meet a diagnostic criterion</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Clear separation from ML research models */}
      <div className="card card-pad" style={{ marginTop: 24 }}>
        <div className="eyebrow">RESEARCH MODELS SEPARATION</div>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--muted)" }}>
          The Pima, NHANES, and CDC BRFSS machine-learning models are preserved strictly as historical and
          US survey research benchmarks on the <Link href="/research" className="text-link">Research dashboard</Link>.
          They are never combined with MDRF-IDRS and are not used to diagnose Indian users.
        </p>
      </div>
    </>
  );
}
