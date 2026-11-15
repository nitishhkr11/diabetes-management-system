# The dataset: Pima Indians Diabetes Database

`data/diabetes.csv` is **not a random "diabetes.csv"**. Many different files carry that name. This project
only trains on a file that passes every check in `src/data_validation.py`.

## What it is
| Item | Value (checked against the file) |
|---|---|
| Rows / columns | 768 / 9 (8 features + `Outcome`) |
| Classes | 500 with `Outcome = 0`, 268 with `Outcome = 1` (34.9 % positive) |
| People | Women aged 21 or more, of Pima heritage, living near Phoenix, Arizona, USA |
| Label | `1` = diabetes according to WHO criteria (2-hour post-load plasma glucose of at least 200 mg/dL at any survey examination, or found during routine care) |
| Original owners | National Institute of Diabetes and Digestive and Kidney Diseases (NIDDK) |
| Donor / date | Vincent Sigillito, Applied Physics Laboratory, Johns Hopkins University, received 9 May 1990 |

Source of this description: the original UCI documentation file `pima-indians-diabetes.names`. The UCI path
for that file returned HTTP 404 when we looked on 2026-10-01, so we read the identical text from the
`jbrownlee/Datasets` copy on GitHub.

## Columns
| Column | Meaning | Zero allowed? |
|---|---|---|
| Pregnancies | number of times pregnant | yes (111 rows) |
| Glucose | plasma glucose 2 h into an oral glucose tolerance test (mg/dL) | **no - 0 means "not measured"** (5 rows) |
| BloodPressure | diastolic blood pressure (mm Hg) | **no** (35 rows) |
| SkinThickness | triceps skin-fold thickness (mm) | **no** (227 rows) |
| Insulin | 2-hour serum insulin (mu U/ml) | **no** (374 rows) |
| BMI | weight (kg) / height (m)^2 | **no** (11 rows) |
| DiabetesPedigreeFunction | family-history score computed in the original study | no zeros present |
| Age | years | no zeros present |
| Outcome | class label | - |

The five "no" columns hold zeros that are physiologically impossible, so they are **missing-value codes**.
The official summary table in the UCI documentation (for example Insulin mean 79.8) was computed
*including* those zeros; our file reproduces every printed mean and standard deviation, which confirms the zeros
are stored as ordinary numbers. Only 392 of the 768 rows have all five measurements.

## Verified copies
Three independent public GitHub copies were downloaded on 2026-10-01. After re-writing the values in one fixed
format they give the **same** "canonical" SHA-256, so they contain identical values:

| Copy | Raw file SHA-256 | Why the raw hash differs |
|---|---|---|
| `plotly/datasets` -> `diabetes.csv` (the copy saved here) | `698c203a14aa31941d2251175330c9199f3ccdb31597abbba2a3e35416257a72` | Windows line endings (CRLF) |
| `npradaschnor/Pima-Indians-Diabetes-Dataset` -> `diabetes.csv` | `b78029447fae2743b3218bb2b76ef0d04afe8d7e55ce2faf4d1ec82d8f8ae8ac` | Unix line endings |
| `jbrownlee/Datasets` -> `pima-indians-diabetes.data.csv` | `6bfe5d0f379d17a0e0819b996407e3c09bf80febd4287f2ed212190dfff154af` | no header row |

**Canonical SHA-256** (hash of the values, independent of line endings, header and `31` versus `31.0`):
`00921e2c6a3f645b215270e6b481a1b3e6283f1db4ee498d0de9b5a9cd0b240b`

Download URLs used by `scripts/download_data.py`:
- https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv
- https://raw.githubusercontent.com/npradaschnor/Pima-Indians-Diabetes-Dataset/master/diabetes.csv
- https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv

Kaggle and OpenML also host copies. We did not verify those in this project, so **check any copy yourself**:

```
python -m src.data_validation path/to/your/diabetes.csv
```

## Look-alike files seen in public repositories (do not use)
| Where we saw it | What is different | Why it is dangerous |
|---|---|---|
| `pranavppramod/Diabetes-Prediction-System`, `Vivekrathod01/Diabetes_prediction_system` | 768 x 9, but 652 cells replaced: each missing value holds ONE constant per class (Glucose 107 / 140, BloodPressure 70 / 74.5, SkinThickness 27 / 32, Insulin 102.5 / 169.5, BMI 30.1 / 34.3 for class 0 / class 1) | the label is written into the features (label leakage); Random Forest reaches ROC-AUC about 0.94 |
| `Nox5556/Diabetes-Prediction-using-Random-forest` | 2,768 x 10 (extra `Id`), classes 1,816 / 952; the first 768 rows are the genuine rows and 1,981 of the other 2,000 are exact copies of them | a random split puts copies of training rows into the test set; Random Forest "accuracy" of about 98 % |
| `CarlousF/pima-indian-diabetes` | same people, different column names (`num_preg`, `glucose_conc`, ...) and an extra column | breaks code that expects the standard names |
| `Pritikaa2006/diabetes-risk-prediction` | 253,680 x 22 survey-style data stored as `diabetes.csv` | an entirely different dataset |

Commits inspected are listed in the project report. The validator rejects all of these automatically.

## Known limitations of the data
- Small (768 rows), collected decades ago, one population. Results do not transfer to other groups.
- The label is defined from the same kind of measurement (2-hour post-load plasma glucose of at least 200 mg/dL) that appears as the `Glucose` feature, so a very strong `Glucose` effect is expected. The documentation does not say how the timing of the features relates to the label, so do not read the model as "predicting the future".
- Two features (`Insulin`, `SkinThickness`) are missing in 49 % and 30 % of rows.

## How to cite
- Dataset: UCI Machine Learning Repository, "Pima Indians Diabetes Database" (original owners: National Institute of Diabetes and Digestive and Kidney Diseases; donor: Vincent Sigillito, Johns Hopkins University Applied Physics Laboratory, 1990).
- Original study: Smith, J. W., Everhart, J. E., Dickson, W. C., Knowler, W. C., & Johannes, R. S. (1988). Using the ADAP learning algorithm to forecast the onset of diabetes mellitus. *Proceedings of the Symposium on Computer Applications and Medical Care*, 261-265. IEEE Computer Society Press.

The documentation does not state a licence. The file is widely redistributed for teaching and research; always cite the source and say so if you modify the data.
