# Security and privacy

## Account boundary

Supabase Auth owns passwords and verification/reset flows. Next.js uses `@supabase/ssr` cookie sessions (`SameSite=Lax`, `Secure` in production) and validates claims server-side. The same-origin API proxy forwards a session token only after claim validation. FastAPI independently validates the token through Supabase Auth. No custom password storage, admin bypass, service-role key or production demo password is included.

The API forwards the user's JWT to Supabase PostgREST. `backend/schema.sql` enables and forces RLS. Reads, inserts and deletes require `auth.uid() = user_id`; database defaults assign `user_id`, and browser input cannot select an owner. No live Supabase project was available in this workspace, so policies are implemented but not exercised against a provisioned database.

## What may be stored

Public education pages and the unauthed synthetic demo are non-persistent. For an authenticated assessment, the result remains in browser memory unless the user checks a separate consent control. A saved record includes the eight model inputs, manual/report source labels, output score/label/threshold, model name/version, timestamp and SHAP explanation. The uploaded file and extracted text are never saved. No name, patient reference or email is stored with an assessment row.

Users can export their own records as CSV, delete one row, or delete all of their rows. The schema cascades rows when the Supabase Auth user is deleted. Self-service account deletion is not implemented because it requires a carefully controlled server-side administrative action; the project owner must remove an account in Supabase. No retention timer is configured.

## API protections

Pydantic and the shared model input validator run server-side. The API buffers request bodies only up to 16 KiB and rejects larger streams even when `Content-Length` is missing. Prediction/sensitivity calls use a per-process 30-request-per-minute throttle, browser-to-API CORS must use exact origins, errors avoid stack traces/provider internals, and health values contain no user data. The Next.js proxy forwards the platform's client IP for this throttle; a multi-instance production deployment should use an edge/API gateway for distributed throttling and body limits.

Use HTTPS on deployed frontend/API and store environment settings in host secret managers. Only publishable Supabase keys go to the browser. This student app has not received a security, privacy, regulatory or compliance review. Do not submit real or identifiable patient data.

## Medical-report extraction

Report extraction is restricted to a signed-in session. PDF, PNG, and JPEG/JPG files are limited to 10 MiB; PDFs are limited to 5 pages and images to 40 megapixels. Content is type- and signature-checked. Starlette may spool a multipart request buffer to the operating system's private temporary directory; the upload is never written to a public or persistent application directory, and the temporary buffer is closed on success and failure. Extracted text and lab values are processed for the response only, not stored in prediction history or ordinary logs. The request and proxy enforce bounded body sizes.

Text-based PDFs use embedded text extraction. Scanned PDFs and images use local Tesseract OCR (the Docker API image installs the Tesseract binary). No third-party OCR service is used. On a local Windows setup, install Tesseract separately and make `tesseract.exe` available on `PATH`; missing OCR produces a manual-entry fallback. Extracted observations are editable and are not considered confirmed until the user reviews them. HbA1c, fasting/random glucose, and other incompatible lab results are never substituted for Pima model features. The UI maps only a matching feature (age, BMI, or a clearly labeled two-hour OGTT glucose) after explicit user action. The app does not persist the report or extracted lab observations.

This lightweight parser is not validated for clinical use. OCR can misread labels, decimal points, values, and units. Users must compare the extraction with the source report; unreadable and ambiguous values should be entered manually or omitted.
