// lib/screening-api.ts — Public screening model API client (Model 2, NHANES)
// Completely separate from the existing Pima model API in api.ts.

export interface ScreeningInput {
  age_years?: number | null;
  sex_male?: number | null;       // 1=male, 0=female
  bmi?: number | null;
  waist_cm?: number | null;
  sys_bp?: number | null;
  dia_bp?: number | null;
  mod_days_per_week?: number | null;
  vig_days_per_week?: number | null;
  sedentary_min_day?: number | null;
  smoked_100?: number | null;
  current_smoker?: number | null;
}

export interface ScreeningResult {
  ok: true;
  probability: number;
  label: 0 | 1;
  band: "higher" | "lower";
  band_label: string;
  threshold: number;
  model: string;
  model_version: string;
  model_type: string;
  dataset: string;
  inputs: Record<string, number | null>;
  missing_inputs: string[];
  warnings: string[];
  disclaimer: string;
  population_note: string;
}

export interface ScreeningMetadata {
  model_version: string;
  model_name: string;
  features: string[];
  feature_labels: Record<string, string>;
  input_limits: Record<string, [number, number]>;
  threshold: number;
  intended_use: string;
  population: string;
  population_limitations: string[];
  test_metrics: Record<string, number | string>;
  test_confidence_intervals: Record<string, [number, number]>;
  calibration_bins: Array<{
    bin_low: number; bin_high: number;
    count: number; mean_predicted: number; observed_fraction: number;
  }>;
  disclaimer: string;
}

export const FEATURE_FIELDS = [
  { key: "age_years",          label: "Age",                       unit: "years",    min: 21,  max: 80,   step: 1,    required: true,  help: "Adults aged 21–80. Age 80 represents all participants aged 80 and above in the training data." },
  { key: "sex_male",           label: "Sex",                       unit: "",         min: 0,   max: 1,    step: 1,    required: true,  help: "1 = male, 0 = female. Used as a risk factor based on NHANES survey data.", isSelect: true, options: [{value:"1",label:"Male"},{value:"0",label:"Female"}] },
  { key: "bmi",                label: "BMI",                       unit: "kg/m²",   min: 10,  max: 70,   step: 0.1,  required: false, help: "Body mass index. If you know your height and weight, BMI = weight(kg) ÷ height(m)²." },
  { key: "waist_cm",           label: "Waist circumference",       unit: "cm",       min: 40,  max: 200,  step: 0.1,  required: false, help: "Measured at the natural waist. Strongly associated with metabolic risk in the NHANES data." },
  { key: "sys_bp",             label: "Systolic blood pressure",   unit: "mmHg",     min: 60,  max: 220,  step: 1,    required: false, help: "Upper number from a blood pressure reading. Use an average of multiple readings if available." },
  { key: "dia_bp",             label: "Diastolic blood pressure",  unit: "mmHg",     min: 20,  max: 130,  step: 1,    required: false, help: "Lower number from a blood pressure reading." },
  { key: "mod_days_per_week",  label: "Moderate activity",         unit: "days/week",min: 0,   max: 7,    step: 1,    required: false, help: "Days per week with at least 10 minutes of moderate physical activity (e.g. brisk walking, cycling)." },
  { key: "vig_days_per_week",  label: "Vigorous activity",         unit: "days/week",min: 0,   max: 7,    step: 1,    required: false, help: "Days per week with at least 10 minutes of vigorous physical activity (e.g. running, sports)." },
  { key: "sedentary_min_day",  label: "Sedentary time",            unit: "min/day",  min: 0,   max: 1440, step: 10,   required: false, help: "Minutes per day spent sitting or lying (excluding sleep)." },
  { key: "smoked_100",         label: "Ever smoked ≥100 cigarettes",unit: "",        min: 0,   max: 1,    step: 1,    required: false, help: "Have you smoked at least 100 cigarettes in your lifetime?", isSelect: true, options: [{value:"1",label:"Yes"},{value:"0",label:"No"}] },
  { key: "current_smoker",     label: "Currently smoking",         unit: "",         min: 0,   max: 1,    step: 1,    required: false, help: "Do you currently smoke cigarettes?", isSelect: true, options: [{value:"1",label:"Yes (every day or some days)"},{value:"0",label:"No"}] },
] as const;

export async function screeningApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/dms${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const msg =
      typeof detail === "string" ? detail :
      Array.isArray(detail?.errors) ? detail.errors.join(" ") :
      "The request could not be completed.";
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}
