export type IdrsBreakdown = {
  age_points: number;
  waist_points: number;
  activity_points: number;
  family_history_points: number;
};

export type IdrsResult = {
  ok: true;
  tool: "mdrf_idrs";
  guideline_version: string;
  source_url: string;
  score: number;
  max_score: number;
  risk_category: "low" | "moderate" | "high";
  risk_label: string;
  next_steps: string;
  breakdown: IdrsBreakdown;
  normalized_inputs: {
    age_years: number;
    sex: "female" | "male";
    waist_cm: number;
    physical_activity: "vigorous" | "moderate" | "mild" | "sedentary";
    family_history: "none" | "one_parent" | "both_parents";
  };
  limitations: string[];
  disclaimer: string;
};

export type LabFinding = {
  test: string;
  value_display: string;
  category: "normal" | "prediabetes" | "diabetes" | "indeterminate";
  label: string;
};

export type LabInterpretResult = {
  ok: true;
  tool: "lab_interpretation";
  guideline_version: string;
  pregnancy_pathway: boolean;
  overall_category: string;
  overall_label: string;
  results: LabFinding[];
  confirmation_required: boolean;
  guidance: string;
  guideline_notes: string[];
  disclaimer: string;
};

export type IndiaRiskRecord = {
  id: string;
  created_at: string;
  assessment_type: "mdrf_idrs" | "lab_interpretation";
  guideline_version: string;
  result_category: string;
  score: number | null;
  inputs: Record<string, unknown>;
  result_payload: IdrsResult | LabInterpretResult;
  consent: boolean;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/dms${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    const validationErrors = Array.isArray(detail)
      ? detail.map((item: { message?: string; msg?: string }) => item.message || item.msg).filter(Boolean).join(" ")
      : "";
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail?.errors)
          ? detail.errors.join(" ")
          : validationErrors || "The request could not be completed."
    );
  }
  return response.json() as Promise<T>;
}
