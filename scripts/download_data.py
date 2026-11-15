"""Download the Pima Indians Diabetes CSV from a public mirror and verify it.

    python scripts/download_data.py

The CSV is saved as data/diabetes.csv. The script tries three public GitHub
mirrors of the original UCI data in turn and only keeps a file that passes
every check in src/data_validation.py. If your network blocks GitHub, download
the file by hand (see data/README_DATA.md) and run:
    python -m src.data_validation data/diabetes.csv
"""
import io
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config as C  # noqa: E402
from src.data_validation import sha256_file, validate_dataframe  # noqa: E402

MIRRORS = [  # (label, url, file has a header row?)
    ("plotly/datasets",
     "https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv", True),
    ("npradaschnor/Pima-Indians-Diabetes-Dataset",
     "https://raw.githubusercontent.com/npradaschnor/Pima-Indians-Diabetes-Dataset/master/diabetes.csv", True),
    ("jbrownlee/Datasets (no header row)",
     "https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv", False),
]


def main() -> int:
    if C.DATA_PATH.exists():
        print(f"{C.DATA_PATH} already exists - checking it instead of downloading.")
        rep = validate_dataframe(pd.read_csv(C.DATA_PATH))
        rep.raw_sha256 = sha256_file(C.DATA_PATH)
        print(rep.to_text())
        return 0 if rep.ok else 1

    C.DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    for label, url, has_header in MIRRORS:
        print(f"Trying {label} ...")
        try:
            raw = urllib.request.urlopen(url, timeout=30).read()
            df = pd.read_csv(io.BytesIO(raw), header=0 if has_header else None)
        except Exception as exc:  # network error, 404, bad file ...
            print(f"  could not use it: {exc}")
            continue
        if not has_header:
            df.columns = C.FEATURES + [C.TARGET]
        rep = validate_dataframe(df)
        if not rep.ok:
            print("  downloaded, but it FAILED validation:\n" + rep.to_text())
            continue
        if has_header:
            C.DATA_PATH.write_bytes(raw)            # keep the file exactly as published
        else:
            df.to_csv(C.DATA_PATH, index=False)
        rep.raw_sha256 = sha256_file(C.DATA_PATH)
        print(f"  OK - saved {C.DATA_PATH}\n" + rep.to_text())
        return 0
    print("No mirror worked. Download the file by hand - see data/README_DATA.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
