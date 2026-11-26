// Research / Model comparison page — shows both Pima and Public screening model evidence
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, BookOpen, Database, FlaskConical } from "lucide-react";

interface PublicMetrics {
  roc_auc?: number; recall?: number; precision?: number;
  specificity?: number; f1?: number; brier?: number;
  balanced_accuracy?: number; accuracy?: number;
  tn?: number; fp?: number; fn?: number; tp?: number;
}

interface PublicEval {
  model_version: string;
  model_name: string;
  dataset: { source?: string; n_eligible?: number; prevalence_train?: number };
  target_definition: { positive?: string; negative?: string; note?: string };
  test_metrics: PublicMetrics;
  test_confidence_intervals: Record<string, [number, number]>;
  features: string[];
  feature_labels: Record<string, string>;
  population: string;
  population_limitations: string[];
  threshold: number;
  protocol: string;
}

interface PimaEval {
  cv: Array<Record<string, number | string>>;
  test: Array<Record<string, number | string>>;
  threshold: number;
  confidence_intervals: Record<string, [number, number]>;
  selection_rule: string;
  test_exposure_note: string;
}

function MetricRow({ label, value, ci }: { label: string; value?: number | string; ci?: [number, number] }) {
  if (value == null) return null;
  const fv = typeof value === "number" ? value.toFixed(4) : value;
  return (
    <tr style={{ borderBottom: "1px solid var(--border)" }}>
      <td style={{ padding: "7px 12px", color: "var(--muted)", fontSize: 13 }}>{label}</td>
      <td style={{ padding: "7px 12px", fontWeight: 700, fontSize: 13 }}>{fv}</td>
      <td style={{ padding: "7px 12px", fontSize: 11, color: "var(--muted)" }}>
        {ci ? `[${ci[0].toFixed(3)}, ${ci[1].toFixed(3)}]` : ""}
      </td>
    </tr>
  );
}

export default function ResearchPage() {
  const [pubEval, setPubEval] = useState<PublicEval | null>(null);
  const [pimaEval, setPimaEval] = useState<PimaEval | null>(null);
  const [pubLoading, setPubLoading] = useState(true);
  const [pimaLoading, setPimaLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"public" | "pima" | "compare">("public");

  useEffect(() => {
    fetch("/api/dms/api/v1/public-screening/evaluation").then(r => r.json()).then(setPubEval).catch(() => {}).finally(() => setPubLoading(false));
    fetch("/api/dms/api/v1/evaluation").then(r => r.json()).then(setPimaEval).catch(() => {}).finally(() => setPimaLoading(false));
  }, []);

  const tabs = [
    { id: "public" as const, label: "Public screening model" },
    { id: "pima" as const, label: "Pima research model" },
    { id: "compare" as const, label: "Side-by-side comparison" },
  ];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MODEL EVIDENCE · RESEARCH DASHBOARD</div>
          <h1>ML model research</h1>
          <p>
            Inspect actual evaluation results, dataset details, algorithm selection rationale,
            and research limitations for both models. All values come from real model artifacts.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/datasets" className="btn btn-secondary"><Database size={15} /> Datasets</Link>
          <Link href="/model-lab" className="btn btn-secondary"><FlaskConical size={15} /> Model lab</Link>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: "1px solid var(--border)" }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: "10px 18px", fontSize: 13, fontWeight: 650, cursor: "pointer",
              border: "none", background: "transparent",
              borderBottom: activeTab === t.id ? "2px solid var(--primary)" : "2px solid transparent",
              color: activeTab === t.id ? "var(--primary)" : "var(--muted)",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* PUBLIC SCREENING TAB */}
      {activeTab === "public" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {pubLoading ? <p style={{ color: "var(--muted)" }}>Loading public model data…</p> : !pubEval ? (
            <div className="note note-warn"><AlertTriangle size={16} /><p>Public screening model evaluation not available. Run the training script first.</p></div>
          ) : (
            <>
              <div className="card card-pad">
                <h2 style={{ marginBottom: 4 }}>Public Screening Model — {pubEval.model_name}</h2>
                <p style={{ margin: "0 0 16px", color: "var(--muted)", fontSize: 13 }}>
                  Version: <code>{pubEval.model_version}</code> · Dataset: {pubEval.dataset?.source}
                </p>
                <div className="note" style={{ marginBottom: 16 }}>
                  <BookOpen size={15} />
                  <p style={{ fontSize: 12, margin: 0 }}>
                    <strong>Target:</strong> {pubEval.target_definition?.positive}.<br />
                    {pubEval.target_definition?.note}
                  </p>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div>
                    <h3 style={{ fontSize: 14, marginBottom: 8 }}>Test set metrics</h3>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead><tr><th style={{ textAlign: "left", padding: "6px 12px", fontSize: 12, color: "var(--muted)" }}>Metric</th><th style={{ padding: "6px 12px", fontSize: 12, color: "var(--muted)" }}>Value</th><th style={{ padding: "6px 12px", fontSize: 12, color: "var(--muted)" }}>95% CI</th></tr></thead>
                      <tbody>
                        {Object.entries(pubEval.test_metrics).filter(([k]) => !["tn","fp","fn","tp","threshold","n_samples","n_positive","n_negative"].includes(k)).map(([k, v]) => (
                          <MetricRow key={k} label={k.replace(/_/g, " ")} value={v as number} ci={pubEval.test_confidence_intervals[k]} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <h3 style={{ fontSize: 14, marginBottom: 8 }}>Confusion matrix (test set)</h3>
                    {["tn","fp","fn","tp"].every(k => pubEval.test_metrics[k as keyof PublicMetrics] != null) && (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                        {[
                          { label: "True Negative", key: "tn", bg: "var(--surface-soft)" },
                          { label: "False Positive", key: "fp", bg: "var(--warning-bg)" },
                          { label: "False Negative", key: "fn", bg: "var(--warning-bg)" },
                          { label: "True Positive", key: "tp", bg: "color-mix(in srgb,var(--success) 12%,transparent)" },
                        ].map(({ label, key, bg }) => (
                          <div key={key} style={{ background: bg, borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
                            <div style={{ fontSize: 24, fontWeight: 800 }}>{pubEval.test_metrics[key as keyof PublicMetrics]}</div>
                            <div style={{ fontSize: 11, color: "var(--muted)" }}>{label}</div>
                          </div>
                        ))}
                      </div>
                    )}
                    <p style={{ marginTop: 12, fontSize: 12, color: "var(--muted)" }}>
                      Threshold: {pubEval.threshold} · n={
                        (pubEval.test_metrics.tn ?? 0) + (pubEval.test_metrics.fp ?? 0) +
                        (pubEval.test_metrics.fn ?? 0) + (pubEval.test_metrics.tp ?? 0)
                      }
                    </p>
                  </div>
                </div>
              </div>

              <div className="card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 10 }}>Evaluation figures</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
                  {["roc_test.png","confusion_test.png","calibration_test.png","feature_importance.png"].map((fig) => (
                    <div key={fig} style={{ border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
                      <img
                        src={`/api/dms/api/v1/public-screening/figures/${fig}`}
                        alt={fig.replace(".png","").replace(/_/g," ")}
                        style={{ width: "100%", display: "block" }}
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                      <div style={{ padding: "6px 10px", fontSize: 11, color: "var(--muted)" }}>{fig.replace(".png","").replace(/_/g," ")}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 10 }}>Features used</h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {pubEval.features.map((f) => (
                    <span key={f} style={{ padding: "4px 10px", background: "var(--surface-soft)", borderRadius: 999, fontSize: 12, fontWeight: 650 }}>
                      {pubEval.feature_labels[f] || f}
                    </span>
                  ))}
                </div>
              </div>

              <div className="card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 10 }}>Population and limitations</h3>
                <p style={{ margin: "0 0 10px", fontSize: 13, color: "var(--muted)" }}>{pubEval.population}</p>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {pubEval.population_limitations.map((l, i) => (
                    <li key={i} style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>{l}</li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      )}

      {/* PIMA TAB */}
      {activeTab === "pima" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {pimaLoading ? <p style={{ color: "var(--muted)" }}>Loading Pima model data…</p> : !pimaEval ? (
            <div className="note note-warn"><AlertTriangle size={16} /><p>Pima model evaluation not available.</p></div>
          ) : (
            <>
              <div className="card card-pad">
                <h2 style={{ marginBottom: 4 }}>Pima Research Model — Logistic Regression</h2>
                <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: 13 }}>
                  768-observation historical benchmark dataset · Women aged 21+ of Pima heritage.
                </p>
                <div className="note">
                  <AlertTriangle size={15} />
                  <p style={{ fontSize: 12, margin: 0 }}>
                    <strong>Population-specific:</strong> {pimaEval.test_exposure_note}
                  </p>
                </div>
              </div>
              <div className="card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 8 }}>CV results (5-fold, training split)</h3>
                <div style={{ overflow: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead><tr style={{ background: "var(--surface-soft)", borderBottom: "2px solid var(--border)" }}>
                      <th style={{ padding: "8px 12px", textAlign: "left" }}>Model</th>
                      {["accuracy","balanced_accuracy","precision","recall","f1","roc_auc"].map(k => (
                        <th key={k} style={{ padding: "8px 12px", textAlign: "right" }}>{k.replace(/_/g," ")}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {pimaEval.cv.map((row, i) => (
                        <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td style={{ padding: "8px 12px", fontWeight: row.model === "Logistic Regression" ? 700 : 400 }}>{String(row.model)}</td>
                          {["accuracy","balanced_accuracy","precision","recall","f1","roc_auc"].map(k => (
                            <td key={k} style={{ padding: "8px 12px", textAlign: "right" }}>{typeof row[k] === "number" ? (row[k] as number).toFixed(4) : "—"}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 8 }}>Evaluation figures</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
                  {["roc_test.png","confusion_test.png","calibration_test.png"].map((fig) => (
                    <div key={fig} style={{ border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
                      <img src={`/api/dms/api/v1/evaluation/figures/${fig}`} alt={fig} style={{ width: "100%", display: "block" }} onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                      <div style={{ padding: "6px 10px", fontSize: 11, color: "var(--muted)" }}>{fig.replace(".png","").replace(/_/g," ")}</div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* COMPARE TAB */}
      {activeTab === "compare" && pubEval && pimaEval && (
        <div className="card card-pad">
          <h2 style={{ marginBottom: 4 }}>Side-by-side comparison</h2>
          <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 20 }}>
            These two models have different purposes, datasets, and feature sets.
            Comparison is for educational research only — they are not interchangeable.
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--surface-soft)", borderBottom: "2px solid var(--border)" }}>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>Property</th>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>Pima Research Model</th>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>Public Screening Model</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Purpose", "Educational benchmark research", "Non-laboratory public screening"],
                ["Dataset", "Pima Indians Diabetes (768 rows)", pubEval.dataset?.source ?? "NHANES"],
                ["Population", "Pima women, aged 21+", pubEval.population.split(".")[0]],
                ["Algorithm", "Logistic Regression", pubEval.model_name],
                ["Features", "8 (incl. lab values)", `${pubEval.features.length} (no lab values)`],
                ["Threshold", String(pimaEval.threshold.toFixed(3)), String(pubEval.threshold)],
                ["Test ROC-AUC", pimaEval.test?.[0]?.roc_auc != null ? (pimaEval.test[0].roc_auc as number).toFixed(4) : "—", (pubEval.test_metrics.roc_auc ?? 0).toFixed(4)],
                ["Test Recall", pimaEval.test?.[0]?.recall != null ? (pimaEval.test[0].recall as number).toFixed(4) : "—", (pubEval.test_metrics.recall ?? 0).toFixed(4)],
                ["Requires lab tests?", "Yes (glucose, insulin)", "No"],
                ["Clinical validation", "None", "None"],
              ].map(([prop, pima, pub]) => (
                <tr key={prop} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "9px 14px", color: "var(--muted)", fontWeight: 650 }}>{prop}</td>
                  <td style={{ padding: "9px 14px" }}>{pima}</td>
                  <td style={{ padding: "9px 14px" }}>{pub}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
