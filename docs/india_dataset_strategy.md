# India Dataset Strategy & Governance (ICMR-INDIAB)

**Project:** GlucoGuide  
**Intended Population:** Indian adults aged 20 years and above (men and women, rural and urban, across Indian states and union territories)  
**Current Data Acquisition Status:** `NOT REQUESTED`  
**External Validation Status:** `External validation has not yet been completed.`

---

## 1. Primary Dataset: ICMR-INDIAB National Diabetes Study

| Property | Details |
|---|---|
| **Full Name** | Indian Council of Medical Research–India Diabetes (ICMR-INDIAB) National Study |
| **Official Repository** | https://nhrdr.icmr.org.in/datasets/icmr-indiab |
| **Main Research Publication** | Anjana RM et al., *Lancet Diabetes & Endocrinology* 2023 — https://pubmed.ncbi.nlm.nih.gov/37301218/ |
| **Sample Size (Published)** | ~113,043 participants |
| **Age Eligibility** | Adults aged **20 years and above** (do not extrapolate to 18–19-year-olds) |
| **Geographic Scope** | 31 Indian states and union territories, rural and urban strata |
| **Survey Period** | 2008–2020 (phased multistage stratified survey) |
| **Sampling Design** | Stratified multistage cluster sampling (state, urban/rural strata, primary sampling units / clusters, households, survey weights) |
| **Diagnostic Criteria** | Documented WHO criteria (fasting plasma glucose ≥ 126 mg/dL and/or 2-h post-load glucose ≥ 200 mg/dL, or self-reported physician-diagnosed diabetes on medication, per study protocol) |

---

## 2. Data Access & Restrictions

- **Portal Limitation:** The official NHRDR portal (`nhrdr.icmr.org.in/datasets/icmr-indiab`) explicitly states that individual-level raw data are **not** available through its ordinary public query service; only aggregate query outcomes are provided.
- **Authorised Access Path:** Individual-level data require a formal data-sharing request, institutional approvals, ethics/governance review, and an executed Data Use / Data Sharing Agreement (DUA) mediated through ICMR / the study investigators.
- **Remote vs. Local Analysis:** Depending on the executed DUA, analysis may be restricted to an approved secure environment or remote enclave rather than local download.
- **Strict Prohibition:**
  - Never substitute a public Kaggle or non-Indian dataset and label it as ICMR-INDIAB.
  - Never train a production or published India model on synthetic fixtures or public sample files.
  - Never commit participant-level records to Git.

---

## 3. Data Acquisition Lifecycle Statuses

The project enforces an explicit state machine in `src/india_config.py` and `data/private/indiab/manifest.json`:

1. `NOT REQUESTED` *(Current status)*
2. `REQUEST SUBMITTED`
3. `ACCESS APPROVED`
4. `DATA RECEIVED`
5. `DATA VERIFIED` *(requires passing `scripts/audit_indiab_dataset.py`)*
6. `MODEL TRAINED` *(requires passing `scripts/train_india_model.py` release gates)*

The inference module (`src/india_predict.py`) and API (`/api/v1/india-screening/*`) will **refuse** to serve predictions unless the status is `MODEL TRAINED` and all artifact hashes and release gates pass.

---

## 4. Local Directory Structure

```text
data/
  private/
    indiab/
      raw/          # Excluded from Git — place authorised raw files here
      processed/    # Excluded from Git — cleaned participant-level data
      manifest.json # Tracked in Git — metadata only, zero participant records
  reports/          # Machine-readable & Markdown audit reports
  samples/          # Small synthetic/schema fixtures for unit tests only
```

---

## 5. Target Definition & Leakage Prevention

- **Target:** Binary diabetes status (`diabetes_label`: 1 = diabetes, 0 = no diabetes) constructed strictly from the ICMR-INDIAB WHO diagnostic criteria (documented fasting/2-h glucose thresholds and/or confirmed prior diagnosis/treatment as defined in the authorised codebook). Prediabetes is kept separate and not conflated with diabetes.
- **Leakage Guard:** Fasting glucose, 2-hour post-load glucose, random glucose, HbA1c, and self-reported diabetes diagnosis/medication variables used to construct the outcome **must never** be included in the non-laboratory screening feature set.

---

## 6. External Validation Investigation (LASI)

- **Candidate:** Longitudinal Ageing Study in India (LASI)
- **Assessment:** LASI focuses on older adults (aged 45+ and their spouses), uses different biomarker/dried-blood-spot protocols (e.g., HbA1c rather than OGTT), and has a distinct sampling frame compared to ICMR-INDIAB (adults aged 20+, WHO OGTT/FBG criteria).
- **Decision:** Do **not** automatically combine LASI and ICMR-INDIAB. Any future external validation on LASI must first harmonise age eligibility (45+), predictor definitions/units, and target definitions.
- **Current Status:** **External validation has not yet been completed.**
