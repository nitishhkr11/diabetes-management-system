The five release pipelines in this folder were generated from data/diabetes.csv
using: python scripts/train.py

model_card.json records each artifact's SHA-256, schema, training dataset
fingerprint, model selection rule, package versions and evaluation evidence.
The application verifies hashes and the scikit-learn version before loading.
Never load model files from an untrusted source. Regenerate all files together
after changing the training workflow or pinned dependencies.
