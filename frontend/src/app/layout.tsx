import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import { AppShell } from "@/components/app-shell";
import { createClient } from "@/lib/supabase/server";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "GlucoGuide · Indian Diabetes Risk Screening & Lab Interpretation", template: "%s · GlucoGuide" },
  description: "Understand your diabetes risk using the published Indian MDRF-IDRS score or interpret blood-test results with clear, educational guidance.",
  applicationName: "GlucoGuide",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f8fafc" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  let authenticated = false;
  const supabase = await createClient();
  if (supabase) {
    const { data } = await supabase.auth.getClaims();
    authenticated = Boolean(data?.claims?.sub);
  }
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <AppShell authenticated={authenticated}>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
