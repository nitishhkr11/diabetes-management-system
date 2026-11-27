"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Download, TrendingUp } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { createClient } from "@/lib/supabase/browser";
import { api, IndiaRiskRecord } from "@/lib/api";

const MMOL_TO_MGDL = 18.0182;

function toMgDl(val: unknown, unit: unknown): number | null {
  if (typeof val !== "number" || Number.isNaN(val)) return null;
  if (unit === "mmol/L") return Number((val * MMOL_TO_MGDL).toFixed(1));
  return Number(val.toFixed(1));
}

export default function ProgressPage() {
  const [records, setRecords] = useState<IndiaRiskRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const sb = createClient();
        const { data: { session } } = await sb.auth.getSession();
        if (!session) {
          setError("Sign in to view your trends and progress.");
          setLoading(false);
          return;
        }
        const data = await api<{ items: IndiaRiskRecord[] }>(
          "/api/v1/india-risk/history?limit=100",
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        );
        setRecords(data.items || []);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load saved history.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleExport() {
    setExporting(true);
    try {
      const sb = createClient();
      const { data: { session } } = await sb.auth.getSession();
      if (!session) return;
      const res = await fetch("/api/dms/api/v1/india-risk/history/export", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) throw new Error("Export failed.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "glucoguide-india-history.csv";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <div style={{ padding: 40, color: "var(--muted)" }}>Loading your progress…</div>;
  if (error) {
    return (
      <div style={{ padding: 40 }}>
        <p className="status-error">{error}</p>
        <Link href="/auth/login?next=/dashboard/progress" className="btn">Sign in</Link>
      </div>
    );
  }

  const chronological = [...records].sort((a, b) => a.created_at.localeCompare(b.created_at));

  const idrsSeries = chronological
    .filter((r) => r.assessment_type === "mdrf_idrs" && r.score != null)
    .map((r) => ({
      date: new Date(r.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
      score: r.score as number,
      category: r.result_category,
    }));

  const hba1cSeries = chronological
    .filter((r) => r.assessment_type === "lab_interpretation" && typeof r.inputs?.hba1c_pct === "number")
    .map((r) => ({
      date: new Date(r.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
      value: r.inputs.hba1c_pct as number,
    }));

  const fpgSeries = chronological
    .filter((r) => r.assessment_type === "lab_interpretation" && typeof r.inputs?.fasting_glucose === "number")
    .map((r) => ({
      date: new Date(r.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
      value: toMgDl(r.inputs.fasting_glucose, r.inputs.fasting_unit) as number,
    }))
    .filter((d) => d.value != null);

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PERSONAL PROGRESS · REAL SAVED RECORDS</div>
          <h1>Trends &amp; Progress</h1>
          <p>
            Separate chronological charts for comparable assessments. Compatible units are enforced; different test
            types are never mixed into one chart.
          </p>
        </div>
        {records.length > 0 && (
          <button className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
            <Download size={15} /> {exporting ? "Exporting…" : "Export CSV"}
          </button>
        )}
      </div>

      {records.length === 0 ? (
        <div className="card empty-state">
          <div>
            <span className="empty-mark"><TrendingUp size={24} /></span>
            <h2>Your health journey starts here.</h2>
            <p>Save at least two comparable MDRF-IDRS or lab-test records to see chronological trends.</p>
            <Link className="btn" href="/screening">
              Check Your Risk <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 18 }}>
          {/* Chart A: MDRF-IDRS */}
          <section className="card card-pad">
            <div className="section-title">
              <div>
                <h2>MDRF-IDRS Screening Score Over Time (0–100)</h2>
                <p>Reference lines at 30 (Moderate threshold) and 60 (High risk threshold). Screening score only.</p>
              </div>
            </div>
            {idrsSeries.length < 2 ? (
              <p style={{ color: "var(--muted)", fontSize: 13.5, margin: 0 }}>
                {idrsSeries.length === 1
                  ? `1 saved MDRF-IDRS score (${idrsSeries[0].score}/100 on ${idrsSeries[0].date}). Save another assessment later to plot a trend.`
                  : "No saved MDRF-IDRS records yet."}
              </p>
            ) : (
              <div style={{ width: "100%", height: 260 }} aria-label="MDRF-IDRS score trend chart">
                <ResponsiveContainer>
                  <LineChart data={idrsSeries} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={12} />
                    <YAxis domain={[0, 100]} stroke="var(--muted)" fontSize={12} />
                    <Tooltip />
                    <ReferenceLine y={30} stroke="var(--warning)" strokeDasharray="4 4" label={{ value: "30 Mod", fill: "var(--warning)", fontSize: 11 }} />
                    <ReferenceLine y={60} stroke="var(--danger)" strokeDasharray="4 4" label={{ value: "60 High", fill: "var(--danger)", fontSize: 11 }} />
                    <Line type="monotone" dataKey="score" name="MDRF-IDRS" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>

          {/* Chart B: HbA1c */}
          <section className="card card-pad">
            <div className="section-title">
              <div>
                <h2>HbA1c (%) Over Time</h2>
                <p>Reference lines at 5.7% (Prediabetes) and 6.5% (Diabetes range). Lowering values do not imply cure without clinical review.</p>
              </div>
            </div>
            {hba1cSeries.length < 2 ? (
              <p style={{ color: "var(--muted)", fontSize: 13.5, margin: 0 }}>
                {hba1cSeries.length === 1
                  ? `1 saved HbA1c entry (${hba1cSeries[0].value}% on ${hba1cSeries[0].date}). Save a follow-up HbA1c later to plot a trend.`
                  : "No saved HbA1c records yet."}
              </p>
            ) : (
              <div style={{ width: "100%", height: 260 }} aria-label="HbA1c trend chart">
                <ResponsiveContainer>
                  <LineChart data={hba1cSeries} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={12} />
                    <YAxis domain={["auto", "auto"]} stroke="var(--muted)" fontSize={12} unit="%" />
                    <Tooltip />
                    <ReferenceLine y={5.7} stroke="var(--warning)" strokeDasharray="4 4" label={{ value: "5.7%", fill: "var(--warning)", fontSize: 11 }} />
                    <ReferenceLine y={6.5} stroke="var(--danger)" strokeDasharray="4 4" label={{ value: "6.5%", fill: "var(--danger)", fontSize: 11 }} />
                    <Line type="monotone" dataKey="value" name="HbA1c (%)" stroke="var(--secondary)" strokeWidth={2.5} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>

          {/* Chart C: Fasting Plasma Glucose */}
          <section className="card card-pad">
            <div className="section-title">
              <div>
                <h2>Fasting Plasma Glucose (mg/dL) Over Time</h2>
                <p>Converted to mg/dL for consistent comparison. Reference lines at 100 mg/dL (ADA IFG) and 126 mg/dL.</p>
              </div>
            </div>
            {fpgSeries.length < 2 ? (
              <p style={{ color: "var(--muted)", fontSize: 13.5, margin: 0 }}>
                {fpgSeries.length === 1
                  ? `1 saved Fasting Glucose entry (${fpgSeries[0].value} mg/dL on ${fpgSeries[0].date}). Save another fasting result later to plot a trend.`
                  : "No saved Fasting Plasma Glucose records yet."}
              </p>
            ) : (
              <div style={{ width: "100%", height: 260 }} aria-label="Fasting plasma glucose trend chart">
                <ResponsiveContainer>
                  <LineChart data={fpgSeries} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={12} />
                    <YAxis domain={["auto", "auto"]} stroke="var(--muted)" fontSize={12} />
                    <Tooltip />
                    <ReferenceLine y={100} stroke="var(--warning)" strokeDasharray="4 4" label={{ value: "100 mg/dL", fill: "var(--warning)", fontSize: 11 }} />
                    <ReferenceLine y={126} stroke="var(--danger)" strokeDasharray="4 4" label={{ value: "126 mg/dL", fill: "var(--danger)", fontSize: 11 }} />
                    <Line type="monotone" dataKey="value" name="Fasting Glucose (mg/dL)" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
