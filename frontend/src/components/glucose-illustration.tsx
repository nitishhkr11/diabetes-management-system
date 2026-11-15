"use client";
import { useState } from "react";
import { Activity, ArrowRight, CircleHelp } from "lucide-react";

type State = "response" | "resistance" | "insufficient";
const states: Record<State, { title: string; short: string; detail: string; insulin: number; glucose: number; cell: string }> = {
  response: { title: "Insulin response", short: "Insulin helps glucose enter cells", detail: "After food, glucose enters the bloodstream. The pancreas releases insulin, which helps body cells take up glucose for energy. This illustration is a simplified concept, not a measured curve.", insulin: 78, glucose: 37, cell: "Cells receive glucose" },
  resistance: { title: "Insulin resistance", short: "Cells respond less effectively", detail: "When cells respond less effectively to insulin, the pancreas may initially make more. Over time, glucose regulation can be affected. This conceptual view does not represent a person's physiology.", insulin: 58, glucose: 72, cell: "Reduced response" },
  insufficient: { title: "Insufficient insulin", short: "Too little insulin is available", detail: "In Type 1 diabetes, the immune system destroys insulin-producing beta cells, so the body makes little or no insulin. Type 1 is not caused by lifestyle habits.", insulin: 16, glucose: 88, cell: "Less glucose uptake" },
};

export function GlucoseIllustration({ compact = false }: { compact?: boolean }) {
  const [mode, setMode] = useState<State>("response");
  const current = states[mode];
  return <section className={`simulation-card ${compact ? "simulation-compact" : ""}`} aria-labelledby="sim-heading">
    <div className="sim-top"><div><span className="eyebrow">CONCEPTUAL VISUAL · NOT PATIENT DATA</span><h2 id="sim-heading">How glucose & insulin interact</h2><p>A simplified learning model, not a physiological simulation.</p></div><div className="illustrative-badge"><Activity size={15}/> Illustrative</div></div>
    <div className="sim-layout"><div className="sim-art-wrap">
      <svg viewBox="0 0 620 340" role="img" aria-labelledby="glucoseTitle glucoseDesc" className="sim-art">
        <title id="glucoseTitle">Illustration of glucose and insulin moving from blood toward cells</title>
        <desc id="glucoseDesc">A conceptual flow diagram showing a pancreas, glucose symbols, insulin keys, blood stream, and a cell doorway. State: {current.title}.</desc>
        <defs><linearGradient id="stream" x1="0" x2="1"><stop offset="0" stopColor="var(--sim-stream-a)"/><stop offset="1" stopColor="var(--sim-stream-b)"/></linearGradient><linearGradient id="cell" x1="0" x2="1"><stop offset="0" stopColor="var(--sim-cell-a)"/><stop offset="1" stopColor="var(--sim-cell-b)"/></linearGradient></defs>
        <rect x="14" y="15" width="592" height="310" rx="28" fill="var(--surface-soft)"/>
        <path d="M36 174 C105 132 160 213 227 173 S352 139 411 174 S526 216 584 174" fill="none" stroke="url(#stream)" strokeWidth="102" strokeLinecap="round" opacity=".72"/>
        <path d="M38 174 C112 135 165 210 231 174 S352 139 411 174 S522 213 582 174" fill="none" stroke="var(--border)" strokeWidth="2" strokeDasharray="4 7"/>
        <g transform="translate(56 43)"><path d="M0 28c17-25 41-10 48-2 15-8 32-2 29 11-2 8-12 11-22 12-11 1-17 12-31 8C9 53-7 42 0 28Z" fill="var(--secondary)"/><circle cx="28" cy="34" r="5" fill="var(--primary-soft)"/><text x="36" y="76" textAnchor="middle" fill="var(--muted)" fontSize="12" fontWeight="700">PANCREAS</text></g>
        <g className="glucose-particles" fill="var(--primary)">{[[135,136],[189,217],[261,131],[324,211],[388,134],[465,213],[533,147]].slice(0, mode === "response" ? 3 : mode === "resistance" ? 5 : 7).map(([x,y], i) => <g key={i}><circle cx={x} cy={y} r="13"/><text x={x} y={y+4} textAnchor="middle" fontSize="8" fill="var(--on-primary)" fontWeight="800">G</text></g>)}</g>
        <g fill="var(--secondary)">{Array.from({length: mode === "response" ? 5 : mode === "resistance" ? 3 : 1}, (_, i) => <g key={i} transform={`translate(${95 + i * 35} ${96 + (i % 2) * 20})`}><path d="M0 0v21m0 0-8 8m8-8 8 8" fill="none" stroke="var(--secondary)" strokeWidth="3" strokeLinecap="round"/><circle cy="0" r="5"/></g>)}</g>
        <g transform="translate(453 88)"><path d="M12 16c-18 1-29 14-29 33v51c0 19 12 34 30 34h83c18 0 30-15 30-34V49c0-19-12-33-30-33H12Z" fill="url(#cell)" stroke="var(--secondary)" strokeWidth="3"/><path d="M-4 47v30m0-15h16m-16 0-10-10m10 10-10 10" fill="none" stroke="var(--secondary)" strokeWidth="5" strokeLinecap="round"/><circle cx="50" cy="75" r="19" fill="var(--surface)" opacity=".55"/><text x="55" y="157" textAnchor="middle" fill="var(--muted)" fontSize="12" fontWeight="700">BODY CELL</text></g>
        <text x="47" y="295" fill="var(--text)" fontSize="13" fontWeight="700">Bloodstream</text><text x="470" y="295" fill="var(--text)" fontSize="13" fontWeight="700">Cell uptake</text>
      </svg>
      <div className="sim-key"><span><i className="legend-glucose"/> Glucose</span><span><i className="legend-insulin"/> Insulin</span><span><i className="legend-cell"/> Cell</span></div>
    </div><div className="sim-detail"><div className="sim-state-label"><span className="state-dot"/> {current.title}</div><h3>{current.short}</h3><p>{current.detail}</p><div className="sim-bars" aria-label="Illustrative concept indicators, not measurements"><div><span>Insulin availability</span><b>{current.insulin}% illustrative</b></div><div className="meter"><i style={{ width: `${current.insulin}%` }}/></div><div><span>Glucose not taken up</span><b>{current.glucose}% illustrative</b></div><div className="meter"><i className="meter-maroon" style={{ width: `${current.glucose}%` }}/></div><small>Illustrative labels only · no values are measured or predicted.</small></div>
      <div className="sim-modes" role="group" aria-label="Choose an educational concept">{(Object.keys(states) as State[]).map((key) => <button key={key} onClick={() => setMode(key)} className={mode === key ? "mode-selected" : ""} aria-pressed={mode === key}>{key === "response" ? "Typical response" : key === "resistance" ? "Resistance" : "Less insulin"}</button>)}</div>
    </div></div>
    {!compact && <div className="sim-note"><CircleHelp size={17}/><span>Diabetes has multiple causes and types. This simplified visual cannot explain an individual person's health, and the model on this website does not measure glucose-insulin physiology.</span></div>}
  </section>;
}

export function MiniFlow() { return <div className="mini-flow" aria-label="Research workflow: inputs, preprocessing, models, score, explanation"><span>Input</span><ArrowRight/><span>Pipeline</span><ArrowRight/><span>Models</span><ArrowRight/><span>Score</span><ArrowRight/><span>SHAP</span></div>; }
