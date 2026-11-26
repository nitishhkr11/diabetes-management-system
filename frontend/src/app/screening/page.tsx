"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, Info, ShieldCheck } from "lucide-react";
import { FEATURE_FIELDS, ScreeningInput, ScreeningResult, screeningApi } from "@/lib/screening-api";

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: (typeof FEATURE_FIELDS)[number];
  value: string;
  onChange: (v: string) => void;
}) {
  if ("isSelect" in field && field.isSelect && "options" in field) {
    return (
      <select
        id={field.key}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="form-input"
      >
        <option value="">— not specified —</option>
        {(field.options as readonly { value: string; label: string }[]).map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    );
  }
  return (
    <input
      id={field.key}
      type="number"
      min={field.min}
      max={field.max}
      step={field.step}
      value={value}
      placeholder={`${field.min}–${field.max}${field.unit ? " " + field.unit : ""}`}
      onChange={(e) => onChange(e.target.value)}
      className="form-input"
    />
  );
}

export default function ScreeningPage() {
  const router = useRouter();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setValue(key: string, v: string) {
    setValues((prev) => ({ ...prev, [key]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: ScreeningInput = {};
      for (const f of FEATURE_FIELDS) {
        const raw = values[f.key];
        if (raw !== undefined && raw !== "") {
          (payload as Record<string, number>)[f.key] = parseFloat(raw);
        } else {
          (payload as Record<string, null>)[f.key] = null;
        }
      }

      // Require at least age and sex
      if (payload.age_years == null) {
        setError("Age is required.");
        setLoading(false);
        return;
      }
      if (payload.sex_male == null) {
        setError("Sex is required.");
        setLoading(false);
        return;
      }

      const result = await screeningApi<ScreeningResult>(
        "/api/v1/public-screening/predictions",
        { method: "POST", body: JSON.stringify(payload) }
      );

      // Store result in sessionStorage and navigate to result page
      sessionStorage.setItem("screening_result", JSON.stringify(result));
      sessionStorage.setItem("screening_inputs_raw", JSON.stringify(values));
      router.push("/screening/result");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PUBLIC DIABETES SCREENING · MODEL 2</div>
          <h1>Non-laboratory screening estimate</h1>
          <p>
            Enter your physical measurements below to receive an estimate from a machine-learning model
            trained on US population survey data (NHANES 2017–2018). No laboratory tests required.
            No account needed.
          </p>
        </div>
      </div>

      <div className="note" style={{ marginBottom: 24 }}>
        <ShieldCheck size={17} />
        <p>
          <strong>This is not a diagnostic tool.</strong> The result is a research model estimate based
          on population survey patterns, not a clinical test. Missing measurements are imputed from
          population medians — provide as many as you can for a more informative result. Always consult
          a qualified healthcare provider for clinical assessment.
        </p>
      </div>

      <div className="split-grid" style={{ gap: 24, alignItems: "start" }}>
        <form onSubmit={handleSubmit} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          <div className="section-title" style={{ marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 18, margin: 0 }}>Your measurements</h2>
              <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
                Required: Age and Sex. All other fields are optional but improve accuracy.
              </p>
            </div>
          </div>

          {FEATURE_FIELDS.map((field) => (
            <div key={field.key} style={{ marginBottom: 18 }}>
              <label htmlFor={field.key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 650, marginBottom: 5 }}>
                {field.label}
                {"unit" in field && field.unit && <span style={{ color: "var(--muted)", fontWeight: 400 }}>{field.unit}</span>}
                {"required" in field && field.required && <span style={{ color: "var(--primary)", fontSize: 11 }}>*</span>}
              </label>
              <FieldInput
                field={field}
                value={values[field.key] ?? ""}
                onChange={(v) => setValue(field.key, v)}
              />
              <p style={{ margin: "4px 0 0", fontSize: 11, color: "var(--muted)" }}>{field.help}</p>
            </div>
          ))}

          {error && (
            <div className="note note-warn" style={{ marginBottom: 16 }}>
              <AlertTriangle size={16} />
              <p>{error}</p>
            </div>
          )}

          <button type="submit" className="btn" disabled={loading} style={{ marginTop: 8, alignSelf: "flex-start" }}>
            {loading ? <span className="spin">⟳</span> : <ArrowRight size={16} />}
            {loading ? "Estimating…" : "Get screening estimate"}
          </button>
        </form>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 10 }}>About this model</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--muted)", lineHeight: 1.7 }}>
              <li>Trained on NHANES 2017–2018 US population survey data</li>
              <li>4,900 adult participants aged 21 and older</li>
              <li>21.8% prevalence of survey-defined diabetes in the training data</li>
              <li>Uses Logistic Regression (best validation ROC-AUC: 0.79)</li>
              <li>Test ROC-AUC: 0.796 (95% CI: 0.766–0.828)</li>
              <li>No laboratory measurements used as inputs</li>
            </ul>
          </div>

          <div className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 10 }}>Missing measurements</div>
            <div style={{ display: "flex", gap: 10 }}>
              <Info size={16} style={{ flexShrink: 0, color: "var(--muted)", marginTop: 2 }} />
              <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                If you skip a measurement, the model uses the median value from the NHANES training data
                for that feature. This reduces result specificity. The result page shows which inputs
                were provided vs. imputed.
              </p>
            </div>
          </div>

          <div className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 10 }}>Why no blood glucose?</div>
            <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
              Blood glucose and HbA1c are laboratory tests that most people cannot access at home.
              They are also used to construct the training target — including them as inputs would
              cause data leakage and inflate results. This model uses only measurements that any
              adult can realistically provide without visiting a lab.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
