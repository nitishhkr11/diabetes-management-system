# ML methodology and reproduction

## Verified baseline and audit

The saved baseline card/report matches the dashboard to floating-point precision. On the existing stratified 80:20 split (seed 42), Logistic Regression at 0.50 had accuracy 0.7078, precision 0.6000, recall 0.5000, F1 0.5455, ROC-AUC 0.8130, Brier 0.1754, and confusion counts TN=82, FP=18, FN=27, TP=27. Random Forest had the highest baseline held-out ROC-AUC (0.8160), but this did not select it: baseline selection was correctly based on training-only stratified CV (LR ROC-AUC 0.8434 versus RF 0.8209). The dashboard figures were not a selection criterion.

The baseline reports exposed a threshold synchronization defect: an OOF operating point at 0.40 and its separate test result were recorded, but the saved model card and API still used 0.50. Thus the baseline API behavior was the 0.50 result. The original code compared fixed defaults and did not search hyperparameters or SVM/boosting/class weights.

## Research protocol

Run python scripts/train.py. The unchanged Pima file is validated by schema and canonical value hash, then split once with a stratified 80:20 split and seed 42. In this training run, model and threshold choices use development data only; prior repository experiments have already examined this same nominal holdout, so it cannot be claimed as a pristine independent test.

Five families are compared: Logistic Regression, Gaussian Naive Bayes, Random Forest, RBF SVM, and Gradient Boosting. Each candidate uses a small predeclared grid. Class weighting (None/balanced) is included for Logistic Regression, Random Forest, and SVM. No resampling is performed: with only 268 positive rows overall, class-weighting tests the imbalance intervention without creating synthetic observations; resampling can be considered in a future nested-fold-only experiment.

Each candidate receives 5-fold outer stratified CV on the development split. For each outer fold, preprocessing and ROC-AUC hyperparameter search are fitted by 4-fold inner stratified CV using only that outer training partition. The outer held-out fold produces its probability predictions once. Model-family selection maximizes the aggregated nested OOF ROC-AUC; candidates within 0.005 are resolved by simplicity in this order: Logistic Regression, Gaussian Naive Bayes, Random Forest, SVM, Gradient Boosting. This yields a less biased comparison than reusing tuning folds, although choosing among five families still creates selection optimism. Prior files in `reports/experiments/` include explicit threshold tuning on the nominal test split as a leakage demonstration, as well as repeated baseline comparisons. Therefore the saved holdout metrics are descriptive and are not an independent confirmatory estimate.

The threshold rule is fixed in code before looking at new final-test results: among all nested OOF scores, choose the highest threshold achieving recall at least 0.65 and precision at least 0.50. If no threshold satisfies both, report infeasibility and use 0.50 as the release threshold; do not relax the constraints after observing the test. The objective is a benchmark engineering trade-off, not a clinical cutoff.

After selection, each model family is tuned on all development rows and saved as a complete preprocessing-plus-model pipeline. In the current training run, only the selected family is scored on the nominal holdout after choices are fixed. Reports include accuracy, balanced accuracy, precision, recall, specificity, F1, ROC-AUC, average precision (PR-AUC), false-negative rate, Brier score, and confusion counts. Calibration bins and a reliability plot are descriptive and unstable with a small sample. A future independent evaluation requires new, appropriately aligned data or a prospective study; the existing 768 records cannot restore holdout independence.

Uncertainty uses 2,000 stratified bootstrap resamples of the held-out cases, preserving the observed positive and negative sample counts. Percentile intervals are conditional on this one split and do not include training, threshold-selection, model-selection, or population-sampling uncertainty. They should not be read as clinical confidence intervals.

## Artifacts and outputs

models/model_card.json hashes every joblib artifact and records selected model, threshold, data fingerprint, package versions, protocol and final metrics. reports/research_experiment.json records seed, split, outer/inner folds, candidate grids, selection and threshold rules, full-development best parameters, and data hashes. Other generated outputs are:

- reports/nested_oof_metrics.csv
- reports/class_weight_ablation.csv (nested OOF comparison of none vs balanced)
- reports/threshold_table_nested_oof.csv
- reports/test_metrics.csv
- reports/test_bootstrap_ci.csv
- reports/calibration_test_bins.csv and reports/figures/calibration_test.png
- reports/baseline_vs_research.csv

Reproduce with Python 3.11 and pinned requirements.txt:

    .\.venv\Scripts\python.exe scripts\train.py

Use --outer-folds, --inner-folds or --bootstrap only for explicit sensitivity work; record those changes because they change the experiment.

## Data and clinical limits

data/diabetes.csv remains the original 768-row Pima benchmark (500 negatives, 268 positives). Known impossible zeros in Glucose, BloodPressure, SkinThickness, Insulin and BMI are converted to missing inside each pipeline; pregnancy count zero is valid. Median imputation and scaling are learned inside each training fold. The dataset documents a narrow historical population: Pima women aged 21+ near Phoenix. Its diabetes outcome includes a 2-hour glucose criterion while glucose is also a predictor; source documentation does not establish a prospective prediction horizon. Results cannot establish future onset, diagnosis, clinical utility, or transportability.

An additional-data review found NHANES and BRFSS are feasible complementary survey tasks but have different self-reported diagnosed-diabetes outcomes, populations, predictors and complex sampling designs. Neither is aligned for external validation of this Pima pipeline. Details and official sources are in docs/independent-dataset-assessment.md.

