# Dataset provenance

- **Dataset:** Pima Indians Diabetes Database (768 rows; 8 predictors plus binary `Outcome`).
- **Local redistribution source:** [Plotly datasets mirror](https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv); source discussion and verification details are in `data/README_DATA.md`.
- **Population scope:** commonly described as adult women of Pima heritage aged 21 and older. It is not representative of all people, including the wider Indian population.
- **Raw-file SHA-256:** `698c203a14aa31941d2251175330c9199f3ccdb31597abbba2a3e35416257a72`.
- **Canonical-values SHA-256:** `00921e2c6a3f645b215270e6b481a1b3e6283f1db4ee498d0de9b5a9cd0b240b`.
- **Validation command:** `python -m src.data_validation data/diabetes.csv`.

The validator checks ordered columns, numeric values, row/class counts, missing cells, duplicates, known-zero counts and a canonical fingerprint. The training pipeline transforms only five specified measurement zero codes to missing and keeps `Pregnancies=0` as a valid value.

`Outcome` is binary. It does not label Type 1, Type 2 or gestational diabetes. Do not use this dataset to infer diabetes type or to claim that model scores are personal medical probabilities.
