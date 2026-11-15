"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, BookOpen, ChartNoAxesCombined, ChevronRight, ClipboardList, FlaskConical, Home, Info, LogIn, LogOut, Menu, Moon, PanelLeftClose, PanelLeftOpen, ShieldCheck, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { createClient } from "@/lib/supabase/browser";

const nav = [
  { label: "Home", href: "/", icon: Home, group: "Explore" },
  { label: "Learn", href: "/learn", icon: BookOpen, group: "Explore" },
  { label: "Glucose & insulin", href: "/simulation", icon: Activity, group: "Explore" },
  { label: "Estimator", href: "/estimate", icon: ClipboardList, group: "Research tools" },
  { label: "Model reliability", href: "/reliability", icon: ChartNoAxesCombined, group: "Research tools" },
  { label: "Model lab", href: "/model-lab", icon: FlaskConical, group: "Research tools" },
  { label: "About & privacy", href: "/about", icon: Info, group: "Project" },
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
    try { await createClient().auth.signOut(); } finally { window.location.href = "/"; }
  }
  return <div className={`app-frame ${collapsed ? "app-collapsed" : ""}`}>
    {open && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Main navigation">
      <Link href="/" className="brand" onClick={() => setOpen(false)}><span className="brand-mark"><Activity size={19} strokeWidth={2.5} /></span><span><strong>GlucoGuide</strong><small>RESEARCH EDITION</small></span></Link>
      <div className="side-scope"><span className="scope-dot"/> EDUCATION + MODEL TRANSPARENCY</div>
      <nav className="side-nav" aria-label="Primary navigation">
        {groups.map((group) => <div className="nav-group" key={group}><p>{group}</p>{nav.filter((x) => x.group === group).map(({ label, href, icon: Icon }) => <Link key={href} href={href} title={label} aria-label={label} onClick={() => setOpen(false)} className={`nav-link ${pathname === href ? "nav-active" : ""}`}><Icon size={17}/><span>{label}</span>{pathname === href && <ChevronRight size={15} className="nav-chevron"/>}</Link>)}</div>)}
      </nav>
      <div className="side-bottom">
        <div className="side-safety"><ShieldCheck size={18}/><p><b>Education only</b><br/>Not a diagnosis or medical advice.</p></div>
        {authenticated ? <><Link className="nav-link" href="/dashboard"><Home size={17}/><span>My dashboard</span></Link><Link className="nav-link" href="/history"><ClipboardList size={17}/><span>My history</span></Link><button className="nav-link nav-button" onClick={logout}><LogOut size={17}/><span>Sign out</span></button></> : <Link className="nav-link" href="/auth/login"><LogIn size={17}/><span>Sign in</span></Link>}
      </div>
    </aside>
    <div className="main-column">
      <header className="topbar"><button className="icon-button desktop-collapse" onClick={()=>setCollapsed(!collapsed)} aria-label={collapsed?"Expand sidebar":"Collapse sidebar"} title={collapsed?"Expand sidebar":"Collapse sidebar"}>{collapsed?<PanelLeftOpen size={17}/>:<PanelLeftClose size={17}/>}</button><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu size={20}/></button><div className="breadcrumbs"><span>Diabetes Management System</span><b>/</b><strong>{nav.find((item) => item.href === pathname)?.label || (pathname.split("/").filter(Boolean).at(-1)?.replaceAll("-", " ") || "Home")}</strong></div><div className="top-actions"><span className="prototype-pill"><i/> RESEARCH PROTOTYPE</span><button className="theme-toggle" onClick={() => setTheme(isDark ? "light" : "dark")} aria-label={`Switch to ${isDark ? "light" : "dark"} theme`} title={`Switch to ${isDark ? "light" : "dark"} theme`}>{isDark ? <Sun size={16}/> : <Moon size={16}/>}<span>{isDark ? "Light" : "Dark"}</span></button>{authenticated ? <Link href="/settings" className="avatar-link" aria-label="Account settings">GG</Link> : <Link href="/auth/login" className="top-signin">Sign in <ChevronRight size={15}/></Link>}</div></header>
      <main id="main-content" className="main-content">{children}</main>
      <footer className="site-footer"><span>GlucoGuide · Diabetes Management System</span><span><Link href="/about">About</Link><Link href="/about#privacy">Privacy</Link><Link href="/learn#sources">Sources</Link></span><span>Educational research only · Not a medical device</span></footer>
    </div>
  </div>;
}
