"""Print the open rows (confidence medium, low or none) as a markdown table for the README.

    python tools/gaps.py

Standard library only.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS = {"havell": "Audubon, *America*", "gould-europe": "Gould, *Europe*", "gould-australia": "Gould, *Australia*",
         "gould-asia": "Gould, *Asia*", "gould-britain": "Gould, *Great Britain*"}
STATUS = {"none": "not identified", "low": "low", "medium": "leaning"}


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def main() -> None:
    print("| Book | Plate | Printed name | Leaning to | Status | What would settle it |")
    print("|---|---|---|---|---|---|")
    for book, title in BOOKS.items():
        links = {}
        for p in read(ROOT / book / "plates.csv"):
            links[(p.get("volume", "") if "volume" in read(ROOT / book / "species.csv")[0] else "", p["plate"])] = \
                p.get("page_url") or p.get("image_url") or ""
        for r in read(ROOT / book / "species.csv"):
            if r["confidence"] not in STATUS:
                continue
            key = (r.get("volume", ""), r["plate"])
            label = ".".join(x for x in key if x)
            url = links.get(key, "")
            plate = f"[{label}]({url})" if url else label
            print(f"| {title} | {plate} | {cell(r['printed_name'])} | {cell(r['common']) or '–'} | "
                  f"{STATUS[r['confidence']]} | {cell(r['reason'])} |")


if __name__ == "__main__":
    main()
