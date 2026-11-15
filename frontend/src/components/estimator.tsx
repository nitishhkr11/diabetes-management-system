"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowDownToLine, ArrowRight, CheckCircle2, CircleHelp, LoaderCircle, RotateCcw, ShieldCheck, Upload } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { api, assessmentSchema, featureFields, featureNames, type AssessmentInputs, type Prediction } from "@/lib/api";

const demo: AssessmentInputs = { Pregnancies: 2, Glucose: 132, BloodPressure: 72, SkinThickness: 28, Insulin: 126, BMI: 31.6, DiabetesPedigreeFunction: .42, Age: 34 };
const sections = [
  { title: "Core information", keys: ["Pregnancies", "Age", "DiabetesPedigreeFunction"] },
  { title: "Measurements from the benchmark", keys: ["Glucose", "BloodPressure", "BMI", "SkinThickness", "Insulin"] },
];
type LabObservation = { name: string; value: string; unit: string; context: string; source: string; suggested_model_feature: string | null; confidence: number | null; review_required: boolean };
type ExtractedReport = { observations: LabObservation[]; method: string; pages: number; confidence: number | null; source_name: string; retained: false; notice: string };

export function Estimator({ authenticated }: { authenticated: boolean }) {
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(featureFields.map((field) => [field.key, authenticated ? "" : String(demo[field.key as keyof AssessmentInputs] ?? "")])));
  const [result, setResult] = useState<Prediction | null>(null); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [saved, setSaved] = useState(false); const [consent, setConsent] = useState(false);
  const [caseReference, setCaseReference] = useState("");
  const [report, setReport] = useState<ExtractedReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const [valueSources, setValueSources] = useState<Record<string, string>>({});
  const [replaceConfirm, setReplaceConfirm] = useState<Record<number, string>>({});
  const [reportCompatibilityError, setReportCompatibilityError] = useState<Record<number, string>>({});

  function reset() {
    setValues(Object.fromEntries(featureFields.map((field) => [field.key, authenticated ? "" : String(demo[field.key as keyof AssessmentInputs] ?? "")])));
    setResult(null); setError(""); setSaved(false); setConsent(false); setCaseReference(""); setReport(null); setReportError(""); setValueSources({}); setReplaceConfirm({}); setReportCompatibilityError({});
  }
  async function uploadReport(file?: File) {
    if (!file || reportBusy) return;
    setReportBusy(true); setReportError(""); setReport(null); setReplaceConfirm({}); setReportCompatibilityError({});
    try {
      const data = new FormData(); data.set("file", file);
      const response = await fetch("/api/dms/api/v1/reports/extract", { method: "POST", body: data, cache: "no-store" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "The report could not be read.");
      setReport(body as ExtractedReport);
      if (!(body as ExtractedReport).observations.length) setReportError("Text was read, but no supported lab values were confidently identified. Enter values manually.");
    } catch (err) { setReportError(err instanceof Error ? err.message : "The report could not be read. Enter values manually."); }
    finally { setReportBusy(false); }
  }
  function useObservation(index: number, observation: LabObservation, replace = false) {
    const feature = observation.suggested_model_feature;
    if (!feature || !(feature in values)) return;
    const unit = observation.unit.toLowerCase().replaceAll(" ", "");
    const compatible = feature === "BMI" ? ["kg/m²", "kg/m2"].includes(unit)
      : feature === "Age" ? ["year", "years", "yr", "yrs"].includes(unit)
      : feature === "Glucose" ? unit === "mg/dl" && /2\s*(?:-|hour\s*)?h|ogtt|oral glucose tolerance/i.test(observation.context)
      : false;
    if (!compatible) {
      setReportCompatibilityError((current) => ({ ...current, [index]: "This unit or test context does not match the benchmark feature. No conversion is performed; enter a compatible value manually." }));
      return;
    }
    setReportCompatibilityError((current) => { const next = { ...current }; delete next[index]; return next; });
    const nextValue = observation.value;
    if (values[feature] && values[feature] !== nextValue && !replace) {
      setReplaceConfirm((current) => ({ ...current, [index]: feature })); return;
    }
    setValues((current) => ({ ...current, [feature]: nextValue }));
    setValueSources((current) => ({ ...current, [feature]: `Confirmed report value · ${report?.source_name || "uploaded report"}` }));
    setReplaceConfirm((current) => { const next = { ...current }; delete next[index]; return next; });
  }
  function makeInputs(): AssessmentInputs {
    return Object.fromEntries(featureFields.map((field) => {
      const raw = values[field.key];
      return [field.key, raw === "" ? null : Number(raw)];
    })) as AssessmentInputs;
  }
  function makeInputSources(): Record<string, "manual" | "report"> {
    return Object.fromEntries(Object.entries(valueSources).map(([feature, source]) => [feature, source === "Manually entered" ? "manual" : "report"]));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return; setBusy(true); setError(""); setResult(null); setSaved(false);
    try { const parsed=assessmentSchema.safeParse(makeInputs()); if(!parsed.success) throw new Error(parsed.error.issues.map((issue)=>`${issue.path.join(" ")}: ${issue.message}`).join(" ")); const answer = await api<Prediction>("/api/v1/predictions", { method: "POST", body: JSON.stringify({ ...parsed.data, input_sources: makeInputSources() }) }); setResult(answer); }
    catch (err) { setError(err instanceof Error ? err.message : "The assessment could not be calculated."); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!consent || !result) return; setBusy(true); setError("");
    try { const parsed=assessmentSchema.safeParse(makeInputs());if(!parsed.success)throw new Error("Review the assessment values before saving.");await api("/api/v1/history", { method: "POST", body: JSON.stringify({ consent: true, inputs: { ...parsed.data, input_sources: makeInputSources() } }) }); setSaved(true); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not save this assessment."); }
    finally { setBusy(false); }
  }
  async function downloadReport() {
    if (!result) return; setBusy(true); setError("");
    try {
      const response = await fetch("/api/dms/api/v1/reports/assessment", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inputs: makeInputs(), case_reference: caseReference }), cache: "no-store" });
      if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "The report could not be created."); }
      const blob = await response.blob(); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "assessment-audit.html"; link.click(); URL.revokeObjectURL(link.href);
    } catch (err) { setError(err instanceof Error ? err.message : "The report could not be created."); }
    finally { setBusy(false); }
  }

  return <>
    <PageHeader eyebrow="RESEARCH ESTIMATOR" title="Explore a model estimate" description={authenticated ? "Enter benchmark variables and inspect the selected model’s output and local explanation." : "Try a clearly synthetic example with no saving. Sign in to enter your own assessment variables."}/>
    {!authenticated && <div className="notice notice-info" role="note" style={{marginBottom:15}}><CircleHelp size={18}/><p><b>Example values · not user data.</b> These invented values are supplied for a no-save demonstration. Sign in to enter your own assessment values or upload a report. <Link className="text-link" href="/auth/login?next=%2Festimate">Sign in to continue <ArrowRight size={13}/></Link></p></div>}
    <div className="notice notice-safety" role="note" style={{marginBottom:15}}><ShieldCheck size={18}/><p><b>Safety notice · research estimate only.</b> This model uses a historical binary dataset label. It cannot diagnose, screen for, or rule out diabetes, and it cannot identify a diabetes type. Diagnosis requires appropriate clinical assessment.</p></div>
    <div className="form-layout"><form className="card form-card" onSubmit={submit}>
      {error && <div className="status-error" role="alert">{error}</div>}{saved && <div className="status-success" role="status">Saved to your private account history.</div>}
      {sections.map((section)=><section key={section.title}><h2 className="form-section-title">{section.title}</h2><div className="field-grid">{section.keys.map((key)=>{
        const field = featureFields.find((item)=>item.key===key)!;
        const min = field.key === "Age" ? 21 : ["Glucose","BloodPressure","BMI","SkinThickness","Insulin"].includes(field.key) ? 0 : field.key === "DiabetesPedigreeFunction" ? .01 : field.min;
        return <div className="field" key={field.key}><label htmlFor={field.key}>{field.label} <span>({field.unit} · {field.key})</span>{field.required && authenticated && <span className="required-mark"> · required</span>}{!field.required && <span> · optional</span>}</label><input id={field.key} name={field.key} type="number" min={min} max={field.max} step={field.step} required={authenticated && field.required} disabled={!authenticated || busy} value={values[field.key]} onChange={(e)=>{setValues({...values,[field.key]:e.target.value});setValueSources({...valueSources,[field.key]:"Manually entered"});}} aria-describedby={`${field.key}-help`}/><small id={`${field.key}-help`}>{field.help}{valueSources[field.key] ? ` · Source: ${valueSources[field.key]}` : ""}</small></div>;
      })}</div></section>)}
      <details className="card aside-card" style={{marginTop:13}}><summary style={{cursor:"pointer",fontSize:11,fontWeight:750}}>Review inputs before submitting</summary><div className="factor-list" style={{marginTop:9}}>{featureFields.map((field)=>{const value=values[field.key];const omitted=value==="";const missing=Number(value)===0&&!['Pregnancies'].includes(field.key);return <div className="factor-item" key={field.key}><b>{field.label}</b><span>{omitted||missing?"Not measured":`${value} ${field.unit}`}</span><span/></div>;})}</div></details>
      <section className="card aside-card" style={{marginTop:14}} aria-labelledby="report-heading">
        <h2 className="form-section-title" id="report-heading"><Upload size={16}/> Add values from a medical report</h2>
        <p className="report-meta">Laboratory values are shown as extracted observations, not interpreted results. HbA1c summarizes average blood glucose over roughly the prior three months; fasting, random, and glucose-tolerance tests have different contexts. Read the <a className="text-link" href="https://www.cdc.gov/diabetes/diabetes-testing/prediabetes-a1c-test.html" target="_blank" rel="noreferrer">CDC A1C test explanation</a>. A healthcare professional should interpret results in context.</p>
        {!authenticated ? <p>Sign in to upload a report. The upload endpoint is restricted to authenticated users.</p> : <>
          <label className="report-drop">{reportBusy ? <><LoaderCircle size={17} className="spin"/> Reading report locally…</> : <><Upload size={17}/> Choose a PDF, PNG, JPG, or JPEG report<input type="file" accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg" disabled={reportBusy} onChange={(event)=>{void uploadReport(event.currentTarget.files?.[0]);event.currentTarget.value="";}}/></>}</label>
          <small>Maximum 10 MB and 5 PDF pages. Reports are not persistently stored; the upload buffer may briefly use private OS temporary storage and is closed after processing. OCR stays local with no third-party provider. Scanned files need Tesseract OCR installed. Review every extracted value before use.</small>
          {reportError && <div className="status-error" role="alert" style={{marginTop:9}}>{reportError}</div>}
          {report && <div style={{marginTop:12}}><p className="report-meta">{report.source_name} · {report.pages} page(s) · {report.method === "local_ocr" ? "Local OCR" : "Embedded PDF text"}{report.confidence !== null ? ` · OCR confidence ${(report.confidence*100).toFixed(0)}%` : ""}</p>
            <p className="report-meta">{report.notice}</p>
            {report.observations.map((observation,index)=><article className="report-observation" key={`${observation.name}-${index}`}>
              <b>{observation.name}</b><div><label>Extracted value<input aria-label={`${observation.name} extracted value`} value={observation.value} onChange={(event)=>setReport((current)=>current?({...current,observations:current.observations.map((item,i)=>i===index?({...item,value:event.target.value}):item)}):current)}/></label><label>Unit<input aria-label={`${observation.name} unit`} value={observation.unit} onChange={(event)=>setReport((current)=>current?({...current,observations:current.observations.map((item,i)=>i===index?({...item,unit:event.target.value}):item)}):current)}/></label></div>
              <small>Source: {observation.source} · Context: {observation.context}{observation.confidence !== null ? ` · OCR confidence ${(observation.confidence*100).toFixed(0)}%` : ""}</small>
              {observation.suggested_model_feature ? <><button type="button" className="btn btn-secondary" style={{marginTop:8}} onClick={()=>useObservation(index,observation)}>Use as matching {observation.suggested_model_feature}</button>{reportCompatibilityError[index] && <p role="alert" className="report-meta">{reportCompatibilityError[index]}</p>}{replaceConfirm[index] && <p role="alert" className="report-meta">A manual value is already present. <button type="button" className="text-link" onClick={()=>useObservation(index,observation,true)}>Replace it with the reviewed report value</button> or keep the manual value.</p>}</> : <small>Displayed as a laboratory observation; no compatible model feature is mapped automatically.</small>}
            </article>)}
          </div>}
        </>}
      </section>
      <div className="privacy-check"><CircleHelp size={16}/><span>Values are sent to the research API to calculate this result. They are not retained by default. Uploaded reports and extracted text are discarded after processing; temporary upload buffers are closed and cleaned up. Measurements set to zero in the dataset’s known missing-value fields are treated as “not measured”; zero pregnancies remains valid.</span></div>
      <label className="field" style={{marginTop:12}}><span style={{fontSize:11,fontWeight:700}}>Optional anonymous report reference</span><input maxLength={80} disabled={busy} value={caseReference} onChange={(e)=>setCaseReference(e.target.value)} placeholder="For example, CASE-014"/><small>Only short CASE-, P- or REF- codes are included in a downloaded report; other text is omitted.</small></label>
      <div className="form-actions"><button className="btn" type="submit" disabled={busy}>{busy ? <><LoaderCircle size={15} className="spin"/> Calculating…</> : "Review model output"}</button><button className="btn btn-secondary" type="button" onClick={reset} disabled={busy}><RotateCcw size={14}/> Reset</button></div>
    </form><aside className="form-aside"><section className="card aside-card"><h3>Why these variables?</h3><p>They are the eight predictors in the Pima benchmark used in this project. They are not a comprehensive clinical assessment.</p></section><section className="card aside-card"><h3>How input is processed</h3><ul><li>Exact shared schema validation</li><li>Five known zero codes become missing values</li><li>Training-only median imputation and scaling in the saved pipeline</li><li>No retraining during an estimate</li></ul></section><section className="card aside-card"><h3>What is retained?</h3><p>Nothing by default. Signed-in users see a separate save-consent option only after the model result is returned.</p></section></aside></div>
    {result && <section className="result-card" style={{marginTop:18}} aria-live="polite"><div className="result-top"><div><div className="eyebrow">MODEL ESTIMATE · NOT A DIAGNOSIS</div><div className="result-score">{(result.probability*100).toFixed(1)}<small>model score · not a personal clinical probability</small></div><small style={{display:"block",color:"var(--muted)",fontSize:10,marginTop:4}}>Selected model: {result.model} · release {result.model_version}</small></div><span className="output-label">Model estimate: {result.label===1?"positive":"negative"} class under the selected benchmark threshold ({result.threshold.toFixed(6)})</span></div>
      <section className="result-findings" aria-labelledby="findings-heading">
        <h2 id="findings-heading">Laboratory report findings</h2>
        {report && report.observations.length > 0 ? <>
          <p>Extracted observations are shown separately from the model estimate. Review and correct these values before use; no clinical reference ranges or interpretations are inferred.</p>
          <div className="result-finding-list">{report.observations.map((observation, index) => <article key={`${observation.name}-finding-${index}`}>
            <b>{observation.name}</b><span>{observation.value}{observation.unit ? ` ${observation.unit}` : ""}</span>
            <small>Source: {report.source_name} · {observation.context || "Context not identified"}
              {observation.confidence !== null ? ` · extraction confidence ${(observation.confidence * 100).toFixed(0)}%` : " · extraction confidence unavailable"}</small>
            {observation.suggested_model_feature && <small>Confirmed as model input: {observation.suggested_model_feature}</small>}
          </article>)}</div>
        </> : <p>No medical-report observations were supplied for this estimate. Model inputs came from the form; review each field’s source before continuing.</p>}
        <p>Laboratory findings require clinical interpretation in context. Fasting glucose, random glucose, glucose-tolerance measurements, and HbA1c are distinct tests and are not treated as interchangeable.</p>
      </section>
      <p className="result-disclaimer">This value is a score produced by {result.model} from the research dataset; it is not a personal medical probability. It cannot confirm or rule out diabetes. If you have a health concern, talk with a qualified healthcare professional.</p>
      <div className="model-bars" aria-label="Scores from the compared research model families">{Object.entries(result.all_models).map(([name,value])=><div className="model-bar-line" key={name}><span>{name}</span><div className="model-bar-track"><div className="model-bar-fill" style={{width:`${Math.round(value*100)}%`}}/></div><strong>{(value*100).toFixed(1)}%</strong></div>)}</div>
      <div className="split-grid" style={{marginTop:20}}><section><h2 className="chart-title">Why the model returned this output</h2><p style={{margin:"0 0 9px",color:"var(--muted)",fontSize:11}}>Local SHAP contributions describe how inputs shifted this model output relative to its reference. They do not show medical cause.</p><div className="factor-list">{result.explanation.contributions.slice(0,6).map((item)=><div className="factor-item" key={item.feature}><b>{featureNames[item.feature] || item.feature}</b><span>{item.value == null ? "Not measured" : item.value}</span><strong className={item.contribution>=0?"factor-positive":"factor-negative"}>{item.contribution>=0?"+":""}{item.contribution.toFixed(3)} {result.explanation.units}</strong></div>)}</div><small style={{display:"block",marginTop:8,color:"var(--muted)",fontSize:10}}>Explanation method: SHAP · additivity check error {result.explanation.additivity_error.toExponential(2)}</small></section><section className="card card-pad"><h2 className="chart-title">What happens next?</h2><p style={{color:"var(--muted)",fontSize:12}}>The app does not provide diagnosis, treatment or urgency advice. Health professionals use approved laboratory tests, medical history and context.</p><Link className="text-link" href="/learn">Read how diabetes is diagnosed <ArrowRight size={14}/></Link><div style={{display:"flex",gap:8,flexWrap:"wrap",marginTop:18}}><button className="btn btn-secondary" onClick={downloadReport} disabled={busy}><ArrowDownToLine size={14}/> Download explanation</button><button className="btn btn-quiet" onClick={reset}><RotateCcw size={14}/> New assessment</button></div>{authenticated && <div style={{marginTop:15}}>{saved ? <div className="status-success"><CheckCircle2 size={15}/> Saved to your account.</div> : <><label className="privacy-check"><input type="checkbox" checked={consent} onChange={(e)=>setConsent(e.target.checked)} disabled={busy}/><span>I consent to save these measurements, field sources, model output and explanation to my private account history. I can export or delete it later.</span></label><button className="btn" style={{marginTop:10}} onClick={save} disabled={!consent||busy}>Save assessment to my history</button></>}</div>}</section></div>
      {result.warnings.length>0 && <div className="note" style={{marginTop:15}}><CircleHelp size={16}/><div><b>Input and reliability notes</b><ul>{result.warnings.map((warning)=> <li key={warning}>{warning}</li>)}</ul></div></div>}
    </section>}
  </>;
}
