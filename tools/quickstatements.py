"""Write a QuickStatements (V1) batch that creates one Wikidata item per plate.

    python3 tools/quickstatements.py gould-europe                 # every eligible plate
    python3 tools/quickstatements.py gould-europe --limit 5       # a test batch
    python3 tools/quickstatements.py gould-europe --plates 1,12,425
    python3 tools/quickstatements.py gould-asia --plates IV.59    # VOL.N for per-volume folios
    python3 tools/quickstatements.py havell --chunk 80 -o havell  # havell-1.qs, havell-2.qs, ...

Each item: instance of (print type), part of the work with the plate's number
(and volume) as qualifiers, creators and printer from the plate's credit line
(credits.csv), each referenced to the scan, title, BHL page ID where the folio is
scanned on BHL, and `depicts` for every species identified with confidence
high or judged, referenced to this dataset. A plate is eligible when it is
identified and that identification was checked against the engraved caption
(Havell: when it is identified at all). The Supplement to The Birds of
Australia is its own work on Wikidata, so its plates are part of that.

Plates Wikidata already has are skipped: same work and number, or same BHL
page. An item that is part of the work, has no plate number and has the
plate's name gets the plate's statements instead of a new item being made.
The check reads Wikidata's search index and API, not the query service, which
can lag by hours; wait a few minutes after a batch ends before rerunning.

Wikidata lets an account make about 90 edits a minute, and QuickStatements'
background runner goes faster, so the excess fails. Split a batch with
--chunk 80 and run the files one after another.

Standard library only. Paste the output into https://quickstatements.toolforge.org/.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "historical-bird-plates quickstatements (+https://github.com/wr/historical-bird-plates)"}
API = "https://www.wikidata.org/w/api.php"
REPO = "https://github.com/wr/historical-bird-plates"

GOULD, AUDUBON = "Q313787", "Q182882"
LITHOGRAPH, ENGRAVING = "Q15123870", "Q11835431"
LIST_ARTICLE = "Q13406463"
DRAFTSPERSON, LITHOGRAPHER, ENGRAVER, COLORIST = "Q15296811", "Q16947657", "Q329439", "Q1111648"
# credits.csv role -> the item that qualifies `creator` (P3831, object of statement has role).
# "retouched" has none: Wikidata's retoucher (Q33383789) is a photographic trade, so a
# retoucher is a creator with no role rather than a wrong one. "printed" is `printed by`.
ROLE_ITEM = {"drew": DRAFTSPERSON, "lithographed": LITHOGRAPHER, "engraved": ENGRAVER, "coloured": COLORIST}
FOLIOS = {
    "gould-europe":    ("Q51448070", "The Birds of Europe", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "gould-australia": ("Q967304", "The Birds of Australia", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "gould-britain":   ("Q51404118", "The Birds of Great Britain", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "gould-asia":      ("Q51448002", "The Birds of Asia", GOULD, LITHOGRAPH, "hand-coloured lithograph"),
    "havell":          ("Q377817", "The Birds of America", AUDUBON, ENGRAVING, "hand-coloured engraving and aquatint"),
}
# A "volume" that is really a separate publication: (folio, volume) -> (work, how the description names it).
SEPARATE = {("gould-australia", "Supp"): ("Q51382318", "the Supplement to John Gould's The Birds of Australia")}
ARTIST = {GOULD: "John Gould", AUDUBON: "John James Audubon"}
ROMAN = dict(I=1, V=5, X=10, L=50)


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def api(**params) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.load(r)


def volume_key(v: str) -> str:
    """"III", "iii" and "3" compare equal."""
    v = v.strip().upper()
    if v and set(v) <= set(ROMAN):
        total = 0
        for a, b in zip(v, v[1:] + " "):
            total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
        return str(total)
    return v


def fold(s: str) -> str:
    return " ".join(s.split()).casefold()


def existing(work: str, kind: str, artist: str, volumes: bool) -> tuple[set, set, dict]:
    """What Wikidata already has for the work: (volume, number) pairs, BHL page ids,
    and items with no plate number, by label. Only a print of the plate itself (same
    print type and artist, in no collection) counts as unnumbered; a museum's
    impression is a different thing."""
    # Pages sorted by relevance shift under an index that is still updating, so an
    # item can come twice and another not at all; creation order holds still.
    qids, offset, total = [], 0, 0
    while offset is not None:
        d = api(action="query", list="search", srsearch=f"haswbstatement:P361={work}", srnamespace=0,
                srlimit=500, sroffset=offset, srprop="", srsort="create_timestamp_asc", srinfo="totalhits")
        qids += [r["title"] for r in d["query"]["search"]]
        total = d["query"]["searchinfo"]["totalhits"]
        offset = d.get("continue", {}).get("sroffset")
    qids = list(dict.fromkeys(qids))
    if len(qids) != total:
        sys.exit(f"search for part of {work} gave {len(qids)} distinct items of {total}; try again in a minute")
    value = lambda snak: snak.get("datavalue", {}).get("value")
    nums, pages, unnumbered = set(), set(), collections.defaultdict(list)
    for i in range(0, len(qids), 50):
        for qid, e in api(action="wbgetentities", ids="|".join(qids[i:i + 50]),
                          props="claims|labels", languages="en")["entities"].items():
            claims = e.get("claims", {})
            if any((value(s["mainsnak"]) or {}).get("id") == LIST_ARTICLE for s in claims.get("P31", [])):
                continue
            pages |= {value(s["mainsnak"]) for s in claims.get("P687", []) if value(s["mainsnak"])}
            numbered = False
            for s in claims.get("P361", []):
                if (value(s["mainsnak"]) or {}).get("id") != work:
                    continue
                qual = s.get("qualifiers", {})
                vol = next((value(x) for x in qual.get("P478", []) if value(x)), "")
                for x in qual.get("P1545", []):
                    if value(x):
                        nums.add((volume_key(vol) if volumes else "", value(x)))
                        numbered = True
            ids = lambda p: {(value(s["mainsnak"]) or {}).get("id") for s in claims.get(p, [])}
            if (not numbered and "en" in e.get("labels", {}) and kind in ids("P31")
                    and artist in ids("P170") and not claims.get("P195")):
                unnumbered[fold(e["labels"]["en"]["value"])].append(qid)
    return nums, pages, unnumbered


def q(s: str) -> str:
    return '"' + s.replace('"', "'").strip() + '"'


def clean(s: str) -> str:
    return " ".join(s.split())


def artist_qids() -> dict[str, str]:
    """artists.csv name -> Wikidata item, for the names that have one."""
    return {r["name"]: r["wikidata"] for r in read(ROOT / "artists.csv") if r["wikidata"]}


def credited(folder: str, per_volume: bool) -> dict[tuple[str, str], list[dict]]:
    """credits.csv rows by (volume, plate); volume blank for a folio numbered straight through."""
    by: dict[tuple[str, str], list[dict]] = {}
    for c in read(ROOT / folder / "credits.csv"):
        by.setdefault((c["volume"] if per_volume else "", c["plate"]), []).append(c)
    return by


def creator_lines(subject: str, plate_credits: list[dict], qids: dict[str, str], url: str, imprint: str) -> list[str]:
    """`creator` with its roles for each artist the credit line names, and `printed by` for
    its printer; each referenced to the plate's scan, quoting the credit line."""
    ref = f"\tS854\t{q(url)}\tS1683\ten:{q(imprint)}"
    roles: dict[str, list[str]] = {}
    for c in plate_credits:
        roles.setdefault(c["name"], []).append(c["role"])
    lines = []
    for name, rs in roles.items():
        qid = qids.get(name)
        if not qid:
            continue
        if any(r != "printed" for r in rs):
            quals = "".join(f"\tP3831\t{ROLE_ITEM[r]}" for r in rs if r in ROLE_ITEM)
            lines.append(f"{subject}\tP170\t{qid}{quals}{ref}")
        if "printed" in rs:
            lines.append(f"{subject}\tP872\t{qid}{ref}")
    return lines


def listing(parts: list[str], names: set = frozenset()) -> str:
    """"A, B and C". A last part with an "and" in it is one bird if it is a printed
    name ("Black and White Kingfisher"); otherwise it already joins two
    ("Blackburnian and Mourning Warbler") and is left alone."""
    parts = [re.sub(r"^and\s+", "", p.strip(" .,")) for p in parts if p.strip(" .,")]
    if len(parts) < 2 or (" and " in parts[-1] and fold(parts[-1]) not in names):
        return ", ".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def label(printed: str, figures: int, names: set = frozenset()) -> str:
    """The item's label, from the printed name. A composite sheet's figures are joined
    as a list: "1. House Sparrow. 2. Tree Sparrow." is "House Sparrow and Tree Sparrow".
    Figure notes such as "(whole figure)" are left to the title."""
    printed = re.sub(r"\s*\([^)]*\)", "", printed).strip() or printed
    parts = re.split(r"\s*\b\d+\.\s+", printed)
    if len([p for p in parts if p.strip(" .,")]) < 2 and " / " in printed:
        parts = printed.split(" / ")
    if (len([p for p in parts if p.strip(" .,")]) < 2 and (figures > 1 or printed.count(",") > 1)
            and not re.search(r",\s*or\b", printed)):
        parts = printed.split(",")
    name = listing(parts, names)
    return re.sub(r"(?<=\s)(And|Or)(?=\s)", lambda m: m.group(1).lower(), name)


def batch(folder: str, only: set | None, limit: int | None, check_existing: bool) -> tuple[list[list[str]], int, int]:
    """One block of commands per plate; and how many plates were skipped or adopted."""
    work, title, artist, kind, medium = FOLIOS[folder]
    plates = read(ROOT / folder / "plates.csv")
    species = read(ROOT / folder / "species.csv")
    # A folio numbered per volume (Australia, Britain, Asia) keys its plates by
    # volume and number; species.csv then leads with `volume` too.
    per_volume = bool(species) and "volume" in species[0]
    creds, qids = credited(folder, per_volume), artist_qids()
    key = lambda r: (r.get("volume", "") if per_volume else "", r["plate"])
    by_plate: dict = {}
    for s in species:
        by_plate.setdefault(key(s), []).append(s)
    sheets = collections.defaultdict(list)
    for p in plates:
        if p.get("bhl_page"):
            sheets[p["bhl_page"]].append(key(p))
    works = {work} | {w for (f, _), (w, _) in SEPARATE.items() if f == folder}
    have = {w: existing(w, kind, artist, per_volume and w == work) if check_existing else (set(), set(), {})
            for w in works}
    readme = f"{REPO}/tree/main/{folder}"
    blocks, skipped, adopted, seen = [], 0, 0, set()
    for p in plates:
        k = key(p)
        if k in seen:
            continue
        seen.add(k)
        vol, n = k
        tag = f"{vol}.{n}" if vol else n
        if only and tag not in only:
            continue
        rows = by_plate.get(k, [])
        ids = [s for s in rows if s["scientific"]]
        if folder == "havell":
            eligible = bool(ids)
        else:
            eligible = any(s["caption_checked"] == "yes" and s["scientific"] for s in rows)
        if not eligible:
            continue
        on, where = work, f"plate {n}" + (f", volume {vol}," if vol else "")
        of = f"{ARTIST[artist]}'s {title}"
        if (folder, vol) in SEPARATE:
            on, of = SEPARATE[(folder, vol)]
            where = f"plate {n}"
        nums, pages, unnumbered = have[on]
        if (volume_key(vol) if on == work else "", n) in nums or (p.get("bhl_page") and p["bhl_page"] in pages):
            skipped += 1
            continue
        if vol and on == work and ("", n) in nums:
            print(f"plate {tag}: Wikidata has a plate {n} with no volume; skipped, check it by hand", file=sys.stderr)
            skipped += 1
            continue
        printed, lang = clean(p.get("caption_name") or p.get("list_name") or p.get("title") or ""), "en"
        if re.fullmatch(r"\(.*\)", printed):   # "(no English name printed)": the title is the Latin
            printed, lang = clean(p.get("list_latin") or p.get("caption_latin") or "").strip(" ."), "la"
        names = {fold(s["printed_name"]) for s in rows if s.get("printed_name")}
        name = label(printed, len(rows), names) if printed else " / ".join(s["common"] for s in ids)
        desc = f"{medium}, {where} of {of}"
        others = [o for o in sheets.get(p.get("bhl_page", ""), []) if o != k] if p.get("bhl_page") else []
        if others:
            # Two plate numbers printed on one sheet: each item is named for its own bird.
            own = [clean(s["printed_name"]) for s in rows if s.get("printed_name")]
            name = listing(list(dict.fromkeys(own)), names) or name
            desc += " (printed on one sheet with plate " + ", ".join(
                f"{o[1]}, volume {o[0]}" if o[0] else o[1] for o in others) + ")"
        part = f"\t{on}\tP1545\t{q(n)}" + (f"\tP478\t{q(vol)}" if vol and on == work else "")
        found = unnumbered.pop(fold(name), [])
        if len(found) > 1:
            print(f"plate {tag}: {', '.join(found)} all have its name and no plate number; skipped, check by hand",
                  file=sys.stderr)
            skipped += 1
            continue
        target = found[0] if found else None
        if target:
            # The plate is already on Wikidata without its number: add to that item.
            adopted += 1
            print(f"plate {tag}: adding its statements to {target}, which has no plate number", file=sys.stderr)
            block = [f"{target}\tP361{part}"]
            subject = target
        else:
            block = ["CREATE",
                     f"LAST\tLen\t{q(name)}",
                     f"LAST\tDen\t{q(desc)}",
                     f"LAST\tP31\t{kind}",
                     f"LAST\tP361{part}"]
            subject = "LAST"
        url = p.get("page_url") or p.get("image_url") or ""
        if p.get("imprint") and url:
            block += creator_lines(subject, creds.get(k, []), qids, url, p["imprint"])
        if printed:
            block.append(f"{subject}\tP1476\t{lang}:{q(printed)}")
        if p.get("bhl_page"):
            block.append(f"{subject}\tP687\t{q(p['bhl_page'])}")
        for qid in dict.fromkeys(s["wikidata"] for s in ids
                                 if s["wikidata"] and s["confidence"] in ("high", "judged")):
            block.append(f"{subject}\tP180\t{qid}\tS854\t{q(readme)}")
        blocks.append(block)
        if limit and len(blocks) >= limit:
            break
    return blocks, skipped, adopted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folio", choices=sorted(FOLIOS))
    ap.add_argument("--limit", type=int, help="at most this many items (a test batch)")
    ap.add_argument("--plates", help="only these plates, comma-separated: N, or VOL.N for per-volume folios")
    ap.add_argument("--no-check", action="store_true", help="don't ask Wikidata which plates already have items")
    ap.add_argument("--chunk", type=int, help="split into files of this many items (needs -o)")
    ap.add_argument("-o", "--out", help="with --chunk: write OUT-1.qs, OUT-2.qs, ...")
    args = ap.parse_args()
    if bool(args.chunk) != bool(args.out):
        ap.error("--chunk and --out go together")
    only = set(args.plates.split(",")) if args.plates else None
    blocks, skipped, adopted = batch(args.folio, only, args.limit, not args.no_check)
    if args.chunk:
        for i in range(0, len(blocks), args.chunk):
            path = Path(f"{args.out}-{i // args.chunk + 1}.qs")
            path.write_text("\n".join(line for b in blocks[i:i + args.chunk] for line in b) + "\n", encoding="utf-8")
            print(f"{path}: {len(blocks[i:i + args.chunk])} items", file=sys.stderr)
    else:
        print("\n".join(line for b in blocks for line in b))
    created = len(blocks) - adopted
    print(f"{created} new items, {adopted} existing items given their plate, "
          f"{skipped} skipped as already on Wikidata", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
