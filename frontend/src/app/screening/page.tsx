"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  ClipboardCheck,
  FileSpreadsheet,
  HelpCircle,
  Save,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { createClient } from "@/lib/supabase/browser";
import { api, IdrsResult, LabInterpretResult } from "@/lib/api";

type Pathway = "idrs" | "lab";

const ACTIVITY_LABELS: Record<string, string> = {
  vigorous: "Regular vigorous exercise / strenuous manual work (0 pts)",
  moderate: "Regular moderate exercise / brisk walking (10 pts)",
  mild: "Regular mild exercise / light activity (20 pts)",
  sedentary: "No regular exercise & mostly sedentary (30 pts)",
};

const FAMILY_LABELS: Record<string, string> = {
  none: "Neither parent has diabetes (0 pts)",
  one_parent: "One parent has diabetes (10 pts)",
  both_parents: "Both parents have diabetes (20 pts)",
};

function RiskBadge({ category, label }: { category: string; label: string }) {
  const cls =
    category === "low" || category === "normal"
      ? "badge-success"
      : category === "moderate" || category === "prediabetes"
        ? "badge-warning"
        : category === "high" || category === "diabetes" || category === "diabetes_range"
          ? "badge-danger"
          : "badge-neutral";
  return <span className={`status-badge ${cls}`}>{label}</span>;
}

function ScreeningContent() {
  const searchParams = useSearchParams();
  const initialMode = searchParams.get("mode") === "lab" ? "lab" : "idrs";

  const [pathway, setPathway] = useState<Pathway>(initialMode);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  // Pathway A: MDRF-IDRS wizard state
  const [idrsStep, setIdrsStep] = useState<1 | 2 | 3>(1);
  const [age, setAge] = useState<string>("38");
  const [sex, setSex] = useState<"female" | "male">("female");
  const [waistVal, setWaistVal] = useState<string>("84");
  const [waistUnit, setWaistUnit] = useState<"cm" | "in">("cm");
  const [activity, setActivity] = useState<"vigorous" | "moderate" | "mild" | "sedentary">("moderate");
  const [familyHistory, setFamilyHistory] = useState<"none" | "one_parent" | "both_parents">("none");
  const [idrsLoading, setIdrsLoading] = useState(false);
  const [idrsError, setIdrsError] = useState<string | null>(null);
  const [idrsResult, setIdrsResult] = useState<IdrsResult | null>(null);
  const [idrsConsent, setIdrsConsent] = useState(false);
  const [idrsSaving, setIdrsSaving] = useState(false);
  const [idrsSavedMsg, setIdrsSavedMsg] = useState<string | null>(null);

  // Pathway B: Lab interpretation wizard state
  const [labStep, setLabStep] = useState<1 | 2>(1);
  const [isPregnant, setIsPregnant] = useState(false);
  const [hba1c, setHba1c] = useState<string>("");
  const [fpg, setFpg] = useState<string>("");
  const [fpgUnit, setFpgUnit] = useState<"mg/dL" | "mmol/L">("mg/dL");
  const [ogtt, setOgtt] = useState<string>("");
  const [ogttUnit, setOgttUnit] = useState<"mg/dL" | "mmol/L">("mg/dL");
  const [randomGlucose, setRandomGlucose] = useState<string>("");
  const [randomUnit, setRandomUnit] = useState<"mg/dL" | "mmol/L">("mg/dL");
  const [hasSymptoms, setHasSymptoms] = useState(false);
  const [labLoading, setLabLoading] = useState(false);
  const [labError, setLabError] = useState<string | null>(null);
  const [labResult, setLabResult] = useState<LabInterpretResult | null>(null);
  const [labConsent, setLabConsent] = useState(false);
  const [labSaving, setLabSaving] = useState(false);
  const [labSavedMsg, setLabSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    const modeParam = searchParams.get("mode");
    if (modeParam === "lab" || modeParam === "idrs") {
      setPathway(modeParam);
    }
  }, [searchParams]);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (data?.user?.email) setUserEmail(data.user.email);
    });
  }, []);

  function validateIdrsStep1(): boolean {
    setIdrsError(null);
    const ageNum = Number(age);
    const waistNum = Number(waistVal);
    if (!age || Number.isNaN(ageNum) || ageNum < 20 || ageNum > 120) {
      setIdrsError("Please enter an age between 20 and 120 years. MDRF-IDRS is validated for Indian adults aged 20+.");
      return false;
    }
    const waistCm = waistUnit === "in" ? waistNum * 2.54 : waistNum;
    if (!waistVal || Number.isNaN(waistNum) || waistCm < 40 || waistCm > 200) {
      setIdrsError("Please enter a valid waist circumference between 40 and 200 cm (15.7–78.7 in).");
      return false;
    }
    return true;
  }

  async function handleIdrsSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validateIdrsStep1()) return;
    setIdrsError(null);
    setIdrsSavedMsg(null);
    setIdrsLoading(true);
    try {
      const data = await api<IdrsResult>("/api/v1/india-risk/idrs", {
        method: "POST",
        body: JSON.stringify({
          age_years: Number(age),
          sex,
          waist_value: Number(waistVal),
          waist_unit: waistUnit,
          physical_activity: activity,
          family_history: familyHistory,
        }),
      });
      setIdrsResult(data);
    } catch (err: unknown) {
      setIdrsError(err instanceof Error ? err.message : "Could not calculate MDRF-IDRS.");
    } finally {
      setIdrsLoading(false);
    }
  }

  async function handleSaveIdrs() {
    if (!idrsResult || !idrsConsent) return;
    setIdrsSaving(true);
    setIdrsSavedMsg(null);
    setIdrsError(null);
    try {
      const sb = createClient();
      const { data: { session } } = await sb.auth.getSession();
      if (!session) throw new Error("Please sign in to save your assessment.");
      await api("/api/v1/india-risk/history", {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: JSON.stringify({
          consent: true,
          assessment_type: "mdrf_idrs",
          idrs_inputs: {
            age_years: Number(age),
            sex,
            waist_value: Number(waistVal),
            waist_unit: waistUnit,
            physical_activity: activity,
            family_history: familyHistory,
          },
        }),
      });
      setIdrsSavedMsg("Saved to your private account history.");
    } catch (err: unknown) {
      setIdrsError(err instanceof Error ? err.message : "Could not save assessment.");
    } finally {
      setIdrsSaving(false);
    }
  }

  async function handleLabSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLabError(null);
    setLabSavedMsg(null);
    if (!isPregnant && !hba1c && !fpg && !ogtt && !randomGlucose) {
      setLabError("Please enter at least one blood-test value (HbA1c, Fasting Glucose, 2-hour OGTT, or Random Glucose).");
      return;
    }
    setLabLoading(true);
    try {
      const data = await api<LabInterpretResult>("/api/v1/india-risk/lab-interpret", {
        method: "POST",
        body: JSON.stringify({
          is_pregnant: isPregnant,
          hba1c_pct: hba1c ? Number(hba1c) : null,
          fasting_glucose: fpg ? Number(fpg) : null,
          fasting_unit: fpgUnit,
          ogtt_2h_glucose: ogtt ? Number(ogtt) : null,
          ogtt_unit: ogttUnit,
          random_glucose: randomGlucose ? Number(randomGlucose) : null,
          random_unit: randomUnit,
          has_classic_symptoms: hasSymptoms,
        }),
      });
      setLabResult(data);
    } catch (err: unknown) {
      setLabError(err instanceof Error ? err.message : "Could not interpret blood-test values.");
    } finally {
      setLabLoading(false);
    }
  }

  async function handleSaveLab() {
    if (!labResult || !labConsent) return;
    setLabSaving(true);
    setLabSavedMsg(null);
    setLabError(null);
    try {
      const sb = createClient();
      const { data: { session } } = await sb.auth.getSession();
      if (!session) throw new Error("Please sign in to save your interpretation.");
      await api("/api/v1/india-risk/history", {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: JSON.stringify({
          consent: true,
          assessment_type: "lab_interpretation",
          lab_inputs: {
            is_pregnant: isPregnant,
            hba1c_pct: hba1c ? Number(hba1c) : null,
            fasting_glucose: fpg ? Number(fpg) : null,
            fasting_unit: fpgUnit,
            ogtt_2h_glucose: ogtt ? Number(ogtt) : null,
            ogtt_unit: ogttUnit,
            random_glucose: randomGlucose ? Number(randomGlucose) : null,
            random_unit: randomUnit,
            has_classic_symptoms: hasSymptoms,
          },
        }),
      });
      setLabSavedMsg("Saved to your private account history.");
    } catch (err: unknown) {
      setLabError(err instanceof Error ? err.message : "Could not save interpretation.");
    } finally {
      setLabSaving(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">INDIAN DIABETES SCREENING &amp; LAB GUIDE</div>
          <h1>Check Your Diabetes Risk</h1>
          <p>
            Choose whether you want to assess your risk without a blood test (MDRF-IDRS) or understand existing
            laboratory blood-test results.
          </p>
        </div>
      </div>

      {/* Pathway Selector */}
      <section className="split-grid" style={{ marginBottom: 24 }} aria-label="Screening pathway selection">
        <button
          type="button"
          onClick={() => setPathway("idrs")}
          className={`pathway-card ${pathway === "idrs" ? "pathway-card-active" : ""}`}
          style={{ textAlign: "left", cursor: "pointer" }}
          aria-pressed={pathway === "idrs"}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span className="feature-icon" style={{ marginBottom: 0 }}>
              <ClipboardCheck size={20} />
            </span>
            <span className="status-badge badge-neutral">Option 1 · No Blood Test</span>
          </div>
          <div>
            <strong style={{ display: "block", fontSize: 17, marginBottom: 4 }}>I don&apos;t have a blood test</strong>
            <span style={{ color: "var(--muted)", fontSize: 13.5 }}>
              I want to assess my diabetes risk using basic health and lifestyle information (MDRF-IDRS).
            </span>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setPathway("lab")}
          className={`pathway-card ${pathway === "lab" ? "pathway-card-active" : ""}`}
          style={{ textAlign: "left", cursor: "pointer" }}
          aria-pressed={pathway === "lab"}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span className="feature-icon" style={{ marginBottom: 0 }}>
              <FileSpreadsheet size={20} />
            </span>
            <span className="status-badge badge-neutral">Option 2 · Lab Report</span>
          </div>
          <div>
            <strong style={{ display: "block", fontSize: 17, marginBottom: 4 }}>
              I already have a blood-test report
            </strong>
            <span style={{ color: "var(--muted)", fontSize: 13.5 }}>
              I want to understand what my glucose or HbA1c results mean against clinical thresholds.
            </span>
          </div>
        </button>
      </section>

      {/* PATHWAY A: MDRF-IDRS */}
      {pathway === "idrs" && (
        <section className="split-grid" style={{ alignItems: "start" }}>
          <form onSubmit={handleIdrsSubmit} className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 4 }}>PATHWAY A · NO BLOOD TEST REQUIRED</div>
            <h2 style={{ margin: "0 0 6px", fontSize: 20 }}>MDRF Indian Diabetes Risk Score (MDRF-IDRS)</h2>
            <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--muted)" }}>
              Evaluated in ICMR-INDIAB for Indian adults aged 20 and above. Not validated for individuals under 20.
            </p>

            <div className="stepper" aria-label="MDRF-IDRS form progress">
              <span className={`step-pill ${idrsStep === 1 ? "step-pill-active" : "step-pill-done"}`}>
                1. Age &amp; Waist
              </span>
              <span className={`step-pill ${idrsStep === 2 ? "step-pill-active" : idrsStep > 2 ? "step-pill-done" : ""}`}>
                2. Activity &amp; Family
              </span>
              <span className={`step-pill ${idrsStep === 3 ? "step-pill-active" : ""}`}>
                3. Review &amp; Calculate
              </span>
            </div>

            {idrsError && <div className="status-error" role="alert">{idrsError}</div>}

            {idrsStep === 1 && (
              <div style={{ display: "grid", gap: 16 }}>
                <div className="field-grid">
                  <div className="field">
                    <label htmlFor="idrs-age">Age (years)</label>
                    <input
                      id="idrs-age"
                      type="number"
                      min={20}
                      max={120}
                      required
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                      className="form-input"
                    />
                    <small>Adults aged 20–120 years (below 35 = 0 pts, 35–49 = 20 pts, 50+ = 30 pts).</small>
                  </div>

                  <div className="field">
                    <label htmlFor="idrs-sex">Sex (for waist threshold)</label>
                    <select
                      id="idrs-sex"
                      value={sex}
                      onChange={(e) => setSex(e.target.value as "female" | "male")}
                      className="form-input"
                    >
                      <option value="female">Female (cutoffs: 80 cm / 90 cm)</option>
                      <option value="male">Male (cutoffs: 90 cm / 100 cm)</option>
                    </select>
                    <small>MDRF-IDRS uses sex-specific waist circumference cutoffs.</small>
                  </div>
                </div>

                <div className="field">
                  <label htmlFor="idrs-waist">Waist Circumference</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="idrs-waist"
                      type="number"
                      step="0.1"
                      min={15}
                      max={200}
                      required
                      value={waistVal}
                      onChange={(e) => setWaistVal(e.target.value)}
                      className="form-input"
                    />
                    <select
                      aria-label="Waist circumference unit"
                      value={waistUnit}
                      onChange={(e) => setWaistUnit(e.target.value as "cm" | "in")}
                      className="form-input"
                      style={{ width: 96 }}
                    >
                      <option value="cm">cm</option>
                      <option value="in">in</option>
                    </select>
                  </div>
                  <small>
                    <HelpCircle size={12} style={{ display: "inline", verticalAlign: "-2px", marginRight: 4 }} />
                    Measure horizontally around your abdomen just above your hipbone (midway between lowest rib and top
                    of hipbone) while breathing out gently.
                  </small>
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      if (validateIdrsStep1()) setIdrsStep(2);
                    }}
                  >
                    Next: Activity &amp; Family <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}

            {idrsStep === 2 && (
              <div style={{ display: "grid", gap: 16 }}>
                <div className="field">
                  <label htmlFor="idrs-activity">Physical Activity Level</label>
                  <select
                    id="idrs-activity"
                    value={activity}
                    onChange={(e) => setActivity(e.target.value as typeof activity)}
                    className="form-input"
                  >
                    <option value="vigorous">Regular vigorous exercise or strenuous manual work (0 pts)</option>
                    <option value="moderate">Regular moderate exercise or moderate physical activity (10 pts)</option>
                    <option value="mild">Regular mild exercise or mild physical activity (20 pts)</option>
                    <option value="sedentary">No exercise and sedentary activities (30 pts)</option>
                  </select>
                  <small>Includes both daily occupation/household physical effort and structured exercise.</small>
                </div>

                <div className="field">
                  <label htmlFor="idrs-family">Family History of Diabetes (Parents)</label>
                  <select
                    id="idrs-family"
                    value={familyHistory}
                    onChange={(e) => setFamilyHistory(e.target.value as typeof familyHistory)}
                    className="form-input"
                  >
                    <option value="none">Neither parent has diabetes (0 pts)</option>
                    <option value="one_parent">One parent has diabetes (10 pts)</option>
                    <option value="both_parents">Both parents have diabetes (20 pts)</option>
                  </select>
                  <small>Biological parents only, per the published MDRF-IDRS scoring table.</small>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setIdrsStep(1)}>
                    <ArrowLeft size={15} /> Back
                  </button>
                  <button type="button" className="btn" onClick={() => setIdrsStep(3)}>
                    Review Inputs <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}

            {idrsStep === 3 && (
              <div style={{ display: "grid", gap: 14 }}>
                <div className="card" style={{ padding: 14, background: "var(--surface-soft)" }}>
                  <strong style={{ display: "block", fontSize: 13.5, marginBottom: 8 }}>Review your entries</strong>
                  <div style={{ display: "grid", gap: 6, fontSize: 13 }}>
                    <div><strong>Age:</strong> {age} years</div>
                    <div><strong>Sex:</strong> {sex === "female" ? "Female" : "Male"}</div>
                    <div><strong>Waist circumference:</strong> {waistVal} {waistUnit}</div>
                    <div><strong>Physical activity:</strong> {ACTIVITY_LABELS[activity]}</div>
                    <div><strong>Parental history:</strong> {FAMILY_LABELS[familyHistory]}</div>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setIdrsStep(2)}>
                    <ArrowLeft size={15} /> Edit
                  </button>
                  <button type="submit" className="btn" disabled={idrsLoading}>
                    {idrsLoading ? "Calculating…" : "Calculate MDRF-IDRS"} <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}
          </form>

          {/* MDRF-IDRS Result Panel */}
          <div style={{ display: "grid", gap: 16 }}>
            {idrsResult ? (
              <div className="card card-pad" role="region" aria-label="MDRF-IDRS screening result">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
                  <div>
                    <div className="eyebrow">SCREENING RESULT (0–100)</div>
                    <div style={{ fontSize: 42, fontWeight: 800, lineHeight: 1.05, marginTop: 4 }}>
                      {idrsResult.score}
                      <span style={{ fontSize: 18, color: "var(--muted)", fontWeight: 600 }}> / 100</span>
                    </div>
                  </div>
                  <RiskBadge category={idrsResult.risk_category} label={idrsResult.risk_label} />
                </div>

                {/* Visual 0-100 Score Bar */}
                <div style={{ marginTop: 18 }}>
                  <div className="idrs-scale-track" aria-hidden="true">
                    <div className="idrs-seg-low" />
                    <div className="idrs-seg-mod" />
                    <div className="idrs-seg-high" />
                    <div className="idrs-marker" style={{ left: `${Math.min(100, Math.max(0, idrsResult.score))}%` }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)", marginTop: 6 }}>
                    <span>0 · Low (&lt;30)</span>
                    <span>30–50 · Moderate</span>
                    <span>60–100 · High</span>
                  </div>
                </div>

                <div style={{ marginTop: 18 }}>
                  <strong style={{ display: "block", fontSize: 13.5, marginBottom: 8 }}>How your score was calculated</strong>
                  <div className="field-grid" style={{ gap: 8 }}>
                    <div className="card" style={{ padding: "10px 12px" }}>
                      <span style={{ fontSize: 11.5, color: "var(--muted)" }}>Age</span>
                      <strong style={{ display: "block", fontSize: 15 }}>{idrsResult.breakdown.age_points} pts</strong>
                    </div>
                    <div className="card" style={{ padding: "10px 12px" }}>
                      <span style={{ fontSize: 11.5, color: "var(--muted)" }}>Waist ({idrsResult.normalized_inputs.waist_cm} cm)</span>
                      <strong style={{ display: "block", fontSize: 15 }}>{idrsResult.breakdown.waist_points} pts</strong>
                    </div>
                    <div className="card" style={{ padding: "10px 12px" }}>
                      <span style={{ fontSize: 11.5, color: "var(--muted)" }}>Physical Activity</span>
                      <strong style={{ display: "block", fontSize: 15 }}>{idrsResult.breakdown.activity_points} pts</strong>
                    </div>
                    <div className="card" style={{ padding: "10px 12px" }}>
                      <span style={{ fontSize: 11.5, color: "var(--muted)" }}>Parental History</span>
                      <strong style={{ display: "block", fontSize: 15 }}>{idrsResult.breakdown.family_history_points} pts</strong>
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 16 }}>
                  <strong style={{ display: "block", fontSize: 13.5, marginBottom: 4 }}>Suggested next steps</strong>
                  <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)" }}>{idrsResult.next_steps}</p>
                </div>

                <div className="note" style={{ marginTop: 16 }}>
                  <ShieldAlert size={18} />
                  <p>{idrsResult.disclaimer}</p>
                </div>

                {/* Consent-gated save */}
                <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
                  {userEmail ? (
                    <>
                      <label className="privacy-check" style={{ marginTop: 0 }}>
                        <input
                          type="checkbox"
                          checked={idrsConsent}
                          onChange={(e) => setIdrsConsent(e.target.checked)}
                        />
                        <span>I consent to saving this MDRF-IDRS screening score to my private account history.</span>
                      </label>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ marginTop: 10 }}
                        disabled={!idrsConsent || idrsSaving}
                        onClick={handleSaveIdrs}
                      >
                        <Save size={15} /> {idrsSaving ? "Saving…" : "Save to My History"}
                      </button>
                      {idrsSavedMsg && (
                        <div className="status-success" style={{ marginTop: 10, marginBottom: 0 }}>
                          {idrsSavedMsg}{" "}
                          <Link href="/dashboard" style={{ textDecoration: "underline", fontWeight: 700 }}>
                            View Dashboard
                          </Link>
                        </div>
                      )}
                    </>
                  ) : (
                    <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
                      <Link href="/auth/login?next=/screening" className="text-link">Sign in</Link> if you want to save
                      this assessment to your personal dashboard.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="card card-pad">
                <div className="eyebrow" style={{ marginBottom: 6 }}>ABOUT MDRF-IDRS</div>
                <h3 style={{ margin: "0 0 8px", fontSize: 17 }}>Published Indian Screening Method</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, color: "var(--muted)", display: "grid", gap: 8 }}>
                  <li><strong>Low risk (&lt; 30):</strong> Maintain healthy habits and routine preventive check-ups.</li>
                  <li><strong>Moderate risk (30–50):</strong> Discuss routine blood glucose screening with a doctor.</li>
                  <li><strong>High risk (≥ 60):</strong> Recommended to get a clinical blood test (HbA1c or Fasting Glucose).</li>
                  <li>Risk-screening score only — <strong>not a diabetes diagnosis</strong> and not a personalised probability.</li>
                  <li>GlucoGuide implements the published scoring table and does not possess ICMR-INDIAB raw data.</li>
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* PATHWAY B: LAB RESULT INTERPRETATION */}
      {pathway === "lab" && (
        <section className="split-grid" style={{ alignItems: "start" }}>
          <form onSubmit={handleLabSubmit} className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 4 }}>PATHWAY B · EXISTING BLOOD TEST REPORT</div>
            <h2 style={{ margin: "0 0 6px", fontSize: 20 }}>Interpret Blood-Test Results</h2>
            <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--muted)" }}>
              Enter one or more laboratory values from your report. Uses ADA and ICMR/WHO reference ranges.
            </p>

            <div className="stepper" aria-label="Lab interpretation progress">
              <span className={`step-pill ${labStep === 1 ? "step-pill-active" : "step-pill-done"}`}>
                1. Clinical Context
              </span>
              <span className={`step-pill ${labStep === 2 ? "step-pill-active" : ""}`}>
                2. Enter Lab Values
              </span>
            </div>

            {labError && <div className="status-error" role="alert">{labError}</div>}

            {labStep === 1 && (
              <div style={{ display: "grid", gap: 14 }}>
                <label className="privacy-check" style={{ marginTop: 0 }}>
                  <input
                    type="checkbox"
                    checked={isPregnant}
                    onChange={(e) => setIsPregnant(e.target.checked)}
                  />
                  <span>
                    <strong>Currently pregnant</strong> — Gestational diabetes (GDM) uses separate pregnancy-specific
                    clinical thresholds and cannot be evaluated with standard adult cutoffs.
                  </span>
                </label>

                <label className="privacy-check" style={{ marginTop: 0 }}>
                  <input
                    type="checkbox"
                    checked={hasSymptoms}
                    onChange={(e) => setHasSymptoms(e.target.checked)}
                  />
                  <span>
                    <strong>Classic hyperglycemia symptoms present</strong> (excessive thirst, frequent urination, or
                    unexplained weight loss — required when interpreting Random Plasma Glucose ≥ 200 mg/dL).
                  </span>
                </label>

                {isPregnant ? (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <button type="submit" className="btn" disabled={labLoading}>
                      {labLoading ? "Checking…" : "View Pregnancy Guidance"} <ArrowRight size={15} />
                    </button>
                  </div>
                ) : (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <button type="button" className="btn" onClick={() => setLabStep(2)}>
                      Next: Enter Lab Values <ArrowRight size={15} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {labStep === 2 && (
              <div style={{ display: "grid", gap: 16 }}>
                <div className="field">
                  <label htmlFor="lab-hba1c">HbA1c (%)</label>
                  <input
                    id="lab-hba1c"
                    type="number"
                    step="0.1"
                    min={3}
                    max={20}
                    placeholder="e.g. 5.8"
                    value={hba1c}
                    onChange={(e) => setHba1c(e.target.value)}
                    className="form-input"
                  />
                  <small>3-month average blood glucose. Normal &lt;5.7% · Prediabetes 5.7–6.4% · Diabetes range ≥6.5%.</small>
                </div>

                <div className="field">
                  <label htmlFor="lab-fpg">Fasting Plasma Glucose (FPG)</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="lab-fpg"
                      type="number"
                      step="0.1"
                      min={1}
                      placeholder="e.g. 108"
                      value={fpg}
                      onChange={(e) => setFpg(e.target.value)}
                      className="form-input"
                    />
                    <select
                      aria-label="Fasting glucose unit"
                      value={fpgUnit}
                      onChange={(e) => setFpgUnit(e.target.value as "mg/dL" | "mmol/L")}
                      className="form-input"
                      style={{ width: 112 }}
                    >
                      <option value="mg/dL">mg/dL</option>
                      <option value="mmol/L">mmol/L</option>
                    </select>
                  </div>
                  <small>Measured after at least 8 hours of fasting. Normal &lt;100 · ADA Prediabetes 100–125 · Diabetes ≥126 mg/dL.</small>
                </div>

                <div className="field">
                  <label htmlFor="lab-ogtt">2-Hour Oral Glucose Tolerance Test (OGTT)</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="lab-ogtt"
                      type="number"
                      step="0.1"
                      min={1}
                      placeholder="e.g. 152"
                      value={ogtt}
                      onChange={(e) => setOgtt(e.target.value)}
                      className="form-input"
                    />
                    <select
                      aria-label="OGTT unit"
                      value={ogttUnit}
                      onChange={(e) => setOgttUnit(e.target.value as "mg/dL" | "mmol/L")}
                      className="form-input"
                      style={{ width: 112 }}
                    >
                      <option value="mg/dL">mg/dL</option>
                      <option value="mmol/L">mmol/L</option>
                    </select>
                  </div>
                  <small>Measured 2 hours after a 75 g oral glucose load. Normal &lt;140 · IGT 140–199 · Diabetes ≥200 mg/dL.</small>
                </div>

                <div className="field">
                  <label htmlFor="lab-random">Random Plasma Glucose</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="lab-random"
                      type="number"
                      step="0.1"
                      min={1}
                      placeholder="e.g. 165"
                      value={randomGlucose}
                      onChange={(e) => setRandomGlucose(e.target.value)}
                      className="form-input"
                    />
                    <select
                      aria-label="Random glucose unit"
                      value={randomUnit}
                      onChange={(e) => setRandomUnit(e.target.value as "mg/dL" | "mmol/L")}
                      className="form-input"
                      style={{ width: 112 }}
                    >
                      <option value="mg/dL">mg/dL</option>
                      <option value="mmol/L">mmol/L</option>
                    </select>
                  </div>
                  <small>≥200 mg/dL is only considered diagnostic alongside classic symptoms of hyperglycemia.</small>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setLabStep(1)}>
                    <ArrowLeft size={15} /> Back
                  </button>
                  <button type="submit" className="btn" disabled={labLoading}>
                    {labLoading ? "Interpreting…" : "Interpret Test Results"} <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}
          </form>

          {/* Lab Result Panel */}
          <div style={{ display: "grid", gap: 16 }}>
            {labResult ? (
              <div className="card card-pad" role="region" aria-label="Laboratory interpretation result">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
                  <div>
                    <div className="eyebrow">LABORATORY INTERPRETATION</div>
                    <h3 style={{ margin: "4px 0 0", fontSize: 19 }}>{labResult.overall_label}</h3>
                  </div>
                  <RiskBadge category={labResult.overall_category} label={labResult.overall_label} />
                </div>

                {labResult.pregnancy_pathway && (
                  <div className="note" style={{ marginTop: 14 }}>
                    <AlertTriangle size={18} />
                    <p>
                      <strong>Separate Pregnancy Pathway:</strong> Standard non-pregnant thresholds are not applied.
                      Please consult your obstetrician for DIPSI / IADPSG / WHO gestational diabetes screening.
                    </p>
                  </div>
                )}

                {labResult.results.length > 0 && (
                  <div style={{ display: "grid", gap: 10, marginTop: 16 }}>
                    {labResult.results.map((r) => (
                      <div key={r.test} className="card" style={{ padding: 14, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                        <div>
                          <strong style={{ display: "block", fontSize: 14 }}>{r.test}</strong>
                          <span style={{ fontSize: 13, color: "var(--muted)" }}>{r.label}</span>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <strong style={{ display: "block", fontSize: 16 }}>{r.value_display}</strong>
                          <RiskBadge category={r.category} label={r.category} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ marginTop: 16 }}>
                  <strong style={{ display: "block", fontSize: 13.5, marginBottom: 4 }}>Clinical guidance &amp; next steps</strong>
                  <p style={{ margin: 0, fontSize: 13.5, color: "var(--muted)" }}>{labResult.guidance}</p>
                </div>

                {labResult.guideline_notes.length > 0 && (
                  <div className="card" style={{ marginTop: 14, padding: 13, background: "var(--surface-soft)" }}>
                    <strong style={{ display: "block", fontSize: 12.5, marginBottom: 6 }}>Guideline &amp; safety notes</strong>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--muted)", display: "grid", gap: 4 }}>
                      {labResult.guideline_notes.map((n) => (
                        <li key={n}>{n}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="note" style={{ marginTop: 14 }}>
                  <ShieldCheck size={18} />
                  <p>{labResult.disclaimer}</p>
                </div>

                <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
                  {userEmail ? (
                    <>
                      <label className="privacy-check" style={{ marginTop: 0 }}>
                        <input
                          type="checkbox"
                          checked={labConsent}
                          onChange={(e) => setLabConsent(e.target.checked)}
                        />
                        <span>I consent to saving this laboratory interpretation to my private account history.</span>
                      </label>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ marginTop: 10 }}
                        disabled={!labConsent || labSaving}
                        onClick={handleSaveLab}
                      >
                        <Save size={15} /> {labSaving ? "Saving…" : "Save to My History"}
                      </button>
                      {labSavedMsg && (
                        <div className="status-success" style={{ marginTop: 10, marginBottom: 0 }}>
                          {labSavedMsg}{" "}
                          <Link href="/dashboard" style={{ textDecoration: "underline", fontWeight: 700 }}>
                            View Dashboard
                          </Link>
                        </div>
                      )}
                    </>
                  ) : (
                    <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
                      <Link href="/auth/login?next=/screening?mode=lab" className="text-link">Sign in</Link> if you want
                      to save this interpretation to your personal dashboard.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="card card-pad">
                <div className="eyebrow" style={{ marginBottom: 6 }}>REFERENCE THRESHOLDS &amp; SAFEGUARDS</div>
                <h3 style={{ margin: "0 0 8px", fontSize: 17 }}>How GlucoGuide interprets blood tests</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, color: "var(--muted)", display: "grid", gap: 8 }}>
                  <li><strong>HbA1c:</strong> &lt;5.7% Below diabetes threshold · 5.7–6.4% Prediabetes · ≥6.5% Diabetes range</li>
                  <li><strong>Fasting Plasma Glucose:</strong> &lt;100 Normal · 100–125 Prediabetes (ADA; WHO/ICMR IFG starts at 110 mg/dL) · ≥126 mg/dL Diabetes range</li>
                  <li><strong>2-Hour OGTT:</strong> &lt;140 Normal · 140–199 Prediabetes · ≥200 mg/dL Diabetes range</li>
                  <li><strong>Random Glucose:</strong> ≥200 mg/dL requires classic symptoms; asymptomatic high values require formal repeat testing.</li>
                  <li><strong>Home Glucometer:</strong> A single finger-prick glucometer reading cannot establish a clinical diagnosis.</li>
                </ul>
              </div>
            )}
          </div>
        </section>
      )}
    </>
  );
}

export default function ScreeningPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, color: "var(--muted)" }}>Loading screening tool…</div>}>
      <ScreeningContent />
    </Suspense>
  );
}
