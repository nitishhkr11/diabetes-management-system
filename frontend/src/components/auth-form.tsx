"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { createClient } from "@/lib/supabase/browser";

type Mode = "login" | "register" | "forgot" | "reset";
const labels = { login: ["Welcome back", "Sign in to use your personal dashboard and private assessment history."], register: ["Create your account", "Your account lets you use the estimator and choose whether to save assessments."], forgot: ["Reset your password", "We’ll send a secure password reset link to your email."], reset: ["Choose a new password", "Set a new password for your GlucoGuide account."] } as const;

export function AuthForm({ mode }: { mode: Mode }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const supabase = createClient();
      if (mode === "register") {
        const { error: authError } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/dashboard` } });
        if (authError) throw authError;
        setMessage("Check your email for a verification link. Once verified, sign in to continue.");
      } else if (mode === "login") {
        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
        if (authError) throw authError;
        const requested = new URL(window.location.href).searchParams.get("next");
        let destination = "/dashboard";
        if (requested?.startsWith("/") && !requested.startsWith("//") && !requested.includes("\\")) {
          const target = new URL(requested, window.location.origin);
          if (target.origin === window.location.origin) destination = `${target.pathname}${target.search}${target.hash}`;
        }
        window.location.assign(destination);
      } else if (mode === "forgot") {
        const { error: authError } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/auth/callback?next=/auth/reset-password` });
        if (authError) throw authError;
        setMessage("If an account exists for that address, a reset link is on its way.");
      } else {
        if (password !== confirm) throw new Error("The passwords do not match.");
        const { error: authError } = await supabase.auth.updateUser({ password });
        if (authError) throw authError;
        setMessage("Password updated. You can now sign in with your new password.");
      }
    } catch (err) { setError(err instanceof Error ? err.message : "That request could not be completed."); }
    finally { setBusy(false); }
  }
  const [title, subtitle] = labels[mode];
  return <div className="auth-wrap"><section className="auth-card"><div className="eyebrow">GLUCOGUIDE ACCOUNT</div><h1>{title}</h1><p>{subtitle}</p>
    {error && <div className="status-error" role="alert">{error}</div>}{message && <div className="status-success" role="status">{message}</div>}
    <form className="auth-form" onSubmit={submit}>
      {mode !== "reset" && <div className="field"><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>}
      {(mode === "login" || mode === "register" || mode === "reset") && <div className="field"><label htmlFor="password">{mode === "reset" ? "New password" : "Password"}</label><input id="password" type="password" minLength={10} autoComplete={mode === "login" ? "current-password" : "new-password"} required value={password} onChange={(e) => setPassword(e.target.value)} /><small>Use at least 10 characters.</small></div>}
      {mode === "reset" && <div className="field"><label htmlFor="confirm">Confirm password</label><input id="confirm" type="password" minLength={10} autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} /></div>}
      {mode === "register" && <label className="check-row"><input type="checkbox" required/><span>I understand this is an educational research project and that assessment history is only saved after I explicitly opt in.</span></label>}
      <button className="btn" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset link" : "Update password"}</button>
    </form>
    <div className="auth-meta">{mode === "login" ? <><Link href="/auth/forgot-password">Forgot password?</Link><span>New here? <Link href="/auth/register">Create an account</Link></span></> : mode === "register" ? <span>Already registered? <Link href="/auth/login">Sign in</Link></span> : mode === "forgot" ? <Link href="/auth/login">Return to sign in</Link> : <Link href="/auth/login">Go to sign in</Link>}</div>
    <div className="note" style={{marginTop:18}}><span>Account services are hosted by Supabase. GlucoGuide does not store passwords. No health information is needed to create an account.</span></div>
  </section></div>;
}
