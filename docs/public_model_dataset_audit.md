# Public Screening Model — Dataset Audit

**GlucoGuide · Model 2 (NHANES Public Screening)**
Prepared: 2026-11-26 | Version: `ps_v1`

---

> [!IMPORTANT]
> This document records the actual dataset used for Model 2 (the public screening model). It is completely independent of the existing Pima Indians benchmark used by Model 1. The two models share no data, features or artifacts.

## 1. Dataset Source

| Field | Value |
|---|---|
| **Name** | National Health and Nutrition Examination Survey (NHANES) |
| **Administering body** | US Centers for Disease Control and Prevention (CDC) / NCHS |
| **Official URL** | https://wwwn.cdc.gov/Nchs/Nhanes/ |
| **Survey cycle used** | **2017–2018 (Cycle J)** |
| **Access conditions** | Public domain — US Government data, no registration required |
| **License** | Public domain (US Government works) |
| **Download date** | 2026-11-26 |

## 2. Survey Cycle Selection

### Candidates Evaluated

| Cycle | Years | Status | Reason |
|---|---|---|---|
| H | 2015–2016 | **Excluded** | Not available at the new CDC data URL structure (`wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/`) — returns 404. |
| J | **2017–2018** | **Used** | Available and complete. All component files successfully downloaded. |
| P | 2021–2023 | **Excluded** | 15-month survey gap, updated sampling design, pandemic-era protocol changes. CDC advises caution about cross-cycle comparisons. Retained separately for future out-of-time evaluation. |

### Why Not Pool Multiple Cycles

NHANES multi-cycle pooling requires:
1. Harmonised survey weights computed across pooled cycles
2. Verification that variable definitions, questionnaire wording and examination protocols match across cycles
3. Adjustment for the 2021–2023 protocol gap

Since cycle H is unavailable and cycle P has design discontinuities, only cycle J is used. This is **documented explicitly** — not a shortcut. A single-cycle analysis avoids specious precision from improperly pooled data.

## 3. Downloaded Files

| File | Contents | Rows | Key Variables |
|---|---|---|---|
| `DEMO_J.xpt` | Demographics | 9,254 | SEQN, RIDAGEYR, RIAGENDR |
| `BMX_J.xpt` | Body measures | — | BMXBMI, BMXWT, BMXHT, BMXWAIST |
| `BPX_J.xpt` | Blood pressure | — | BPXSY1–3, BPXDI1–3 |
| `DIQ_J.xpt` | Diabetes questionnaire | — | DIQ010 |
| `GHB_J.xpt` | Glycohaemoglobin | — | LBXGH (HbA1c) |
| `PAQ_J.xpt` | Physical activity | — | PAQ605, PAQ610, PAQ650, PAQ655, PAD680 |
| `SMQ_J.xpt` | Smoking | — | SMQ020, SMQ040 |

> [!NOTE]
> **Actual NHANES variable names differ from the task specification.** Blood pressure variables are `BPXSY1/BPXDI1` through `BPXSY3/BPXDI3` (not `BPXOSY`/`BPXODI`). Physical activity variables are `PAQ605`/`PAQ610`/`PAQ650`/`PAQ655` (not `PAD790Q`/`PAD810Q`). The implemented code uses the correct CDC-documented variable names.

## 4. Participant Eligibility

| Filter | Count |
|---|---|
| Raw NHANES 2017–2018 total | **9,254** |
| Adults aged 21 and above | **5,493** |
| With defined outcome (see §5) | **4,900** |
| — Positive (survey-defined diabetes) | **1,066 (21.8%)** |
| — Negative (no diabetes, confirmed) | **3,834 (78.2%)** |
| Excluded: age < 21 | 1,761 |
| Excluded: borderline/refused/gestational/both missing | 593 |

**Age top-coding note:** `RIDAGEYR` is capped at 80 in all NHANES public releases. All 370 participants with age coded as 80 may actually be older; this is a known limitation documented in the model card.

## 5. Target Definition

The binary outcome `diabetes_label` is defined as follows:

```
Positive (1):
  DIQ010 == 1 (ever told have diabetes, excluding gestational)
  OR LBXGH >= 6.5 (HbA1c ≥ 6.5%)

Negative (0):
  DIQ010 == 2 (no) AND LBXGH < 6.5

Excluded (not modelled):
  DIQ010 == 3 (borderline/pre-diabetic)
  DIQ010 in {7, 9} (refused / don't know)
  Gestational-only cases (DIQ010 == 1 AND DIQ175D present but DIQ010 not 1)
  Both DIQ010 and LBXGH missing
```

> [!CAUTION]
> This is a **survey-defined phenotype** combining self-report and a single HbA1c measurement. It is **not** equivalent to a clinical diagnosis of diabetes. The model estimates a research-defined screening outcome, not clinical diabetes status.

### Leakage Prevention

`LBXGH` (HbA1c) and `DIQ010` (diabetes diagnosis) are used **exclusively** for target construction. They are **never** passed as model features. This was verified programmatically:
- `test_no_forbidden_lab_features` in `tests/test_public_screening.py` asserts their absence from the feature schema
- `src/public_config.py` defines the feature list independently from the training script

## 6. Feature Schema

| Feature | Variable Source | Type | Missing % | Allowed Range |
|---|---|---|---|---|
| `age_years` | RIDAGEYR | Continuous | 0.0% | 21–80 |
| `sex_male` | RIAGENDR (recoded) | Binary | 0.0% | 0, 1 |
| `bmi` | BMXBMI | Continuous | 2.49% | 10–70 |
| `waist_cm` | BMXWAIST | Continuous | 6.31% | 40–200 |
| `sys_bp` | Mean(BPXSY1, BPXSY2, BPXSY3) | Continuous | 6.96% | 60–220 |
| `dia_bp` | Mean(BPXDI1, BPXDI2, BPXDI3) | Continuous | 7.37% | 20–130 |
| `mod_days_per_week` | PAQ605/PAQ610 | Continuous (0–7) | 0.12% | 0–7 |
| `vig_days_per_week` | PAQ650/PAQ655 | Continuous (0–7) | 0.02% | 0–7 |
| `sedentary_min_day` | PAD680 | Continuous | 0.78% | 0–1440 |
| `smoked_100` | SMQ020 (recoded) | Binary | 0.0% | 0, 1 |
| `current_smoker` | SMQ040 (recoded) | Binary | 0.0% | 0, 1 |

### Why These Features

Each feature was retained because:
- It is **physically obtainable** without laboratory equipment or clinical visit
- It has **valid NHANES documentation** with a codebook-confirmed definition
- It has **sufficient coverage** (< 10% missing before imputation)
- It does **not derive from the diagnostic target** (no leakage)
- It has **prior evidence** supporting association with diabetes risk in literature

Features that were investigated but **not included**:
- `LBXGH`, `LBXGLU` — laboratory values, used for target only
- `DIQ010` — target variable
- `BMXHT`, `BMXWT` — subsumed by BMI; adding separately risks multicollinearity
- `SLQ050` (trouble sleeping) — high missingness in this cycle

## 7. Data Quality and Missingness

Blood pressure missing values arise from participants who either did not complete the examination or had no valid readings. Missingness was handled by **median imputation within the training fold only** — the imputer was fit on training rows and applied to validation and test rows, preventing leakage of imputation statistics.

```
Missing before imputation (eligible 4,900 participants):
  bmi              2.5%
  waist_cm         6.3%
  sys_bp           7.0%
  dia_bp           7.4%
  sedentary_min_day  0.8%
  mod_days_per_week  0.1%
  vig_days_per_week  0.0%
  age_years          0.0%
  sex_male           0.0%
  smoked_100         0.0%
  current_smoker     0.0%
```

## 8. Data Split

| Split | Rows | Positive | Prevalence |
|---|---|---|---|
| Train (68%) | 3,332 | 725 | 21.8% |
| Validation (12%) | 588 | 128 | 21.8% |
| Test (20%) | 980 | 213 | 21.7% |

Stratified by `diabetes_label`. Split fixed with `random_state=42`.

## 9. Survey Weights

NHANES uses a complex multi-stage cluster sampling design. Survey weights (`WTMEC2YR`, `WTINT2YR`) represent the number of US civilians each respondent represents.

**Decision:** Weights were **not applied during model training.** Applying weights requires:
- Multi-cycle weight combination formulas (not applicable for a single cycle)
- Weighted cross-validation (non-standard sklearn)
- Weighted calibration

The unweighted model provides internally consistent results. The model card explicitly notes this limitation. Future work should evaluate weighted training for prevalence estimation use cases.

## 10. Processed Dataset Fingerprint

```
SHA-256: 24959158b157c2cbd830e9e42824d3b8d5c40a977e4cc4d693f30c6ca44c022b
File:    data/nhanes_processed.csv
Rows:    4,900
Columns: 13 (11 features + SEQN + diabetes_label)
```

The fingerprint is verified at training time and recorded in `models/public_screening/model_card.json`.

## 11. Model Selection Results

Four classifiers were compared via 5-fold stratified cross-validation on the training set only:

| Model | Val ROC-AUC | Val F1 | Val Recall | Selected |
|---|---|---|---|---|
| **Logistic Regression** | **0.791** | **0.498** | **0.690** | **✅** |
| Gradient Boosting | 0.785 | 0.495 | 0.700 | |
| Random Forest | 0.769 | 0.479 | 0.672 | |
| HistGradientBoosting | 0.782 | 0.492 | 0.681 | |

Selection rule: highest validation ROC-AUC with recall ≥ 0.60 and precision ≥ 0.40.

**Test set results (held-out, not used for selection):**

| Metric | Value | 95% CI |
|---|---|---|
| ROC-AUC | 0.796 | [0.766, 0.828] |
| Recall (sensitivity) | 0.714 | — |
| Precision | 0.426 | — |
| F1 score | 0.533 | — |
| Accuracy | 0.729 | — |
| Brier score | 0.140 | — |
| Threshold | 0.26 | (validation-selected) |

## 12. Candidate Datasets Investigated

### NIH All of Us
- **Status: Access not pursued** — requires institutional agreement, researcher training, and registration with the All of Us Research Program. As of this implementation, raw individual-level data require approved institutional affiliation and DUA. This project uses publicly downloadable NHANES data instead.
- **URL:** https://www.researchallofus.org/

### NHANES (Selected)
- **Status: Used** — public domain, no registration required, complete documentation.

### ICMR-INDIAB
- **Status: Not used** — the NHRDR portal (`nhrdr.icmr.org.in/datasets/icmr-indiab`) indicates individual-level data are not shared through its standard query service. No freely downloadable dataset was found. This would require formal research collaboration with ICMR.

### BRFSS
- **Status: Not used in this release** — BRFSS contains self-reported diagnosed diabetes and self-reported measurements. Its target definition (self-reported diagnosis) is methodologically distinct from NHANES's HbA1c-confirmed target. Mixing the two targets would not be defensible. BRFSS is documented as a candidate for a separate future model focused on self-reported diagnosis patterns.

## 13. Known Limitations

1. **Single survey cycle** — 2017–2018 only; temporal generalisability is unknown
2. **US adult population** — NHANES represents US non-institutionalised civilians; not validated outside this population
3. **Survey-defined target** — HbA1c + self-report, not equivalent to clinical diagnosis
4. **Age top-coding** — participants aged ≥ 80 are indistinguishable
5. **Survey weights not applied** — model is not calibrated to represent national prevalence
6. **Physical activity self-report** — susceptible to recall bias; known to under-report
7. **Cross-sectional design** — no longitudinal follow-up; cannot infer causation
8. **No external validation** — model has not been evaluated on an independent dataset

## 14. Reproducibility

```bash
# Download NHANES components
python scripts/download_nhanes.py

# Build processed dataset (verify fingerprint)
python scripts/build_nhanes_dataset.py

# Train Model 2 (do not run unless retrain is intentional)
python scripts/train_public_model.py
```

> [!WARNING]
> Re-running `train_public_model.py` will **overwrite** existing model artifacts. The existing trained model (`models/public_screening/selected_model.joblib`) should not be retrained during normal development. This script is provided for reproducibility documentation only.

---

*This document was generated during the initial build of GlucoGuide. Update it whenever the dataset, features or training procedure change.*
