"""Print the README's "By the numbers" table from the tables.

    python tools/stats.py

Standard library only.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = ["havell", "gould-europe", "gould-australia", "gould-asia", "gould-britain"]


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def row(book: str) -> str:
    folder = ROOT / book
    plates = read(folder / "plates.csv")
    species = read(folder / "species.csv")
    key = lambda r: (r.get("volume", ""), r["plate"])
    identified = [r for r in species if r["scientific"]]
    plates_identified = len({key(r) for r in identified})
    checked = len({key(r) for r in species if r["caption_checked"] == "yes"})
    counts = " / ".join(str(sum(1 for r in species if r["confidence"] == c))
                        for c in ("high", "judged", "medium", "low", "none"))
    n = len(identified)
    birdnet = sum(1 for r in identified if r["birdnet_label"])
    wikidata = sum(1 for r in identified if r["wikidata"])
    ku = folder / "ku-disagreements.csv"
    return (f"| `{book}` | {len({key(r) for r in plates})} | {plates_identified} | "
            f"{checked if book != 'havell' else '–'} | {len({r['scientific'] for r in identified})} | {counts} | "
            f"{birdnet} / {n} | {wikidata} / {n} | {len(read(ku)) if ku.exists() else '–'} |")


def main() -> None:
    print("| Folio | Plates | Plates identified | Caption-checked | Species | "
          "Rows: `high` / `judged` / `medium` / `low` / `none` | BirdNET-labelled | Wikidata-linked | "
          "Kansas disagreements |")
    print("|---|---:|---:|---:|---:|---|---:|---:|---:|")
    for book in ORDER:
        print(row(book))


if __name__ == "__main__":
    main()
