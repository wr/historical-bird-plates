"""Validate every folio in this repo.

    python tools/validate.py            # all folios
    python tools/validate.py --offline  # structure only; skip the name checks

Checks, per folio folder (any folder holding a species.csv):
  - both tables have exactly the columns datapackage.json declares
  - plates.csv has one row per plate (volume and plate, where numbered per volume) and leaf; every species row names a plate in it
  - confidence, form and caption_checked hold only the declared values
  - a row with a species has an eBird code and a taxonomy; a row without one has a reason
  - every ebird_code is a species or group code in the eBird taxonomy named in `taxonomy`
  - every birdnet_label is, verbatim, a line of BirdNET GLOBAL 6K V2.4's labels
  - wikidata / gbif / avibase ids are well formed

The eBird taxonomy and the BirdNET labels are downloaded into .cache/, never
committed: the labels file is CC BY-NC-SA, and this repo only names species.
Standard library only.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
EBIRD_URL = "https://api.ebird.org/v2/ref/taxonomy/ebird?fmt=csv&version={version}"
BIRDNET_LABELS_URL = ("https://raw.githubusercontent.com/joeweiss/birdnetlib/main/src/birdnetlib/"
                      "models/analyzer/BirdNET_GLOBAL_6K_V2.4_Labels.txt")
UA = {"User-Agent": "historical-bird-plates validate (+https://github.com/wr/historical-bird-plates)"}

CONFIDENCE = {"high", "judged", "medium", "low", "none"}
FORM = {"", "subspecies", "variant", "pre-split"}
CAPTION_CHECKED = {"", "yes", "no"}
ID_PATTERNS = {"wikidata": r"Q\d+", "gbif": r"\d+", "avibase": r"[0-9A-F]{8}(?:[0-9A-F]{8})?"}


def fetch(name: str, url: str) -> Path:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            path.write_bytes(r.read())
    return path


def read(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def schema_fields() -> dict[str, list[str]]:
    pkg = json.loads((ROOT / "datapackage.json").read_text())
    return {r["path"]: [f["name"] for f in r["schema"]["fields"]] for r in pkg["resources"]}


def validate(offline: bool) -> list[str]:
    errors: list[str] = []
    fields = schema_fields()
    ebird: dict[str, set] = {}
    labels: set = set()
    if not offline:
        labels = set(fetch("BirdNET_GLOBAL_6K_V2.4_Labels.txt", BIRDNET_LABELS_URL)
                     .read_text(encoding="utf-8").splitlines())
    folders = sorted(p.parent for p in ROOT.glob("*/species.csv"))
    for folder in folders:
        name = folder.name
        for table in ("plates.csv", "species.csv"):
            rel = f"{name}/{table}"
            if rel not in fields:
                errors.append(f"{rel}: not declared in datapackage.json")
                continue
            cols, _ = read(folder / table)
            if cols != fields[rel]:
                errors.append(f"{rel}: columns {cols} != datapackage.json {fields[rel]}")
        _, plates = read(folder / "plates.csv")
        species_cols, species = read(folder / "species.csv")
        # A folio numbered per volume keys a plate by its volume and number.
        per_volume = "volume" in species_cols
        keys = [(r.get("volume", ""), r["plate"], r.get("leaf", "")) for r in plates]
        if len(keys) != len(set(keys)):
            errors.append(f"{name}/plates.csv: a plate and leaf appear twice")
        plate_ids = {(r["volume"] if per_volume else "", r["plate"]) for r in plates}
        for i, r in enumerate(species, start=2):
            plate = (r["volume"], r["plate"]) if per_volume else ("", r["plate"])
            where = f"{name}/species.csv:{i} (plate {'.'.join(x for x in plate if x)})"
            if plate not in plate_ids:
                errors.append(f"{where}: plate not in plates.csv")
            for col, allowed in (("confidence", CONFIDENCE), ("form", FORM), ("caption_checked", CAPTION_CHECKED)):
                if r[col] not in allowed:
                    errors.append(f"{where}: {col} {r[col]!r} not one of {sorted(allowed)}")
            if r["scientific"]:
                if not r["ebird_code"] or not r["taxonomy"]:
                    errors.append(f"{where}: a species needs an ebird_code and a taxonomy")
            elif not r["reason"]:
                errors.append(f"{where}: a row with no species needs a reason")
            for col, pat in ID_PATTERNS.items():
                if r[col] and not re.fullmatch(pat, r[col]):
                    errors.append(f"{where}: malformed {col} {r[col]!r}")
            if offline:
                continue
            if r["birdnet_label"] and r["birdnet_label"] not in labels:
                errors.append(f"{where}: birdnet_label {r['birdnet_label']!r} is not in BirdNET V2.4's labels")
            if r["ebird_code"]:
                m = re.fullmatch(r"eBird/Clements (\d{4})", r["taxonomy"])
                if not m:
                    errors.append(f"{where}: taxonomy {r['taxonomy']!r} is not 'eBird/Clements YYYY'")
                    continue
                version = m.group(1)
                if version not in ebird:
                    _, rows = read(fetch(f"ebird-{version}.csv", EBIRD_URL.format(version=version)))
                    ebird[version] = {x["SPECIES_CODE"]: x["SCIENTIFIC_NAME"] for x in rows}
                sci = ebird[version].get(r["ebird_code"])
                if sci is None:
                    errors.append(f"{where}: ebird_code {r['ebird_code']!r} is not in eBird {version}")
                elif sci != r["scientific"]:
                    errors.append(f"{where}: ebird_code {r['ebird_code']} is {sci} in eBird {version}, "
                                  f"not {r['scientific']}")
        print(f"{name}: {len(plates)} plate rows, {sum(1 for r in species if r['scientific'])} identifications")
    if not folders:
        errors.append("no folio folders found")
    return errors


def main() -> int:
    errors = validate("--offline" in sys.argv)
    for e in errors:
        print("  x", e)
    print("ok" if not errors else f"{len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
