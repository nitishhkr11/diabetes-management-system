import { z } from "zod";

export type Contribution = { feature: string; value: number | null; contribution: number; was_missing: boolean };
export type Explanation = { units: string; contributions: Contribution[]; output_value: number; base_value: number; additivity_error: number };
export type Prediction = {
  ok: true; probability: number; threshold: number; label: number; band: string;
  model: string; model_version: string; inputs: Record<string, number | null>;
  input_sources: Record<string, "manual" | "report">;
  all_models: Record<string, number>; explanation: Explanation; warnings: string[];
};
export type AssessmentInputs = {
  Pregnancies: number; Glucose: number | null; BloodPressure: number | null;
  SkinThickness: number | null; Insulin: number | null; BMI: number | null;
  DiabetesPedigreeFunction: number; Age: number;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/dms${path}`, { ...init, cache: "no-store", headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    const validationErrors = Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(" ") : "";
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail?.errors) ? detail.errors.join(" ") : validationErrors || "The request could not be completed.");
  }
  return response.json() as Promise<T>;
}

export const featureFields = [
  { key: "Pregnancies", label: "Pregnancies", unit: "count", help: "Zero is a valid value.", required: true, min: 0, max: 20, step: 1 },
  { key: "Glucose", label: "Glucose after glucose load", unit: "mg/dL", help: "The benchmark records a 2-hour measurement. Enter 0 if not measured.", required: false, min: 0, max: 500, step: 1 },
  { key: "BloodPressure", label: "Diastolic blood pressure", unit: "mm Hg", help: "Enter 0 if not measured.", required: false, min: 0, max: 150, step: 1 },
  { key: "BMI", label: "Body mass index", unit: "kg/m²", help: "Enter 0 if not measured.", required: false, min: 0, max: 80, step: 0.1 },
  { key: "SkinThickness", label: "Triceps skinfold thickness", unit: "mm", help: "Enter 0 if not measured.", required: false, min: 0, max: 100, step: 1 },
  { key: "Insulin", label: "Serum insulin after glucose load", unit: "µU/mL", help: "The benchmark records a 2-hour measurement. Enter 0 if not measured.", required: false, min: 0, max: 1000, step: 1 },
  { key: "DiabetesPedigreeFunction", label: "Family-history score", unit: "benchmark index", help: "Dataset-specific score derived from family history.", required: true, min: 0, max: 3, step: 0.01 },
  { key: "Age", label: "Age", unit: "years", help: "The benchmark population starts at age 21.", required: true, min: 0, max: 100, step: 1 },
] as const;

export const featureNames: Record<string, string> = Object.fromEntries(featureFields.map((field) => [field.key, field.label]));
export const assessmentSchema = z.object({
  Pregnancies: z.number().min(0).max(20),
  Glucose: z.number().min(0).max(500).nullable(),
  BloodPressure: z.number().min(0).max(150).nullable(),
  SkinThickness: z.number().min(0).max(100).nullable(),
  Insulin: z.number().min(0).max(1000).nullable(),
  BMI: z.number().min(0).max(80).nullable(),
  DiabetesPedigreeFunction: z.number().min(.01).max(3),
  Age: z.number().min(21).max(100),
});
