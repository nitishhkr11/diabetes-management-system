# Data card

## Source and identity

The checked-in file is the Pima Indians Diabetes Database, a public teaching/research benchmark historically associated with the National Institute of Diabetes and Digestive and Kidney Diseases and the UCI repository. The local CSV was obtained from the Plotly public mirror: <https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv>. This mirror is a redistribution, not the original data owner. Provenance notes and cross-copy hashes are in `data/README_DATA.md`.

Expected schema: 768 rows, eight numeric features and `Outcome`; class counts are 500 negative and 268 positive. The canonical values fingerprint is `00921e2c6a3f645b215270e6b481a1b3e6283f1db4ee498d0de9b5a9cd0b240b`. The repository validator prints the current raw file SHA-256 and checks the canonical fingerprint before training.

## Missingness and population

Zero is treated as a missing-value code for Glucose, BloodPressure, SkinThickness, Insulin and BMI. Zero pregnancies remains valid. Median imputation is fit only on training rows inside the saved pipeline. The source represents women of Pima heritage aged 21 and older in the Phoenix, Arizona area; it is small and historical. The measurement timing and label definition mean this should not be described as future disease prediction.

## Intended and prohibited use

Use only to demonstrate a reproducible educational ML workflow. Do not use for diagnosis, screening, treatment, care decisions, or generalization to other populations. No fairness or external validation study was conducted. The data documentation does not state a clear redistribution license; cite the source and do not imply ownership.
