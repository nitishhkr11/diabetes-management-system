# Public GitHub projects for Pima diabetes prediction — verified by reading the code

Date of inspection: 2026-10-01 (shallow `git clone --depth 1`, files read locally). Every repo is a COMMUNITY IMPLEMENTATION, not peer-reviewed evidence.
Labels: SOURCE FACT = observed in the repo at the pinned commit; INFERENCE = my reading; RECOMMENDATION = what our team should do.
Not collected (no GitHub API from this environment): star/fork counts, deployment-link health. Licence = presence/absence of a LICENSE file at the repo root; code with no licence is all-rights-reserved by default, so it must not be copied.

## Headline findings
1. SOURCE FACT — No inspected repo combines ALL of: genuine Pima data + zero->missing inside a leakage-safe Pipeline + multi-model comparison + patient-level SHAP + SQLite history + Streamlit. Searches run (WebSearch): "streamlit diabetes prediction app Pima Indians dataset github repository random forest"; "diabetes prediction SHAP explainability streamlit SQLite prediction history Pima github"; plus the topic pages returned by them. 13 repos cloned and scanned for `streamlit`, `shap`, `lime`, `sqlite3`, `Pipeline`, `stratify`, imputers, `GaussianNB`.
2. SOURCE FACT — Closest single-feature neighbours: akshada-Git (Pima + Pipeline + SHAP + Streamlit + tests + near-identical requirement wording, but no history DB and no GaussianNB); anandd46 (Streamlit + SHAP + SQLite history, but SYNTHETIC data, not Pima).
3. SOURCE FACT + REPRODUCTION — Three repos (pranavppramod, Vivekrathod01, Faiyaz-48) report RF ROC-AUC 0.94-0.95 / accuracy 0.86-0.88 on a Pima dataset in which missing values were filled with CLASS-CONDITIONAL constants (the label leaks into the features). Our rerun with pranavppramod's exact RF settings and split (stratified 80:20, random_state=42, n_estimators=200): their CSV -> AUC 0.9458 (README says 94.58%); genuine Pima with train-only median imputation -> AUC 0.8168, accuracy 0.7468 (sklearn 1.8.0). Raw output kept in `scratchpad` run log; reproduce with `scripts/leakage_demo.py` and `python scripts/experiments.py --only B` in our project.

## Look-alike / modified datasets seen inside repos (wrong-CSV evidence)
| Seen in | File | Shape | Verified fact |
|---|---|---|---|
| pranavppramod/Diabetes-Prediction-System @2f3f2674b1 | dataset/diabetes_original.csv | 768x9, Pima column names, labels identical to genuine | NOT the original: 652 cells differ (Glucose 5, BloodPressure 35, SkinThickness 227, Insulin 374, BMI 11 = exactly the genuine zeros). Each replaced cell holds ONE constant per class: Glucose 107/140, BloodPressure 70/74.5, SkinThickness 27/32, Insulin 102.5/169.5, BMI 30.1/34.3 (class 0 / class 1). Zero counts now 0 except Pregnancies 111. |
| Vivekrathod01/Diabetes_prediction_system @47662a00b4 | diabetes.csv | 768x9 | Value-for-value identical to the file above (same 652 replaced cells). |
| Nox5556/Diabetes-Prediction-using-Random-forest @4ee582191c | Diabetes.csv | 2768x10 (extra Id column), classes 1816/952 | First 768 rows equal the genuine Pima rows; 1,981 of the 2,000 remaining rows are exact copies (4-dp) of genuine rows -> a random split puts copies of training rows in the test set. |
| CarlousF/pima-indian-diabetes @a9b26317a1 | pima-data.csv | 768x10 | Different schema: num_preg, glucose_conc, diastolic_bp, thickness, insulin, bmi, diab_pred, age, skin, diabetes (True/False); classes 500/268. Same people, different columns. |
| Pritikaa2006/diabetes-risk-prediction @c38dc22315 | data/diabetes.csv | 253,680x22 | A different (survey-style) dataset stored under the same file name `diabetes.csv`. |

## Per-repo records
### 1. akshada-Git/Explainable-Diabetes-Risk-Prediction — https://github.com/akshada-Git/Explainable-Diabetes-Risk-Prediction  (commit cce0c5fc7b, 2026-09-29)
- Licence: MIT. Described in its README as a "B.Sc. Data Science, TY mini project".
- Dataset: Pima; not committed; `src/config.py` lists 3 public mirror URLs (plotly/datasets, npradaschnor, jbrownlee) tried in order; schema validated (`src/data.py`, `DatasetError`).
- Models: LogisticRegression, DecisionTree, RandomForest (class_weight="balanced"), XGBoost if installed; GridSearchCV 5-fold on the training split (`src/training.py`); SELECTED BY CV ROC-AUC (`best_name = max(results, key=cv_roc_auc)`, line 176).
- Preprocessing: zeros->NaN, median imputer + scaler inside a Pipeline (`src/preprocessing.py`); stratified 80/20.
- Explainability: SHAP with explicit unit handling (`model_units`, `unit_label`) and an additivity check (`additivity_gap`) in `src/explain.py`; plain-language summary; PDF report (`src/report.py`).
- Tests: 26 test functions in `tests/`; a sanity gate `MIN_TEST_ROC_AUC = 0.70`; docs folder with FRD/PRD/TRD. UI: Streamlit `app.py`. Deployment: none seen.
- README limitations mention: small dataset, one population, default threshold 0.5, tune towards recall for real screening.
- INFERENCE: this is the closest public analogue to OUR specification (its FR-1 wording matches ours almost word for word). We must write our own code, cite it as related work if read, and differentiate on real differences.
- Missing (grep of *.py): SQLite/history, GaussianNB, LIME, calibration/Brier, SHA-256 data check, repeated-split stability.

### 2. anandd46/DiabetesRiskPrediction_AI — https://github.com/anandd46/DiabetesRiskPrediction_AI  (commit d6a09655d6, 2026-09-25)
- Licence: MIT. Streamlit + SHAP + SQLite + tests.
- Dataset: SYNTHETIC. `train_model.py` line 54 `generate_synthetic_dataset()` draws features from normal/Poisson/gamma distributions "modelled loosely on" Pima summary statistics, adds PhysicalActivity/Smoking/FamilyHistory, and GENERATES the label from a logistic formula. Any metric it reports describes how well a model recovers that formula, not real patients.
- Models: RandomForest, LogisticRegression, DecisionTree; scaler fitted on the training split only but saved as a SEPARATE file (scaler + model, not one Pipeline).
- SHAP: `model.py` lines 144-147 TreeExplainer / LinearExplainer.
- History: `database.py` table `prediction_history(id, timestamp, risk_band, risk_score, confidence, patient_inputs JSON)`; parameterised `?` queries; connection context manager.
- Also: constraint-satisfaction + fuzzy-logic + rule-based advice text; in-app tests with invalid inputs (age 200, BMI -5).
- Useful idea (RECOMMENDATION): parameterised SQL and a small repository class; storing raw inputs as typed. Do NOT copy: synthetic data, two-artifact scaler/model, advice text that reads like medical guidance.

### 3. UznetDev/Diabetes-Prediction — https://github.com/UznetDev/Diabetes-Prediction  (commit a0ca1ceb80, 2024-11-24)
- Licence: MIT. Dataset: genuine Pima `datasets/diabetes.csv` (768x9). Model: RandomForest(max_depth=6, n_estimators=300, criterion="entropy") in a Pipeline with custom FeatureEngineering + WeightOfEvidence encoding.
- UI: Streamlit multi-page (`app/*.py`), SHAP TreeExplainer waterfall + force plots (`app/explainer.py`); README links a live Streamlit demo (not checked).
- WHAT NOT TO COPY (SOURCE FACT):
  - `training.py` lines 11-15: `Model.fit(X, y)` on ALL rows, then prints ROC-AUC computed on the same rows.
  - `loader.py` lines 14-36: the accuracy/F1/recall/precision/ROC-AUC shown in the app are computed on the FULL dataset with the model that was fitted on it (in-sample).
  - `notebooks/Model.ipynb` code cell 22 fits the pipeline on all of X, y; cell 24 then scores `X_test` (rows already seen in training) and prints the cross-validated AUC under the label "ROC AUC Score".
  - Only 5 of the 8 inputs (Pregnancies, Glucose, Insulin, BMI, Age) are used by `training.py`.
- Missing: honest hold-out report, tests, history.

### 4. pranavppramod/Diabetes-Prediction-System — https://github.com/pranavppramod/Diabetes-Prediction-System  (commit 2f3f2674b1, 2026-09-20)
- Licence: NO LICENSE FILE. Pima-column CSV but pre-imputed with class-conditional constants (see table above).
- Models: LogisticRegression baseline in a scaler Pipeline; RandomForest(n_estimators=200); GridSearchCV; feature-engineering experiment; 5-fold CV; SHAP explainer saved with joblib (`src/explainability.py` line 8); Streamlit `app.py`; 10 test functions (`tests/`).
- README-reported (community-reported, unreviewed): LR acc 70.78%, AUC 82.63% (we reproduce these EXACTLY on its CSV); RF "final test" acc 87.01%, prec 82.69%, rec 79.63%, F1 81.13%, ROC-AUC 94.58% (we reproduce AUC 0.9458, acc 0.8636 on its CSV).
- Good: clean `src/` split into prediction/explainability; tests; honest "tuning did not help" note. Do NOT copy: the dataset file; presenting 0.9458 as Pima performance.

### 5. Faiyaz-48/diabetes-prediction-system — https://github.com/Faiyaz-48/diabetes-prediction-system  (commit cf669d2c4b, 2026-09-19)
- Licence: NO LICENSE FILE. Genuine Pima `diabetes.csv`; 5-page Streamlit app (Home, Predict, Dataset Explorer, Model Performance, About); disclaimer "Educational / academic project only. Not a medical device."
- Models: LogisticRegression(C=1) and RandomForest(200 trees, max_depth=6) each in a Pipeline(StandardScaler, classifier); stratified 80:20; joblib.
- WHAT NOT TO COPY: `preprocessing.py` line 91 `df.groupby(TARGET_COLUMN)[col].transform(lambda s: s.fillna(s.median()))` — imputes with the CLASS-CONDITIONAL median, and `model.py` line 82 calls `load_and_clean()` BEFORE `train_test_split` (line 85). The label leaks into the features and the statistics are computed on test rows. Its committed `assets/metrics.json` RF row (acc 0.8636, AUC 0.942) matches what we reproduce on label-leaking data.
- Good: `validate_input()` bounds table; Model Performance page; clear disclaimers.
- Inference-time issue: widgets allow 0 for Glucose/BloodPressure/etc. and the model was trained after imputation, so a 0 is treated as a real value.

### 6. Vivekrathod01/Diabetes_prediction_system — https://github.com/Vivekrathod01/Diabetes_prediction_system  (commit 47662a00b4, 2026-09-08)
- Licence: NO LICENSE FILE. Committed `diabetes.csv` = class-conditional pre-imputed Pima (table above).
- Models (all in scaler Pipelines): LogisticRegression, KNN, SVM, GaussianNB, DecisionTree, RandomForest, XGBoost; GridSearchCV on RF and XGB; SMOTE applied AFTER the split on the training part only (`main.py` lines 67-71 — correct order); FastAPI + Streamlit; XGB saved with pickle.
- Not to copy: hard-coded absolute Windows path (`main.py` line 22); split without `stratify` (line 67); the leaky CSV.
- Community-reported (`diabetes_model_evaluation_results.csv`, test n=154): LR acc 0.8506 recall 0.9149; NaiveBayes acc 0.8571; RF acc 0.8831; XGBoost acc 0.8831 — INFERENCE: inflated by the pre-imputed CSV; genuine clean Pima accuracy is ~0.71-0.77 (our runs).
- Useful: wide model-comparison table saved as CSV; separate inference API.

### 7. Niharikaneelu/diabetes_risk_prediction — https://github.com/Niharikaneelu/diabetes_risk_prediction  (commit b5b2bcbe3c, 2026-09-29)
- Licence: NO LICENSE FILE. Pima `data/diabetes.csv` (README: 768 patients). RF vs XGBoost with SHAP (`explainability/`, `src/explainability.py` TreeExplainer); Streamlit `app.py` plus a generated static HTML front end.
- GOOD PRACTICE (`src/preprocessing.py`): `split_data(..., leak_free=True)` splits first and computes train-only medians (lines 58-75); the old leaky path is still reachable with `leak_free=False` (lines 49-56) — a nice teaching device.
- Community-reported, unreviewed (`ml/results/model_comparison.csv`, hold-out n=154): RF acc 0.7532, prec 0.6429, rec 0.6667, F1 0.6545, AUC 0.8257; XGBoost acc 0.7727, prec 0.7021, rec 0.6111, F1 0.6535, AUC 0.8409. 5-fold CV on train (`cross_validation_results.csv`): RF AUC 0.8276 +/- 0.0313, XGB 0.8278 +/- 0.0230. INFERENCE: these are in the realistic range.
- Not to copy: imputation lives outside the saved pipeline, so inference must re-implement it.

### 8. Linggge/diabetes-risk-prediction — https://github.com/Linggge/diabetes-risk-prediction  (commit 8e3fa8c8b7, 2026-09-24)
- Licence: MIT. Single-file Streamlit app. Pima file is NOT committed: the app shows "Dataset not found. Download the Pima Indians Diabetes Database..." (good practice). Zeros->NaN, SimpleImputer(median) in a ColumnTransformer inside the Pipeline, stratified 80/20, class-balanced RandomForest; metrics computed at runtime; README states it is a cleaned portfolio edition of a university team project and does not claim sole authorship of the original.
- Missing: SHAP, history DB, multi-model comparison, tests.

### 9. Arshavir01/diabetes-app — https://github.com/Arshavir01/diabetes-app  (commit adf58adcdb, 2026-09-24)
- Licence: NO LICENSE FILE. Linear SVM on Pima (README), `diabetes_trained_model.sav` + `scaler.sav` pickles, Streamlit, live app link in README (not checked).
- Community-reported: train accuracy 78.7%, test accuracy 77.3% (154 unseen patients). README honestly records two lessons: the scaler must travel with the model, and scikit-learn is pinned (1.6.1) so the pickle loads.
- Caution: loading pickle files from unknown sources can execute code — only load files you created.

### 10. arunnthevapalan/diabetes-prediction-app — https://github.com/arunnthevapalan/diabetes-prediction-app  (commit 7a439fda3a, 2024-05-07)
- Licence: NO LICENSE FILE. Pima `data/datasets_228_482_diabetes.csv` (768x9, genuine columns); Streamlit + Dockerfile; model/scaler joblibs; Python 3.6.7 era.
- Notebook (`notebooks/diabetes_prediction_pipeline.ipynb`, cell indices from the JSON): cells 9-10 `impute_median` groups by Outcome (class-conditional median); cell 12 `StandardScaler().fit(x)` on ALL rows; cell 16 split WITHOUT stratify; cell 17 RF(n_estimators=300). Three leakage/protocol issues.

### 11. CoreyLeath-code/Disease_Prediction_Capstone — https://github.com/CoreyLeath-code/Disease_Prediction_Capstone  (commit fa2aaeb99a, 2026-09-26)
- Licence: MIT. Not Pima-aligned (Streamlit asks age, BMI, cholesterol, systolic BP; target column `target`; data not committed). Large engineering scaffold: FastAPI, Dockerfile, tests, MODEL_CARD.md, SECURITY.md, ARCHITECTURE.md.
- `preprocess.py` lines 40-42 fit a StandardScaler on the whole matrix, and `src/src/preprocessing.py` line 27 splits afterwards -> scaler leakage.
- Use only as a REFERENCE for documentation files (model card, security notes), not as a Pima example.

## Feature matrix (Y = present in code, N = not found by scan/reading, p = partial)
| Repo | Real Pima | Zero->missing | Leak-safe imputation | Multi-model | Multi-metric | CV | SHAP | LIME | Streamlit | SQLite/history | Tests |
|---|---|---|---|---|---|---|---|---|---|---|---|
| akshada-Git | Y (mirrors) | Y | Y (in Pipeline) | Y | Y | Y | Y | N | Y | N | Y |
| anandd46 | N (synthetic) | n/a | n/a | Y | Y | N | Y | N | Y | Y | Y |
| UznetDev | Y | N | n/a | N | Y (in-sample) | p (leaky final) | Y | N | Y | N | N |
| pranavppramod | p (pre-imputed) | N | N (label leak in file) | Y | Y | Y | Y | N | Y | N | Y |
| Faiyaz-48 | Y | Y | N (class-conditional, pre-split) | Y | Y | N | N | N | Y | N | N |
| Vivekrathod01 | p (pre-imputed) | N | N (label leak in file) | Y | Y | Y (grid) | N | N | Y | N | N |
| Niharikaneelu | Y | Y | Y (default) | Y | Y | Y | Y | N | Y | N | N |
| Linggge | Y (user-supplied) | Y | Y | N | p | N | N | N | Y | N | N |
| Arshavir01 | Y | N | n/a | N | N (accuracy only) | N | N | N | Y | N | N |
| arunnthevapalan | Y | Y | N (class-conditional, scaler on all) | N | p | N | N | N | Y | N | N |
No row has Y in every column; none has a GaussianNB-vs-LR-vs-RF comparison with SHAP, SQLite history and a data-provenance check together (Vivekrathod01 has GaussianNB among 7 models but no SHAP/history).

## What our project can safely claim (RECOMMENDATION)
- Individual parts (zero->missing, median imputation in a Pipeline, stratified split, multi-metric comparison, SHAP, Streamlit, SQLite history, tests) each exist in public projects.
- What we can claim as OUR contribution is the integration plus protocol discipline: a hash-verified, schema-validated dataset; the zero->missing rule INSIDE the saved Pipeline so training and inference match; model selection by cross-validation on the training split with an explicit tie rule; test-set used once; patient-level SHAP stored with each history row; reproducible numbers with uncertainty; and a documented leakage demonstration reproducing why some repos report AUC 0.95.
