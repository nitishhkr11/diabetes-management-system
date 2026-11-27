"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Database, Info, ShieldCheck } from "lucide-react";
import { FEATURE_FIELDS, ScreeningInput, ScreeningResult, screeningApi } from "@/lib/screening-api";

interface IndiaStatus {
  model_label: string;
  model_version: string;
  ready: boolean;
  permission_status: string;
  status_message: string;
  intended_population: string;
  dataset_source: string;
  external_validation: string;
  blockers: string[];
}

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
  const [indiaStatus, setIndiaStatus] = useState<IndiaStatus | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/dms/api/v1/india-screening/status")
      .then((r) => r.json())
      .then(setIndiaStatus)
      .catch(() => {});
  }, []);

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
          <div className="eyebrow">INDIA ADULT SCREENING &amp; RESEARCH BENCHMARKS</div>
          <h1>India adult screening</h1>
          <p>
            Target population: Indian adults aged 20 years and above (men and women, rural and urban,
            across Indian states). Intended primary dataset: ICMR-INDIAB National Diabetes Study.
          </p>
        </div>
        <Link href="/research" className="btn btn-secondary">
          Research dashboard <ArrowRight size={15} />
        </Link>
      </div>

      {/* India Model Status Gate */}
      <div className="card card-pad" style={{ marginBottom: 24, borderLeft: "4px solid var(--warning)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12, marginBottom: 10 }}>
          <div>
            <div className="eyebrow">ICMR-INDIAB INDIAN ADULT RESEARCH MODEL</div>
            <h2 style={{ margin: "4px 0 0", fontSize: 18 }}>
              {indiaStatus?.ready ? "ICMR-INDIAB model ready" : "India-specific model is under development"}
            </h2>
          </div>
          <span
            style={{
              alignSelf: "flex-start",
              padding: "5px 11px",
              borderRadius: 999,
              fontSize: 11,
              fontWeight: 700,
              background: "var(--warning-bg)",
              color: "var(--warning)",
            }}
          >
            Data status: {indiaStatus?.permission_status ?? "NOT REQUESTED"}
          </span>
        </div>

        <p style={{ margin: "0 0 12px", fontSize: 14, lineHeight: 1.6 }}>
          {indiaStatus?.status_message ??
            "India-specific model is under development. Existing international and historical models are available for research comparison only."}
        </p>

        <div className="split-grid" style={{ gap: 14, fontSize: 12, color: "var(--muted)" }}>
          <div>
            <strong>Target population:</strong> Indian adults aged 20+ (no extrapolation to 18–19-year-olds).<br />
            <strong>Dataset source:</strong>{" "}
            <Link href="/datasets" className="text-link">ICMR-INDIAB National Diabetes Study</Link>.<br />
            <strong>External validation:</strong> External validation has not yet been completed.
          </div>
          <div>
            <strong>Planned non-lab inputs:</strong> Age (20+), sex, BMI, waist circumference,
            waist-to-height ratio, blood pressure, family history, physical activity, tobacco/alcohol,
            education, socioeconomic status, rural/urban residence, and state/region.
          </div>
        </div>
      </div>

      {/* Clearly labeled US benchmark section */}
      <div className="note" style={{ marginBottom: 24 }}>
        <ShieldCheck size={17} />
        <p>
          <strong>US population research benchmark (NHANES 2017–2018):</strong> The interactive form below
          runs Model 2, which was trained on United States survey data. It is <strong>not</strong> an
          Indian-validated screening model and is provided strictly for educational and research comparison.
          Always consult a qualified healthcare provider for clinical assessment.
        </p>
      </div>

      <div className="split-grid" style={{ gap: 24, alignItems: "start" }}>
        <form onSubmit={handleSubmit} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          <div className="section-title" style={{ marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 18, margin: 0 }}>US population research benchmark form</h2>
              <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
                NHANES 2017–2018 (US adults 21+). Required: Age and Sex. All other fields optional.
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
            {loading ? "Estimating…" : "Run US benchmark estimate"}
          </button>
        </form>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 10 }}>Model Scope &amp; Limitations</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--muted)", lineHeight: 1.7 }}>
              <li><strong>US population research benchmark:</strong> NHANES 2017–2018 (4,900 US adults 21+)</li>
              <li><strong>Historical Pima research benchmark:</strong> 768 Pima heritage women (<Link href="/estimate" className="text-link">Estimator</Link>)</li>
              <li><strong>ICMR-INDIAB Indian adult model:</strong> Pending authorised dataset access</li>
              <li>Test ROC-AUC (NHANES): 0.796 (95% CI: 0.766–0.828)</li>
              <li>No laboratory measurements used as inputs</li>
              <li>Not clinically validated for diagnosis</li>
            </ul>
          </div>

          <div className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 10 }}>Missing measurements</div>
            <div style={{ display: "flex", gap: 10 }}>
              <Info size={16} style={{ flexShrink: 0, color: "var(--muted)", marginTop: 2 }} />
              <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                Skipped measurements use training-data medians, which reduces specificity.
                The result page reports exactly which inputs were supplied vs. imputed.
              </p>
            </div>
          </div>

          <div className="card card-pad">
            <div className="eyebrow" style={{ marginBottom: 10 }}>Dataset comparison</div>
            <div style={{ display: "flex", gap: 10 }}>
              <Database size={16} style={{ flexShrink: 0, color: "var(--muted)", marginTop: 2 }} />
              <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
                Compare Pima, NHANES, and ICMR-INDIAB eligibility, diagnostic protocols, and limitations
                on the <Link href="/datasets" className="text-link">Datasets page</Link>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
