# Architecture

The release is a small monorepo: the Next.js App Router frontend owns the public user experience; FastAPI validates requests and serves already trained scikit-learn pipelines; Supabase Auth and PostgreSQL provide optional signed-in accounts and per-user history.

```mermaid
flowchart LR
  CSV[Verified Pima CSV] --> TRAIN[scripts/train.py]
  TRAIN --> ART[Three SHA-256 verified pipeline artifacts + model card]
  ART --> API[FastAPI inference API]
  WEB[Next.js App Router] -->|same-origin proxy| API
  API --> PRED[Prediction + SHAP + evaluation + sensitivity]
  WEB --> AUTH[Supabase Auth cookie session]
  WEB -->|user access token| API
  API -->|user JWT + anon/publishable key| PG[Supabase PostgREST]
  PG --> RLS[PostgreSQL RLS: auth.uid() = user_id]
```

## Responsibilities

- `frontend/src/app/`: public landing, education, simulation, estimator, reliability, Model Lab, project, account, history, settings, auth and API proxy routes.
- `frontend/src/components/`: theme-aware responsive shell, education illustration, assessment results, charts, auth and account UI.
- `frontend/src/lib/supabase/`: cookie-backed SSR clients; proxy refresh uses verified claims. The Next.js API route validates claims before forwarding private calls.
- `backend/main.py`: versioned REST API, Pydantic validation, model artifact checks, prediction, SHAP report, sensitivity, Supabase token validation and history requests.
- `backend/schema.sql`: assessment table, grants and row-level owner policies. User identity is assigned by `auth.uid()`; the browser cannot set `user_id`.
- `src/`, `scripts/`, `data/`, `models/`, `reports/`: original training, data checks, explainability, release artifacts and generated evaluation evidence.
- `tests/`: original ML/data tests and FastAPI route tests. `frontend/e2e/`: Playwright browser smoke/flow tests.

## Trust boundaries

The browser only receives a Supabase publishable key. Next.js uses the cookie session and checks claims; the API independently validates the bearer token with Supabase Auth for protected history calls. PostgREST receives the same user's JWT, so PostgreSQL RLS remains the final ownership check. There is no service-role key or password table in this project.

Offline training is never triggered by a web request. Inference loads only the manifested artifacts and verifies package versions, dataset fingerprint, model set, feature schema and each artifact's SHA-256 before unpickling.

The public estimator demonstration uses fixed synthetic inputs; personal inputs require a signed-in session. Nothing is stored unless the user checks the explicit history consent control after the result.
