# GlucoGuide — Architecture & Technical Documentation

## 1. Project Objective & Problem Statement
Adults in India often face two practical challenges regarding diabetes awareness:
1. Knowing whether they are at elevated risk *before* getting a laboratory blood test, using India-relevant anthropometric cutoffs.
2. Understanding what existing blood-test numbers (HbA1c, Fasting Glucose, 2-hour OGTT, Random Glucose) mean in plain language without misinterpreting a single reading as a definitive diagnosis.

GlucoGuide addresses both needs through two separated, rule-based, medically grounded pathways — **without** claiming to be an AI diagnostic tool or relying on non-Indian research datasets.

---

## 2. System Architecture
```
Next.js 16 (App Router, TypeScript)
   │  Same-origin API proxy (/api/dms/[...path])
   ▼
FastAPI Backend (Pydantic v2 validation, RateWindow, BodyLimitMiddleware)
   ├── src/mdrf_idrs.py            (MDRF-IDRS deterministic scoring engine)
   ├── src/lab_interpretation.py   (ADA / ICMR-WHO lab interpreter + safeguards)
   └── Supabase Auth + PostgREST   (Optional, consent-gated user history via RLS)
```

---

## 3. Technology Stack
- **Frontend:** Next.js 16.4.6 (App Router), React 19, TypeScript, Recharts, Lucide icons, `next-themes` (light/dark mode), CSS custom properties.
- **Backend:** FastAPI, Pydantic v2, `httpx`, Uvicorn (Python 3.11).
- **Authentication & Database:** Supabase Auth (JWT Bearer verification via `/auth/v1/user`) + PostgreSQL Row Level Security (`india_risk_assessments`).
- **Testing:** `pytest` (unit + FastAPI `TestClient`), ESLint, `tsc --noEmit`, Next.js production build, and Playwright E2E tests.

---

## 4. Core Screening & Interpretation Logic
### Pathway A: MDRF-IDRS (`src/mdrf_idrs.py`)
Implements the published Madras Diabetes Research Foundation Indian Diabetes Risk Score evaluated in the ICMR-INDIAB study for Indian adults aged 20+:
- **Age:** `< 35` (0), `35–49` (20), `≥ 50` (30). Ages `< 20` or `> 120` are rejected (`422`).
- **Waist Circumference (cm, or converted from inches × 2.54):**
  - Female: `< 80` (0), `80–89.9` (10), `≥ 90` (20)
  - Male: `< 90` (0), `90–99.9` (10), `≥ 100` (20)
- **Physical Activity:** Vigorous (0), Moderate (10), Mild (20), Sedentary (30).
- **Parental History:** Neither (0), One parent (10), Both parents (20).
- **Risk Bands (0–100):** `< 30` Low risk · `30–50` Moderate risk · `≥ 60` High risk.

### Pathway B: Laboratory Result Interpretation (`src/lab_interpretation.py`)
- **Pregnancy Guard:** `is_pregnant = true` routes directly to `pregnancy_specialist_pathway` (gestational diabetes uses DIPSI / IADPSG / WHO criteria).
- **HbA1c (%):** `< 5.7` Normal · `5.7–6.4` Prediabetes · `≥ 6.5` Diabetes range.
- **Fasting Plasma Glucose (`mg/dL` or `mmol/L` × 18.0182):** `< 100` Normal (ADA) · `100–125` Prediabetes (ADA; notes WHO/ICMR `110–125` IFG cutoff) · `≥ 126` Diabetes range.
- **2-hour OGTT (`mg/dL` or `mmol/L`):** `< 140` Normal · `140–199` Prediabetes/IGT · `≥ 200` Diabetes range.
- **Random Plasma Glucose:** `≥ 200 mg/dL` requires classic symptoms; asymptomatic high values return `indeterminate_requires_confirmation`.
- **Confirmation Safeguard:** Unconfirmed diabetes-range values advise repeat clinical testing; single home glucometer readings are explicitly noted as non-diagnostic.

---

## 5. API Endpoints (`backend/main.py`)
- `GET /health/live`, `GET /health/ready` — Service health checks.
- `POST /api/v1/india-risk/idrs` — Compute MDRF-IDRS score.
- `POST /api/v1/india-risk/lab-interpret` — Interpret laboratory test values.
- `POST /api/v1/india-risk/history` — Save assessment (requires Supabase Bearer token + `consent: true`).
- `GET /api/v1/india-risk/history` — List authenticated user's saved records.
- `GET /api/v1/india-risk/history/export` — Export authenticated user's records as CSV.
- `DELETE /api/v1/india-risk/history/{assessment_id}` — Delete one record.
- `DELETE /api/v1/india-risk/history` — Delete all records for the authenticated user.

---

## 6. Database & Security (`backend/schema_india_screening.sql`)
- Table `public.india_risk_assessments` stores `user_id` (`default auth.uid()`), `assessment_type`, `guideline_version`, `result_category`, `score`, `inputs` (JSONB), `result_payload` (JSONB), and `consent` (`check (consent = true)`).
- **Row Level Security (RLS)** is enabled and forced: `anon` is revoked; `authenticated` users can only `SELECT`, `INSERT`, and `DELETE` rows where `(select auth.uid()) = user_id`.
- Pydantic `RequestValidationError` handler strips submitted health values from 422 responses so sensitive measurements are not echoed into logs.

---

## 7. Known Limitations & Future Improvements
- **Not a diagnostic device:** GlucoGuide provides educational screening and reference-range guidance only.
- **ICMR-INDIAB data:** GlucoGuide does not possess raw ICMR-INDIAB participant data; MDRF-IDRS uses the published scoring table.
- **Future improvements:** Multi-language Indian regional translations (Hindi, Tamil, Marathi, etc.) and PDF lab-report OCR extraction scoped strictly to Indian pathology formats.
