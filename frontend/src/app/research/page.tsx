// Research / Model comparison page — interactive Recharts charts + CDC BRFSS, India, US NHANES, and Historical Pima models
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, BookOpen, Database, Download, FlaskConical } from "lucide-react";
import {
  BarChart, Bar, CartesianGrid, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

interface PublicMetrics {
  roc_auc?: number; recall?: number; precision?: number;
  specificity?: number; f1?: number; brier?: number;
  balanced_accuracy?: number; accuracy?: number;
  tn?: number; fp?: number; fn?: number; tp?: number;
}

interface PublicEval {
  model_version: string;
  model_name: string;
  model_label?: string;
  dataset: { source?: string; n_eligible?: number; prevalence_train?: number };
  target_definition: { positive?: string; negative?: string; note?: string };
  test_metrics: PublicMetrics;
  test_confidence_intervals: Record<string, [number, number]>;
  calibration_bins?: Array<{ mean_predicted: number; observed_fraction: number; count: number }>;
  roc_curve?: Array<{ fpr: number; tpr: number }>;
  pr_curve?: Array<{ recall: number; precision: number }>;
  model_comparison?: Array<Record<string, number | string>>;
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

interface IndiaEval {
  model_label: string;
  model_version: string;
  ready: boolean;
  available: boolean;
  permission_status: string;
  status_message: string;
  intended_population: string;
  external_validation: string;
  blockers: string[];
}

interface BrfssModelMetrics {
  model: string;
  cv_roc_auc_mean: number;
  cv_roc_auc_std: number;
  cv_balanced_acc_mean: number;
  cv_f1_mean: number;
  accuracy: number;
  balanced_accuracy: number;
  precision: number;
  recall: number;
  specificity: number;
  f1: number;
  roc_auc: number;
  pr_auc: number;
  brier: number;
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
  confidence_intervals_95: Record<string, [number, number]>;
}

interface BrfssEval {
  available: boolean;
  model_version: string;
  model_label: string;
  selected_model: string;
  selection_reasoning: string;
  limitation_statement: string;
  dataset: {
    source: string;
    url: string;
    n_records: number;
    n_train: number;
    n_test: number;
    n_features: number;
    features: string[];
    target_definition: string;
    class_distribution: Record<string, number>;
  };
  models: Record<string, BrfssModelMetrics>;
  model_comparison: Array<Record<string, number | string>>;
  confusion_matrices: Record<string, { tn: number; fp: number; fn: number; tp: number }>;
  roc_curves: Record<string, Array<{ x: number; y: number }>>;
  pr_curves: Record<string, Array<{ x: number; y: number }>>;
  feature_importance: Array<{ model: string; feature: string; importance: number }>;
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
  const [brfssEval, setBrfssEval] = useState<BrfssEval | null>(null);
  const [indiaEval, setIndiaEval] = useState<IndiaEval | null>(null);
  const [pubEval, setPubEval] = useState<PublicEval | null>(null);
  const [pimaEval, setPimaEval] = useState<PimaEval | null>(null);
  const [brfssLoading, setBrfssLoading] = useState(true);
  const [pubLoading, setPubLoading] = useState(true);
  const [pimaLoading, setPimaLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"brfss" | "india" | "public" | "pima" | "compare">("brfss");

  useEffect(() => {
    fetch("/api/dms/api/v1/brfss-benchmark/evaluation").then(r => r.json()).then(setBrfssEval).catch(() => {}).finally(() => setBrfssLoading(false));
    fetch("/api/dms/api/v1/india-screening/evaluation").then(r => r.json()).then(setIndiaEval).catch(() => {});
    fetch("/api/dms/api/v1/public-screening/evaluation").then(r => r.json()).then(setPubEval).catch(() => {}).finally(() => setPubLoading(false));
    fetch("/api/dms/api/v1/evaluation").then(r => r.json()).then(setPimaEval).catch(() => {}).finally(() => setPimaLoading(false));
  }, []);

  function exportJson(filename: string, data: unknown) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const tabs = [
    { id: "brfss" as const, label: "CDC BRFSS Research Benchmark" },
    { id: "india" as const, label: "ICMR-INDIAB Indian adult model" },
    { id: "public" as const, label: "US benchmark (NHANES)" },
    { id: "pima" as const, label: "Historical Pima benchmark" },
    { id: "compare" as const, label: "Side-by-side comparison" },
  ];

  const rocPoints = (pubEval?.roc_curve || []).filter((_, i, arr) => i % Math.max(1, Math.floor(arr.length / 80)) === 0 || i === arr.length - 1);
  const prPoints = (pubEval?.pr_curve || []).filter((_, i, arr) => i % Math.max(1, Math.floor(arr.length / 80)) === 0 || i === arr.length - 1);

  const brfssTopFeatures = (brfssEval?.feature_importance || [])
    .filter((f) => f.model === brfssEval?.selected_model)
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 12);

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MODEL EVIDENCE · RESEARCH DASHBOARD</div>
          <h1>ML model research</h1>
          <p>
            Inspect evaluation results, interactive ROC/PR/calibration charts, dataset provenance,
            and limitations across all model families. No fabricated metrics.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/datasets" className="btn btn-secondary"><Database size={15} /> Datasets</Link>
          <Link href="/model-lab" className="btn btn-secondary"><FlaskConical size={15} /> Model lab</Link>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 24, borderBottom: "1px solid var(--border)" }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: "10px 16px", fontSize: 13, fontWeight: 650, cursor: "pointer",
              border: "none", background: "transparent",
              borderBottom: activeTab === t.id ? "2px solid var(--primary)" : "2px solid transparent",
              color: activeTab === t.id ? "var(--primary)" : "var(--muted)",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* CDC BRFSS RESEARCH BENCHMARK TAB */}
      {activeTab === "brfss" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {brfssLoading ? <p style={{ color: "var(--muted)" }}>Loading CDC BRFSS benchmark…</p> : !brfssEval?.available ? (
            <div className="note note-warn"><AlertTriangle size={16} /><p>BRFSS benchmark not yet generated.</p></div>
          ) : (
            <>
              <div className="card card-pad">
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
                  <div>
                    <div className="eyebrow">CDC BRFSS RESEARCH BENCHMARK</div>
                    <h2 style={{ margin: "4px 0" }}>{brfssEval.dataset.source}</h2>
                    <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: 13 }}>
                      Records: <strong>{brfssEval.dataset.n_records.toLocaleString()}</strong> (Train: {brfssEval.dataset.n_train.toLocaleString()} · Test: {brfssEval.dataset.n_test.toLocaleString()}) · Features: <strong>{brfssEval.dataset.n_features}</strong> · Selected: <strong>{brfssEval.selected_model}</strong>
                    </p>
                  </div>
                  <button className="btn btn-secondary" onClick={() => exportJson("brfss-evaluation.json", brfssEval)}>
                    <Download size={15} /> Export JSON
                  </button>
                </div>

                <div className="note note-warn" style={{ marginBottom: 16 }}>
                  <AlertTriangle size={16} />
                  <p style={{ margin: 0, fontSize: 13 }}>{brfssEval.limitation_statement}</p>
                </div>

                <div className="split-grid" style={{ gap: 16, marginBottom: 16 }}>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Target definition (<code>Diabetes_binary</code>)</div>
                    <div style={{ fontSize: 13, fontWeight: 650 }}>{brfssEval.dataset.target_definition}</div>
                  </div>
                  <div className="card" style={{ padding: 14 }}>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Class distribution</div>
                    <div style={{ fontSize: 13, fontWeight: 650 }}>
                      0 (No diabetes): {brfssEval.dataset.class_distribution["0_no_diabetes"]?.toLocaleString()} ·{" "}
                      1 (Prediabetes/Diabetes): {brfssEval.dataset.class_distribution["1_prediabetes_or_diabetes"]?.toLocaleString()}
                    </div>
                  </div>
                </div>

                <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--muted)" }}>{brfssEval.selection_reasoning}</p>

                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "var(--surface-soft)", borderBottom: "2px solid var(--border)" }}>
                        <th style={{ padding: "8px 10px", textAlign: "left" }}>Algorithm</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>CV ROC-AUC (mean±std)</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>Accuracy</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>Bal. Acc</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>Precision</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>Recall</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>Specificity</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>F1</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>ROC-AUC</th>
                        <th style={{ padding: "8px 10px", textAlign: "right" }}>PR-AUC</th>
                      </tr>
                    </thead>
                    <tbody>
                      {brfssEval.model_comparison.map((row) => (
                        <tr key={String(row.model)} style={{ borderBottom: "1px solid var(--border)", fontWeight: row.model === brfssEval.selected_model ? 700 : 400 }}>
                          <td style={{ padding: "8px 10px" }}>{String(row.model)} {row.model === brfssEval.selected_model ? "★" : ""}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.cv_roc_auc_mean).toFixed(4)} ± {Number(row.cv_roc_auc_std).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.accuracy).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.balanced_accuracy).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.precision).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.recall).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.specificity).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.f1).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.roc_auc).toFixed(4)}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right" }}>{Number(row.pr_auc).toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Interactive Charts: Comparison & Feature Importance */}
              <div className="split-grid" style={{ gap: 20 }}>
                <div className="card card-pad">
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>3-Algorithm Held-out Test Comparison</h3>
                  <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 12px" }}>
                    All 3 algorithms evaluated independently on the same 50,736 held-out test records.
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={brfssEval.model_comparison}>
                      <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                      <XAxis dataKey="model" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="roc_auc" name="ROC-AUC" fill="var(--primary)" />
                      <Bar dataKey="balanced_accuracy" name="Balanced Acc" fill="var(--secondary)" />
                      <Bar dataKey="recall" name="Recall" fill="#4a7c59" />
                      <Bar dataKey="f1" name="F1" fill="#3a6b8a" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="card card-pad">
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>Top Feature Importance ({brfssEval.selected_model})</h3>
                  <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 12px" }}>
                    Normalized feature importance across the 21 BRFSS survey indicators.
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={brfssTopFeatures} layout="vertical" margin={{ left: 30 }}>
                      <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                      <XAxis type="number" tick={{ fontSize: 11 }} />
                      <YAxis dataKey="feature" type="category" width={110} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Bar dataKey="importance" name="Importance" fill="var(--primary)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Interactive ROC & PR Curves for all 3 models */}
              <div className="split-grid" style={{ gap: 20 }}>
                <div className="card card-pad">
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>ROC Curves (All 3 Algorithms)</h3>
                  <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 12px" }}>
                    True Positive Rate vs. False Positive Rate on held-out test set.
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart>
                      <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                      <XAxis dataKey="x" type="number" domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: "False Positive Rate", position: "insideBottom", offset: -4, fontSize: 11 }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: "True Positive Rate", angle: -90, position: "insideLeft", fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--muted)" strokeDasharray="4 4" />
                      <Line data={brfssEval.roc_curves["Logistic Regression"]} dataKey="y" name="Logistic Regression" stroke="#3a6b8a" strokeWidth={2} dot={false} />
                      <Line data={brfssEval.roc_curves["Random Forest"]} dataKey="y" name="Random Forest" stroke="var(--primary)" strokeWidth={2.5} dot={false} />
                      <Line data={brfssEval.roc_curves["Gradient Boosting"]} dataKey="y" name="Gradient Boosting" stroke="#4a7c59" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="card card-pad">
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>Precision–Recall Curves (All 3 Algorithms)</h3>
                  <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 12px" }}>
                    Precision vs. Recall across thresholds on held-out test set.
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart>
                      <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                      <XAxis dataKey="x" type="number" domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: "Recall", position: "insideBottom", offset: -4, fontSize: 11 }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: "Precision", angle: -90, position: "insideLeft", fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line data={brfssEval.pr_curves["Logistic Regression"]} dataKey="y" name="Logistic Regression" stroke="#3a6b8a" strokeWidth={2} dot={false} />
                      <Line data={brfssEval.pr_curves["Random Forest"]} dataKey="y" name="Random Forest" stroke="var(--primary)" strokeWidth={2.5} dot={false} />
                      <Line data={brfssEval.pr_curves["Gradient Boosting"]} dataKey="y" name="Gradient Boosting" stroke="#4a7c59" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Confusion Matrices for every model */}
              <div className="card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 12 }}>Confusion Matrices (Held-out Test Set, n={brfssEval.dataset.n_test.toLocaleString()})</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
                  {Object.entries(brfssEval.confusion_matrices).map(([name, cm]) => (
                    <div key={name} className="card" style={{ padding: 14 }}>
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>{name}</div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, textAlign: "center" }}>
                        <div style={{ background: "var(--surface-soft)", padding: 8, borderRadius: 8 }}>
                          <div style={{ fontWeight: 800 }}>{cm.tn.toLocaleString()}</div>
                          <div style={{ fontSize: 10, color: "var(--muted)" }}>TN</div>
                        </div>
                        <div style={{ background: "var(--warning-bg)", padding: 8, borderRadius: 8 }}>
                          <div style={{ fontWeight: 800 }}>{cm.fp.toLocaleString()}</div>
                          <div style={{ fontSize: 10, color: "var(--muted)" }}>FP</div>
                        </div>
                        <div style={{ background: "var(--warning-bg)", padding: 8, borderRadius: 8 }}>
                          <div style={{ fontWeight: 800 }}>{cm.fn.toLocaleString()}</div>
                          <div style={{ fontSize: 10, color: "var(--muted)" }}>FN</div>
                        </div>
                        <div style={{ background: "color-mix(in srgb,var(--success) 12%,transparent)", padding: 8, borderRadius: 8 }}>
                          <div style={{ fontWeight: 800 }}>{cm.tp.toLocaleString()}</div>
                          <div style={{ fontSize: 10, color: "var(--muted)" }}>TP</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* INDIA ICMR-INDIAB TAB */}
      {activeTab === "india" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="card card-pad">
            <h2 style={{ marginBottom: 4 }}>ICMR-INDIAB Indian Adult Research Model (<code>in_v1</code>)</h2>
            <p style={{ margin: "0 0 14px", color: "var(--muted)", fontSize: 13 }}>
              {indiaEval?.intended_population ?? "Indian adults aged 20 years and above (men and women, rural and urban, across Indian states)."}
            </p>
            <div className="note note-warn" style={{ marginBottom: 16 }}>
              <AlertTriangle size={16} />
              <p style={{ margin: 0, fontSize: 13 }}>
                <strong>Permission Status: {indiaEval?.permission_status ?? "NOT REQUESTED"}.</strong>{" "}
                {indiaEval?.status_message ?? "India-specific model is under development. Existing international and historical models are available for research comparison only."}
              </p>
            </div>
            <h3 style={{ fontSize: 15, marginBottom: 8 }}>Planned Validation &amp; Governance Protocol</h3>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--muted)", lineHeight: 1.7 }}>
              <li>Cluster-safe train/validation/test split grouped by PSU (no sampling cluster overlap).</li>
              <li>Independent comparison of Logistic Regression, Random Forest, and Gradient Boosting with survey weights.</li>
              <li>Subgroup evaluation across sex, age groups (20–34, 35–49, 50–64, 65+), rural/urban residence, and states/regions.</li>
              <li>External validation status: <strong>{indiaEval?.external_validation ?? "External validation has not yet been completed."}</strong></li>
            </ul>
          </div>
        </div>
      )}

      {/* US BENCHMARK (NHANES) TAB */}
      {activeTab === "public" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {pubLoading ? <p style={{ color: "var(--muted)" }}>Loading US benchmark evaluation…</p> : !pubEval ? (
            <div className="note note-warn"><AlertTriangle size={16} /><p>US benchmark evaluation not available.</p></div>
          ) : (
            <>
              <div className="card card-pad">
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
                  <div>
                    <h2 style={{ marginBottom: 4 }}>US population research benchmark — {pubEval.model_name}</h2>
                    <p style={{ margin: "0 0 16px", color: "var(--muted)", fontSize: 13 }}>
                      Version: <code>{pubEval.model_version}</code> · Dataset: {pubEval.dataset?.source} (United States — not India-validated)
                    </p>
                  </div>
                  <button className="btn btn-secondary" onClick={() => exportJson("nhanes-evaluation.json", pubEval)}>
                    <Download size={15} /> Export JSON
                  </button>
                </div>

                <div className="note" style={{ marginBottom: 16 }}>
                  <BookOpen size={15} />
                  <p style={{ fontSize: 12, margin: 0 }}>
                    <strong>Target:</strong> {pubEval.target_definition?.positive}. {pubEval.target_definition?.note}
                  </p>
                </div>

                <div className="split-grid" style={{ gap: 16 }}>
                  <div>
                    <h3 style={{ fontSize: 14, marginBottom: 8 }}>Held-out Test Metrics</h3>
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
                    <h3 style={{ fontSize: 14, marginBottom: 8 }}>Confusion Matrix (Test Set, threshold={pubEval.threshold})</h3>
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
                  </div>
                </div>
              </div>

              <div className="split-grid" style={{ gap: 20 }}>
                <div className="card card-pad">
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>ROC Curve (Test Set)</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={rocPoints}>
                      <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                      <XAxis dataKey="fpr" type="number" domain={[0, 1]} tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--muted)" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="tpr" name="TPR" stroke="var(--primary)" strokeWidth={2.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="card card-pad">
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>Precision–Recall Curve (Test Set)</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={prPoints}>
                      <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                      <XAxis dataKey="recall" type="number" domain={[0, 1]} tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Line type="monotone" dataKey="precision" name="Precision" stroke="var(--secondary)" strokeWidth={2.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* HISTORICAL PIMA TAB */}
      {activeTab === "pima" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {pimaLoading ? <p style={{ color: "var(--muted)" }}>Loading Pima benchmark data…</p> : !pimaEval ? (
            <div className="note note-warn"><AlertTriangle size={16} /><p>Pima benchmark evaluation not available.</p></div>
          ) : (
            <div className="card card-pad">
              <h2 style={{ marginBottom: 4 }}>Historical Pima research benchmark — Logistic Regression</h2>
              <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: 13 }}>
                768 records from a specific cohort of women aged 21+ of Pima heritage. Does not represent all Indian adults.
              </p>
              <div className="note" style={{ marginBottom: 16 }}>
                <AlertTriangle size={15} />
                <p style={{ fontSize: 12, margin: 0 }}>{pimaEval.test_exposure_note}</p>
              </div>
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
          )}
        </div>
      )}

      {/* COMPARE TAB */}
      {activeTab === "compare" && (
        <div className="card card-pad" style={{ overflowX: "auto" }}>
          <h2 style={{ marginBottom: 4 }}>Side-by-side Model Comparison</h2>
          <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 16 }}>
            These four model families have completely separate datasets, targets, and feature schemas.
            Similar algorithm scores on a single dataset can occur when linear and tree models capture the
            same dominant additive predictors — overlapping confidence intervals do not prove model equivalence.
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--surface-soft)", borderBottom: "2px solid var(--border)" }}>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>Property</th>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>Historical Pima benchmark</th>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>US benchmark (NHANES)</th>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>Large US survey (BRFSS)</th>
                <th style={{ padding: "10px 14px", textAlign: "left" }}>ICMR-INDIAB India model</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Dataset", "Pima Indians (768 rows)", pubEval?.dataset?.source ?? "NHANES 2017–2018", "CDC BRFSS (253,680 rows)", "ICMR-INDIAB (pending DUA)"],
                ["Population", "Pima heritage women 21+", "US civilian adults 21+", "US adult survey respondents", "Indian adults 20+ (rural & urban)"],
                ["Status", "Benchmark active", "Benchmark active (US only)", "Benchmark active (US only)", indiaEval?.permission_status ?? "NOT REQUESTED"],
                ["Requires lab tests?", "Yes (glucose, insulin)", "No", "No (21 survey indicators)", "No"],
                ["Test ROC-AUC", pimaEval?.test?.[0]?.roc_auc != null ? Number(pimaEval.test[0].roc_auc).toFixed(4) : "—", pubEval?.test_metrics?.roc_auc?.toFixed(4) ?? "—", brfssEval?.models?.[brfssEval.selected_model]?.roc_auc?.toFixed(4) ?? "—", "Not yet trained"],
                ["External validation", "None", "None in India", "None in India", "External validation has not yet been completed."],
              ].map(([prop, pima, pub, brfss, ind]) => (
                <tr key={prop} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "9px 14px", color: "var(--muted)", fontWeight: 650 }}>{prop}</td>
                  <td style={{ padding: "9px 14px" }}>{pima}</td>
                  <td style={{ padding: "9px 14px" }}>{pub}</td>
                  <td style={{ padding: "9px 14px" }}>{brfss}</td>
                  <td style={{ padding: "9px 14px" }}>{ind}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
