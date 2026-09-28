"""Download the NMB-2017 dataset (real Indian data, CC0) and turn it into a CSV.

    .venv/bin/python scripts/fetch_nmb2017.py      # writes data/reference/nmb2017.csv

NMB-2017 is a nationwide Indian cross-sectional survey of adults at high risk of type 2 diabetes
(Nagarathna et al., Diabetes Res Clin Pract 2020, doi:10.1016/j.diabres.2020.108037). Its data are
published on Mendeley Data under CC0 1.0 (doi:10.17632/twp8xw6p25.1) as one 640-page PDF printed
from a spreadsheet: pages 1-160 hold PatientId..Waist, pages 161-320 hold Height..Hba1c for the
same rows in the same order. This script checks the PDF's SHA-256, reads both blocks with
`pdftotext -layout`, checks that every page pair has the same number of rows, and joins them.

It is a REFERENCE only: DiaCausal's engine never trains on it (it has no drug choice and no
follow-up HbA1c). scripts/compare_cohort.py uses it to check that the synthetic cohort looks like
real Indian adults with diabetes (age, BMI, HbA1c, sex).
"""

from __future__ import annotations

import csv
import hashlib
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "reference" / "nmb2017.csv"
URL = ("https://data.mendeley.com/public-files/datasets/twp8xw6p25/files/"
       "342bf1f4-2e29-46b2-aab5-c77a8f39cf3a/file_downloaded")
SHA256 = "470f01431dcd98eaab122cc5b21ebc9ea01951e959f2fd0bc6d9920a51a44e88"

STATES = sorted([
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jammu And Kashmir", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Orissa", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "Uttaranchal", "West Bengal", "Delhi",
    "Chandigarh", "Puducherry", "Pondicherry", "Andaman And Nicobar", "Dadra And Nagar Haveli",
    "Daman And Diu", "Lakshadweep"], key=len, reverse=True)
BLOCK1 = re.compile(r"^\s*(\d+)\s*([A-Z]{1,2})\s+(.+?)\s+(\d+)\s+(Male|Female)\s+(\d+(?:\.\d+)?)\s*$")
BLOCK2 = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+([A-Za-z]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"
                    r"\s+(\d+(?:\.\d+)?)\s*$")
COLUMNS = ["patient_id", "zone", "state", "district", "age", "gender", "waist_cm", "height_cm", "weight_kg",
           "diabetes_self_declared", "diabetes_father", "diabetes_mother", "moderate_activity",
           "vigorous_activity", "daily_physical", "hba1c"]


def parse(text: str) -> list[list[str]]:
    pages = text.split("\f")
    first = [[m for m in map(BLOCK1.match, p.splitlines()) if m] for p in pages]
    second = [[m for m in map(BLOCK2.match, p.splitlines()) if m] for p in pages]
    left = [rows for rows in first if rows]
    right = [rows for rows, other in zip(second, first) if rows and not other][: len(left)]
    if [len(r) for r in left] != [len(r) for r in right]:
        sys.exit("the two column blocks do not line up page by page; not writing a CSV")
    out = []
    for a, b in zip((m for page in left for m in page), (m for page in right for m in page)):
        pid, zone, place, age, sex, waist = a.groups()
        state = next((s for s in STATES if place.startswith(s)), None)
        if state is None:
            sys.exit(f"unknown state in row {pid}")
        out.append([pid, zone, state, place[len(state):].strip(), age, sex, waist, *b.groups()])
    return out


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "ObesityAnalysis.pdf"
        req = urllib.request.Request(URL, headers={"User-Agent": "DiaCausal-research/1.0 (+https://github.com/Rhian-Roy/DiaCausal-CDSS)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            pdf.write_bytes(r.read())
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != SHA256:
            sys.exit("the downloaded PDF is not the published version (SHA-256 differs)")
        text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                              check=True).stdout
    rows = parse(text)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
