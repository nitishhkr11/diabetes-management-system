"""
Download NHANES public-use data files for GlucoGuide public screening model.

Cycles: 2015-2016 (H) and 2017-2018 (J)
These are the most recent consecutive pre-pandemic cycles.
The 2021-2023 cycle is excluded from pooled training due to CDC's
documented 15-month gap, updated sampling design, and pandemic-era
measurement protocol differences.

Usage:
    python scripts/download_nhanes.py [--cycles H J] [--out data/nhanes]

NHANES Public Data License: Public domain (US Government CDC data).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# XPT files needed for public screening model construction
# Format: (component, cycle_suffix, url_cycle_path, description)
NHANES_FILES = [
    # Demographics: age, sex, survey weights, PSU/strata
    ("DEMO", "H", "2015-2016", "Demographics 2015-2016"),
    ("DEMO", "J", "2017-2018", "Demographics 2017-2018"),
    # Body Measures: height, weight, BMI, waist circumference
    ("BMX",  "H", "2015-2016", "Body Measures 2015-2016"),
    ("BMX",  "J", "2017-2018", "Body Measures 2017-2018"),
    # Blood Pressure (oscillometric readings)
    ("BPX",  "H", "2015-2016", "Blood Pressure 2015-2016"),
    ("BPX",  "J", "2017-2018", "Blood Pressure 2017-2018"),
    # Diabetes questionnaire (DIQ010 = ever told have diabetes)
    ("DIQ",  "H", "2015-2016", "Diabetes Questionnaire 2015-2016"),
    ("DIQ",  "J", "2017-2018", "Diabetes Questionnaire 2017-2018"),
    # Glycohemoglobin (HbA1c) — target construction only, not a feature
    ("GHB",  "H", "2015-2016", "Glycohemoglobin 2015-2016"),
    ("GHB",  "J", "2017-2018", "Glycohemoglobin 2017-2018"),
    # Physical Activity questionnaire
    ("PAQ",  "H", "2015-2016", "Physical Activity 2015-2016"),
    ("PAQ",  "J", "2017-2018", "Physical Activity 2017-2018"),
    # Smoking and tobacco use
    ("SMQ",  "H", "2015-2016", "Smoking 2015-2016"),
    ("SMQ",  "J", "2017-2018", "Smoking 2017-2018"),
]

BASE_URL = "https://wwwn.cdc.gov/Nchs/Nhanes"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            headers = {"User-Agent": "GlucoGuide/1.0 (research; nhanes@cdc.gov)"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
            dest.write_bytes(data)
            return True
        except urllib.error.URLError as e:
            if attempt == retries - 1:
                print(f"  ERROR: {e}", file=sys.stderr)
                return False
            print(f"  Retry {attempt + 1}/{retries}...", file=sys.stderr)
            time.sleep(2 ** attempt)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NHANES XPT files")
    parser.add_argument("--cycles", nargs="+", default=["H", "J"], choices=["H", "J"],
                        help="NHANES cycles to download")
    parser.add_argument("--out", default=str(ROOT / "data" / "nhanes"),
                        help="Output directory")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if file exists")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    missing = []

    for component, cycle_suffix, cycle_path, description in NHANES_FILES:
        if cycle_suffix not in args.cycles:
            continue
        filename = f"{component}_{cycle_suffix}.XPT"
        url = f"{BASE_URL}/{cycle_path}/{filename}"
        dest = out_dir / filename

        if dest.exists() and not args.force:
            size = dest.stat().st_size
            sha = file_sha256(dest)
            print(f"  OK (cached) {filename:25s}  {size:>10,} bytes  sha256={sha[:16]}...")
            manifest.append({"file": filename, "cycle": cycle_path, "description": description,
                              "url": url, "size": size, "sha256": sha, "downloaded": False})
        else:
            print(f"  Downloading {filename:25s}  from {url}")
            ok = download_file(url, dest)
            if ok:
                size = dest.stat().st_size
                sha = file_sha256(dest)
                print(f"    -> {size:,} bytes  sha256={sha[:16]}...")
                manifest.append({"file": filename, "cycle": cycle_path, "description": description,
                                  "url": url, "size": size, "sha256": sha, "downloaded": True})
            else:
                missing.append(filename)
                print(f"    -> FAILED", file=sys.stderr)

    # Write manifest
    import json
    manifest_path = out_dir / "download_manifest.json"
    manifest_data = {
        "download_date": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "source": "NHANES CDC Public Data",
        "source_url": "https://wwwn.cdc.gov/Nchs/Nhanes/",
        "license": "Public domain (US Government CDC data)",
        "cycles": args.cycles,
        "files": manifest,
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2))
    print(f"\nManifest written: {manifest_path}")

    if missing:
        print(f"\nWARNING: {len(missing)} file(s) failed to download: {missing}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nAll {len(manifest)} files ready in {out_dir}")


if __name__ == "__main__":
    main()
