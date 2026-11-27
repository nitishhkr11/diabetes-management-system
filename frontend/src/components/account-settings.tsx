"use client";
import { useState } from "react";
import { Download, ShieldCheck, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/browser";

export function AccountSettings({ email }: { email: string }) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function getToken() {
    const sb = createClient();
    const { data: { session } } = await sb.auth.getSession();
    return session?.access_token || "";
  }

  async function handleExport() {
    setError("");
    const token = await getToken();
    if (!token) {
      setError("Please sign in to export your records.");
      return;
    }
    const res = await fetch("/api/dms/api/v1/india-risk/history/export", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setError("Could not export your records.");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "glucoguide-india-history.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function deleteHistory() {
    if (!window.confirm("Permanently delete every screening and lab record saved to this account? This cannot be undone.")) {
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const token = await getToken();
      await api<{ deleted: boolean; count: number }>("/api/v1/india-risk/history", {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessage("Your saved assessment history has been deleted.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete history.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="ACCOUNT & PRIVACY"
        title="Your Account & Data Controls"
        description="Review your signed-in account email and export or delete your saved screening and lab-interpretation records."
      />
      <div className="content-grid">
        <section className="card content-card">
          <div className="feature-icon"><ShieldCheck size={18} /></div>
          <h2>Account Profile</h2>
          <p>Signed-in email address</p>
          <b>{email}</b>
          <p style={{ marginTop: 12 }}>
            Authentication and password reset are handled securely by Supabase Auth. GlucoGuide never stores plaintext passwords.
          </p>
        </section>

        <section className="card content-card">
          <div className="feature-icon"><Trash2 size={17} /></div>
          <h2>Saved Assessment Data</h2>
          <p>
            Records are stored in `india_risk_assessments` only when you explicitly check the consent box. PostgreSQL
            Row Level Security ensures only your account can access your records.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
            <button className="btn btn-secondary" onClick={handleExport}>
              <Download size={14} /> Export My Records (CSV)
            </button>
            <button className="btn" onClick={deleteHistory} disabled={busy}>
              {busy ? "Deleting…" : "Delete All History"}
            </button>
          </div>
          {message && <p role="status" className="status-success" style={{ marginTop: 12 }}>{message}</p>}
          {error && <p role="alert" className="status-error" style={{ marginTop: 12 }}>{error}</p>}
        </section>

        <section className="card content-card">
          <h2>Retention &amp; Consent</h2>
          <p>
            Saved records remain in your private Supabase account until you delete individual items in History or clear
            all records here. Public screening without signing in saves nothing.
          </p>
        </section>

        <section className="card content-card">
          <h2>Account Removal</h2>
          <p>
            Deleting your authentication account in Supabase cascades to your saved records. A Supabase service-role key
            is never exposed to the browser.
          </p>
        </section>
      </div>
    </>
  );
}
