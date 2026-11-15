# Model card

Selected pipeline: **Logistic Regression**
Version: 4ea22108c507
Threshold: 0.4922 (selection feasible: True)

## Test result

| Metric | Result |
|---|---:|
| accuracy | 0.7142857142857143 |
| balanced_accuracy | 0.7118518518518518 |
| precision | 0.5757575757575758 |
| recall | 0.7037037037037037 |
| specificity | 0.72 |
| f1 | 0.6333333333333333 |
| roc_auc | 0.8103703703703704 |
| pr_auc | 0.66525050246563 |
| false_negative_rate | 0.2962962962962963 |
| brier | 0.18105209237351394 |
| tn | 72 |
| fp | 28 |
| fn | 16 |
| tp | 38 |

95% stratified bootstrap intervals are in reports/test_bootstrap_ci.csv. They condition on this split and exclude training or model-selection uncertainty. Prior repository reports explicitly explored thresholds on this nominal holdout as a leakage demonstration; current-release selection used training-only nested CV, but this historical test exposure means the metrics are descriptive, not independent confirmatory estimates.

## Intended use and limitations

Educational research prototype. Not a medical diagnosis or personal risk estimate.
The dataset has 768 historical records from a narrow population. Its outcome is not a prospective diagnosis; glucose feature timing is not sufficiently documented to claim future prediction. No independent external validation or clinical calibration was performed.
A threshold is an engineering operating point for this benchmark, not a clinical decision threshold.
