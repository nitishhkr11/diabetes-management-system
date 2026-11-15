# Implementation audit and verification

## Pre-change audit

- The workspace contained an existing Streamlit research dashboard, a Python training/inference pipeline, the approved Logistic Regression, Gaussian Naive Bayes and Random Forest pipelines, SHA-256 checked release artifacts, SHAP, reliability reports, optional local SQLite history, data validation, documentation and 83 passing tests from the prior implementation.
- The ML pipeline was already reproducible and leakage-aware: strict dataset checks, zero-to-missing conversion for five measurement features, train-only median imputation/scaling, stratified 80:20 split, training-only 5-fold CV model selection and a held-out test evaluation.
- The prior single-process UI had no Next.js site, API service, hosted identity or account-isolated database. Local SQLite could not safely act as public multi-user storage. It also lacked dedicated sourced education, account workflows, RLS and the requested concept simulation.
- No Supabase credentials, deployment account, Git metadata or Git remote were present. Live auth, production RLS, CI and deployment could not be verified without those external services.
- The default host Python was 3.13 with missing ML dependencies; the repository's pinned Python 3.11 environment was available and used for validation.

## Implementation decisions

- Replaced the competing Streamlit UI with one Next.js App Router/TypeScript frontend; kept offline training and generated evidence in the existing Python modules.
- Added FastAPI serving the saved verified artifacts, versioned prediction, model metadata/evaluation, PNG evidence, sensitivity and report endpoints, input validation, error IDs, stream-enforced 16 KiB body cap, exact-origin CORS and a modest per-process request throttle.
- Added Supabase SSR cookie auth integration and protected account/history screens. The API independently validates Auth tokens and forwards user JWTs to PostgREST. `backend/schema.sql` enables forced RLS. No service-role key or password store is present.
- Guest estimate is a fixed synthetic, labeled demo with no persistence. Authenticated users may enter their own values. History requires post-result consent and server-side recomputation; individual/all-history delete and CSV export are provided.
- Added official-source diabetes education, original SVG insulin/glucose concept visualization, mobile drawer/theme toggle, model lab, actual generated metrics, sensitivity explorer and privacy documentation.

## Verification record

Verified locally on 2026-10-21 with the repository Python 3.11 environment and Node.js 24.22:

- `python -m src.data_validation data/diabetes.csv` — passed all schema, row-count, class-count and fingerprint checks.
- `python -m pytest -q -o addopts=''` — 90 passed; one Starlette deprecation warning from the installed TestClient/httpx integration.
- `python -m compileall -q src scripts backend tests` and `python -m pip check` — passed.
- `npm ci` — completed from the lockfile; npm reported 0 vulnerabilities.
- `npm run lint`, `npm run typecheck`, and `npm run build` — passed. Next generated 13 static pages plus the expected dynamic account/API routes.
- `npm run test:e2e` — 5 passed. Playwright is configured for one worker because parallel Next dev workers stalled route transitions in this environment.
- `docker compose config --quiet` and parsing `render.yaml` — passed. `docker compose build` could not run because Docker Desktop's Linux engine was not running.

Provider-backed auth and RLS need to be checked after configuring a Supabase project. No hosted CI run, production container build, or deployment was performed; those steps remain account- and environment-dependent.

## ML reliability upgrade (2026-10-21)

- Verified the previous dashboard metrics against the saved baseline report. Its actual deployed Logistic Regression threshold was 0.50, although an OOF-selected 0.40 threshold and separate test row had also been reported. Archived a reproducible copy of the original three-model artifacts in models/baseline_v1 and reports/baseline_v1.
- Added scripts/train.py as the canonical entry point for nested stratified 5-fold outer / 4-fold inner model-family comparison. Search covers the three approved models, RBF SVM and Gradient Boosting; every imputer, scaler and parameter search is fit within the corresponding training fold. The holdout is scored only for the preselected winner after the OOF recall/precision threshold rule is fixed.
- Evaluated none versus balanced class weights with nested OOF predictions for LR/RF/SVM. Did not use synthetic resampling. The class-weight ablation is in reports/class_weight_ablation.csv.
- The measured selected model is tuned Logistic Regression at threshold 0.49223698810458655, artifact version 4ea22108c507. The artifact card, inference API, evaluation response and reliability UI now use this same model and threshold. Only this selected model's final holdout metrics are released in the new test report.
- Added nested OOF comparisons, full final metrics, stratified bootstrap intervals, calibration bins/plot, experiment config with data hashes, class-weight comparison, baseline comparison, dynamic five-model inference metadata and regression tests.
- Reviewed CDC NHANES 2021–2023 and BRFSS 2024 as candidate complementary tasks. Their self-reported diagnosis targets, populations, predictors and sampling designs are not aligned with Pima; neither is claimed as external validation. See docs/independent-dataset-assessment.md.
- Runtime checks at that stage: data fingerprint validation, package consistency, artifact hash load, prediction + SHAP API smoke, live API metadata, updated Next.js page HTTP checks, frontend ESLint and TypeScript check passed. `python -m pytest -q` passed all 96 then-current tests; the artifact-version regression added after collection also passed as a focused test. One Starlette/httpx TestClient deprecation warning remains. At that stage the production build and Playwright were deferred to avoid the shared build directory; they were later completed using an isolated `.next-verify` directory and are recorded below.

### Historical holdout exposure correction

Inspection of `reports/experiments/leakage_runs.csv` and `leakage_summary.csv` found explicit `test_set_threshold_tuning` analyses over the nominal seed-42 holdout, used as a leakage demonstration. The saved baseline reports also contain multiple model/threshold comparisons on those same 154 rows. The nested release training code selects its family and threshold on training-only nested OOF predictions and evaluates the chosen model after those choices, but this historical reuse means the holdout is not pristine or independent. Its metrics and bootstrap intervals are descriptive only; a new independent aligned dataset or prospective evaluation is needed for confirmatory claims. API and dashboard disclosures now report current-run selection separately from historical exposure.

## Unified report and manual workflow (2026-10-21)

- Added a signed-in-only `/api/v1/reports/extract` route and same-origin multipart proxy. PDFs, PNG, JPEG and JPG use bounded parsing: 10 MiB file cap, five PDF pages, 40 MP image cap, PDF signature/content checks, OCR timeout, generic errors and upload close in a `finally` block. Multipart parsing may spool a temporary buffer to the OS private temp directory; it is cleaned on close and never persisted by the app. Text PDFs use embedded text; scans/images use local Tesseract only. No report or OCR text is logged.
- Added conservative extraction of HbA1c, glucose, blood pressure, BMI and age into editable, source-labeled lab observations. Ambiguous duplicate values are omitted. HbA1c, fasting/random glucose and non-mg/dL glucose are not mapped into Pima features. Explicit user action maps only a compatible BMI, age, or labeled two-hour OGTT glucose; conflicting manual values require confirmation. Manual entry remains available, and source labels are returned to the API and included with opted-in history.
- The estimator shows a CDC educational link for HbA1c context. It does not interpret laboratory values or diagnose. Production Docker installs the Tesseract binary. A local Windows deployment needs Tesseract installed separately for scanned documents; text PDFs work without OCR.
- Historical test exposure audit: earlier repository leakage reports deliberately swept thresholds on the same nominal holdout. Current nested selection is training-only, but the 154-row holdout is historically exposed. The API, report JSON, model card, methodology and reliability UI now mark its metrics as descriptive and do not claim an independent test.
- Preserved the five release artifacts in packaging ignore rules. Added an isolated Next.js build directory option and used `.next-verify` to avoid touching the live development server. ESLint and Docker ignore generated `.next-*` folders.

### Verification for the report workflow

- `python -m pytest -q -o addopts=''` — 111 passed in 348.23s; one Starlette/httpx TestClient deprecation warning.
- `npm run lint`, `npm run typecheck` — passed after excluding generated build output.
- `NEXT_DIST_DIR=.next-verify npm run build` (PowerShell environment syntax used) — production build passed.
- Production Playwright suite on port 3100 — 6 passed, including authenticated-upload gate and existing landing, education, theme, mobile and synthetic-estimator checks. Supabase-backed signed-in browser upload could not be exercised without configured credentials; the authenticated FastAPI multipart flow is covered by the test suite.
- `docker compose config --quiet` — passed. Docker image build was not available because the Docker Desktop Linux engine is stopped.
- `pip check`, `compileall`, dataset fingerprint validation and `npm audit --omit=dev --audit-level=high` — passed. Docker deployment and live provider/RLS checks remain environment-dependent.
