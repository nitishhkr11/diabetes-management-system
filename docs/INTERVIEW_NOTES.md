# Interview notes

## Contribution and trade-offs

This is a systems-integration contribution with a reproducible nested-CV model comparison: verified data, leakage-aware preprocessing and tuning, three approved baselines, SVM/gradient-boosting comparisons, traceable artifacts, local/global explanations and a privacy-conscious dashboard.

- Logistic Regression is a compact probabilistic reference and easier to interpret linearly.
- Gaussian Naive Bayes makes a fast comparison under a different conditional-independence assumption.
- Random Forest adds nonlinear splits and interactions without requiring a deep-learning stack.
- Model-family selection uses nested training-only stratified CV; a predeclared threshold uses nested OOF predictions, and the held-out test is evaluated once for the selected model only.
- The deliberately leaky examples are isolated teaching material. They demonstrate why data provenance and split discipline matter.

## Resume bullets (edit to match your actual contribution)

- Built a reproducible Next.js + FastAPI ML research website with artifact checks, local SHAP explanations, reliability metrics and a distribution-bounded sensitivity view.
- Implemented verified-schema and canonical-hash checks for the Pima benchmark to reject look-alike or altered datasets.
- Compared Logistic Regression, Gaussian Naive Bayes, Random Forest, RBF SVM and Gradient Boosting under nested stratified CV, with a training-only class-weight ablation and one selected-model holdout evaluation.
- Added privacy-safe single-case HTML audit reports and opt-in local SQLite history with deletion and CSV export.
- Documented model, dataset and deployment limitations, including the absence of external clinical validation.
