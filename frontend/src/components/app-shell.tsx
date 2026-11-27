"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  Home,
  Info,
  LayoutDashboard,
  LogIn,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  Sun,
  TrendingUp,
} from "lucide-react";
import { useTheme } from "next-themes";
import { createClient } from "@/lib/supabase/browser";

const nav = [
  { label: "Home", href: "/", icon: Home, group: "Screening" },
  { label: "Check Your Risk", href: "/screening", icon: ClipboardCheck, group: "Screening" },
  { label: "Understand Diabetes", href: "/learn", icon: BookOpen, group: "Education" },
  { label: "Glucose & Insulin", href: "/simulation", icon: Activity, group: "Education" },
  { label: "About & Privacy", href: "/about", icon: Info, group: "Information" },
];

export function AppShell({ children, authenticated }: { children: React.ReactNode; authenticated: boolean }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { theme, resolvedTheme, setTheme } = useTheme();
  useEffect(() => setMounted(true), []);
  const isDark = mounted && (resolvedTheme || theme) === "dark";
  const groups = [...new Set(nav.map((x) => x.group))];

  async function logout() {
    try {
      await createClient().auth.signOut();
    } finally {
      window.location.href = "/";
    }
  }

  return (
    <div className={`app-frame ${collapsed ? "app-collapsed" : ""}`}>
      {open && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Main navigation">
        <Link href="/" className="brand" onClick={() => setOpen(false)}>
          <span className="brand-mark"><Activity size={19} strokeWidth={2.5} /></span>
          <span><strong>GlucoGuide</strong><small>INDIA SCREENING</small></span>
        </Link>
        <div className="side-scope"><span className="scope-dot" /> RISK SCREENING + LAB GUIDE</div>
        <nav className="side-nav" aria-label="Primary navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group}>
              <p>{group}</p>
              {nav
                .filter((x) => x.group === group)
                .map(({ label, href, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    title={label}
                    aria-label={label}
                    onClick={() => setOpen(false)}
                    className={`nav-link ${pathname === href ? "nav-active" : ""}`}
                  >
                    <Icon size={17} />
                    <span>{label}</span>
                    {pathname === href && <ChevronRight size={15} className="nav-chevron" />}
                  </Link>
                ))}
            </div>
          ))}
        </nav>
        <div className="side-bottom">
          <div className="side-safety">
            <ShieldCheck size={18} />
            <p><b>Guidance only</b><br />Not a clinical diagnosis.</p>
          </div>
          {authenticated ? (
            <>
              <Link className={`nav-link ${pathname === "/dashboard" ? "nav-active" : ""}`} href="/dashboard" onClick={() => setOpen(false)}>
                <LayoutDashboard size={17} /><span>My Dashboard</span>
              </Link>
              <Link className={`nav-link ${pathname === "/dashboard/progress" ? "nav-active" : ""}`} href="/dashboard/progress" onClick={() => setOpen(false)}>
                <TrendingUp size={17} /><span>Trends &amp; Progress</span>
              </Link>
              <Link className={`nav-link ${pathname === "/history" ? "nav-active" : ""}`} href="/history" onClick={() => setOpen(false)}>
                <ClipboardList size={17} /><span>My History</span>
              </Link>
              <Link className={`nav-link ${pathname === "/settings" ? "nav-active" : ""}`} href="/settings" onClick={() => setOpen(false)}>
                <Settings size={17} /><span>Account Settings</span>
              </Link>
              <button className="nav-link nav-button" onClick={logout}>
                <LogOut size={17} /><span>Sign out</span>
              </button>
            </>
          ) : (
            <Link className="nav-link" href="/auth/login" onClick={() => setOpen(false)}>
              <LogIn size={17} /><span>Sign in</span>
            </Link>
          )}
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <button
            className="icon-button desktop-collapse"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="breadcrumbs">
            <span>GlucoGuide</span>
            <b>/</b>
            <strong>
              {nav.find((item) => item.href === pathname)?.label ||
                (pathname.split("/").filter(Boolean).at(-1)?.replaceAll("-", " ") || "Home")}
            </strong>
          </div>
          <div className="top-actions">
            <span className="prototype-pill"><i /> INDIAN ADULTS 20+</span>
            <button
              className="theme-toggle"
              onClick={() => setTheme(isDark ? "light" : "dark")}
              aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
              title={`Switch to ${isDark ? "light" : "dark"} theme`}
            >
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
              <span>{isDark ? "Light" : "Dark"}</span>
            </button>
            {authenticated ? (
              <Link href="/dashboard" className="avatar-link" aria-label="My Dashboard">GG</Link>
            ) : (
              <Link href="/auth/login" className="top-signin">Sign in <ChevronRight size={15} /></Link>
            )}
          </div>
        </header>

        <main id="main-content" className="main-content">{children}</main>

        <footer className="site-footer">
          <span>GlucoGuide · Indian Diabetes Risk Screening &amp; Lab Guide</span>
          <span>
            <Link href="/screening">Screening</Link>
            <Link href="/learn">Learn</Link>
            <Link href="/about">About &amp; Privacy</Link>
          </span>
          <span>Educational guidance only · Not a diagnostic medical device</span>
        </footer>
      </div>
    </div>
  );
}
