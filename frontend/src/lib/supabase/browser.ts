import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key || url.includes("YOUR_PROJECT") || key.includes("YOUR_SUPABASE")) throw new Error("Supabase sign-in is not configured. Add the public project URL and publishable key.");
  return createBrowserClient(url, key, { cookieOptions: { secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/" } });
}
