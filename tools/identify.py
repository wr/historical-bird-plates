"""Apply identification decisions to a book's species.csv.

    python tools/identify.py DECISIONS.csv            # apply, and log each row to <book>/sources/decisions.csv
    python tools/identify.py DECISIONS.csv --dry-run  # print what would change
    python tools/identify.py --audit-ids              # list rows whose ids differ from what the lookup rule gives

A decisions CSV has one row per figure, with the columns

    book, volume, plate, figure, scientific, form, confidence, caption_checked, reason, sources

and optionally printed_name and printed_latin (otherwise kept from the plate's
current rows) and birdnet_label (a label, or "none" for blank; otherwise as
below). `book` is a folder name (havell, gould-asia, ...); `volume` is
blank for books numbered straight through. All of a plate's rows are given
together and replace that plate's rows in species.csv, in place. A row with no
`scientific` leaves the plate open: confidence none, or medium/low with the
doubt in `reason`.

From `scientific` the tool fills the rest of the row. common, ebird_code and
taxonomy come from the eBird/Clements 2025 species of that name. The ids
(wikidata, gbif, avibase, birdnet_label) are copied from the dataset's other
rows for the same species, since those have been reviewed by hand. A species
new to the dataset gets them by rule:

  - wikidata: one item per species, the one Wikipedia uses. Candidates are
    species-rank items named `scientific`, carrying the eBird code, listing
    `scientific` as a taxon synonym, or labelled with the eBird English name;
    the last two only when their own epithet matches. The candidate with the
    most sitelinks wins.
  - gbif: that item's GBIF key (P846), followed to the accepted name when GBIF
    calls it a synonym; blank unless GBIF has it at species rank.
  - avibase: that item's Avibase ID (P2026), blank when it has none or several.
  - birdnet_label: BirdNET GLOBAL 6K V2.4's label with the same scientific
    name, else the one with the same English name; blank when BirdNET has no
    such class. BirdNET keeps some pre-split names, so check a new label.

Lookups are cached in .cache/ (never committed). Standard library only.
"""
from __future__ import annotations

import csv
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
TAXONOMY = "eBird/Clements 2025"
EBIRD_URL = "https://api.ebird.org/v2/ref/taxonomy/ebird?fmt=csv&version=2025"
BIRDNET_LABELS_URL = ("https://raw.githubusercontent.com/joeweiss/birdnetlib/main/src/birdnetlib/"
                      "models/analyzer/BirdNET_GLOBAL_6K_V2.4_Labels.txt")
SPARQL = "https://query.wikidata.org/sparql"
GBIF = "https://api.gbif.org/v1/species/"
UA = {"User-Agent": "historical-bird-plates identify (+https://github.com/wr/historical-bird-plates)"}

DECISION_COLUMNS = ["book", "volume", "plate", "figure", "scientific", "form", "confidence",
                    "caption_checked", "reason", "sources"]
LOG_COLUMNS = ["decided", "volume", "plate", "figure", "printed_name", "printed_latin", "scientific",
               "common", "form", "confidence", "caption_checked", "reason", "sources"]
KNOWN = ("wikidata", "gbif", "avibase", "birdnet_label")


# --- files -----------------------------------------------------------------

def read(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def fetch(name: str, url: str) -> Path:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        path.write_bytes(get(url))
    return path


def get(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def books() -> list[Path]:
    return sorted(p.parent for p in ROOT.glob("*/species.csv"))


# --- eBird and BirdNET -----------------------------------------------------

class Names:
    def __init__(self) -> None:
        _, rows = read(fetch("ebird-2025.csv", EBIRD_URL))
        self.species = {r["SCIENTIFIC_NAME"]: r for r in rows if r["CATEGORY"] == "species"}
        labels = fetch("BirdNET_GLOBAL_6K_V2.4_Labels.txt", BIRDNET_LABELS_URL).read_text(encoding="utf-8")
        self.labels = [l for l in labels.splitlines() if l]
        self.label_by_sci = {l.split("_", 1)[0]: l for l in self.labels}
        self.label_by_common = {l.split("_", 1)[1].lower(): l for l in self.labels}
        # What the dataset already calls each species in BirdNET (BirdNET keeps older names).
        seen: dict[str, Counter] = defaultdict(Counter)
        for book in books():
            for r in read(book / "species.csv")[1]:
                if r["scientific"] and not r["form"]:
                    seen[r["scientific"]][tuple(r[c] for c in KNOWN)] += 1
        self.known = {sci: dict(zip(KNOWN, c.most_common(1)[0][0])) for sci, c in seen.items()}

    def ebird(self, sci: str) -> dict:
        row = self.species.get(sci)
        if row is None:
            raise SystemExit(f"{sci!r} is not a species in eBird/Clements 2025")
        return row

    def birdnet(self, sci: str) -> str:
        if sci in self.label_by_sci:
            return self.label_by_sci[sci]
        return self.label_by_common.get(self.ebird(sci)["COMMON_NAME"].lower(), "")


# --- Wikidata and GBIF -----------------------------------------------------

def stem(epithet: str) -> str:
    """An epithet's first five letters, spelling variants evened (ae/oe/e, rh/r)."""
    e = epithet.lower().replace("ae", "e").replace("oe", "e").replace("rh", "r")
    return e[:5]


def epithet(name: str) -> str:
    return name.split()[-1] if name else ""


def sparql(query: str) -> list[dict]:
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    data = json.loads(get(SPARQL, body, {"Content-Type": "application/x-www-form-urlencoded",
                                         "Accept": "application/sparql-results+json"}))
    return [{k: v["value"] for k, v in b.items()} for b in data["results"]["bindings"]]


def lit(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


ITEM_TAIL = """
  ?item wdt:P105 wd:Q7432 ; wdt:P225 ?name ; wikibase:sitelinks ?links .
  OPTIONAL { ?item wdt:P846 ?gbif }
  OPTIONAL { ?item wdt:P2026 ?avibase }
}"""


class Ids:
    """Wikidata, GBIF and Avibase ids for eBird species, cached in .cache/ids.json."""

    def __init__(self, names: Names) -> None:
        self.names = names
        self.path = CACHE / "ids.json"
        self.cache: dict = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.gbif_path = CACHE / "gbif.json"
        self.gbif_cache: dict = json.loads(self.gbif_path.read_text()) if self.gbif_path.exists() else {}

    def save(self) -> None:
        CACHE.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self.cache, indent=0, sort_keys=True))
        self.gbif_path.write_text(json.dumps(self.gbif_cache, indent=0, sort_keys=True))

    def lookup(self, scis: list[str]) -> None:
        todo = [s for s in dict.fromkeys(scis) if s not in self.cache]
        for i in range(0, len(todo), 60):
            chunk = todo[i:i + 60]
            cands: dict[str, dict[str, dict]] = {s: {} for s in chunk}

            def add(rows: list[dict], guarded: bool) -> None:
                for r in rows:
                    sci = r["key"]
                    if guarded and stem(epithet(r["name"])) != stem(epithet(sci)):
                        continue
                    c = cands[sci].setdefault(r["item"].rsplit("/", 1)[-1],
                                              {"links": int(r["links"]), "gbif": set(), "avibase": set()})
                    if r.get("gbif"):
                        c["gbif"].add(r["gbif"])
                    if r.get("avibase"):
                        c["avibase"].add(r["avibase"])

            by_name = " ".join(f"({lit(s)} {lit(s)})" for s in chunk)
            add(sparql(f"SELECT ?key ?item ?name ?links ?gbif ?avibase WHERE {{ VALUES (?key ?sci) {{ {by_name} }}"
                       f" ?item wdt:P225 ?sci . {ITEM_TAIL}"), False)
            by_code = " ".join(f"({lit(s)} {lit(self.names.ebird(s)['SPECIES_CODE'])})" for s in chunk)
            add(sparql(f"SELECT ?key ?item ?name ?links ?gbif ?avibase WHERE {{ VALUES (?key ?code) {{ {by_code} }}"
                       f" ?item wdt:P3444 ?code . {ITEM_TAIL}"), False)
            add(sparql(f"SELECT ?key ?item ?name ?links ?gbif ?avibase WHERE {{ VALUES (?key ?sci) {{ {by_name} }}"
                       f" ?syn wdt:P225 ?sci . ?item wdt:P1420 ?syn . {ITEM_TAIL}"), True)
            labels = []
            for s in chunk:
                en = self.names.ebird(s)["COMMON_NAME"]
                for v in dict.fromkeys([en, en.lower(), en[:1] + en[1:].lower()]):
                    labels.append(f"({lit(s)} {lit(v)}@en)")
            add(sparql(f"SELECT ?key ?item ?name ?links ?gbif ?avibase WHERE {{ VALUES (?key ?label) "
                       f"{{ {' '.join(labels)} }} ?item rdfs:label ?label . {ITEM_TAIL}"), True)
            for s in chunk:
                if not cands[s]:
                    self.cache[s] = {"wikidata": "", "gbif": "", "avibase": ""}
                    continue
                qid, c = max(cands[s].items(), key=lambda kv: (kv[1]["links"], -int(kv[0][1:])))
                self.cache[s] = {"wikidata": qid,
                                 "gbif": sorted(c["gbif"], key=int)[0] if c["gbif"] else "",
                                 "avibase": next(iter(c["avibase"])) if len(c["avibase"]) == 1 else ""}
            self.save()
            print(f"  wikidata: {min(i + 60, len(todo))}/{len(todo)}", file=sys.stderr)

    @staticmethod
    def _accepted(key: str) -> str:
        try:
            r = json.loads(get(GBIF + key))
        except urllib.error.HTTPError:
            return ""
        if r.get("taxonomicStatus", "").endswith("SYNONYM") and r.get("acceptedKey"):
            acc = json.loads(get(GBIF + str(r["acceptedKey"])))
            return str(acc["key"]) if acc.get("rank") == "SPECIES" else ""
        return key if r.get("rank") == "SPECIES" and r.get("taxonomicStatus") in ("ACCEPTED", "DOUBTFUL") else ""

    def prefetch(self, scis: list[str]) -> None:
        """Look up every species' item, then its GBIF key, several at a time (GBIF answers slowly)."""
        self.lookup(scis)
        keys = sorted({self.cache[s]["gbif"] for s in scis if self.cache[s]["gbif"]} - set(self.gbif_cache))
        with ThreadPoolExecutor(max_workers=16) as pool:
            for n, (key, out) in enumerate(zip(keys, pool.map(self._accepted, keys)), start=1):
                self.gbif_cache[key] = out
                if n % 100 == 0:
                    self.save()
                    print(f"  gbif: {n}/{len(keys)}", file=sys.stderr)
        self.save()

    def gbif(self, key: str) -> str:
        """The key itself if GBIF accepts it as a species, its accepted species if a synonym, else blank."""
        if not key:
            return ""
        if key not in self.gbif_cache:
            self.gbif_cache[key] = self._accepted(key)
            self.save()
        return self.gbif_cache[key]

    def of(self, sci: str) -> dict:
        self.lookup([sci])
        c = self.cache[sci]
        return {"wikidata": c["wikidata"], "gbif": self.gbif(c["gbif"]), "avibase": c["avibase"]}


def fill(r: dict, names: Names, ids: Ids) -> dict:
    """The row with every column that follows from `scientific` filled (or cleared)."""
    r = dict(r)
    sci = r["scientific"]
    if not sci:
        for c in ("common", "ebird_code", "taxonomy", "wikidata", "gbif", "avibase", "birdnet_label", "form"):
            r[c] = ""
        return r
    e = names.ebird(sci)
    r.update(common=e["COMMON_NAME"], ebird_code=e["SPECIES_CODE"], taxonomy=TAXONOMY)
    r.update(names.known.get(sci) or {"birdnet_label": names.birdnet(sci), **ids.of(sci)})
    return r


# --- apply -----------------------------------------------------------------

def plate_key(r: dict) -> tuple[str, str]:
    return (r.get("volume", ""), r["plate"])


def check(d: dict, names: Names) -> None:
    where = f"{d['book']} {'.'.join(x for x in (d['volume'], d['plate']) if x)}"
    if d["scientific"] and d["confidence"] == "none":
        raise SystemExit(f"{where}: confidence none with a species")
    if not d["scientific"] and not d["reason"]:
        raise SystemExit(f"{where}: an open row needs a reason")
    if not d["scientific"] and d["form"]:
        raise SystemExit(f"{where}: a form needs a species")
    if d["scientific"]:
        names.ebird(d["scientific"])
    label = d.get("birdnet_label", "")
    if label and label != "none" and label not in names.labels:
        raise SystemExit(f"{where}: {label!r} is not a BirdNET V2.4 label")


def apply(decisions_path: Path, dry_run: bool) -> int:
    _, decisions = read(decisions_path)
    missing = [c for c in DECISION_COLUMNS if decisions and c not in decisions[0]]
    if missing:
        raise SystemExit(f"{decisions_path}: missing columns {missing}")
    names = Names()
    for d in decisions:
        check(d, names)
    ids = Ids(names)
    ids.prefetch([d["scientific"] for d in decisions
                  if d["scientific"] and d["scientific"] not in names.known])
    by_book: dict[str, list[dict]] = defaultdict(list)
    for d in decisions:
        by_book[d["book"]].append(d)
    today = datetime.date.today().isoformat()
    changed = 0
    for book, ds in by_book.items():
        folder = ROOT / book
        columns, rows = read(folder / "species.csv")
        per_volume = "volume" in columns
        key = (lambda r: (r["volume"], r["plate"])) if per_volume else (lambda r: ("", r["plate"]))
        plates: dict[tuple, list[dict]] = defaultdict(list)
        for d in ds:
            plates[key(d)].append(d)
        unknown = set(plates) - {key(r) for r in rows}
        if unknown:
            raise SystemExit(f"{book}: plates not in species.csv: {sorted(unknown)}")
        out: list[dict] = []
        log: list[dict] = []
        done: set = set()
        for r in rows:
            k = key(r)
            if k not in plates:
                out.append(r)
                continue
            if k in done:
                continue
            done.add(k)
            old = [x for x in rows if key(x) == k]
            new_rows = []
            for d in plates[k]:
                base = next((x for x in old if x["figure"] == d["figure"]), old[0])
                new = {c: base.get(c, "") for c in columns}
                for c in ("figure", "scientific", "form", "confidence", "caption_checked", "reason", "sources"):
                    new[c] = d[c]
                for c in ("printed_name", "printed_latin"):
                    if d.get(c):
                        new[c] = d[c]
                new = fill(new, names, ids)
                new["form"] = d["form"]
                label = d.get("birdnet_label", "")
                if label:
                    new["birdnet_label"] = "" if label == "none" else label
                new_rows.append(new)
                log.append({"decided": today, **{c: new.get(c, "") for c in LOG_COLUMNS if c != "decided"}})
            out.extend(new_rows)
            if old != new_rows:
                changed += 1
                if dry_run:
                    where = f"{book} {'.'.join(x for x in k if x)}"
                    for x in old:
                        print(f"- {where}: {x['scientific'] or '—'} [{x['confidence']}] {x['reason'][:90]}")
                    for x in new_rows:
                        print(f"+ {where}: {x['scientific'] or '—'} ({x['common']}) [{x['confidence']}] "
                              f"{x['reason'][:90]}")
        if not dry_run:
            write(folder / "species.csv", columns, out)
            logp = folder / "sources" / "decisions.csv"
            logp.parent.mkdir(exist_ok=True)
            prior = read(logp)[1] if logp.exists() else []
            write(logp, LOG_COLUMNS, prior + log)
    print(f"{changed} plates {'would change' if dry_run else 'changed'}")
    return 0


def audit() -> int:
    """Compare every identified row's ids with what the lookup rule would give a new species."""
    names = Names()
    ids = Ids(names)
    tables = {b: read(b / "species.csv")[1] for b in books()}
    ids.prefetch([r["scientific"] for rows in tables.values() for r in rows if r["scientific"]])
    diffs = 0
    for book, rows in tables.items():
        for r in rows:
            if not r["scientific"]:
                continue
            rule = {"birdnet_label": names.birdnet(r["scientific"]), **ids.of(r["scientific"])}
            for c in KNOWN:
                if rule[c] != r[c]:
                    diffs += 1
                    print(f"{book.name} {'.'.join(x for x in plate_key(r) if x)} {r['scientific']}: "
                          f"{c} {r[c]!r}, rule {rule[c]!r}")
    print(f"{diffs} differences")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--audit-ids" in args:
        return audit()
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    return apply(Path(paths[0]), "--dry-run" in args)


if __name__ == "__main__":
    sys.exit(main())
