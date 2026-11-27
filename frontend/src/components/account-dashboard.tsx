"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  ClipboardCheck,
  FileSpreadsheet,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { api, IndiaRiskRecord } from "@/lib/api";
import { createClient } from "@/lib/supabase/browser";

export function AccountDashboard({ email }: { email: string }) {
  const [records, setRecords] = useState<IndiaRiskRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const sb = createClient();
        const { data: { session } } = await sb.auth.getSession();
        if (!session) {
          setError("Please sign in to view your dashboard.");
          setLoading(false);
          return;
        }
        const res = await api<{ items: IndiaRiskRecord[]; total: number }>(
          "/api/v1/india-risk/history?limit=100",
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        );
        setRecords(res.items || []);
        setTotal(res.total || 0);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load your saved assessments.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const latest = records[0] || null;
  const latestIdrs = records.find((r) => r.assessment_type === "mdrf_idrs") || null;
  const latestLab = records.find((r) => r.assessment_type === "lab_interpretation") || null;

  const insights: string[] = [];
  if (latestIdrs) {
    insights.push(`Your latest MDRF-IDRS screening score is ${latestIdrs.score ?? "—"} / 100 (${latestIdrs.result_category}).`);
  }
  if (latestLab) {
    insights.push(`Your latest saved laboratory interpretation is: ${latestLab.result_category}.`);
  }
  if (records.length > 0) {
    insights.push("Consider sharing your saved screening and lab records with a qualified healthcare professional during check-ups.");
  }

  return (
    <>
      <PageHeader
        eyebrow="PERSONAL HEALTH DASHBOARD"
        title={`Welcome${email !== "Account" ? `, ${email.split("@")[0]}` : ""}`}
        description="Your private workspace for saved MDRF-IDRS risk screenings and laboratory test interpretations."
        action={
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link className="btn" href="/screening?mode=idrs">
              New Risk Screening <ArrowRight size={15} />
            </Link>
            <Link className="btn btn-secondary" href="/screening?mode=lab">
              Interpret Lab Report
            </Link>
          </div>
        }
      />

      {error && (
        <div className="status-error" role="alert">
          {error} If Supabase is configured, ensure the `india_risk_assessments` schema has been applied.
        </div>
      )}

      {loading ? (
        <div className="card empty-state"><p>Loading your dashboard…</p></div>
      ) : records.length === 0 ? (
        <section className="card empty-state" aria-label="Empty dashboard state">
          <div>
            <span className="empty-mark"><ClipboardCheck size={24} /></span>
            <h2>Your health journey starts here.</h2>
            <p>
              You do not have any saved assessments yet. Nothing is saved automatically — complete a non-laboratory
              MDRF-IDRS screening or interpret an existing blood test, then check the consent box to save it here.
            </p>
            <div style={{ display: "flex", justifyContent: "center", gap: 10, flexWrap: "wrap" }}>
              <Link className="btn" href="/screening?mode=idrs">
                Check Risk (No Blood Test) <ArrowRight size={15} />
              </Link>
              <Link className="btn btn-secondary" href="/screening?mode=lab">
                Interpret Blood Test
              </Link>
            </div>
          </div>
        </section>
      ) : (
        <>
          <div className="stat-grid">
            <section className="card stat-card">
              <span>Saved Assessments</span>
              <strong>{total}</strong>
              <small>Explicitly consented records</small>
            </section>
            <section className="card stat-card">
              <span>Latest Assessment</span>
              <strong style={{ fontSize: 20 }}>
                {latest ? new Date(latest.created_at).toLocaleDateString() : "—"}
              </strong>
              <small>{latest ? (latest.assessment_type === "mdrf_idrs" ? "MDRF-IDRS Screening" : "Lab Interpretation") : "No records"}</small>
            </section>
            <section className="card stat-card">
              <span>Latest MDRF-IDRS</span>
              <strong>{latestIdrs?.score != null ? `${latestIdrs.score}/100` : "—"}</strong>
              <small>{latestIdrs ? latestIdrs.result_category : "No IDRS saved yet"}</small>
            </section>
            <section className="card stat-card">
              <span>Latest Lab Status</span>
              <strong style={{ fontSize: 16, lineHeight: 1.3 }}>
                {latestLab ? latestLab.result_category : "—"}
              </strong>
              <small>{latestLab ? new Date(latestLab.created_at).toLocaleDateString() : "No lab reports saved yet"}</small>
            </section>
          </div>

          {latestIdrs && latestIdrs.score != null && (
            <section className="card card-pad" style={{ marginBottom: 18 }}>
              <div className="section-title">
                <div>
                  <h2>Latest MDRF-IDRS Screening Scale (0–100)</h2>
                  <p>Screening score only — not a diabetes diagnosis or personalised probability.</p>
                </div>
                <Link className="text-link" href="/dashboard/progress">
                  View Trends <TrendingUp size={14} />
                </Link>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                <strong style={{ fontSize: 22 }}>{latestIdrs.score} / 100</strong>
                <span className={`status-badge ${latestIdrs.score < 30 ? "badge-success" : latestIdrs.score <= 50 ? "badge-warning" : "badge-danger"}`}>
                  {latestIdrs.result_category}
                </span>
              </div>
              <div className="idrs-scale-track" aria-label={`MDRF-IDRS score ${latestIdrs.score} out of 100`}>
                <div className="idrs-seg-low" />
                <div className="idrs-seg-mod" />
                <div className="idrs-seg-high" />
                <div className="idrs-marker" style={{ left: `${Math.min(100, Math.max(0, latestIdrs.score))}%` }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--muted)", marginTop: 6 }}>
                <span>Below 30: Low risk</span>
                <span>30–50: Moderate risk</span>
                <span>60+: High risk</span>
              </div>
            </section>
          )}

          <div className="split-grid" style={{ alignItems: "start" }}>
            <section className="card card-pad">
              <div className="section-title">
                <div>
                  <h2>Recent Assessment History</h2>
                  <p>Chronological records scoped strictly to your signed-in account.</p>
                </div>
                <Link className="text-link" href="/history">
                  All history <ArrowRight size={13} />
                </Link>
              </div>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.slice(0, 6).map((r) => (
                      <tr key={r.id}>
                        <td>{new Date(r.created_at).toLocaleDateString()}</td>
                        <td>{r.assessment_type === "mdrf_idrs" ? "MDRF-IDRS" : "Lab Test"}</td>
                        <td>
                          <strong>{r.result_category}</strong>
                          {r.score != null ? ` (${r.score}/100)` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <aside style={{ display: "grid", gap: 14 }}>
              <section className="card card-pad">
                <div className="feature-icon"><Activity size={18} /></div>
                <h2 className="chart-title">Health Insights</h2>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--muted)", display: "grid", gap: 6 }}>
                  {insights.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>

              <section className="card card-pad">
                <div className="feature-icon"><ShieldCheck size={18} /></div>
                <h2 className="chart-title">Quick Actions &amp; Privacy</h2>
                <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--muted)" }}>
                  Your records are protected by Supabase Row Level Security. You can export or delete them anytime.
                </p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Link className="btn btn-secondary" href="/dashboard/progress">
                    <TrendingUp size={14} /> Trends
                  </Link>
                  <Link className="btn btn-secondary" href="/settings">
                    <FileSpreadsheet size={14} /> Export / Delete
                  </Link>
                </div>
              </section>
            </aside>
          </div>
        </>
      )}
    </>
  );
}
