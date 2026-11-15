# Known limitations and incomplete deployment steps

- This is an educational research prototype, not a medical device, clinical risk calculator, diagnosis, screening service or treatment system.
- The Pima benchmark is a 768-row historical cohort with narrow population coverage; no external validation, subgroup fairness review or prospective evaluation was performed.
- The outcome is binary and cannot distinguish diabetes types. Model score output is not a personal medical probability.
- Model performance is modest on the one held-out split. Four aspirational project targets were not reached. Review generated confidence intervals and metrics rather than extrapolating from this split.
- The nominal 154-row holdout was examined by prior exploratory threshold/model reports, so current test metrics are descriptive and not independent confirmatory estimates.
- Medical-report extraction uses conservative label patterns and is not clinically validated. OCR confidence is a technology estimate, not a guarantee that a medical value or unit is correct. The Windows workspace did not have a Tesseract executable, so OCR quality on real scanned reports was not verified; the OCR path uses local Tesseract and can fall back to manual entry.
- The signed-in browser flow could not be tested against a real Supabase project because provider credentials are not available. Automated tests cover authentication gating and the authenticated FastAPI upload path with a test identity. The Docker Compose configuration validates, but a container image build/deployment was not verified because Docker Desktop's Linux engine was unavailable.
- Account sign-up, email verification, reset and RLS history require the operator to create a Supabase project, configure auth redirect URLs, run `backend/schema.sql`, and set environment values. No credentials were supplied; provider-backed flows were not live-tested.
- Self-service account deletion and a configurable data-retention schedule are not implemented. Users can delete individual/all history; the Supabase project owner removes accounts.
- Prediction rate limiting is in-process and resets on restart. Scaled deployments need a gateway/distributed limiter, production monitoring and an external security review.
- A deployment URL, GitHub Actions run and production smoke test do not exist in this supplied workspace because it has no Git remote/deployment credentials.
- Research artifacts remain tracked as the project's reproducible release inputs; review hosting repository size limits before publishing them.
