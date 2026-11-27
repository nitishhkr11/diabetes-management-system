"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, Download, Minus, TrendingUp } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid,
} from "recharts";
import { createClient } from "@/lib/supabase/browser";

interface ScreeningRecord {
  id: string;
  created_at: string;
  model_version: string;
  model_name: string;
  score: number;
  label: number;
  band: string;
  threshold: number;
  inputs: Record<string, number | null>;
  dataset: string;
}

const MEASUREMENT_SERIES = [
  { key: "bmi",        label: "BMI",                    unit: "kg/m²",   color: "#c75d25" },
  { key: "waist_cm",   label: "Waist circumference",    unit: "cm",       color: "#702b3a" },
  { key: "sys_bp",     label: "Systolic BP",            unit: "mmHg",     color: "#4a7c59" },
  { key: "dia_bp",     label: "Diastolic BP",           unit: "mmHg",     color: "#3a6b8a" },
  { key: "weight_kg",  label: "Weight",                 unit: "kg",       color: "#8a5a3a" },
];

function Delta({ first, last, unit }: { first: number | null; last: number | null; unit: string }) {
  if (first == null || last == null) return <span style={{ color: "var(--muted)" }}>—</span>;
  const diff = last - first;
  const pct = first !== 0 ? ((diff / first) * 100).toFixed(1) : null;
  return (
    <span style={{ color: diff < 0 ? "var(--success)" : diff > 0 ? "var(--warning)" : "var(--muted)", fontWeight: 700, display: "flex", alignItems: "center", gap: 4 }}>
      {diff > 0 ? <ArrowUp size={14} /> : diff < 0 ? <ArrowDown size={14} /> : <Minus size={14} />}
      {diff > 0 ? "+" : ""}{diff.toFixed(1)} {unit}
      {pct && <span style={{ fontWeight: 400, fontSize: 11 }}>({pct}%)</span>}
    </span>
  );
}

export default function ProgressPage() {
  const [records, setRecords] = useState<ScreeningRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [activeSeries, setActiveSeries] = useState<string>("bmi");

  useEffect(() => {
    (async () => {
      try {
        const sb = createClient();
        const { data: { session } } = await sb.auth.getSession();
        if (!session) { setError("Sign in to view your progress."); setLoading(false); return; }
        const res = await fetch("/api/dms/api/v1/public-screening/history?limit=100", {
          headers: { Authorization: `Bearer ${session.access_token}` },
          cache: "no-store",
        });
        if (!res.ok) throw new Error("Could not load history.");
        const data = await res.json();
        setRecords(data.items || []);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load.");
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
      const res = await fetch("/api/dms/api/v1/public-screening/history/export", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "screening-history.csv";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <div style={{ padding: 40, color: "var(--muted)" }}>Loading…</div>;
  if (error) return (
    <div style={{ padding: 40 }}>
      <p style={{ color: "var(--warning)" }}>{error}</p>
      <Link href="/auth/login" className="btn" style={{ marginTop: 12 }}>Sign in</Link>
    </div>
  );

  const sorted = [...records].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const first = sorted[0];
  const last = sorted[sorted.length - 1];

  // Build chart data for selected series
  const ser = MEASUREMENT_SERIES.find((s) => s.key === activeSeries)!;
  const chartData = sorted.map((r) => ({
    date: new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    value: r.inputs[ser.key] ?? null,
    score: Math.round(r.score * 100),
  }));

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PERSONAL PROGRESS · SCREENING HISTORY</div>
          <h1>Measurement progress</h1>
          <p>Your saved screening assessments, chronologically. {records.length === 0 && "No assessments saved yet."}</p>
        </div>
        {records.length > 0 && (
          <button className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
            <Download size={15} /> {exporting ? "Exporting…" : "Export CSV"}
          </button>
        )}
      </div>

      {records.length === 0 ? (
        <div className="card card-pad" style={{ textAlign: "center", padding: "60px 20px" }}>
          <TrendingUp size={40} style={{ color: "var(--muted)", marginBottom: 12 }} />
          <h3 style={{ marginBottom: 8 }}>No assessments yet</h3>
          <p style={{ color: "var(--muted)" }}>
            Complete a screening and save it to start tracking your measurements over time.
          </p>
          <Link href="/screening" className="btn" style={{ marginTop: 16 }}>
            Start a screening
          </Link>
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12, marginBottom: 24 }}>
            {MEASUREMENT_SERIES.filter((s) => last?.inputs[s.key] != null).map((s) => (
              <div key={s.key} className="card card-pad" style={{ padding: 16 }}>
                <div style={{ fontSize: 11, color: "var(--muted)", fontWeight: 700, marginBottom: 6 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 2 }}>
                  {last.inputs[s.key]?.toFixed(1)} <span style={{ fontSize: 11, color: "var(--muted)" }}>{s.unit}</span>
                </div>
                {records.length > 1 && <Delta first={first.inputs[s.key]} last={last.inputs[s.key]} unit={s.unit} />}
              </div>
            ))}
            <div className="card card-pad" style={{ padding: 16 }}>
              <div style={{ fontSize: 11, color: "var(--muted)", fontWeight: 700, marginBottom: 6 }}>Assessments</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>{records.length}</div>
              <div style={{ fontSize: 11, color: "var(--muted)" }}>saved total</div>
            </div>
          </div>

          {/* Trend chart */}
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>Measurement trend</h3>
              <div style={{ display: "flex", gap: 6 }}>
                {MEASUREMENT_SERIES.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setActiveSeries(s.key)}
                    style={{
                      padding: "4px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700, cursor: "pointer",
                      border: `1px solid ${activeSeries === s.key ? s.color : "var(--border)"}`,
                      background: activeSeries === s.key ? s.color : "transparent",
                      color: activeSeries === s.key ? "#fff" : "var(--muted)",
                    }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }}
                  formatter={(v) => [v != null ? `${Number(v)} ${ser.unit}` : "—", ser.label]}
                />
                <Line
                  type="monotone" dataKey="value" stroke={ser.color}
                  strokeWidth={2.5} dot={{ r: 4 }} connectNulls={false}
                  name={ser.label}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Model score trend */}
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16 }}>Model score history</h3>
            <p style={{ margin: "0 0 12px", fontSize: 12, color: "var(--muted)" }}>
              Scores belong strictly to their own model family and version (Pima, NHANES US benchmark, or
              ICMR-INDIAB) and are never combined across models. Changes in model scores are{" "}
              <strong>not</strong> proof of health improvement or deterioration.
              Current model version: <code>ps_v1</code>.
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }}
                  formatter={(v) => [`${Number(v)}%`, "Score"]}
                />
                <ReferenceLine
                  y={Math.round((last?.threshold ?? 0.26) * 100)}
                  stroke="var(--warning)" strokeDasharray="4 4"
                  label={{ value: "threshold", position: "right", fontSize: 10 }}
                />
                <Line type="monotone" dataKey="score" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* History table */}
          <div className="card" style={{ overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border)", background: "var(--surface-soft)" }}>
                  <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 700 }}>Date</th>
                  <th style={{ padding: "10px 16px", textAlign: "right", fontWeight: 700 }}>Score</th>
                  <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 700 }}>Result</th>
                  <th style={{ padding: "10px 16px", textAlign: "right", fontWeight: 700 }}>BMI</th>
                  <th style={{ padding: "10px 16px", textAlign: "right", fontWeight: 700 }}>Waist (cm)</th>
                  <th style={{ padding: "10px 16px", textAlign: "right", fontWeight: 700 }}>Sys BP</th>
                </tr>
              </thead>
              <tbody>
                {[...records].reverse().map((r) => (
                  <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "9px 16px" }}>
                      {new Date(r.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
                    </td>
                    <td style={{ padding: "9px 16px", textAlign: "right", fontWeight: 700 }}>
                      {Math.round(r.score * 100)}%
                    </td>
                    <td style={{ padding: "9px 16px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
                        background: r.label === 1 ? "var(--warning-bg)" : "color-mix(in srgb,var(--success) 10%,transparent)",
                        color: r.label === 1 ? "var(--warning)" : "var(--success)",
                      }}>
                        {r.band === "higher" ? "Higher" : "Lower"}
                      </span>
                    </td>
                    <td style={{ padding: "9px 16px", textAlign: "right" }}>
                      {r.inputs.bmi?.toFixed(1) ?? "—"}
                    </td>
                    <td style={{ padding: "9px 16px", textAlign: "right" }}>
                      {r.inputs.waist_cm?.toFixed(0) ?? "—"}
                    </td>
                    <td style={{ padding: "9px 16px", textAlign: "right" }}>
                      {r.inputs.sys_bp?.toFixed(0) ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
