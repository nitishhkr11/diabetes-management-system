"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle, Info, Save, ShieldCheck } from "lucide-react";
import { ScreeningResult } from "@/lib/screening-api";
import { createClient } from "@/lib/supabase/browser";

function ScoreMeter({ probability, threshold }: { probability: number; threshold: number }) {
  const pct = Math.round(probability * 100);
  const isHigher = probability >= threshold;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <div
        style={{
          width: 140, height: 140, borderRadius: "50%",
          border: `8px solid ${isHigher ? "var(--warning)" : "var(--success)"}`,
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          background: isHigher ? "var(--warning-bg)" : "color-mix(in srgb,var(--success) 10%,transparent)",
        }}
      >
        <span style={{ fontSize: 32, fontWeight: 800, color: isHigher ? "var(--warning)" : "var(--success)" }}>
          {pct}<span style={{ fontSize: 16 }}>%</span>
        </span>
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>model score</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 16 }}>
        {isHigher
          ? <><AlertTriangle size={20} color="var(--warning)" /> <span style={{ color: "var(--warning)" }}>Higher likelihood</span></>
          : <><CheckCircle size={20} color="var(--success)" /> <span style={{ color: "var(--success)" }}>Lower likelihood</span></>
        }
      </div>
      <p style={{ margin: 0, fontSize: 12, color: "var(--muted)", textAlign: "center" }}>
        Threshold: {Math.round(threshold * 100)}% · Scores ≥ threshold → higher likelihood
      </p>
    </div>
  );
}

function MissingInputWarning({ missing }: { missing: string[] }) {
  if (missing.length === 0) return null;
  return (
    <div className="note note-warn" style={{ marginTop: 12 }}>
      <Info size={16} />
      <p>
        <strong>{missing.length} measurement{missing.length > 1 ? "s" : ""} not provided</strong> and
        imputed from NHANES training medians:{" "}
        <em>{missing.map((m) => m.replace(/_/g, " ")).join(", ")}</em>.
        These imputed values reduce result specificity.
      </p>
    </div>
  );
}

export default function ScreeningResultPage() {
  const [result, setResult] = useState<ScreeningResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [user, setUser] = useState<{ email: string } | null>(null);

  useEffect(() => {
    const r = sessionStorage.getItem("screening_result");
    if (r) setResult(JSON.parse(r));

    // Check auth state
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (data?.user?.email) setUser({ email: data.user.email });
    });
  }, []);

  async function handleSave() {
    if (!result) return;
    setSaving(true);
    setSaveError(null);
    try {
      const sb = createClient();
      const { data: { session } } = await sb.auth.getSession();
      if (!session) throw new Error("Sign in to save your assessment.");

      const payload: Record<string, number | null> = {};
      for (const [k, v] of Object.entries(result.inputs)) {
        payload[k] = v as number | null;
      }

      const res = await fetch("/api/dms/api/v1/public-screening/history", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ consent: true, inputs: payload }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Could not save assessment.");
      }
      setSaved(true);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  if (!result) {
    return (
      <div style={{ textAlign: "center", padding: "80px 20px" }}>
        <p style={{ color: "var(--muted)" }}>No screening result found.</p>
        <Link href="/screening" className="btn" style={{ marginTop: 16 }}>
          Go to screening form
        </Link>
      </div>
    );
  }

  const isHigher = result.label === 1;

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">SCREENING RESULT · {result.model_version.toUpperCase()}</div>
          <h1>Your screening estimate</h1>
          <p>
            From <strong>{result.model}</strong> trained on {result.dataset}.
            Model version: <code>{result.model_version}</code>.
          </p>
        </div>
        <Link href="/screening" className="btn btn-secondary">
          Try again <ArrowRight size={15} />
        </Link>
      </div>

      <div className="split-grid" style={{ gap: 24, alignItems: "start" }}>
        {/* Left: Score */}
        <div className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <ScoreMeter probability={result.probability} threshold={result.threshold} />
          </div>

          <div
            style={{
              padding: "14px 16px", borderRadius: 12,
              background: isHigher ? "var(--warning-bg)" : "color-mix(in srgb,var(--success) 8%,transparent)",
              border: `1px solid ${isHigher ? "color-mix(in srgb,var(--warning) 30%,transparent)" : "color-mix(in srgb,var(--success) 25%,transparent)"}`,
            }}
          >
            <strong style={{ display: "block", marginBottom: 6 }}>
              {isHigher ? "Higher likelihood pattern detected" : "Lower likelihood pattern detected"}
            </strong>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6 }}>
              {isHigher
                ? "Your measurements show a pattern more common in the survey-defined diabetes group in the NHANES data. This is not a diagnosis — many people with similar measurements do not have diabetes. Please consult a healthcare provider."
                : "Your measurements show a pattern more common in the non-diabetes group in the NHANES data. A lower score does not rule out diabetes or prediabetes. Regular check-ups remain important."
              }
            </p>
          </div>

          <MissingInputWarning missing={result.missing_inputs} />

          {result.warnings.length > 0 && (
            <div className="note note-warn">
              <AlertTriangle size={15} />
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {result.warnings.map((w, i) => <li key={i} style={{ fontSize: 12 }}>{w}</li>)}
              </ul>
            </div>
          )}

          {/* Save to history */}
          <div
            style={{
              padding: 16, borderRadius: 12,
              border: "1px solid var(--border)", background: "var(--surface-soft)",
            }}
          >
            {saved ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--success)" }}>
                <CheckCircle size={18} />
                <strong>Assessment saved to your history.</strong>
              </div>
            ) : user ? (
              <>
                <p style={{ margin: "0 0 10px", fontSize: 13 }}>
                  <Save size={15} style={{ verticalAlign: -2, marginRight: 6 }} />
                  Save this assessment and track your measurements over time.
                </p>
                <p style={{ margin: "0 0 12px", fontSize: 11, color: "var(--muted)" }}>
                  By saving, you consent to storing this result linked to your account.
                  You can delete it at any time from your history.
                </p>
                <button className="btn btn-quiet" onClick={handleSave} disabled={saving}>
                  {saving ? "Saving…" : "Save to my history"}
                </button>
                {saveError && <p style={{ marginTop: 8, color: "var(--warning)", fontSize: 12 }}>{saveError}</p>}
              </>
            ) : (
              <>
                <p style={{ margin: "0 0 10px", fontSize: 13 }}>
                  <Save size={15} style={{ verticalAlign: -2, marginRight: 6 }} />
                  Save this assessment and track your progress over time.
                </p>
                <div style={{ display: "flex", gap: 8 }}>
                  <Link href="/auth/register" className="btn">Create account</Link>
                  <Link href="/auth/login" className="btn btn-secondary">Sign in</Link>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right: Details */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Your inputs */}
          <div className="card card-pad">
            <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>Your measurements</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <tbody>
                {Object.entries(result.inputs).map(([k, v]) => {
                  const isMissing = result.missing_inputs.includes(k);
                  return (
                    <tr key={k} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "7px 0", color: "var(--muted)" }}>
                        {k.replace(/_/g, " ")}
                      </td>
                      <td style={{ padding: "7px 0", textAlign: "right", fontWeight: 650 }}>
                        {isMissing ? (
                          <span style={{ color: "var(--muted)", fontStyle: "italic" }}>imputed</span>
                        ) : (
                          v !== null ? v : "—"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Disclaimer */}
          <div className="note">
            <ShieldCheck size={16} />
            <p style={{ fontSize: 12, margin: 0 }}>{result.disclaimer}</p>
          </div>

          {/* Model info */}
          <div className="card card-pad">
            <h3 style={{ margin: "0 0 10px", fontSize: 15 }}>About this result</h3>
            <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 16px", fontSize: 12 }}>
              <dt style={{ color: "var(--muted)" }}>Model</dt>
              <dd style={{ margin: 0, fontWeight: 650 }}>{result.model}</dd>
              <dt style={{ color: "var(--muted)" }}>Version</dt>
              <dd style={{ margin: 0 }}><code>{result.model_version}</code></dd>
              <dt style={{ color: "var(--muted)" }}>Dataset</dt>
              <dd style={{ margin: 0 }}>{result.dataset}</dd>
              <dt style={{ color: "var(--muted)" }}>Threshold</dt>
              <dd style={{ margin: 0 }}>{result.threshold}</dd>
            </dl>
            <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--muted)" }}>
              {result.population_note}
            </p>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <Link href="/research" className="btn btn-secondary" style={{ flex: 1, justifyContent: "center" }}>
              View model evidence
            </Link>
            <Link href="/datasets" className="btn btn-secondary" style={{ flex: 1, justifyContent: "center" }}>
              Dataset details
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
