import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const target = url.searchParams.get("next") || "/dashboard";
  const safeTarget = target.startsWith("/") && !target.startsWith("//") ? target : "/dashboard";
  const supabase = await createClient();
  if (!supabase || !code) return NextResponse.redirect(new URL("/auth/login?error=verification", url.origin));
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  return NextResponse.redirect(new URL(error ? "/auth/login?error=verification" : safeTarget, url.origin));
}
