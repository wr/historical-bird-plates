"""Build the data the plate explorer renders: site/src/data/plates.json.

    python3 tools/site_data.py           # write site/src/data/plates.json
    python3 tools/site_data.py --stats   # print the counts, write nothing

One record per folio, plate, species and artist, joined from every folio's plates.csv, species.csv,
credits.csv and sources/imprints.csv, the root artists.csv, the eBird 2025 taxonomy (downloaded once
into .cache/, as validate.py does) and the image sizes and colours in site/src/data/images.json
(written by site_images.py). Standard library only.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import credits  # noqa: E402
import misnamed  # noqa: E402
import validate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "src" / "data"
REPO = "https://github.com/wr/historical-bird-plates"
OPEN = {"medium", "low", "none"}
GOULD = {"author": "John Gould", "medium": "Hand-coloured lithograph",
         "credit": "Smithsonian Libraries and Archives, via the Biodiversity Heritage Library."}
FOLIOS = [
    {"id": "havell", "author": "John James Audubon", "title": "The Birds of America", "years": "1827–38",
     "start": 1827, "end": 1838, "cite": "Audubon, The Birds of America", "short": "Audubon",
     "medium": "Hand-coloured engraving and aquatint", "release": "havell-v2", "by_volume": False,
     "intro": "435 plates from Audubon's watercolours, numbered 1–435 on the plates themselves. W. H. Lizars "
              "engraved the first in Edinburgh; Robert Havell Jr. engraved, printed and hand-coloured the rest in "
              "London, his father printing and colouring with him on the early ones.",
     "credit": "Courtesy of the John James Audubon Center at Mill Grove, Montgomery County Audubon Collection, "
               "and Zebra Publishing."},
    {**GOULD, "id": "gould-europe", "title": "The Birds of Europe", "years": "1832–37", "start": 1832, "end": 1837,
     "cite": "Gould, The Birds of Europe", "short": "Europe", "release": "gould-europe-v2", "by_volume": False,
     "intro": "Five volumes and 449 plates, numbered by Gould's General List. Drawn and lithographed by John and "
              "Elizabeth Gould and Edward Lear, hand-coloured and published in parts in London."},
    {**GOULD, "id": "gould-australia", "title": "The Birds of Australia", "years": "1840–69", "start": 1840,
     "end": 1869, "cite": "Gould, The Birds of Australia", "short": "Australia", "release": "gould-australia-v1",
     "by_volume": True,
     "intro": "Seven volumes (1840–48) and a Supplement (1851–69), 681 plates. Drawn by John and Elizabeth Gould "
              "and H. C. Richter, lithographed, hand-coloured and published in parts in London."},
    {**GOULD, "id": "gould-asia", "title": "The Birds of Asia", "years": "1850–83", "start": 1850, "end": 1883,
     "cite": "Gould, The Birds of Asia", "short": "Asia", "release": "gould-asia-v1", "by_volume": True,
     "intro": "Seven volumes and 530 plates, drawn and lithographed by John Gould with H. C. Richter, Joseph Wolf "
              "and William Hart. Gould died in 1881 and R. B. Sharpe finished the work."},
    {**GOULD, "id": "gould-britain", "title": "The Birds of Great Britain", "years": "1862–73", "start": 1862,
     "end": 1873, "cite": "Gould, The Birds of Great Britain", "short": "Britain", "release": "gould-britain-v2",
     "by_volume": True,
     "intro": "Five volumes and 367 plates, drawn by John Gould with H. C. Richter, W. Hart and J. Wolf, "
              "lithographed, hand-coloured and published in parts in London."},
]
# Scans credited to someone other than the folio's source, by (folio, plate key). The havell-v2
# release notes credit plate 165, cut from the University of Pittsburgh's copy, separately.
CREDITS = {("havell", "165"): "University of Pittsburgh, via Wikimedia Commons."}


def slugify(name: str) -> str:
    """'Leach's Storm-Petrel' -> 'leachs-storm-petrel'."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower().replace("'", "")).strip("-")


def plate_key(folio: dict, volume: str, plate: str) -> tuple[str, str]:
    """The plate's key as misnamed.py writes it ('I.1', '121') and its URL slug ('i-1', '121')."""
    if folio["by_volume"]:
        return f"{volume}.{plate}", f"{volume.lower()}-{plate}"
    return plate, plate


def volume_title(volume: str) -> str:
    return "Supplement" if volume == "Supp" else f"Volume {volume}"


def plate_label(folio: dict, volume: str, plate: str) -> str:
    """'Plate 121', 'Volume I, plate 1', 'Supplement, plate 18'."""
    return f"{volume_title(volume)}, plate {plate}" if folio["by_volume"] else f"Plate {plate}"


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plate_rows() -> Iterator[tuple[dict, dict, str, str]]:
    """Every plate as (folio, plates.csv row, key, slug), in folio order."""
    for folio in FOLIOS:
        for row in read(ROOT / folio["id"] / "plates.csv"):
            yield (folio, row, *plate_key(folio, row.get("volume", ""), row["plate"]))


def taxonomy() -> dict[str, dict]:
    """The eBird/Clements 2025 taxonomy, by species code."""
    path = validate.fetch("ebird-2025.csv", validate.EBIRD_URL.format(version="2025"))
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["SPECIES_CODE"]: r for r in csv.DictReader(f)}


def plate_credits(folio: dict) -> dict[tuple[str, str], list[dict]]:
    """credits.csv by (volume, plate): each name once, in the credit line's order, with its roles in credits.py's."""
    names: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(dict)
    for r in read(ROOT / folio["id"] / "credits.csv"):
        names[(r.get("volume", ""), r["plate"])].setdefault(r["name"], []).append(r["role"])
    return {k: [{"name": n, "slug": slugify(n), "roles": sorted(roles, key=credits.ROLES.index)}
                for n, roles in v.items()] for k, v in names.items()}


def unread(folio: dict) -> dict[tuple[str, str], str]:
    """Why no credit line was read, by (volume, plate), from sources/imprints.csv."""
    return {(r.get("volume", ""), r["plate"]): r["note"]
            for r in read(ROOT / folio["id"] / "sources" / "imprints.csv") if r["read"] == "none"}


def artist_records(plates: list[dict]) -> list[dict]:
    """artists.csv, in its order, each with the plates that credit them, their folios and plates per role."""
    out = []
    for a in read(ROOT / "artists.csv"):
        mine = [(p, c) for p in plates for c in p["credits"] if c["name"] == a["name"]]
        roles = {role: sum(1 for _, c in mine if role in c["roles"]) for role in credits.ROLES}
        out.append({"name": a["name"], "slug": slugify(a["name"]), "kind": a["kind"], "wikidata": a["wikidata"],
                    "note": a["note"], "plates": [p["id"] for p, _ in mine],
                    "folios": list(dict.fromkeys(p["folio"] for p, _ in mine)),
                    "roles": {role: n for role, n in roles.items() if n}})
    return out


def identification(row: dict, tax: dict[str, dict]) -> dict:
    code = row["ebird_code"]
    return {"figure": row["figure"], "printed_name": row["printed_name"], "printed_latin": row["printed_latin"],
            "scientific": row["scientific"], "common": row["common"], "code": code,
            "slug": slugify(tax[code]["COMMON_NAME"]) if code else "", "confidence": row["confidence"],
            "form": row["form"], "caption_checked": row["caption_checked"], "reason": row["reason"],
            "sources": row["sources"], "wikidata": row["wikidata"], "gbif": row["gbif"],
            "avibase": row["avibase"], "birdnet": row["birdnet_label"]}


def species_record(t: dict, row: dict) -> dict:
    return {"code": t["SPECIES_CODE"], "slug": slugify(t["COMMON_NAME"]), "common": t["COMMON_NAME"],
            "scientific": t["SCIENTIFIC_NAME"], "family": t["FAMILY_SCI_NAME"],
            "family_common": t["FAMILY_COM_NAME"], "order": t["ORDER"], "taxon_order": float(t["TAXON_ORDER"]),
            "extinct": t["EXTINCT"] == "true", "wikidata": row["wikidata"], "gbif": row["gbif"],
            "avibase": row["avibase"], "birdnet": row["birdnet_label"], "plates": [], "printed_as": []}


def build(images: dict[str, dict]) -> dict:
    """Every folio, plate and species, as the site reads them."""
    tax = taxonomy()
    by_name = {misnamed.norm(t["COMMON_NAME"]): t for t in tax.values() if t["CATEGORY"] == "species"}
    flagged: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for m in misnamed.misnamed():
        flagged[(m["book"], m["plate"])].append(by_name[misnamed.norm(m["printed"])])
    rows: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for folio in FOLIOS:
        for r in read(ROOT / folio["id"] / "species.csv"):
            rows[(folio["id"], r.get("volume", ""), r["plate"])].append(r)
    credited = {f["id"]: plate_credits(f) for f in FOLIOS}
    notes = {f["id"]: unread(f) for f in FOLIOS}

    plates: list[dict] = []
    species: dict[str, dict] = {}
    printed: dict[str, list[str]] = defaultdict(list)
    for folio, r, key, slug in plate_rows():
        volume = r.get("volume", "")
        at = (volume if folio["by_volume"] else "", r["plate"])
        found = rows[(folio["id"], *at)]
        codes = list(dict.fromkeys(s["ebird_code"] for s in found if s["ebird_code"]))
        first = tax[codes[0]] if codes else None
        pid = f"{folio['id']}/{slug}"
        plates.append({
            "id": pid, "folio": folio["id"], "slug": slug, "key": key, "volume": volume, "plate": r["plate"],
            "group": volume_title(volume) if folio["by_volume"] else "",
            "label": plate_label(folio, volume, r["plate"]),
            "printed": {"name": r.get("list_name") or r.get("title", ""), "latin": r.get("list_latin", ""),
                        "caption": " ".join(x for x in (r.get("caption_name", ""), r.get("caption_latin", "")) if x),
                        "legend": r.get("legend", "")},
            "species": [identification(s, tax) for s in found],
            "misnamed": [{"name": t["COMMON_NAME"], "code": t["SPECIES_CODE"]} for t in flagged[(folio["id"], key)]],
            "extinct": any(tax[c]["EXTINCT"] == "true" for c in codes),
            "open": any(s["confidence"] in OPEN for s in found),
            "multi": len(codes) > 1,
            "taxon": {"order": float(first["TAXON_ORDER"]), "family": first["FAMILY_SCI_NAME"],
                      "family_common": first["FAMILY_COM_NAME"], "bird_order": first["ORDER"]} if first else None,
            "image": images.get(pid),
            "imprint": r["imprint"],
            "credits": credited[folio["id"]].get(at, []),
            "imprint_note": "" if r["imprint"] else notes[folio["id"]][at],
            "credit": CREDITS.get((folio["id"], key), ""),
            "scan": r.get("page_url") or r.get("image_url", ""),
            "original": f"{REPO}/releases/download/{folio['release']}/{r['sheet_asset']}" if r["sheet_asset"] else "",
        })
        for c in codes:
            row = next(s for s in found if s["ebird_code"] == c)
            species.setdefault(c, species_record(tax[c], row))["plates"].append(pid)
        for t in flagged[(folio["id"], key)]:
            printed[t["SPECIES_CODE"]].append(pid)
    for code, pids in printed.items():
        if code in species:
            species[code]["printed_as"] = pids

    folios = [{k: f[k] for k in ("id", "author", "title", "years", "start", "end", "cite", "short", "medium",
                                 "release", "intro", "credit")}
              | {"plates": sum(1 for p in plates if p["folio"] == f["id"]),
                 "readme": f"{REPO}/tree/main/{f['id']}#readme", "makers": f"{REPO}/tree/main/{f['id']}#who-made-the-plates",
                 "images": f"{REPO}/releases/tag/{f['release']}"}
              for f in FOLIOS]
    return {"folios": folios, "plates": plates, "species": sorted(species.values(), key=lambda s: s["taxon_order"]),
            "artists": artist_records(plates)}


def load_images() -> dict[str, dict]:
    """images.json's plates, or nothing before site_images.py has run."""
    path = DATA / "images.json"
    return json.loads(path.read_text(encoding="utf-8"))["plates"] if path.exists() else {}


def main() -> int:
    data = build(load_images())
    plates = data["plates"]
    if "--stats" in sys.argv:
        for label, n in (("plates", len(plates)), ("species", len(data["species"])), ("artists", len(data["artists"])),
                         ("families", len({s["family"] for s in data["species"]})),
                         ("misnamed", sum(1 for p in plates if p["misnamed"])),
                         ("open", sum(1 for p in plates if p["open"])),
                         ("several species", sum(1 for p in plates if p["multi"])),
                         ("extinct", sum(1 for p in plates if p["extinct"])),
                         ("without a credit line", sum(1 for p in plates if not p["imprint"])),
                         ("without images", sum(1 for p in plates if not p["image"]))):
            print(f"{label}: {n}")
        return 0
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "plates.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"site/src/data/plates.json: {len(plates)} plates, {len(data['species'])} species, {len(data['artists'])} artists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
