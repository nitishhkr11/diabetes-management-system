"use client";

import {
  Bar, BarChart, CartesianGrid, Label, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
  type TooltipContentProps, type TooltipValueType,
} from "recharts";

export type EvaluationChartData = {
  available: boolean;
  reason?: string;
  model_version?: string;
  model?: string;
  threshold?: number;
  roc_auc?: number;
  roc_points?: { false_positive_rate: number; true_positive_rate: number; threshold: number | null }[];
  confusion_matrix?: {
    actual_negative: { predicted_negative: number; predicted_positive: number };
    actual_positive: { predicted_negative: number; predicted_positive: number };
    sample_count: number;
  };
  calibration_bins?: { bin_low: number; bin_high: number; count: number; mean_predicted: number; observed_fraction: number }[];
  shap_units?: string;
  shap_importance?: { feature: string; mean_abs_shap: number }[];
  provenance?: string;
};

type CalibrationPoint = NonNullable<EvaluationChartData["calibration_bins"]>[number] & { ideal: number };
type RocPoint = NonNullable<EvaluationChartData["roc_points"]>[number];
type ShapPoint = NonNullable<EvaluationChartData["shap_importance"]>[number];
type PlotPayload<T> = Omit<TooltipContentProps<TooltipValueType, string | number>, "payload"> & {
  payload?: ReadonlyArray<{ payload?: T }>;
};

function CalibrationTooltip({ active, payload, model }: PlotPayload<CalibrationPoint> & { model: string }) {
  if (!active || !payload?.length || !payload[0].payload) return null;
  const point = payload[0].payload;
  return <div className="chart-tooltip" role="status" aria-live="polite">
    <b>{model} · calibration bin</b><span>Score range: {point.bin_low.toFixed(3)}–{point.bin_high.toFixed(3)}</span>
    <span>Mean predicted score: {point.mean_predicted.toFixed(6)}</span><span>Observed positive fraction: {point.observed_fraction.toFixed(6)}</span><span>Samples: {point.count}</span>
  </div>;
}

function RocTooltip({ active, payload, model, auc }: PlotPayload<RocPoint> & { model: string; auc: number }) {
  if (!active || !payload?.length || !payload[0].payload) return null;
  const point = payload[0].payload;
  return <div className="chart-tooltip" role="status" aria-live="polite">
    <b>{model} · ROC point</b><span>False-positive rate: {point.false_positive_rate.toFixed(6)}</span>
    <span>True-positive rate: {point.true_positive_rate.toFixed(6)}</span>
    <span>Threshold: {point.threshold === null ? "above maximum score" : point.threshold.toFixed(6)}</span>
    <span>Saved ROC-AUC: {auc.toFixed(6)}</span>
  </div>;
}

function ShapTooltip({ active, payload, model, units }: PlotPayload<ShapPoint> & { model: string; units: string }) {
  if (!active || !payload?.length || !payload[0].payload) return null;
  const point = payload[0].payload;
  return <div className="chart-tooltip" role="status" aria-live="polite">
    <b>{point.feature}</b><span>Mean absolute SHAP: {point.mean_abs_shap.toFixed(6)} {units}</span>
    <span>Model: {model}</span><span>SHAP describes model behaviour; it does not show medical causation.</span>
  </div>;
}

const axisTick = { fill: "var(--muted)", fontSize: 10 };
function ConfusionMatrix({ data, model, threshold }: { data: NonNullable<EvaluationChartData["confusion_matrix"]>; model: string; threshold: number }) {
  const cells = [
    { actual: "Negative", predicted: "Negative", count: data.actual_negative.predicted_negative },
    { actual: "Negative", predicted: "Positive", count: data.actual_negative.predicted_positive },
    { actual: "Positive", predicted: "Negative", count: data.actual_positive.predicted_negative },
    { actual: "Positive", predicted: "Positive", count: data.actual_positive.predicted_positive },
  ];
  return <div className="matrix-scroll">
    <table className="confusion-matrix" aria-label={`${model} confusion matrix at threshold ${threshold.toFixed(3)}`}>
      <caption>Counts · rows are actual class; columns are predicted class · n = {data.sample_count}</caption>
      <thead><tr><th scope="col">Actual ↓ / Predicted →</th><th scope="col">Negative</th><th scope="col">Positive</th></tr></thead>
      <tbody>{["Negative", "Positive"].map((actual) => <tr key={actual}><th scope="row">{actual}</th>{cells.filter((cell) => cell.actual === actual).map((cell) => {
        const id = `matrix-${actual.toLowerCase()}-${cell.predicted.toLowerCase()}`;
        const label = `Actual ${cell.actual}; predicted ${cell.predicted}; count ${cell.count}; selected threshold ${threshold.toFixed(6)}; model ${model}`;
        return <td key={cell.predicted}><button type="button" className="matrix-cell" aria-label={label} aria-describedby={id}>
          <strong>{cell.count}</strong><span className="matrix-tooltip" role="tooltip" id={id}>{label}</span>
        </button></td>;
      })}</tr>)}</tbody>
    </table>
  </div>;
}

export function EvaluationCharts({ data }: { data: EvaluationChartData | null }) {
  if (!data?.available || !data.model || !data.model_version) {
    return <section className="card card-pad" aria-label="Interactive evaluation charts"><h2 className="chart-title">Interactive evaluation charts</h2><p className="chart-fallback" role="status">{data?.reason || "Interactive chart data are not available for this model release."}</p></section>;
  }
  const bins = data.calibration_bins ?? [];
  const roc = data.roc_points ?? [];
  const shap = data.shap_importance ?? [];
  const matrix = data.confusion_matrix;
  return <section id="interactive-evaluation-charts" className="card card-pad" aria-label="Interactive evaluation charts">
    <div className="section-title"><div><h2>Interactive release charts</h2><p>{data.model} · release {data.model_version} · hover or focus points for exact saved values.</p></div></div>
    <div className="content-grid evaluation-chart-grid">
      <article className="card card-pad evaluation-chart-card" data-testid="calibration-chart">
        <h3 className="chart-title">Calibration on nominal holdout</h3><p className="chart-subtitle">Selected model · small bins are descriptive. Scores are not personal clinical probabilities.</p>
        {bins.length ? <div className="chart-frame"><ResponsiveContainer width="100%" height="100%"><LineChart accessibilityLayer data={bins.map((bin) => ({ ...bin, ideal: bin.mean_predicted }))} margin={{ top: 12, right: 14, bottom: 20, left: 12 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="4 4"/><XAxis type="number" dataKey="mean_predicted" domain={[0, 1]} tick={axisTick}><Label value="Mean predicted score" position="insideBottom" offset={-12} fill="var(--muted)" fontSize={10}/></XAxis><YAxis type="number" dataKey="observed_fraction" domain={[0, 1]} tick={axisTick}><Label value="Observed positive fraction" angle={-90} position="insideLeft" fill="var(--muted)" fontSize={10}/></YAxis>
          <Tooltip isAnimationActive={false} content={(props) => <CalibrationTooltip {...props} model={data.model!}/>}/><Legend wrapperStyle={{ color: "var(--muted)", fontSize: 10 }}/>
          <Line name="Ideal calibration" dataKey="ideal" type="linear" stroke="var(--muted)" strokeDasharray="5 4" dot={false} isAnimationActive={false}/><Line name="Observed fraction" dataKey="observed_fraction" type="linear" stroke="var(--primary)" strokeWidth={2} dot={{ r: 4, fill: "var(--primary)" }} activeDot={{ r: 6 }} isAnimationActive={false}/>
        </LineChart></ResponsiveContainer></div> : <p className="chart-fallback">Calibration bins are not available for this release.</p>}
      </article>
      <article className="card card-pad evaluation-chart-card" data-testid="confusion-chart">
        <h3 className="chart-title">Confusion matrix</h3><p className="chart-subtitle">{data.model} · selected threshold {data.threshold?.toFixed(3) ?? "unavailable"} · counts, not percentages.</p>
        {matrix && data.threshold !== undefined ? <ConfusionMatrix data={matrix} model={data.model} threshold={data.threshold}/> : <p className="chart-fallback">Confusion-matrix counts are not available for this release.</p>}
      </article>
      <article className="card card-pad evaluation-chart-card" data-testid="roc-chart">
        <h3 className="chart-title">ROC curve · AUC {data.roc_auc?.toFixed(3) ?? "unavailable"}</h3><p className="chart-subtitle">{data.model} · thresholds are from the saved release scores.</p>
        {roc.length ? <div className="chart-frame"><ResponsiveContainer width="100%" height="100%"><LineChart accessibilityLayer data={roc} margin={{ top: 12, right: 14, bottom: 20, left: 12 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="4 4"/><XAxis type="number" dataKey="false_positive_rate" domain={[0, 1]} tick={axisTick}><Label value="False-positive rate" position="insideBottom" offset={-12} fill="var(--muted)" fontSize={10}/></XAxis><YAxis type="number" dataKey="true_positive_rate" domain={[0, 1]} tick={axisTick}><Label value="True-positive rate" angle={-90} position="insideLeft" fill="var(--muted)" fontSize={10}/></YAxis>
          <Tooltip isAnimationActive={false} content={(props) => <RocTooltip {...props} model={data.model!} auc={data.roc_auc ?? 0}/>}/><Legend wrapperStyle={{ color: "var(--muted)", fontSize: 10 }}/>
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--muted)" strokeDasharray="5 4" ifOverflow="extendDomain"/><Line name="Selected model" dataKey="true_positive_rate" type="linear" stroke="var(--primary)" strokeWidth={2} dot={false} activeDot={{ r: 5 }} isAnimationActive={false}/>
        </LineChart></ResponsiveContainer></div> : <p className="chart-fallback">ROC points are unavailable for this release.</p>}
      </article>
      <article className="card card-pad evaluation-chart-card" data-testid="shap-chart">
        <h3 className="chart-title">Global SHAP feature importance</h3><p className="chart-subtitle">Mean absolute attribution in {data.shap_units ?? "saved explainer units"}; feature input units remain in the model card.</p>
        {shap.length ? <div className="chart-frame"><ResponsiveContainer width="100%" height="100%"><BarChart accessibilityLayer data={shap} layout="vertical" margin={{ top: 8, right: 18, bottom: 18, left: 16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" horizontal={false}/><XAxis type="number" dataKey="mean_abs_shap" tick={axisTick}><Label value={`Mean |SHAP| (${data.shap_units ?? "attribution units"})`} position="insideBottom" offset={-12} fill="var(--muted)" fontSize={10}/></XAxis><YAxis type="category" dataKey="feature" width={142} tick={axisTick}/>
          <Tooltip isAnimationActive={false} content={(props) => <ShapTooltip {...props} model={data.model!} units={data.shap_units ?? "attribution units"}/>}/><Bar name="Mean absolute SHAP" dataKey="mean_abs_shap" fill="var(--primary)" radius={[0, 5, 5, 0]} isAnimationActive={false}/>
        </BarChart></ResponsiveContainer></div> : <p className="chart-fallback">SHAP feature-importance values are not available for this release.</p>}
        <p className="chart-subtitle">SHAP describes how this model uses features. It does not establish medical cause.</p>
      </article>
    </div>
    <p className="chart-provenance">{data.provenance}</p>
  </section>;
}
