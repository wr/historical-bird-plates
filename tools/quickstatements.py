"""Write a QuickStatements (V1) batch that creates one Wikidata item per plate.

    python3 tools/quickstatements.py gould-europe                 # every eligible plate
    python3 tools/quickstatements.py gould-europe --limit 5       # a test batch
    python3 tools/quickstatements.py gould-europe --plates 1,12,425

Each item: instance of (print type), part of the work with the plate's number
(and volume) as qualifiers, creator, title, BHL page ID where the folio is
scanned on BHL, and `depicts` for every species identified with confidence
high or judged, referenced to this dataset. A plate is eligible when one of
its identifications was checked against the engraved caption (Havell: when it
is identified at all). Plates Wikidata already has an item for (same work and
number, or same BHL page) are skipped, so a batch can be rerun safely.

Standard library only. Paste the output into https://quickstatements.toolforge.org/.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "historical-bird-plates quickstatements (+https://github.com/wr/historical-bird-plates)"}
SPARQL = "https://query.wikidata.org/sparql"
REPO = "https://github.com/wr/historical-bird-plates"

GOULD, AUDUBON = "Q313787", "Q182882"
LITHOGRAPH, ENGRAVING = "Q15123870", "Q11835431"
FOLIOS = {
    "gould-europe":    ("Q51448070", "The Birds of Europe", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "gould-australia": ("Q967304", "The Birds of Australia", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "gould-britain":   ("Q51404118", "The Birds of Great Britain", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "gould-asia":      ("Q51448002", "The Birds of Asia", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "havell":          ("Q377817", "The Birds of America", AUDUBON, ENGRAVING, "hand-coloured engraving and aquatint"),
}
ARTIST = {GOULD: "John Gould", AUDUBON: "John James Audubon"}


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sparql(query: str) -> list[dict]:
    url = SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.load(r)["results"]["bindings"]


def existing(work: str) -> tuple[set, set]:
    """(volume, number) pairs and BHL page ids Wikidata already has for the work."""
    rows = sparql(f"""SELECT ?n ?v ?bhl WHERE {{
      ?item p:P361 ?st . ?st ps:P361 wd:{work} .
      OPTIONAL {{ ?st pq:P1545 ?n }} OPTIONAL {{ ?st pq:P478 ?v }}
      OPTIONAL {{ ?item wdt:P687 ?bhl }} }}""")
    nums = {(r.get("v", {}).get("value", ""), r["n"]["value"]) for r in rows if "n" in r}
    pages = {r["bhl"]["value"] for r in rows if "bhl" in r}
    return nums, pages


def q(s: str) -> str:
    return '"' + s.replace('"', "'").strip() + '"'


def batch(folder: str, only: set | None, limit: int | None, check_existing: bool) -> tuple[list[str], int]:
    work, title, artist, kind, medium = FOLIOS[folder]
    plates = read(ROOT / folder / "plates.csv")
    species = read(ROOT / folder / "species.csv")
    # A folio numbered per volume (Australia, Britain, Asia) keys its plates by
    # volume and number; species.csv then leads with `volume` too.
    per_volume = bool(species) and "volume" in species[0]
    key = lambda r: (r.get("volume", "") if per_volume else "", r["plate"])
    by_plate: dict = {}
    for s in species:
        by_plate.setdefault(key(s), []).append(s)
    nums, pages = existing(work) if check_existing else (set(), set())
    readme = f"{REPO}/tree/main/{folder}"
    lines, skipped, seen = [], 0, set()
    for p in plates:
        k = key(p)
        if k in seen:
            continue
        seen.add(k)
        vol, n = k
        if only and n not in only and f"{vol}.{n}" not in only:
            continue
        rows = by_plate.get(k, [])
        ids = [s for s in rows if s["scientific"]]
        eligible = any(s["caption_checked"] == "yes" for s in rows) if folder != "havell" else bool(ids)
        if not eligible:
            continue
        if k in nums or (p.get("bhl_page") and p["bhl_page"] in pages):
            skipped += 1
            continue
        printed = (p.get("caption_name") or p.get("list_name") or p.get("title") or "").strip()
        # The label drops a composite sheet's figure numbers: "1. House Sparrow. 2. Tree
        # Sparrow." is labelled "House Sparrow and Tree Sparrow"; the title keeps them.
        parts = [x.strip(" .") for x in re.split(r"\s*\b\d+\.\s+", printed) if x.strip(" .")]
        name = " and ".join(parts) if len(parts) > 1 else printed
        if not printed:
            printed = name = " / ".join(s["common"] for s in ids)
        where = f"plate {n}" + (f", volume {vol}," if vol else "")
        desc = f"{medium}, {where} of {ARTIST[artist]}'s {title}"
        lines += ["CREATE",
                  f"LAST\tLen\t{q(name)}",
                  f"LAST\tDen\t{q(desc)}",
                  f"LAST\tP31\t{kind}",
                  f"LAST\tP361\t{work}\tP1545\t{q(n)}" + (f"\tP478\t{q(vol)}" if vol else ""),
                  f"LAST\tP170\t{artist}",
                  f"LAST\tP1476\ten:{q(printed)}"]
        if p.get("bhl_page"):
            lines.append(f"LAST\tP687\t{q(p['bhl_page'])}")
        for qid in dict.fromkeys(s["wikidata"] for s in ids
                                 if s["wikidata"] and s["confidence"] in ("high", "judged")):
            lines.append(f"LAST\tP180\t{qid}\tS854\t{q(readme)}")
        if limit and lines.count("CREATE") >= limit:
            break
    return lines, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folio", choices=sorted(FOLIOS))
    ap.add_argument("--limit", type=int, help="at most this many items (a test batch)")
    ap.add_argument("--plates", help="only these plate numbers, comma-separated (VOL.N for per-volume folios)")
    ap.add_argument("--no-check", action="store_true", help="don't ask Wikidata which plates already have items")
    args = ap.parse_args()
    only = set(args.plates.split(",")) if args.plates else None
    lines, skipped = batch(args.folio, only, args.limit, not args.no_check)
    print("\n".join(lines))
    print(f"{lines.count('CREATE')} items, {skipped} skipped as already on Wikidata", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
