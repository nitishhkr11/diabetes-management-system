# Deployment

## Local setup

Use Python 3.11 (the model release pins its compatible runtime) and Node.js 20.9 or newer. From the repository root, in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m src.data_validation data/diabetes.csv
python -m uvicorn backend.main:app --reload --port 8000
```

In a second PowerShell window:

```powershell
Copy-Item .env.example frontend/.env.local
Set-Location frontend
npm ci
npm run dev
```

Edit `frontend/.env.local` with a Supabase project URL and publishable key before trying account flows. Public education pages and the synthetic, non-persistent demo work without Supabase. `API_BASE_URL` is server-only and should point to the FastAPI origin.

Run `docker compose up --build` to start a reproducible local web/API pair. Add Supabase settings in the shell or a local environment file; never commit values.

## Supabase setup

1. Create a Supabase project and configure email/password authentication.
2. Add local and deployed frontend URLs to Auth redirect allowlists, including `/auth/callback`.
3. Run `backend/schema.sql` in the Supabase SQL Editor and confirm RLS is enabled/forced on `public.assessments`.
4. Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` in the frontend host.
5. Set server-only `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and exact `CORS_ORIGINS` in the API host. The anon/publishable key is used with each user's JWT; do not use a service-role key.
6. Test signup/verification, logout, reset, per-user history, export and cross-user denial with two test accounts before real deployment.

## Frontend: Vercel

Connect the Git repository and set the project root directory to `frontend`. Use Node.js 22 LTS or another version satisfying the installed Next.js requirement. Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, and server-only `API_BASE_URL` to the deployed API. Deploy a preview, check public routes, auth callbacks and responsive/theme flows, then promote only after account tests pass.

## Backend: Render

Create a Docker web service using `render.yaml` (`backend/Dockerfile`, repository root as Docker context). Add `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `CORS_ORIGINS` using the Render environment UI. The health check is `/health/ready`; it loads and verifies all three release artifacts. After deploy, check `/health/live`, `/health/ready`, `/docs`, `/api/v1/metadata` and the prediction endpoint with synthetic inputs.

The tracked `models/*.joblib` files and `models/model_card.json` are required and SHA-256 checked before inference. Online requests never retrain. Confirm repository/image size limits and build compatibility before public release.

## Before publishing

- Use HTTPS and exact frontend origin in CORS.
- Verify email delivery, redirect allowlists, RLS, two-account ownership denial and deletion/export.
- Verify body-size/rate limits at the provider edge for multi-instance deployments.
- Run the root pytest suite, frontend lint/typecheck/build and Playwright flow tests.
- Manually check a small mobile viewport, light/dark theme, browser console, accessibility and host logs.
- Do not add a deployment URL to project materials until the app is live and smoke-tested.
