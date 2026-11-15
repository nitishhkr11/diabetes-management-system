import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import { AppShell } from "@/components/app-shell";
import { createClient } from "@/lib/supabase/server";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "GlucoGuide · Diabetes Management System", template: "%s · GlucoGuide" },
  description: "Understand diabetes and explore an explainable, educational machine-learning research prototype.",
  applicationName: "GlucoGuide",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#fff9f3" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  let authenticated = false;
  const supabase = await createClient();
  if (supabase) {
    const { data } = await supabase.auth.getClaims();
    authenticated = Boolean(data?.claims?.sub);
  }
  return <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning><body><ThemeProvider><AppShell authenticated={authenticated}>{children}</AppShell></ThemeProvider></body></html>;
}
