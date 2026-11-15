import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export async function requireUser(returnTo = "/dashboard") {
  const supabase = await createClient();
  const login = `/auth/login?next=${encodeURIComponent(returnTo)}`;
  if (!supabase) redirect(`${login}&error=configuration`);
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims?.sub) redirect(login);
  const email = typeof data.claims.email === "string" ? data.claims.email : "Account";
  return { id: String(data.claims.sub), email };
}
