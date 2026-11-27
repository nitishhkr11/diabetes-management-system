"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowDownToLine, ArrowRight, Trash2 } from "lucide-react";
import { api, IndiaRiskRecord } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/browser";

export function HistoryManager() {
  const [rows, setRows] = useState<IndiaRiskRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  async function getToken() {
    const sb = createClient();
    const { data: { session } } = await sb.auth.getSession();
    return session?.access_token || "";
  }

  async function refresh() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sign in to view your saved history.");
      const result = await api<{ items: IndiaRiskRecord[]; total: number }>(
        "/api/v1/india-risk/history?limit=100",
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setRows(result.items || []);
      setTotal(result.total || 0);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "History is unavailable.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function remove(id: string) {
    if (!window.confirm("Delete this saved assessment? This cannot be undone.")) return;
    setBusy(id);
    try {
      const token = await getToken();
      await api(`/api/v1/india-risk/history/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete that record.");
    } finally {
      setBusy("");
    }
  }

  async function handleExport() {
    const token = await getToken();
    if (!token) return;
    const res = await fetch("/api/dms/api/v1/india-risk/history/export", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "glucoguide-india-history.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const activeRow = rows.find((r) => r.id === selected);

  return (
    <>
      <PageHeader
        eyebrow="PRIVATE ACCOUNT HISTORY"
        title="My Saved Assessments"
        description="Only records associated with your signed-in account are listed. Nothing is stored without your explicit consent."
        action={
          rows.length > 0 ? (
            <button className="btn btn-secondary" onClick={handleExport}>
              <ArrowDownToLine size={14} /> Export CSV
            </button>
          ) : undefined
        }
      />

      {error && <div className="status-error" role="alert">{error}</div>}

      {loading ? (
        <div className="card empty-state"><p>Loading your records…</p></div>
      ) : rows.length === 0 ? (
        <div className="card empty-state">
          <div>
            <span className="empty-mark"><ArrowDownToLine size={22} /></span>
            <h2>No saved assessments yet</h2>
            <p>
              After completing an MDRF-IDRS screening or blood-test interpretation, check the consent box to save it to
              your history.
            </p>
            <Link className="btn" href="/screening">
              Check Your Risk <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Pathway</th>
                  <th>Guideline</th>
                  <th>Score / Summary</th>
                  <th>Result Category</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{new Date(r.created_at).toLocaleString()}</td>
                    <td>{r.assessment_type === "mdrf_idrs" ? "MDRF-IDRS (No Blood Test)" : "Lab Interpretation"}</td>
                    <td>{r.guideline_version}</td>
                    <td>{r.score != null ? `${r.score} / 100` : "Lab values"}</td>
                    <td><strong>{r.result_category}</strong></td>
                    <td>
                      <button
                        className="icon-button"
                        onClick={() => setSelected(selected === r.id ? "" : r.id)}
                        aria-expanded={selected === r.id}
                      >
                        {selected === r.id ? "Hide" : "View"}
                      </button>{" "}
                      <button
                        className="icon-button"
                        onClick={() => remove(r.id)}
                        disabled={busy === r.id}
                        aria-label="Delete assessment"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {activeRow && (
            <section className="card card-pad" style={{ marginTop: 14 }}>
              <h2 className="chart-title">
                Assessment Details · {new Date(activeRow.created_at).toLocaleString()}
              </h2>
              <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
                {activeRow.assessment_type === "mdrf_idrs"
                  ? "MDRF-IDRS risk-screening record (not a clinical diagnosis)."
                  : "Laboratory reference-range interpretation record."}
              </p>
              <div className="field-grid">
                {Object.entries(activeRow.inputs || {}).map(([key, value]) => (
                  <div key={key} className="card" style={{ padding: "10px 12px" }}>
                    <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{key}</span>
                    <strong style={{ display: "block", fontSize: 14 }}>
                      {value === null || value === undefined ? "Not entered" : String(value)}
                    </strong>
                  </div>
                ))}
              </div>
            </section>
          )}

          {total > rows.length && (
            <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 10 }}>
              Showing {rows.length} of {total} records.
            </p>
          )}
        </>
      )}
    </>
  );
}
