"""List the plates whose printed English name is now the eBird name of a different species.

    python tools/misnamed.py            # markdown list, by folio
    python tools/misnamed.py --count

Only identified rows count (the open ones have no modern name to differ from).
Spelling is compared loosely: case, punctuation, grey/gray and parrakeet/parakeet.
Standard library only; reads the eBird taxonomy that validate.py caches.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS = OrderedDict([("havell", "Audubon, *The Birds of America*"), ("gould-europe", "Gould, *The Birds of Europe*"),
                     ("gould-australia", "Gould, *The Birds of Australia*"), ("gould-asia", "Gould, *The Birds of Asia*"),
                     ("gould-britain", "Gould, *The Birds of Great Britain*")])


def norm(s: str) -> str:
    s = s.lower().replace("grey", "gray").replace("parrakeet", "parakeet")
    return re.sub(r"[^a-z]", "", s)


def misnamed() -> list[dict]:
    with open(ROOT / ".cache" / "ebird-2025.csv", newline="", encoding="utf-8-sig") as f:
        names = {norm(r["COMMON_NAME"]): r["COMMON_NAME"] for r in csv.DictReader(f) if r["CATEGORY"] == "species"}
    out = []
    for book in BOOKS:
        plates: dict = OrderedDict()
        with open(ROOT / book / "species.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                plates.setdefault((r.get("volume", ""), r["plate"]), []).append(r)
        for (vol, plate), rows in plates.items():
            commons = {norm(r["common"]) for r in rows if r["common"]}
            for printed in dict.fromkeys(r["printed_name"].strip() for r in rows if r["printed_name"].strip()):
                if norm(printed) in names and commons and norm(printed) not in commons:
                    shows = [r for r in rows if r["printed_name"].strip() == printed and r["common"]] or \
                            [r for r in rows if r["common"]]
                    out.append({"book": book, "plate": f"{vol}.{plate}" if vol else plate, "printed": printed,
                                "shows": " + ".join(dict.fromkeys(r["common"] for r in shows))})
    return out


def main() -> None:
    rows = misnamed()
    if "--count" in sys.argv:
        print(len(rows))
        return
    for book, title in BOOKS.items():
        mine = [r for r in rows if r["book"] == book]
        if mine:
            print(f"**{title}**\n")
            for r in mine:
                print(f"- {r['plate']}: \"{r['printed']}\" → {r['shows']}")
            print()


if __name__ == "__main__":
    main()
