# Plate explorer implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, search-indexable website for every plate in the dataset: a filterable wall of all 2,462 plates, a page per plate, a page per species. It is served from GitHub Pages at `https://wr.github.io/historical-bird-plates/`.

**Architecture:** Python owns the data and the images. `tools/site_data.py` joins the CSVs with the eBird taxonomy into `site/src/data/plates.json`. `tools/site_images.py` cuts every plate into three WebP sizes and measures its colour; the images ship as one tarball in a GitHub release. An Astro 7 static site in `site/` renders every page at build time, and two small TypeScript scripts add the wall's filters and the plate viewer. `tools/site_check.py` checks the build before a GitHub Actions workflow deploys it.

**Tech stack:**
- Python 3.12+: the data and check tools are standard library only; the image tool needs Pillow with WebP.
- Astro 7.3 and `@astrojs/sitemap` 3.7.
- `@fontsource-variable/newsreader`.
- Node 24 in CI, Node ≥ 22.12 locally; `node --test` runs the TypeScript tests through type stripping.
- GitHub Actions and GitHub Pages.

**Spec:** [`docs/superpowers/specs/2026-10-01-plate-explorer-design.md`](../specs/2026-10-01-plate-explorer-design.md). Read its *Amendments from planning* section: it overrides the body where they differ.

## Global constraints

- The CSVs are never edited by this work. The site reads them.
- Python tools follow `tools/`'s style:
  - a module docstring with usage lines;
  - `from __future__ import annotations`, type hints, `ROOT = Path(__file__).resolve().parents[1]`;
  - `def main() -> int` with `sys.exit(main())`;
  - tests in `unittest`, run as `python3 tools/test_site.py`.
- `site_data.py`, `site_check.py` and `test_site.py` use the standard library only. `site_images.py` may import Pillow. `test_site.py` skips its image tests when Pillow is missing.
- Python code must run on 3.12 (CI) as well as 3.14 (local).
- Astro config: `site: "https://wr.github.io"`, `base: "/historical-bird-plates"`, `trailingSlash: "always"`. Every internal URL is built with `href()` from `site/src/lib/data.ts`, never written by hand.
- No UI framework. Client code is plain TypeScript, bundled by Astro.
- TypeScript under `src/lib/` and `src/scripts/` that `node --test` loads must be erasable syntax only: no `enum`, no `namespace`, no parameter properties. Runtime imports between those files carry the `.ts` extension; `import type` may omit it.
- Image cuts: `thumb` 480 px long edge at WebP quality 70; `crop` 1600 px at quality 70; `sheet` 1000 px at quality 65. All images together stay under 850,000,000 bytes.
- The image release is tag `site-images-v1`, asset `site-images.tar`. Paths inside are `img/<folio>/<slug>-<cut>.webp`.
- Plate URLs:
  - `/havell/121/` and `/gould-europe/427/` for folios numbered straight through;
  - `/gould-asia/i-1/` and `/gould-australia/supp-18/` for folios numbered by volume.

  Species URLs are `/species/<slugified eBird common name>/`.
- Copy follows the repo's voice: plain, exact, British spelling ("colour", "hand-coloured"), no serial comma, no exclamation marks.
- Colours are CSS custom properties with a `prefers-color-scheme: dark` set. Body text meets WCAG AA in both schemes.
- Three actions need the user's explicit yes, asked in chat, before they happen:
  - publishing the release;
  - switching on GitHub Pages;
  - pushing the branch or opening a PR.

  Merging to `main` is the user's own action.

## File map

```
tools/
  site_data.py        plates.json: folios, plates, species (stdlib)
  site_images.py      WebP cuts + colour → site/public/img/, images.json, .cache/site-images.tar (Pillow)
  site_check.py       checks a built dist/: links, images, titles, descriptions, canonicals, sitemap, JSON-LD (stdlib)
  test_site.py        unittest for all three
site/
  package.json, package-lock.json, astro.config.mjs, tsconfig.json
  public/             favicon.svg, robots.txt, img/ (gitignored: the WebP images)
  src/data/           images.json (committed), plates.json (generated, gitignored)
  src/lib/            types.ts, data.ts, links.ts, seo.ts, seo.test.ts
  src/scripts/        wall-core.ts, wall-core.test.ts, wall.ts, viewer.ts, pager.ts
  src/styles/         global.css
  src/layouts/        Layout.astro
  src/components/     Seo.astro, Filters.astro, Wall.astro, Tile.astro, PlateViewer.astro, SpeciesBlock.astro, PlateStrip.astro
  src/pages/          index.astro, wall.json.ts, about.astro, 404.astro, [folio]/index.astro, [folio]/[plate].astro,
                      species/index.astro, species/[slug].astro
.github/workflows/    validate.yml (gains test_site.py and a site job), pages.yml (new)
.gitignore, README.md
```

---

### Task 1: `site_data.py`, the data the site renders

**Files:**
- Create: `tools/site_data.py`
- Create: `tools/test_site.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes:
  - `validate.fetch(name: str, url: str) -> Path` and `validate.EBIRD_URL`;
  - `misnamed.misnamed() -> list[dict]` (keys `book`, `plate`, `printed`, `shows`) and `misnamed.norm(s: str) -> str`.
- Produces, for later tasks:
  - constants `ROOT`, `DATA` (`site/src/data`), `REPO`, `FOLIOS` (a list of dicts, each with `id`, `release` and `by_volume`);
  - `slugify(name) -> str`;
  - `plate_key(folio, volume, plate) -> tuple[key, slug]`;
  - `plate_label(folio, volume, plate) -> str`;
  - `read(path) -> list[dict]`;
  - `plate_rows() -> Iterator[(folio, row, key, slug)]`;
  - `build(images: dict) -> dict` and `load_images() -> dict`.

  The JSON shape is fixed by `site/src/lib/types.ts` in Task 4. Its keys:

  ```
  folios[]:  id author title years start end cite short medium release intro credit plates readme images
  plates[]:  id folio slug key volume plate group label printed{name latin caption legend} species[] misnamed[{name code}]
             extinct open multi taxon{order family family_common bird_order}|null image|null scan original
  species[] (in identifications): figure printed_name printed_latin scientific common code slug confidence form
             caption_checked reason sources wikidata gbif avibase birdnet
  species[] (top level): code slug common scientific family family_common order taxon_order extinct wikidata gbif
             avibase birdnet plates[] printed_as[]
  ```

- [ ] **Step 1: Ignore the generated files**

Append to `.gitignore`:

```
site/node_modules/
site/dist/
site/.astro/
site/public/img/
site/src/data/plates.json
```

- [ ] **Step 2: Write the failing tests**

Create `tools/test_site.py`:

```python
"""Tests for the plate explorer's tools: site_data.py, site_images.py and site_check.py.

    python3 tools/test_site.py

The data tests build from the real tables. The image tests need Pillow and are skipped without it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import misnamed  # noqa: E402
import site_data  # noqa: E402

DATA = site_data.build(site_data.load_images())
FOLIO = {f["id"]: f for f in site_data.FOLIOS}
PLATE = {p["id"]: p for p in DATA["plates"]}
SPECIES = {s["common"]: s for s in DATA["species"]}


class Data(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(site_data.slugify("Leach's Storm-Petrel"), "leachs-storm-petrel")
        self.assertEqual(site_data.slugify("Baudin’s Black-Cockatoo"), "baudins-black-cockatoo")
        self.assertEqual(site_data.slugify("Rüppell's Warbler"), "ruppells-warbler")

    def test_keys_slugs_and_labels(self) -> None:
        asia, australia, europe = FOLIO["gould-asia"], FOLIO["gould-australia"], FOLIO["gould-europe"]
        self.assertEqual(site_data.plate_key(asia, "I", "1"), ("I.1", "i-1"))
        self.assertEqual(site_data.plate_key(australia, "Supp", "18"), ("Supp.18", "supp-18"))
        self.assertEqual(site_data.plate_key(europe, "II", "132"), ("132", "132"))
        self.assertEqual(site_data.plate_label(asia, "I", "1"), "Volume I, plate 1")
        self.assertEqual(site_data.plate_label(australia, "Supp", "18"), "Supplement, plate 18")
        self.assertEqual(site_data.plate_label(FOLIO["havell"], "", "121"), "Plate 121")

    def test_every_plate_once(self) -> None:
        rows = sum(len(site_data.read(site_data.ROOT / f["id"] / "plates.csv")) for f in site_data.FOLIOS)
        ids = [p["id"] for p in DATA["plates"]]
        self.assertEqual(len(ids), rows)
        self.assertEqual(len(set(ids)), rows)

    def test_every_species_once_with_a_unique_slug(self) -> None:
        codes = {r["ebird_code"] for f in site_data.FOLIOS
                 for r in site_data.read(site_data.ROOT / f["id"] / "species.csv") if r["ebird_code"]}
        self.assertEqual({s["code"] for s in DATA["species"]}, codes)
        slugs = [s["slug"] for s in DATA["species"]]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_plates_and_species_point_at_each_other(self) -> None:
        by_code = {s["code"]: s for s in DATA["species"]}
        for p in DATA["plates"]:
            for s in p["species"]:
                if s["code"]:
                    self.assertIn(p["id"], by_code[s["code"]]["plates"], p["id"])
                    self.assertEqual(s["slug"], by_code[s["code"]]["slug"], p["id"])
        for s in DATA["species"]:
            self.assertLessEqual(set(s["plates"] + s["printed_as"]), set(PLATE), s["code"])

    def test_misnamed_is_what_misnamed_py_lists(self) -> None:
        listed = {(m["book"], m["plate"]) for m in misnamed.misnamed()}
        self.assertEqual({(p["folio"], p["key"]) for p in DATA["plates"] if p["misnamed"]}, listed)

    def test_a_misnamed_plate(self) -> None:
        gull = PLATE["gould-europe/427"]
        self.assertEqual([s["common"] for s in gull["species"]], ["Mediterranean Gull"])
        self.assertEqual([m["name"] for m in gull["misnamed"]], ["Black-headed Gull"])
        self.assertIn("gould-europe/427", SPECIES["Black-headed Gull"]["printed_as"])

    def test_a_plate_numbered_by_volume(self) -> None:
        p = PLATE["gould-asia/i-1"]
        self.assertEqual((p["key"], p["label"], p["group"]), ("I.1", "Volume I, plate 1", "Volume I"))
        self.assertEqual(p["taxon"]["family"], "Accipitridae")
        self.assertTrue(p["scan"].startswith("https://www.biodiversitylibrary.org/page/"))
        self.assertTrue(p["original"].endswith("/gould-asia-v1/sheet-BirdsAsiaJohnGoIGoul-0028.jpg"))

    def test_flags(self) -> None:
        self.assertTrue(PLATE["havell/11"]["open"])  # Bird of Washington, not identified
        self.assertIsNone(PLATE["havell/11"]["taxon"])
        self.assertTrue(PLATE["havell/62"]["extinct"])  # Passenger Pigeon
        self.assertTrue(PLATE["havell/399"]["multi"])
        self.assertFalse(PLATE["havell/121"]["multi"])
        self.assertEqual(PLATE["havell/121"]["scan"][:30], "https://www.audubon.org/sites/")

    def test_species_are_in_taxonomic_order(self) -> None:
        orders = [s["taxon_order"] for s in DATA["species"]]
        self.assertEqual(orders, sorted(orders))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `python3 tools/test_site.py`
Expected: `ModuleNotFoundError: No module named 'site_data'`.

- [ ] **Step 4: Write `tools/site_data.py`**

```python
"""Build the data the plate explorer renders: site/src/data/plates.json.

    python3 tools/site_data.py           # write site/src/data/plates.json
    python3 tools/site_data.py --stats   # print the counts, write nothing

One record per folio, plate and species, joined from every folio's plates.csv and species.csv, the
eBird 2025 taxonomy (downloaded once into .cache/, as validate.py does) and the image sizes and
colours in site/src/data/images.json (written by site_images.py). Standard library only.
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
     "medium": "Hand-coloured engraving and aquatint", "release": "havell-v1", "by_volume": False,
     "intro": "435 plates, engraved, printed and hand-coloured by Robert Havell Jr. in London from Audubon's "
              "watercolours, and numbered 1–435 on the plates themselves.",
     "credit": "Courtesy of the John James Audubon Center at Mill Grove, Montgomery County Audubon Collection, "
               "and Zebra Publishing."},
    {**GOULD, "id": "gould-europe", "title": "The Birds of Europe", "years": "1832–37", "start": 1832, "end": 1837,
     "cite": "Gould, The Birds of Europe", "short": "Europe", "release": "gould-europe-v1", "by_volume": False,
     "intro": "Five volumes and 449 plates, numbered by Gould's General List. Drawn and lithographed by John and "
              "Elizabeth Gould and Edward Lear, hand-coloured, and published in parts in London."},
    {**GOULD, "id": "gould-australia", "title": "The Birds of Australia", "years": "1840–69", "start": 1840,
     "end": 1869, "cite": "Gould, The Birds of Australia", "short": "Australia", "release": "gould-australia-v1",
     "by_volume": True,
     "intro": "Seven volumes (1840–48) and a Supplement (1851–69), 681 plates. Drawn by John and Elizabeth Gould "
              "and H. C. Richter, lithographed, hand-coloured, and published in parts in London."},
    {**GOULD, "id": "gould-asia", "title": "The Birds of Asia", "years": "1850–83", "start": 1850, "end": 1883,
     "cite": "Gould, The Birds of Asia", "short": "Asia", "release": "gould-asia-v1", "by_volume": True,
     "intro": "Seven volumes and 530 plates, drawn and lithographed by John Gould with H. C. Richter, Joseph Wolf "
              "and William Hart. Gould died in 1881 and R. B. Sharpe finished the work."},
    {**GOULD, "id": "gould-britain", "title": "The Birds of Great Britain", "years": "1862–73", "start": 1862,
     "end": 1873, "cite": "Gould, The Birds of Great Britain", "short": "Britain", "release": "gould-britain-v2",
     "by_volume": True,
     "intro": "Five volumes and 367 plates, drawn by John Gould with H. C. Richter, W. Hart and J. Wolf, "
              "lithographed, hand-coloured, and published in parts in London."},
]


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

    plates: list[dict] = []
    species: dict[str, dict] = {}
    printed: dict[str, list[str]] = defaultdict(list)
    for folio, r, key, slug in plate_rows():
        volume = r.get("volume", "")
        found = rows[(folio["id"], volume if folio["by_volume"] else "", r["plate"])]
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
                 "readme": f"{REPO}/tree/main/{f['id']}#readme", "images": f"{REPO}/releases/tag/{f['release']}"}
              for f in FOLIOS]
    return {"folios": folios, "plates": plates, "species": sorted(species.values(), key=lambda s: s["taxon_order"])}


def load_images() -> dict[str, dict]:
    """images.json's plates, or nothing before site_images.py has run."""
    path = DATA / "images.json"
    return json.loads(path.read_text(encoding="utf-8"))["plates"] if path.exists() else {}


def main() -> int:
    data = build(load_images())
    plates = data["plates"]
    if "--stats" in sys.argv:
        for label, n in (("plates", len(plates)), ("species", len(data["species"])),
                         ("families", len({s["family"] for s in data["species"]})),
                         ("misnamed", sum(1 for p in plates if p["misnamed"])),
                         ("open", sum(1 for p in plates if p["open"])),
                         ("several species", sum(1 for p in plates if p["multi"])),
                         ("extinct", sum(1 for p in plates if p["extinct"])),
                         ("without images", sum(1 for p in plates if not p["image"]))):
            print(f"{label}: {n}")
        return 0
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "plates.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"site/src/data/plates.json: {len(plates)} plates, {len(data['species'])} species")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `python3 tools/test_site.py`
Expected: `Ran 10 tests … OK`. The first run downloads the eBird taxonomy into `.cache/`.

- [ ] **Step 6: Check the counts**

Run: `python3 tools/site_data.py --stats`
Expected (data as of 2026-10-01):

```
plates: 2462
species: 1762
families: 153
misnamed: 62
open: 21
several species: 58
extinct: 15
without images: 2462
```

Then run `python3 tools/site_data.py`. Expected: `site/src/data/plates.json: 2462 plates, 1762 species`. Then `git status --short` must not list `plates.json`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore tools/site_data.py tools/test_site.py
git commit -m "site_data.py: the plates, species and folios the explorer renders"
```

---

### Task 2: `site_images.py`, the WebP cuts and each plate's colour

**Files:**
- Create: `tools/site_images.py`
- Modify: `tools/test_site.py` (add the `Images` class)

**Interfaces:**
- Consumes: `site_data.ROOT`, `site_data.DATA`, `site_data.REPO`, `site_data.FOLIOS` and `site_data.plate_rows()`.
- Produces:
  - `colour(im) -> {"colour": "#rrggbb", "hue": int | None, "light": float}`;
  - `cut(im, long_edge) -> Image`;
  - the `build` and `fetch` commands;
  - `site/src/data/images.json`, shaped `{"release": "site-images-v1", "plates": {"<folio>/<slug>": {"thumb": [w, h], "crop": [w, h], "sheet": [w, h], "colour": "#rrggbb", "hue": int | null, "light": float}}}`.

- [ ] **Step 1: Write the failing tests**

In `tools/test_site.py`, add after `import site_data  # noqa: E402`:

```python
try:
    from PIL import Image, ImageDraw
    import site_images
except ImportError:  # Pillow is needed only to make the images
    site_images = None
```

Add this class before `if __name__ == "__main__":`:

```python
@unittest.skipUnless(site_images, "needs Pillow")
class Images(unittest.TestCase):
    def canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = Image.new("RGB", (400, 500), (255, 255, 255))
        return im, ImageDraw.Draw(im)

    def test_a_red_bird_on_white(self) -> None:
        im, draw = self.canvas()
        draw.ellipse([100, 100, 300, 400], fill=(200, 30, 40))
        c = site_images.colour(im)
        self.assertTrue(c["hue"] is not None and (c["hue"] < 10 or c["hue"] > 350), c)

    def test_cream_paper_inside_a_white_margin_is_masked(self) -> None:
        im, draw = self.canvas()
        draw.rectangle([20, 20, 380, 480], fill=(218, 204, 177))  # a Havell sheet's paper
        draw.ellipse([120, 150, 280, 350], fill=(40, 90, 170))
        c = site_images.colour(im)
        self.assertTrue(c["hue"] is not None and 200 <= c["hue"] <= 230, c)

    def test_a_grey_engraving_has_no_hue(self) -> None:
        im, draw = self.canvas()
        draw.ellipse([100, 100, 300, 400], fill=(90, 90, 92))
        c = site_images.colour(im)
        self.assertIsNone(c["hue"])
        self.assertLess(c["light"], 0.5)

    def test_cut_never_enlarges(self) -> None:
        self.assertEqual(site_images.cut(Image.new("RGB", (3000, 2000)), 480).size, (480, 320))
        self.assertEqual(site_images.cut(Image.new("RGB", (300, 200)), 480).size, (300, 200))
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 tools/test_site.py`
Expected: the four `Images` tests are skipped with `needs Pillow`. The reason is misleading for now: importing `site_images` failed because the module doesn't exist yet, and the `ImportError` branch caught it. Confirm Pillow is installed (`python3 -c "from PIL import features; print(features.check('webp'))"` prints `True`) so they will run once the module exists.

- [ ] **Step 3: Write `tools/site_images.py`**

```python
"""Make the plate explorer's images: three WebP cuts of every plate, and the plate's colour.

    python3 tools/site_images.py build   # cut every plate into site/public/img/, then write
                                         # site/src/data/images.json and .cache/site-images.tar
    python3 tools/site_images.py fetch   # unpack the published tarball into site/public/img/

Each plate's crop and sheet come from its folio's image release; Australia's and Asia's crops come
from crops.zip, downloaded once into .cache/. Plates already cut are skipped, so a stopped build
resumes. Needs Pillow with WebP. CI never runs this: the site's build reads only images.json.
"""
from __future__ import annotations

import colorsys
import io
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_data  # noqa: E402

CACHE = site_data.ROOT / ".cache"
PUBLIC = site_data.ROOT / "site" / "public"
OUT = PUBLIC / "img"
TAR = CACHE / "site-images.tar"
IMAGES = site_data.DATA / "images.json"
RELEASE = "site-images-v1"
CUTS = {"thumb": (480, 70), "crop": (1600, 70), "sheet": (1000, 65)}  # long edge in px, WebP quality
BUDGET = 850_000_000  # GitHub Pages publishes at most 1 GB
ZIPPED = {"gould-australia", "gould-asia"}
UA = {"User-Agent": "historical-bird-plates site_images (+https://github.com/wr/historical-bird-plates)"}


def colour(im: Image.Image) -> dict:
    """The plate's colour, as {"colour": "#rrggbb", "hue": degrees or None, "light": 0-1}.

    The paper is masked first: the border's median tone (the crops' white margin) and the two
    commonest tones that are light and nearly grey (a sheet's own paper, where it shows). Of the
    rest, pixels with real chroma vote for one of 24 hue bins, weighted by chroma squared so a
    vivid patch outvotes a wash; the winning bin's weighted mean is the colour. Under 3% of pixels
    voting means an engraved grey or a white bird: hue None, and the mean of the non-paper pixels,
    so the colour arrangement can sort it by lightness.
    """
    small = im.convert("RGB")
    small.thumbnail((160, 160))
    w, h = small.size
    px = small.load()
    pixels = [px[x, y] for y in range(h) for x in range(w)]
    border = [px[x, y] for x in range(w) for y in (0, h - 1)] + [px[x, y] for y in range(h) for x in (0, w - 1)]
    paper = [tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))]
    for q, _ in Counter((r >> 4, g >> 4, b >> 4) for r, g, b in pixels).most_common(2):
        tone = tuple(v * 16 + 8 for v in q)
        if max(tone) > 0.6 * 255 and max(tone) - min(tone) < 0.25 * 255:
            paper.append(tone)
    ink: list[tuple[int, int, int]] = []
    votes = [[0.0, 0.0, 0.0, 0.0] for _ in range(24)]
    voters = 0
    for r, g, b in pixels:
        if any(max(abs(r - t[0]), abs(g - t[1]), abs(b - t[2])) < 30 for t in paper):
            continue
        ink.append((r, g, b))
        chroma = (max(r, g, b) - min(r, g, b)) / 255
        if chroma < 0.12:
            continue
        voters += 1
        k = int(colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 24) % 24
        weight = chroma * chroma
        votes[k][0] += weight
        votes[k][1] += r * weight
        votes[k][2] += g * weight
        votes[k][3] += b * weight
    if voters < 0.03 * len(pixels):
        pool = ink or paper[:1]
        rgb = tuple(round(sum(c[i] for c in pool) / len(pool)) for i in range(3))
        hue = None
    else:
        best = max(votes, key=lambda v: v[0])
        rgb = tuple(round(best[i] / best[0]) for i in (1, 2, 3))
        hue = round(colorsys.rgb_to_hls(*(v / 255 for v in rgb))[0] * 360) % 360
    light = colorsys.rgb_to_hls(*(v / 255 for v in rgb))[1]
    return {"colour": "#%02x%02x%02x" % rgb, "hue": hue, "light": round(light, 3)}


def cut(im: Image.Image, long_edge: int) -> Image.Image:
    """A copy no longer than long_edge on its long side; never enlarged."""
    out = im.convert("RGB")
    out.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
    return out


def download(url: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    part.rename(path)
    return path


def crops_zip(folio: dict) -> Path:
    path = CACHE / "releases" / folio["release"] / "crops.zip"
    if not path.exists():
        download(f"{site_data.REPO}/releases/download/{folio['release']}/crops.zip", path)
    return path


def asset(folio: dict, name: str) -> bytes:
    """One file of the folio's image release; zipped crops are read from the cached crops.zip."""
    if name.startswith("crop-") and folio["id"] in ZIPPED:
        with zipfile.ZipFile(crops_zip(folio)) as z:
            return z.read(next(m for m in z.namelist() if m.rsplit("/", 1)[-1] == name))
    url = f"{site_data.REPO}/releases/download/{folio['release']}/{name}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
        return r.read()


def make(folio: dict, row: dict, slug: str, known: dict | None) -> dict:
    """Cut one plate's three images, unless they're already cut; return its images.json entry."""
    paths = {name: OUT / folio["id"] / f"{slug}-{name}.webp" for name in CUTS}
    if known and all(p.exists() for p in paths.values()):
        return known
    paths["crop"].parent.mkdir(parents=True, exist_ok=True)
    crop = Image.open(io.BytesIO(asset(folio, row["crop_asset"])))
    sheet = Image.open(io.BytesIO(asset(folio, row["sheet_asset"])))
    entry = {}
    for name, source in (("thumb", crop), ("crop", crop), ("sheet", sheet)):
        long_edge, quality = CUTS[name]
        out = cut(source, long_edge)
        out.save(paths[name], "WEBP", quality=quality, method=6)
        entry[name] = list(out.size)
    entry.update(colour(crop))
    print(f"{folio['id']}/{slug}", flush=True)
    return entry


def build() -> int:
    known = json.loads(IMAGES.read_text(encoding="utf-8"))["plates"] if IMAGES.exists() else {}
    for folio in site_data.FOLIOS:
        if folio["id"] in ZIPPED:
            crops_zip(folio)  # once, before the threads start
    jobs = [(folio, row, slug) for folio, row, _, slug in site_data.plate_rows() if row["crop_asset"]]
    with ThreadPoolExecutor(8) as pool:
        entries = list(pool.map(lambda j: make(*j, known.get(f"{j[0]['id']}/{j[2]}")), jobs))
    plates = {f"{folio['id']}/{slug}": entry for (folio, _, slug), entry in zip(jobs, entries)}
    size = sum(p.stat().st_size for p in OUT.rglob("*.webp"))
    if size > BUDGET:
        print(f"the images come to {size / 1e6:.0f} MB, over the {BUDGET / 1e6:.0f} MB budget", file=sys.stderr)
        return 1
    lines = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}" for k, v in plates.items())
    IMAGES.write_text(f'{{\n "release": "{RELEASE}",\n "plates": {{\n{lines}\n }}\n}}\n', encoding="utf-8")
    with tarfile.open(TAR, "w") as tar:
        tar.add(OUT, arcname="img")
    print(f"{len(plates)} plates, {size / 1e6:.0f} MB; wrote site/src/data/images.json and .cache/site-images.tar")
    return 0


def fetch() -> int:
    release = json.loads(IMAGES.read_text(encoding="utf-8"))["release"]
    download(f"{site_data.REPO}/releases/download/{release}/site-images.tar", TAR)
    with tarfile.open(TAR) as tar:
        tar.extractall(PUBLIC, filter="data")
    print(f"unpacked {release} into site/public/img/")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        return build()
    if command == "fetch":
        return fetch()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 tools/test_site.py`
Expected: `Ran 14 tests … OK` (none skipped).

- [ ] **Step 5: Commit**

```bash
git add tools/site_images.py tools/test_site.py
git commit -m "site_images.py: three WebP cuts of every plate, and its colour"
```

---

### Task 3: Make the images

A long run: about 10 GB of sheets stream through memory and 690 MB of zips are cached. The output is about 620 MB of WebP. Nothing is published in this task.

**Files:**
- Create: `site/src/data/images.json` (committed)
- Modify: `tools/test_site.py` (one test)

**Interfaces:**
- Consumes: Task 2's `build`.
- Produces: `images.json` for every plate with a crop; `site/public/img/**` and `.cache/site-images.tar` locally, for Task 12 and Task 13.

- [ ] **Step 1: Check disk space and the zip layout**

Run `df -h .`. You need at least 4 GB free.

Then run:

```bash
python3 -c "
import sys, zipfile; sys.path.insert(0, 'tools')
import site_data, site_images
for f in site_data.FOLIOS:
    if f['id'] in site_images.ZIPPED:
        print(f['id'], zipfile.ZipFile(site_images.crops_zip(f)).namelist()[:3])"
```

Expected: each list shows names ending in `crop-<barcode>-<leaf>.jpg`, matching `plates.csv`'s `crop_asset` for that folio (for example `crop-birdsAustraliav1Goul-0140.jpg`). A folder prefix is fine, because `asset()` matches on the base name. If the names don't match, stop and report.

- [ ] **Step 2: Run the build in the background**

Run, as a background command with a 2-hour timeout: `python3 tools/site_images.py build > .cache/site-images.log 2>&1`.

When it exits, run `tail -3 .cache/site-images.log`. Expected last line: `2461 plates, NNN MB; wrote site/src/data/images.json and .cache/site-images.tar`, with NNN under 850. It is 2461 because `gould-europe/132` has no crop in the release yet.

If the run fails partway, run it again. It skips plates whose three files exist and that are already in `images.json`. If it failed before writing `images.json`, it re-cuts everything; that is slow but correct.

- [ ] **Step 3: Add the coverage test**

In the `Data` class of `tools/test_site.py`, add:

```python
    def test_every_plate_in_a_release_has_its_images(self) -> None:
        self.assertEqual([p["id"] for p in DATA["plates"] if not p["image"]], ["gould-europe/132"])
        p = PLATE["havell/121"]["image"]
        self.assertEqual(max(p["thumb"]), 480)
        self.assertIsNone(p["hue"])  # a white owl
```

Run: `python3 tools/test_site.py`. Expected: `Ran 15 tests … OK`.

If `havell/121`'s hue isn't `None`, look at its crop. The prototype gave `None` for it. Report the difference rather than changing the threshold blindly.

- [ ] **Step 4: Spot-check the colours by eye**

Write a contact sheet of 120 thumbnails sorted the way the wall's colour arrangement will sort them, with each plate's colour as a swatch:

```bash
python3 - <<'EOF'
import json, random
from PIL import Image, ImageDraw
plates = json.load(open("site/src/data/images.json"))["plates"]
pick = random.Random(1).sample(sorted(plates), 120)
pick.sort(key=lambda k: (plates[k]["hue"] is None, plates[k]["hue"] or 0, -plates[k]["light"]))
sheet = Image.new("RGB", (12 * 110, 10 * 140), "white"); d = ImageDraw.Draw(sheet)
for i, k in enumerate(pick):
    x, y = i % 12 * 110, i // 12 * 140
    t = Image.open(f"site/public/img/{k}-thumb.webp"); t.thumbnail((100, 110)); sheet.paste(t, (x + 5, y + 5))
    d.rectangle([x + 5, y + 118, x + 105, y + 134], fill=plates[k]["colour"])
sheet.save(".cache/colour-check.jpg", quality=85)
EOF
```

Open `.cache/colour-check.jpg` with the Read tool. The swatches should run red, orange, brown, yellow, green, blue, purple, then greys from light to dark, and each swatch should be a colour visible in its plate rather than its paper. Note any plate whose swatch is plainly the paper.

- [ ] **Step 5: Check the counts and commit**

Run `python3 tools/site_data.py --stats`. Expected: `without images: 1`.

```bash
git add site/src/data/images.json tools/test_site.py
git commit -m "Site images: sizes and colours of 2,461 plates"
```

---

### Task 4: The Astro site's skeleton: config, data, search-engine metadata, layout, styles

**Files:**
- Create:
  - `site/package.json`, `site/astro.config.mjs`, `site/tsconfig.json`;
  - `site/public/favicon.svg`, `site/public/robots.txt`;
  - `site/src/lib/types.ts`, `site/src/lib/data.ts`, `site/src/lib/links.ts`, `site/src/lib/seo.ts`, `site/src/lib/seo.test.ts`;
  - `site/src/components/Seo.astro`, `site/src/layouts/Layout.astro`, `site/src/styles/global.css`;
  - `site/src/pages/index.astro` (a placeholder; Task 5 replaces it).
- Generated by npm: `site/package-lock.json`.

**Interfaces:**
- Consumes: `site/src/data/plates.json` (Task 1's shape, with Task 3's images).
- Produces (later tasks import these by exactly these names):
  - `types.ts`: interfaces `Folio`, `Identification`, `PlateImage`, `Plate`, `Species`, `Data`.
  - `data.ts`: `folios`, `plates`, `species`, `entries`, `folioById`, `plateById`, `speciesByCode`, `SITE`, `href(path?)`, `plateHref(p)`, `speciesHref(s)`, `folioHref(f)`, `imageSrc(p, cut)`, `absolute(path)`, `folioOf(p)`.

    `entries` is added in Task 5. Task 4 leaves it out, because `wall-core.ts` doesn't exist yet.
  - `links.ts`: `REPO`, `ebird(code)`, `wikidata(q)`, `gbif(id)`, `avibase(id)`, `outlinks(x)`.
  - `seo.ts`: `norm`, `joinNames`, `identified`, `shown`, `possessive`, `altText`, `plateTitle`, `clip`, `plateDescription`, `plateJsonLd`, `speciesTitle`, `speciesDescription`, `speciesJsonLd`.
  - `Layout.astro`: props `{ title: string; description: string; image?: string; jsonld?: object }`.

- [ ] **Step 1: Create the package and install**

`site/package.json`:

```json
{
  "name": "historical-bird-plates-site",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22.12" },
  "scripts": {
    "data": "python3 ../tools/site_data.py",
    "predev": "npm run data",
    "dev": "astro dev",
    "prebuild": "npm run data",
    "build": "astro build",
    "preview": "astro preview",
    "test": "node --test src/lib/*.test.ts src/scripts/*.test.ts"
  },
  "dependencies": {
    "@astrojs/sitemap": "^3.7.4",
    "@fontsource-variable/newsreader": "^5.3.0",
    "astro": "^7.3.5"
  }
}
```

Run: `cd site && npm install`. Expected: `package-lock.json` is written. A warning about `esbuild` install scripts is harmless: esbuild falls back to its platform package. Tests and builds in later steps prove it works.

- [ ] **Step 2: Config files**

`site/astro.config.mjs`:

```js
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://wr.github.io",
  base: "/historical-bird-plates",
  trailingSlash: "always",
  integrations: [sitemap({ filter: (page) => !page.endsWith("/404/") })],
});
```

`site/tsconfig.json`:

```json
{
  "extends": "astro/tsconfigs/strict",
  "include": [".astro/types.d.ts", "**/*"],
  "exclude": ["dist"]
}
```

`site/public/robots.txt`:

```
User-agent: *
Allow: /

Sitemap: https://wr.github.io/historical-bird-plates/sitemap-index.xml
```

`site/public/favicon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><style>path{fill:#8a3f1c}@media (prefers-color-scheme:dark){path{fill:#e3a27c}}</style><path d="M5 21c4 0 7-3 9-7 2-5 6-8 11-7l3-2-1 4c1 6-3 11-9 13-5 1-9 1-13-1z"/><path d="M9 25h13v2H9z"/></svg>
```

- [ ] **Step 3: Types, data and links**

`site/src/lib/types.ts`:

```ts
export interface Folio {
  id: string;
  author: string;
  title: string;
  years: string;
  start: number;
  end: number;
  cite: string;
  short: string;
  medium: string;
  release: string;
  intro: string;
  credit: string;
  plates: number;
  readme: string;
  images: string;
}

export interface Identification {
  figure: string;
  printed_name: string;
  printed_latin: string;
  scientific: string;
  common: string;
  code: string;
  slug: string;
  confidence: string;
  form: string;
  caption_checked: string;
  reason: string;
  sources: string;
  wikidata: string;
  gbif: string;
  avibase: string;
  birdnet: string;
}

export interface PlateImage {
  thumb: [number, number];
  crop: [number, number];
  sheet: [number, number];
  colour: string;
  hue: number | null;
  light: number;
}

export interface Plate {
  id: string;
  folio: string;
  slug: string;
  key: string;
  volume: string;
  plate: string;
  group: string;
  label: string;
  printed: { name: string; latin: string; caption: string; legend: string };
  species: Identification[];
  misnamed: { name: string; code: string }[];
  extinct: boolean;
  open: boolean;
  multi: boolean;
  taxon: { order: number; family: string; family_common: string; bird_order: string } | null;
  image: PlateImage | null;
  scan: string;
  original: string;
}

export interface Species {
  code: string;
  slug: string;
  common: string;
  scientific: string;
  family: string;
  family_common: string;
  order: string;
  taxon_order: number;
  extinct: boolean;
  wikidata: string;
  gbif: string;
  avibase: string;
  birdnet: string;
  plates: string[];
  printed_as: string[];
}

export interface Data {
  folios: Folio[];
  plates: Plate[];
  species: Species[];
}
```

`site/src/lib/data.ts`:

```ts
import raw from "../data/plates.json";
import type { Data, Folio, Plate } from "./types";

const data = raw as unknown as Data;

export const { folios, plates, species } = data;
export const folioById = new Map(folios.map((f) => [f.id, f]));
export const plateById = new Map(plates.map((p) => [p.id, p]));
export const speciesByCode = new Map(species.map((s) => [s.code, s]));

export const SITE = "https://wr.github.io";
const base = import.meta.env.BASE_URL; // "/historical-bird-plates/"

/** A path inside the site, with the base: href("species/") is "/historical-bird-plates/species/". */
export const href = (path = ""): string => base + path.replace(/^\/+/, "");
export const plateHref = (p: Plate): string => href(`${p.folio}/${p.slug}/`);
export const speciesHref = (s: { slug: string }): string => href(`species/${s.slug}/`);
export const folioHref = (f: { id: string }): string => href(`${f.id}/`);
export const imageSrc = (p: Plate, cut: "thumb" | "crop" | "sheet"): string => href(`img/${p.folio}/${p.slug}-${cut}.webp`);
export const absolute = (path: string): string => new URL(path, SITE).href;
export const folioOf = (p: Plate): Folio => folioById.get(p.folio)!;
```

`site/src/lib/links.ts`:

```ts
export const REPO = "https://github.com/wr/historical-bird-plates";

export const ebird = (code: string): string => `https://ebird.org/species/${code}`;
export const wikidata = (q: string): string => `https://www.wikidata.org/wiki/${q}`;
export const gbif = (id: string): string => `https://www.gbif.org/species/${id}`;
export const avibase = (id: string): string => `https://avibase.bsc-eoc.org/species.jsp?avibaseid=${id}`;

/** The outside pages for a species, in a fixed order, skipping IDs it doesn't have. */
export function outlinks(x: { code: string; wikidata: string; gbif: string; avibase: string }): { label: string; href: string }[] {
  const links: { label: string; href: string }[] = [];
  if (x.code) links.push({ label: "eBird", href: ebird(x.code) });
  if (x.wikidata) links.push({ label: "Wikidata", href: wikidata(x.wikidata) });
  if (x.gbif) links.push({ label: "GBIF", href: gbif(x.gbif) });
  if (x.avibase) links.push({ label: "Avibase", href: avibase(x.avibase) });
  return links;
}
```

- [ ] **Step 4: Write the failing tests for `seo.ts`**

`site/src/lib/seo.test.ts`:

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { altText, clip, plateDescription, plateJsonLd, plateTitle, shown } from "./seo.ts";
import type { Folio, Plate } from "./types.ts";

const europe = {
  id: "gould-europe", author: "John Gould", title: "The Birds of Europe", years: "1832–37", start: 1832, end: 1837,
  cite: "Gould, The Birds of Europe", short: "Europe", medium: "Hand-coloured lithograph", release: "gould-europe-v1",
  intro: "", credit: "Smithsonian Libraries and Archives, via the Biodiversity Heritage Library.", plates: 449,
  readme: "", images: "",
} as Folio;

const ident = (over: Record<string, unknown> = {}) => ({
  figure: "", printed_name: "", printed_latin: "", scientific: "Ichthyaetus melanocephalus",
  common: "Mediterranean Gull", code: "medgul1", slug: "mediterranean-gull", confidence: "high", form: "",
  caption_checked: "yes", reason: "Gould's Black-headed Gull is the Mediterranean Gull: black hood, white primaries.",
  sources: "", wikidata: "Q27064", gbif: "", avibase: "", birdnet: "", ...over,
});

const plate = (over: Record<string, unknown> = {}) => ({
  id: "gould-europe/427", folio: "gould-europe", slug: "427", key: "427", volume: "V", plate: "427", group: "",
  label: "Plate 427", printed: { name: "Black-headed Gull", latin: "Larus melanocephalus", caption: "", legend: "" },
  species: [ident()], misnamed: [{ name: "Black-headed Gull", code: "bkhgul" }], extinct: false, open: false,
  multi: false, taxon: null, image: null, scan: "", original: "", ...over,
}) as unknown as Plate;

test("a printed name that differs leads, quoted, with the modern name after", () => {
  assert.equal(plateTitle(plate(), europe), "“Black-headed Gull” (Mediterranean Gull) · Gould, The Birds of Europe, plate 427");
});

test("a printed name that agrees, grey and gray alike, is not repeated", () => {
  const p = plate({ printed: { name: "Grey Heron", latin: "", caption: "", legend: "" }, species: [ident({ common: "Gray Heron", code: "graher1" })] });
  assert.equal(plateTitle(p, europe), "Gray Heron · Gould, The Birds of Europe, plate 427");
});

test("several species are named once each, joined with and", () => {
  const p = plate({ species: ["A", "B", "C", "A"].map((n) => ident({ common: n, code: n })) });
  assert.equal(shown(p), "A, B and C");
});

test("an unidentified plate is named by its printed name", () => {
  const p = plate({ printed: { name: "Bird of Washington", latin: "", caption: "", legend: "" }, species: [ident({ common: "", scientific: "", code: "" })] });
  assert.equal(plateTitle(p, europe), "“Bird of Washington” · Gould, The Birds of Europe, plate 427");
});

test("a description stops at a word, under 160 characters", () => {
  const d = plateDescription(plate({ species: [ident({ reason: "word ".repeat(80) })] }), europe);
  assert.ok(d.length <= 158, String(d.length));
  assert.ok(d.startsWith("Mediterranean Gull (Ichthyaetus melanocephalus) on plate 427 of Gould's The Birds of Europe, 1832–37. "), d);
  assert.ok(d.endsWith("word…"), d);
  assert.equal(clip("short"), "short");
});

test("alt text names the plate, the folio and the bird", () => {
  assert.equal(altText(plate(), europe), "Plate 427 of Gould's The Birds of Europe: Mediterranean Gull (Ichthyaetus melanocephalus)");
});

test("JSON-LD is a VisualArtwork about a Taxon", () => {
  const ld = plateJsonLd(plate(), europe, "https://x/", "https://x/i.webp") as Record<string, any>;
  assert.equal(ld["@type"], "VisualArtwork");
  assert.equal(ld.dateCreated, "1832/1837");
  assert.equal(ld.image, "https://x/i.webp");
  assert.deepEqual(ld.about[0].sameAs, ["https://www.wikidata.org/wiki/Q27064", "https://ebird.org/species/medgul1"]);
  assert.equal(ld.license, "https://creativecommons.org/publicdomain/mark/1.0/");
});
```

Run: `cd site && npm test`
Expected: FAIL, because `seo.ts` can't be found (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 5: Write `site/src/lib/seo.ts`**

```ts
import { ebird, wikidata } from "./links.ts";
import type { Folio, Identification, Plate, Species } from "./types";

const DESCRIPTION = 158;
const PDM = "https://creativecommons.org/publicdomain/mark/1.0/";

/** Letters only, lower case, grey as gray: how misnamed.py compares a printed name with eBird's. */
export function norm(s: string): string {
  return s.toLowerCase().replace(/grey/g, "gray").replace(/parrakeet/g, "parakeet").replace(/[^a-z]/g, "");
}

/** "A", "A and B", "A, B and C". */
export function joinNames(names: string[]): string {
  return names.length <= 2 ? names.join(" and ") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** The plate's identified species, once each, in figure order. */
export function identified(p: Plate): Identification[] {
  const seen = new Set<string>();
  return p.species.filter((s) => s.code && !seen.has(s.code) && seen.add(s.code));
}

/** "Snowy Owl"; "Mallard and Northern Pintail"; "An unidentified bird". */
export function shown(p: Plate): string {
  const names = identified(p).map((s) => s.common);
  return names.length ? joinNames(names) : "An unidentified bird";
}

/** "Gould's The Birds of Europe". */
export function possessive(f: Folio): string {
  return `${f.author.split(" ").pop()}'s ${f.title}`;
}

const lowerFirst = (s: string): string => s.charAt(0).toLowerCase() + s.slice(1);
const named = (ids: Identification[]): string => joinNames(ids.map((s) => `${s.common} (${s.scientific})`));

/** "Plate 427 of Gould's The Birds of Europe: Mediterranean Gull (Ichthyaetus melanocephalus)". */
export function altText(p: Plate, f: Folio): string {
  const ids = identified(p);
  return `${p.label} of ${possessive(f)}: ${ids.length ? named(ids) : `“${p.printed.name}”, not identified`}`;
}

/** The modern name, or the printed name quoted first when it differs. */
export function plateTitle(p: Plate, f: Folio): string {
  const modern = shown(p);
  const printed = p.printed.name;
  const lead = !identified(p).length ? `“${printed}”`
    : printed && norm(printed) !== norm(modern) ? `“${printed}” (${modern})` : modern;
  return `${lead} · ${f.cite}, ${lowerFirst(p.label)}`;
}

/** At most max characters, cut at a word, with an ellipsis when cut. */
export function clip(text: string, max = DESCRIPTION): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max - 1);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:.–-]+$/, "")}…`;
}

export function plateDescription(p: Plate, f: Folio): string {
  const ids = identified(p);
  const why = p.species.map((s) => s.reason).find(Boolean) ?? "";
  return clip(`${ids.length ? named(ids) : "An unidentified bird"} on ${lowerFirst(p.label)} of ${possessive(f)}, ${f.years}. ${why}`);
}

function taxon(s: { scientific: string; common: string; code: string; wikidata: string }): object {
  return {
    "@type": "Taxon", name: s.scientific, alternateName: s.common, taxonRank: "species",
    sameAs: [s.wikidata ? wikidata(s.wikidata) : "", ebird(s.code)].filter(Boolean),
  };
}

export function plateJsonLd(p: Plate, f: Folio, url: string, image?: string): object {
  return {
    "@context": "https://schema.org",
    "@type": "VisualArtwork",
    name: p.printed.name || shown(p),
    url,
    ...(image ? { image } : {}),
    artform: "Print",
    artMedium: f.medium,
    creator: { "@type": "Person", name: f.author },
    dateCreated: `${f.start}/${f.end}`,
    isPartOf: { "@type": "Book", name: f.title, author: { "@type": "Person", name: f.author } },
    position: p.key,
    about: identified(p).map(taxon),
    license: PDM,
    creditText: f.credit,
  };
}

export function speciesTitle(s: Species): string {
  return `${s.common} in nineteenth-century bird plates`;
}

export function speciesDescription(s: Species, folios: Folio[]): string {
  const n = s.plates.length;
  return clip(`${s.common} (${s.scientific}, ${s.family}) on ${n} ${n === 1 ? "plate" : "plates"} of ${joinNames(folios.map(possessive))}, each with its printed name and how it was identified.`);
}

export function speciesJsonLd(s: Species, url: string, image?: string): object {
  return {
    "@context": "https://schema.org",
    ...taxon(s),
    url,
    ...(image ? { image } : {}),
    parentTaxon: { "@type": "Taxon", name: s.family, taxonRank: "family" },
  };
}
```

Run: `cd site && npm test`
Expected: `# pass 7`, `# fail 0`.

- [ ] **Step 6: `Seo.astro`, `Layout.astro` and a placeholder home page**

`site/src/components/Seo.astro`:

```astro
---
interface Props {
  title: string;
  description: string;
  image?: string;
  jsonld?: object;
}
const { title, description, image, jsonld } = Astro.props;
const canonical = new URL(Astro.url.pathname, Astro.site).href;
const ld = jsonld ? JSON.stringify(jsonld).replace(/</g, "\\u003c") : "";
---
<title>{title}</title>
<meta name="description" content={description} />
<link rel="canonical" href={canonical} />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Historical bird plates" />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:url" content={canonical} />
{image && <meta property="og:image" content={image} />}
<meta name="twitter:card" content="summary_large_image" />
{ld && <script type="application/ld+json" set:html={ld} />}
```

`site/src/layouts/Layout.astro`:

```astro
---
import "@fontsource-variable/newsreader/opsz.css";
import "@fontsource-variable/newsreader/opsz-italic.css";
import "../styles/global.css";
import Seo from "../components/Seo.astro";
import { absolute, folioHref, folios, href, imageSrc, plates } from "../lib/data";
import { REPO } from "../lib/links";

interface Props {
  title: string;
  description: string;
  image?: string;
  jsonld?: object;
}
const { title, description, image, jsonld } = Astro.props;
const cover = plates.find((p) => p.image);
const ogImage = image ?? (cover ? absolute(imageSrc(cover, "crop")) : undefined);
---
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script is:inline>document.documentElement.classList.add("js")</script>
    <Seo title={title} description={description} image={ogImage} jsonld={jsonld} />
    <meta name="color-scheme" content="light dark" />
    <link rel="icon" href={href("favicon.svg")} type="image/svg+xml" />
    <link rel="sitemap" href={href("sitemap-index.xml")} />
  </head>
  <body>
    <a class="skip" href="#main">Skip to content</a>
    <header class="site-head">
      <a class="brand" href={href()}>Historical bird plates</a>
      <nav aria-label="Site">
        <details class="menu">
          <summary>Folios</summary>
          <ul>
            {folios.map((f) => (
              <li><a href={folioHref(f)}>{f.author.split(" ").pop()}, <i>{f.title}</i></a></li>
            ))}
          </ul>
        </details>
        <a href={href("species/")}>Species</a>
        <a href={href("about/")}>About</a>
        <a href={REPO}>Data</a>
      </nav>
    </header>
    <main id="main"><slot /></main>
    <footer class="site-foot">
      <p>Every plate of five nineteenth-century bird folios, identified to modern species. The tables are CC0; the plates are in the public domain.</p>
      <p>Gould scans: Smithsonian Libraries and Archives, via the Biodiversity Heritage Library. Havell scans: courtesy of the John James Audubon Center at Mill Grove, Montgomery County Audubon Collection, and Zebra Publishing.</p>
      <p>Cite: Riley, W. <i>Historical bird plates: modern identifications</i>. Zenodo. <a href="https://doi.org/10.5281/zenodo.22964828">doi:10.5281/zenodo.22964828</a></p>
    </footer>
  </body>
</html>
```

`site/src/pages/index.astro` (a placeholder until Task 5):

```astro
---
import Layout from "../layouts/Layout.astro";
import { plates } from "../lib/data";
---
<Layout title="Historical bird plates" description="Every plate of five nineteenth-century bird folios, identified to modern species.">
  <h1>Historical bird plates</h1>
  <p>{plates.length} plates.</p>
</Layout>
```

- [ ] **Step 7: `global.css`**

`site/src/styles/global.css`:

```css
:root {
  --paper: #f7f3ea;
  --paper-2: #efe9dc;
  --ink: #221f1a;
  --ink-2: #5a5246;
  --rule: #d8cfbd;
  --accent: #8a3f1c;
  --focus: #1f5f99;
  --tile: #e9e2d3;
  --serif: "Newsreader Variable", "Iowan Old Style", Georgia, serif;
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --gutter: clamp(16px, 4vw, 40px);
  --measure: 68ch;
  --row-h: 180px;
  color-scheme: light dark;
}
@media (max-width: 600px) {
  :root { --row-h: 120px; }
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #161412;
    --paper-2: #1f1c19;
    --ink: #ede7db;
    --ink-2: #b3aa9b;
    --rule: #39332c;
    --accent: #e3a27c;
    --focus: #8cbbe8;
    --tile: #24201c;
  }
}

*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 1rem/1.6 var(--sans); }
h1, h2, .serif { font-family: var(--serif); font-weight: 500; line-height: 1.15; letter-spacing: -0.01em; }
h1 { font-size: clamp(2rem, 4.5vw, 3.25rem); margin: 0 0 0.25em; }
h2 { font-size: 1.5rem; margin: 2rem 0 0.75rem; }
h3 { font-size: 0.95rem; font-weight: 600; margin: 1.25rem 0 0.25rem; }
p { margin: 0 0 0.75rem; }
a { color: inherit; text-decoration-color: color-mix(in srgb, currentColor 35%, transparent); text-underline-offset: 0.18em; }
a:hover { text-decoration-color: currentColor; }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.skip { position: absolute; left: -9999px; }
.skip:focus { left: var(--gutter); top: 8px; z-index: 30; background: var(--paper); padding: 8px 12px; }
.eyebrow { font: 500 0.75rem/1.4 var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-2); margin: 0 0 0.35rem; }
.small { font-size: 0.875rem; color: var(--ink-2); }
.js-only { display: none; }
.js .js-only { display: block; }

.site-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 0.5rem 1.5rem; padding: 1rem var(--gutter); border-bottom: 1px solid var(--rule); }
.brand { font-family: var(--serif); font-size: 1.3rem; text-decoration: none; }
.site-head nav { display: flex; flex-wrap: wrap; gap: 1.25rem; align-items: baseline; }
.site-head nav a { text-decoration: none; }
.site-head nav a:hover { text-decoration: underline; }
.menu { position: relative; }
.menu summary { cursor: pointer; list-style: none; }
.menu summary::-webkit-details-marker { display: none; }
.menu summary::after { content: " ▾"; font-size: 0.75em; }
.menu ul { position: absolute; right: 0; top: calc(100% + 8px); z-index: 20; margin: 0; padding: 0.4rem 0; list-style: none; min-width: 17rem; background: var(--paper); border: 1px solid var(--rule); border-radius: 6px; box-shadow: 0 8px 24px rgb(0 0 0 / 0.12); }
.menu li a { display: block; padding: 0.4rem 1rem; }
.menu li a:hover { background: var(--paper-2); text-decoration: none; }
main { padding: 0 var(--gutter) 4rem; }
.site-foot { display: grid; gap: 0.25rem; padding: 2rem var(--gutter) 3rem; border-top: 1px solid var(--rule); font-size: 0.85rem; color: var(--ink-2); }
.site-foot p { max-width: var(--measure); margin: 0; }

.intro, .folio-head { padding: 2.5rem 0 1.25rem; max-width: 52rem; }
.lede { font-family: var(--serif); font-size: 1.25rem; line-height: 1.5; color: var(--ink-2); }
.folio-head .years { font-family: var(--serif); font-size: 1.25rem; color: var(--ink-2); }

.controls { display: none; position: sticky; top: 0; z-index: 10; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 0.6rem 1rem; padding: 0.75rem 0; margin-bottom: 0.5rem; background: color-mix(in srgb, var(--paper) 94%, transparent); backdrop-filter: blur(8px); border-bottom: 1px solid var(--rule); }
.js .controls { display: grid; }
.controls input[type="search"], .controls select, .species-filter input { font: inherit; color: var(--ink); background: var(--paper); border: 1px solid var(--rule); border-radius: 6px; padding: 0.5rem 0.75rem; }
.controls input[type="search"] { width: 100%; }
.arrange { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: var(--ink-2); }
.pills { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 0.4rem; }
.pill { font: inherit; font-size: 0.85rem; padding: 0.25rem 0.75rem; border-radius: 999px; border: 1px solid var(--rule); background: transparent; color: var(--ink); cursor: pointer; }
.pill:hover { border-color: var(--ink-2); }
.pill[aria-pressed="true"] { background: var(--ink); border-color: var(--ink); color: var(--paper); }
.status { grid-column: 1 / -1; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.5rem 1rem; font-size: 0.875rem; color: var(--ink-2); }
.status p { margin: 0; }
.status input[type="range"] { width: 8rem; vertical-align: middle; accent-color: var(--ink); }

.group-title { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.25rem 0.75rem; font-size: 1.35rem; margin: 2rem 0 0.75rem; }
.group-count { font: 400 0.8rem var(--sans); color: var(--ink-2); }
.rows { display: flex; flex-wrap: wrap; gap: 6px; }
.rows::after { content: ""; flex-grow: 10000; }
.tile { position: relative; display: block; flex: var(--ar) 1 calc(var(--ar) * var(--row-h)); aspect-ratio: var(--ar); overflow: hidden; border-radius: 2px; background: color-mix(in srgb, var(--c, var(--tile)) 22%, var(--tile)); }
.tile img { display: block; width: 100%; height: 100%; object-fit: contain; }
.missing { display: grid; place-items: center; height: 100%; padding: 0.5rem; text-align: center; font-size: 0.75rem; color: var(--ink-2); }
.cap { position: absolute; inset: auto 0 0 0; display: grid; padding: 1.75rem 0.6rem 0.5rem; font-size: 0.78rem; line-height: 1.3; color: #fff; background: linear-gradient(transparent, rgb(0 0 0 / 0.75)); opacity: 0; transform: translateY(4px); transition: opacity 0.15s, transform 0.15s; pointer-events: none; }
.tile:hover .cap, .tile:focus-visible .cap { opacity: 1; transform: none; }
.cap-name { font-family: var(--serif); font-size: 1rem; }
.empty { padding: 3rem 0; font-family: var(--serif); font-size: 1.25rem; color: var(--ink-2); }

.crumbs { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.5rem 1rem; padding: 1rem 0; font-size: 0.875rem; color: var(--ink-2); }
.pager { display: flex; gap: 1rem; }
.plate-head { margin: 0.5rem 0 1.5rem; }
.printed-as { font-family: var(--serif); font-size: 1.3rem; color: var(--ink-2); margin: 0; }
.plate { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2rem; align-items: start; }
@media (min-width: 900px) {
  .plate { grid-template-columns: minmax(0, 3fr) minmax(18rem, 2fr); }
  .viewer { position: sticky; top: 1rem; }
}
.viewer { margin: 0; }
.stage { position: relative; display: grid; place-items: center; overflow: hidden; max-height: 82vh; background: var(--paper-2); border-radius: 4px; touch-action: pan-y pinch-zoom; cursor: zoom-in; }
.stage.zoomed { touch-action: none; cursor: grab; }
.stage.zoomed:active { cursor: grabbing; }
.stage img { display: block; max-width: 100%; max-height: 82vh; width: auto; height: auto; transform-origin: center; user-select: none; -webkit-user-drag: none; }
.stage .missing { min-height: 50vh; font-size: 1rem; }
.viewer-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 1rem; margin-top: 0.6rem; font-size: 0.875rem; }
.segmented { display: inline-flex; border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; }
.segmented button { font: inherit; padding: 0.3rem 0.75rem; border: 0; background: transparent; color: var(--ink); cursor: pointer; }
.segmented button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.zoom { display: inline-flex; gap: 0.35rem; }
.zoom button { font: inherit; min-width: 2rem; height: 2rem; padding: 0 0.5rem; border: 1px solid var(--rule); border-radius: 6px; background: transparent; color: var(--ink); cursor: pointer; }
.credit { flex-basis: 100%; font-size: 0.8rem; color: var(--ink-2); }
.plate-text { max-width: var(--measure); }
.printed { font-family: var(--serif); font-size: 1.4rem; margin: 0; }
.printed-latin { font-family: var(--serif); font-style: italic; margin: 0 0 0.5rem; }
.note { border-left: 3px solid var(--accent); padding: 0.4rem 0 0.4rem 1rem; margin: 1.25rem 0; }
.ident { margin-bottom: 1rem; }
.ident + .ident { border-top: 1px solid var(--rule); padding-top: 1rem; }
.ident-name { font-family: var(--serif); font-size: 1.4rem; margin: 0; }
.sci { font-family: var(--serif); font-style: italic; font-size: 1.15rem; margin: 0 0 0.5rem; }
.facts { list-style: none; display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0; margin: 0.5rem 0; }
.facts li { font-size: 0.8rem; padding: 0.1rem 0.6rem; border: 1px solid var(--rule); border-radius: 999px; }
.outlinks { list-style: none; display: flex; flex-wrap: wrap; gap: 0.4rem 1.25rem; padding: 0; margin: 1rem 0; font-size: 0.9rem; }
.outlinks a::after { content: " ↗"; }
.elsewhere { margin-top: 3rem; }

.strip { list-style: none; display: flex; flex-wrap: wrap; align-items: flex-start; gap: 1.5rem; padding: 0; margin: 0; }
.strip li { width: min(100%, calc(var(--ar) * var(--strip-h))); }
.strip a { display: grid; gap: 0.5rem; text-decoration: none; }
.strip img, .strip .missing { display: block; width: 100%; height: auto; aspect-ratio: var(--ar); background: var(--tile); }
.strip-cap { display: grid; font-size: 0.85rem; line-height: 1.35; color: var(--ink-2); }
.strip-printed { font-family: var(--serif); font-size: 1rem; color: var(--ink); }

.species-filter { margin: 1rem 0 2rem; }
.families { columns: 17rem; column-gap: 2.5rem; }
.family { break-inside: avoid; margin-bottom: 1.5rem; }
.family h2 { font-size: 1.1rem; margin: 0 0 0.35rem; }
.family ul { list-style: none; padding: 0; margin: 0; font-size: 0.9rem; }
.family li { display: flex; justify-content: space-between; gap: 0.75rem; }
.family .n { color: var(--ink-2); font-variant-numeric: tabular-nums; }

.prose { max-width: var(--measure); padding-top: 2rem; }
.prose p, .prose li { font-size: 1.05rem; }
.prose h2 { margin-top: 2.5rem; }

@view-transition { navigation: auto; }
@media (prefers-reduced-motion: reduce) {
  @view-transition { navigation: none; }
  .cap { transition: none; }
}
```

- [ ] **Step 8: Build**

Run: `cd site && npm run build`
Expected:
- the build ends with `[build] Complete!`;
- `dist/index.html` exists and contains `<title>Historical bird plates</title>`, `rel="canonical" href="https://wr.github.io/historical-bird-plates/"` and an `og:image` pointing at `…/img/havell/1-crop.webp`;
- `dist/sitemap-index.xml` exists.

- [ ] **Step 9: Commit**

```bash
git add site/package.json site/package-lock.json site/astro.config.mjs site/tsconfig.json site/public site/src
git commit -m "Site: Astro skeleton, data access, search-engine metadata, layout and styles"
```

(`site/public/img/` is ignored, so `git add site/public` adds only the favicon and `robots.txt`.)

---

### Task 5: The wall, rendered at build time: home page, folio pages, `wall.json`

**Files:**
- Create:
  - `site/src/scripts/wall-core.ts`, `site/src/scripts/wall-core.test.ts`;
  - `site/src/components/Tile.astro`, `site/src/components/Filters.astro`, `site/src/components/Wall.astro`;
  - `site/src/pages/wall.json.ts`, `site/src/pages/[folio]/index.astro`.
- Modify: `site/src/lib/data.ts` (add `entries`), `site/src/pages/index.astro` (replace the placeholder).

**Interfaces:**
- Consumes: Task 4's `data.ts`, `seo.ts` and `Layout.astro`.
- Produces:
  - `wall-core.ts`:
    - types `Entry`, `Arrangement` (`"folio" | "taxonomy" | "colour"`), `State` (`{ q, folios, flags, arrange }`) and `Group` (`{ title, ids }`);
    - `FLAGS` (`{ m: "Misnamed", x: "Extinct", o: "Open question", s: "Several species" }`);
    - functions `fold`, `entryOf(p, i)`, `matches(e, state)`, `byColour`, `arrange(entries, how, titles, within?)`, `readState(search)`, `writeState(state)`, `isDefault(state)`, `plural(n, word)`.
  - `data.ts`: `entries: Entry[]`.
  - DOM contract for Task 6:
    - `[data-wall]` carries the attributes `data-index`, `data-titles` (JSON) and `data-folio`;
    - its children are `section.group > h2.group-title + div.rows > a.tile[data-id]`;
    - `form[data-controls]` holds `input[name=q]`, `select[name=arrange]`, `button.pill[data-folio|data-flag][aria-pressed]`, `[data-count]` and `input[name=size]`.

- [ ] **Step 1: Write the failing tests**

`site/src/scripts/wall-core.test.ts`:

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { arrange, entryOf, fold, matches, readState, writeState, type Entry, type State } from "./wall-core.ts";
import type { Plate } from "../lib/types.ts";

const plate = (over: Record<string, unknown> = {}) => ({
  id: "havell/121", folio: "havell", slug: "121", key: "121", volume: "", plate: "121", group: "", label: "Plate 121",
  printed: { name: "Snowy Owl", latin: "", caption: "", legend: "" },
  species: [{ figure: "", printed_name: "Snowy Owl", printed_latin: "", scientific: "Bubo scandiacus", common: "Snowy Owl",
    code: "snoowl1", slug: "snowy-owl", confidence: "high", form: "", caption_checked: "", reason: "", sources: "",
    wikidata: "", gbif: "", avibase: "", birdnet: "" }],
  misnamed: [], extinct: false, open: false, multi: false,
  taxon: { order: 9000, family: "Strigidae", family_common: "Owls", bird_order: "Strigiformes" },
  image: { thumb: [360, 480], crop: [1198, 1600], sheet: [666, 1000], colour: "#dfdedf", hue: null, light: 0.87 },
  scan: "", original: "", ...over,
}) as unknown as Plate;

const entry = (over: Partial<Entry>): Entry => ({ id: "a", i: 0, f: "havell", v: "", t: " ", fl: "", ord: null, fam: "", hue: null, light: 1, ...over });
const none: State = { q: "", folios: [], flags: [], arrange: "folio" };

test("fold drops accents, apostrophes and case, and spells grey gray", () => {
  assert.equal(fold("Rüppell’s  Grey Warbler!"), "ruppells gray warbler");
});

test("entryOf indexes printed and modern names, Latin and the eBird code", () => {
  const e = entryOf(plate({ printed: { name: "Black-headed Gull", latin: "Larus melanocephalus", caption: "", legend: "" } }), 7);
  assert.equal(e.i, 7);
  for (const words of ["black headed gull", "larus", "snowy owl", "bubo scandiacus", "snoowl1"]) assert.ok(e.t.includes(` ${words}`), words);
  assert.equal(e.fam, "Owls · Strigidae");
  assert.equal(e.hue, null);
});

test("entryOf writes its flags as letters", () => {
  assert.equal(entryOf(plate({ misnamed: [{ name: "x", code: "y" }], extinct: true, open: true, multi: true }), 0).fl, "mxos");
  assert.equal(entryOf(plate(), 0).fl, "");
});

test("every query word must match the start of a word", () => {
  const e = entry({ t: " snowy owl bubo scandiacus " });
  assert.ok(matches(e, { ...none, q: "snow ow" }));
  assert.ok(matches(e, { ...none, q: "  SCANDIACUS " }));
  assert.ok(!matches(e, { ...none, q: "nowy" }));
  assert.ok(!matches(e, { ...none, q: "snowy gull" }));
});

test("folios are alternatives; flags must all hold", () => {
  const e = entry({ f: "gould-asia", fl: "mo" });
  assert.ok(matches(e, { ...none, folios: ["havell", "gould-asia"] }));
  assert.ok(!matches(e, { ...none, folios: ["havell"] }));
  assert.ok(matches(e, { ...none, flags: ["m", "o"] }));
  assert.ok(!matches(e, { ...none, flags: ["m", "x"] }));
});

test("folio order groups by folio, and by volume within one folio", () => {
  const es = [entry({ id: "b", i: 1, f: "gould-asia", v: "Volume I" }), entry({ id: "a", i: 0 }), entry({ id: "c", i: 2, f: "gould-asia", v: "Volume II" })];
  const titles = { havell: "Audubon", "gould-asia": "Asia" };
  assert.deepEqual(arrange(es, "folio", titles), [{ title: "Audubon", ids: ["a"] }, { title: "Asia", ids: ["b", "c"] }]);
  assert.deepEqual(arrange([es[0], es[2]], "folio", titles, "gould-asia").map((g) => g.title), ["Volume I", "Volume II"]);
  assert.deepEqual(arrange([es[1]], "folio", titles, "havell").map((g) => g.title), ["Plates"]);
});

test("taxonomy follows eBird order and puts unidentified plates last", () => {
  const es = [entry({ id: "none", i: 0 }), entry({ id: "owl", i: 1, ord: 9000, fam: "Owls · Strigidae" }),
    entry({ id: "duck", i: 2, ord: 300, fam: "Ducks · Anatidae" }), entry({ id: "owl2", i: 3, ord: 9001, fam: "Owls · Strigidae" })];
  assert.deepEqual(arrange(es, "taxonomy", {}), [
    { title: "Ducks · Anatidae", ids: ["duck"] },
    { title: "Owls · Strigidae", ids: ["owl", "owl2"] },
    { title: "Not identified", ids: ["none"] },
  ]);
});

test("colour sorts by hue, then the colourless from light to dark", () => {
  const es = [entry({ id: "grey", light: 0.4 }), entry({ id: "green", hue: 90 }), entry({ id: "white", light: 0.9 }), entry({ id: "red", hue: 5 })];
  assert.deepEqual(arrange(es, "colour", {})[0].ids, ["red", "green", "white", "grey"]);
});

test("state survives the query string", () => {
  const s: State = { q: "owl", folios: ["havell"], flags: ["m"], arrange: "taxonomy" };
  assert.equal(writeState(s), "?q=owl&folio=havell&flag=m&arrange=taxonomy");
  assert.deepEqual(readState(writeState(s)), s);
  assert.equal(writeState(none), "");
  assert.deepEqual(readState("?arrange=nonsense&flag=z"), none);
});
```

Run: `cd site && npm test`
Expected: FAIL, because `wall-core.ts` can't be found.

- [ ] **Step 2: Write `site/src/scripts/wall-core.ts`**

```ts
import type { Plate } from "../lib/types";

/** One plate as the wall's script sees it: what to search, filter and sort it by. */
export interface Entry {
  id: string;
  i: number; // place in folio order, across all folios
  f: string; // folio id
  v: string; // "Volume I", "Supplement", or "" for folios numbered straight through
  t: string; // folded search text, padded with spaces so a query word can match a word's start
  fl: string; // flags: m misnamed, x extinct, o open question, s several species
  ord: number | null; // eBird taxonomic order of the first species
  fam: string; // "Owls · Strigidae"
  hue: number | null;
  light: number;
}

export type Arrangement = "folio" | "taxonomy" | "colour";

export interface State {
  q: string;
  folios: string[];
  flags: string[];
  arrange: Arrangement;
}

export interface Group {
  title: string;
  ids: string[];
}

export const FLAGS: Record<string, string> = { m: "Misnamed", x: "Extinct", o: "Open question", s: "Several species" };
const ARRANGEMENTS: Arrangement[] = ["folio", "taxonomy", "colour"];

/** Lower case, accents and apostrophes gone, grey spelled gray, anything else a single space. */
export function fold(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/grey/g, "gray").replace(/['’]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

export function entryOf(p: Plate, i: number): Entry {
  const words = [p.printed.name, p.printed.latin, p.printed.caption,
    ...p.species.flatMap((s) => [s.printed_name, s.printed_latin, s.common, s.scientific, s.code])];
  return {
    id: p.id,
    i,
    f: p.folio,
    v: p.group,
    t: ` ${fold([...new Set(words.filter(Boolean))].join(" "))} `,
    fl: (p.misnamed.length ? "m" : "") + (p.extinct ? "x" : "") + (p.open ? "o" : "") + (p.multi ? "s" : ""),
    ord: p.taxon ? p.taxon.order : null,
    fam: p.taxon ? `${p.taxon.family_common} · ${p.taxon.family}` : "",
    hue: p.image ? p.image.hue : null,
    light: p.image ? p.image.light : 1,
  };
}

export function matches(e: Entry, s: State): boolean {
  if (s.folios.length > 0 && !s.folios.includes(e.f)) return false;
  if (!s.flags.every((flag) => e.fl.includes(flag))) return false;
  return fold(s.q).split(" ").filter(Boolean).every((word) => e.t.includes(` ${word}`));
}

/** By hue; the colourless after, from light to dark. */
export function byColour(a: Entry, b: Entry): number {
  if ((a.hue === null) !== (b.hue === null)) return a.hue === null ? 1 : -1;
  if (a.hue !== null && b.hue !== null && a.hue !== b.hue) return a.hue - b.hue;
  return b.light - a.light || a.i - b.i;
}

function runs(sorted: Entry[], title: (e: Entry) => string): Group[] {
  const groups: Group[] = [];
  for (const e of sorted) {
    const t = title(e);
    const last = groups[groups.length - 1];
    if (last && last.title === t) last.ids.push(e.id);
    else groups.push({ title: t, ids: [e.id] });
  }
  return groups;
}

/** Sort the entries and cut them into titled groups. Within one folio, folio order groups by volume. */
export function arrange(entries: Entry[], how: Arrangement, titles: Record<string, string>, within: string | null = null): Group[] {
  if (how === "colour") return [{ title: "By colour", ids: [...entries].sort(byColour).map((e) => e.id) }];
  if (how === "taxonomy") {
    const sorted = [...entries].sort((a, b) => (a.ord ?? Infinity) - (b.ord ?? Infinity) || a.i - b.i);
    return runs(sorted, (e) => e.fam || "Not identified");
  }
  return runs([...entries].sort((a, b) => a.i - b.i), (e) => (within ? e.v || "Plates" : titles[e.f]));
}

export function readState(search: string): State {
  const p = new URLSearchParams(search);
  const how = p.get("arrange") as Arrangement;
  return {
    q: p.get("q") ?? "",
    folios: p.getAll("folio"),
    flags: p.getAll("flag").filter((f) => f in FLAGS),
    arrange: ARRANGEMENTS.includes(how) ? how : "folio",
  };
}

export function writeState(s: State): string {
  const p = new URLSearchParams();
  if (s.q.trim()) p.set("q", s.q.trim());
  for (const f of s.folios) p.append("folio", f);
  for (const f of s.flags) p.append("flag", f);
  if (s.arrange !== "folio") p.set("arrange", s.arrange);
  const query = p.toString();
  return query ? `?${query}` : "";
}

export const isDefault = (s: State): boolean => writeState(s) === "";

export const plural = (n: number, word: string): string => `${n.toLocaleString("en")} ${n === 1 ? word : `${word}s`}`;
```

Run: `cd site && npm test`
Expected: `# pass 16`, `# fail 0` (seven `seo` tests and nine `wall-core` tests).

- [ ] **Step 3: `entries` in `data.ts`, and the `wall.json` endpoint**

In `site/src/lib/data.ts`, add `import { entryOf } from "../scripts/wall-core";` under the first import, and after the `speciesByCode` line add:

```ts
export const entries = plates.map(entryOf);
```

`site/src/pages/wall.json.ts`:

```ts
import type { APIRoute } from "astro";
import { entries } from "../lib/data";

export const GET: APIRoute = () => new Response(JSON.stringify(entries), { headers: { "Content-Type": "application/json" } });
```

- [ ] **Step 4: `Tile.astro`, `Filters.astro`, `Wall.astro`**

`site/src/components/Tile.astro`:

```astro
---
import { folioOf, imageSrc, plateHref } from "../lib/data";
import { altText, norm, shown } from "../lib/seo";
import type { Plate } from "../lib/types";

interface Props {
  plate: Plate;
}
const { plate: p } = Astro.props;
const f = folioOf(p);
const img = p.image;
const ar = img ? img.thumb[0] / img.thumb[1] : 0.75;
const name = shown(p);
const printed = p.printed.name && norm(p.printed.name) !== norm(name) ? p.printed.name : "";
const style = `--ar:${ar.toFixed(4)}${img ? `;--c:${img.colour}` : ""}`;
---
<a class="tile" href={plateHref(p)} data-id={p.id} style={style}>
  {img ? (
    <img
      src={imageSrc(p, "thumb")}
      srcset={`${imageSrc(p, "thumb")} ${img.thumb[0]}w, ${imageSrc(p, "crop")} ${img.crop[0]}w`}
      sizes="auto, 240px"
      width={img.thumb[0]}
      height={img.thumb[1]}
      alt={altText(p, f)}
      loading="lazy"
      decoding="async"
    />
  ) : (
    <span class="missing">{f.short} {p.key}: not yet in the image release</span>
  )}
  <span class="cap" aria-hidden="true">
    <span class="cap-name">{name}</span>
    {printed && <span>Printed “{printed}”</span>}
    <span>{f.short} {p.key}</span>
  </span>
</a>
```

`site/src/components/Filters.astro`:

```astro
---
import { FLAGS, plural } from "../scripts/wall-core";
import type { Folio } from "../lib/types";

interface Props {
  folios: Folio[];
  count: number;
  showFolios?: boolean;
}
const { folios, count, showFolios = true } = Astro.props;
---
<form class="controls" data-controls role="search">
  <label>
    <span class="sr-only">Search the plates</span>
    <input type="search" name="q" placeholder="Snowy owl, Strix, snoowl1" autocomplete="off" spellcheck="false" />
  </label>
  <label class="arrange">
    <span>Arrange</span>
    <select name="arrange">
      <option value="folio">{showFolios ? "By folio" : "In plate order"}</option>
      <option value="taxonomy">By family</option>
      <option value="colour">By colour</option>
    </select>
  </label>
  <div class="pills" role="group" aria-label="Filters">
    {showFolios && folios.map((f) => (
      <button type="button" class="pill" data-folio={f.id} aria-pressed="false">{f.short}</button>
    ))}
    {Object.entries(FLAGS).map(([flag, label]) => (
      <button type="button" class="pill" data-flag={flag} aria-pressed="false">{label}</button>
    ))}
  </div>
  <div class="status">
    <p data-count aria-live="polite">{plural(count, "plate")}</p>
    <label>Tile size <input type="range" name="size" min="100" max="360" step="20" value="180" /></label>
  </div>
</form>
```

`site/src/components/Wall.astro`:

```astro
---
import Tile from "./Tile.astro";
import { entries, folios, href, plateById } from "../lib/data";
import { arrange, plural } from "../scripts/wall-core";
import type { Folio } from "../lib/types";

interface Props {
  folio?: Folio;
}
const { folio } = Astro.props;
const titles = Object.fromEntries(folios.map((f) => [f.id, f.cite]));
const mine = folio ? entries.filter((e) => e.f === folio.id) : entries;
const groups = arrange(mine, "folio", titles, folio?.id ?? null);
---
<div class="wall" data-wall data-index={href("wall.json")} data-titles={JSON.stringify(titles)} data-folio={folio?.id ?? ""}>
  {groups.map((g) => (
    <section class="group">
      <h2 class="group-title">{g.title} <span class="group-count">{plural(g.ids.length, "plate")}</span></h2>
      <div class="rows">{g.ids.map((id) => <Tile plate={plateById.get(id)!} />)}</div>
    </section>
  ))}
</div>
```

- [ ] **Step 5: The home page and folio pages**

Replace `site/src/pages/index.astro`:

```astro
---
import Layout from "../layouts/Layout.astro";
import Filters from "../components/Filters.astro";
import Wall from "../components/Wall.astro";
import { absolute, folios, href, plates } from "../lib/data";

const description = `${plates.length.toLocaleString("en")} plates from Audubon's Birds of America and Gould's Europe, Australia, Asia and Great Britain, each identified to modern species, with the reasoning.`;
const jsonld = { "@context": "https://schema.org", "@type": "WebSite", name: "Historical bird plates", url: absolute(href()), description };
---
<Layout title="Historical bird plates" description={description} jsonld={jsonld}>
  <header class="intro">
    <h1>Historical bird plates</h1>
    <p class="lede">Every plate of five great nineteenth-century bird folios, identified to modern species. Old plates name their birds the way their authors did, and many of those names now belong to other birds.</p>
  </header>
  <Filters folios={folios} count={plates.length} />
  <Wall />
</Layout>
```

`site/src/pages/[folio]/index.astro`:

```astro
---
import Layout from "../../layouts/Layout.astro";
import Filters from "../../components/Filters.astro";
import Wall from "../../components/Wall.astro";
import { absolute, folios, imageSrc, plates } from "../../lib/data";
import { REPO } from "../../lib/links";
import { clip } from "../../lib/seo";
import type { Folio } from "../../lib/types";

export function getStaticPaths() {
  return folios.map((f) => ({ params: { folio: f.id }, props: { f } }));
}

interface Props {
  f: Folio;
}
const { f } = Astro.props;
const cover = plates.find((p) => p.folio === f.id && p.image);
---
<Layout
  title={`${f.cite} (${f.years}) · Historical bird plates`}
  description={clip(`${f.plates} plates of ${f.author}'s ${f.title} (${f.years}), each identified to modern species. ${f.intro}`)}
  image={cover && absolute(imageSrc(cover, "crop"))}
>
  <header class="folio-head">
    <p class="eyebrow">{f.author}</p>
    <h1><i>{f.title}</i></h1>
    <p class="years">{f.years} · {f.plates} plates</p>
    <p>{f.intro}</p>
    <p class="small">Scans: {f.credit}</p>
    <ul class="outlinks">
      <li><a href={f.readme}>How the plates were identified</a></li>
      <li><a href={`${REPO}/tree/main/${f.id}`}>Tables</a></li>
      <li><a href={f.images}>Full-size images</a></li>
    </ul>
  </header>
  <Filters folios={folios} count={f.plates} showFolios={false} />
  <Wall folio={f} />
</Layout>
```

- [ ] **Step 6: Build and check the output**

Run: `cd site && npm run build`
Expected:
- the build completes, with six HTML pages (the home page and five folio pages) plus `wall.json`;
- `dist/wall.json` parses and is an array of 2,462 entries;
- `grep -c 'class="tile"' dist/index.html` prints `2462`;
- `grep -c 'class="tile"' dist/gould-asia/index.html` prints `530`;
- `dist/gould-asia/index.html` contains `Volume VII`.

An endpoint with a file extension is exempt from `trailingSlash: "always"`; this was checked on Astro 7.3.5 while planning.

- [ ] **Step 7: Commit**

```bash
git add site/src
git commit -m "Site: the wall of every plate, and a page per folio"
```

---

### Task 6: The wall's filters, search and arrangements in the browser

**Files:**
- Create: `site/src/scripts/wall.ts`
- Modify: `site/src/components/Wall.astro` (load the script)

**Interfaces:**
- Consumes: Task 5's DOM contract, `wall-core.ts` and `/wall.json`.
- Produces: no exports. The behaviour:
  - the URL keeps `q`, `folio`, `flag` and `arrange`;
  - the tile size is remembered in `localStorage` under `row-h`;
  - a clicked tile's image takes `view-transition-name: plate`.

- [ ] **Step 1: Write `site/src/scripts/wall.ts`**

```ts
import { arrange, isDefault, matches, plural, readState, writeState, type Entry, type State } from "./wall-core";

const wall = document.querySelector<HTMLElement>("[data-wall]");
const form = document.querySelector<HTMLFormElement>("[data-controls]");
if (wall && form) void start(wall, form);

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // private browsing: the size just isn't remembered
  }
}

async function start(wall: HTMLElement, form: HTMLFormElement): Promise<void> {
  const scope = wall.dataset.folio || null;
  const titles = JSON.parse(wall.dataset.titles ?? "{}") as Record<string, string>;
  const all = (await (await fetch(wall.dataset.index!)).json()) as Entry[];
  const entries = scope ? all.filter((e) => e.f === scope) : all;
  const tiles = new Map(Array.from(wall.querySelectorAll<HTMLElement>(".tile"), (t) => [t.dataset.id!, t]));
  const q = form.elements.namedItem("q") as HTMLInputElement;
  const how = form.elements.namedItem("arrange") as HTMLSelectElement;
  const size = form.elements.namedItem("size") as HTMLInputElement;
  const count = form.querySelector<HTMLElement>("[data-count]")!;
  const pills = Array.from(form.querySelectorAll<HTMLButtonElement>(".pill"));

  let state: State = readState(location.search);
  if (scope) state = { ...state, folios: [] };

  const pressed = (pill: HTMLButtonElement): boolean =>
    pill.dataset.folio ? state.folios.includes(pill.dataset.folio) : state.flags.includes(pill.dataset.flag!);
  const syncControls = (): void => {
    q.value = state.q;
    how.value = state.arrange;
    for (const pill of pills) pill.setAttribute("aria-pressed", String(pressed(pill)));
  };

  const section = (title: string, items: HTMLElement[]): HTMLElement => {
    const s = document.createElement("section");
    s.className = "group";
    const h = document.createElement("h2");
    h.className = "group-title";
    const n = document.createElement("span");
    n.className = "group-count";
    n.textContent = plural(items.length, "plate");
    h.append(`${title} `, n);
    const rows = document.createElement("div");
    rows.className = "rows";
    rows.append(...items);
    s.append(h, rows);
    return s;
  };

  const empty = (): HTMLElement => {
    const p = document.createElement("p");
    p.className = "empty";
    const clear = document.createElement("a");
    clear.href = location.pathname;
    clear.textContent = "Clear filters";
    clear.addEventListener("click", (e) => {
      e.preventDefault();
      state = { q: "", folios: [], flags: [], arrange: state.arrange };
      syncControls();
      render();
    });
    p.append("No plates match. ", clear);
    return p;
  };

  function render(): void {
    const visible = entries.filter((e) => matches(e, state));
    const out = document.createDocumentFragment();
    for (const g of arrange(visible, state.arrange, titles, scope)) out.append(section(g.title, g.ids.map((id) => tiles.get(id)!)));
    if (!visible.length) out.append(empty());
    wall.replaceChildren(out);
    count.textContent = plural(visible.length, "plate");
    history.replaceState(history.state, "", location.pathname + writeState(state) + location.hash);
  }

  const setRow = (): void => wall.style.setProperty("--row-h", `${size.value}px`);
  const saved = stored("row-h");
  if (saved) {
    size.value = saved;
    setRow();
  } else {
    size.value = String(parseInt(getComputedStyle(wall).getPropertyValue("--row-h"), 10) || 180);
  }

  let timer = 0;
  q.addEventListener("input", () => {
    clearTimeout(timer);
    timer = window.setTimeout(() => {
      state = { ...state, q: q.value };
      render();
    }, 120);
  });
  how.addEventListener("change", () => {
    state = { ...state, arrange: how.value as State["arrange"] };
    render();
  });
  for (const pill of pills) {
    pill.addEventListener("click", () => {
      const on = pill.getAttribute("aria-pressed") !== "true";
      pill.setAttribute("aria-pressed", String(on));
      if (pill.dataset.folio) {
        const v = pill.dataset.folio;
        state = { ...state, folios: on ? [...state.folios, v] : state.folios.filter((x) => x !== v) };
      } else {
        const v = pill.dataset.flag!;
        state = { ...state, flags: on ? [...state.flags, v] : state.flags.filter((x) => x !== v) };
      }
      render();
    });
  }
  size.addEventListener("input", () => {
    setRow();
    store("row-h", size.value);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  wall.addEventListener("click", (e) => {
    const tile = (e.target as HTMLElement).closest<HTMLElement>(".tile");
    if (!tile) return;
    for (const img of wall.querySelectorAll<HTMLImageElement>("img")) img.style.viewTransitionName = "";
    const img = tile.querySelector("img");
    if (img) img.style.viewTransitionName = "plate";
  });

  syncControls();
  if (!isDefault(state)) render();
}
```

- [ ] **Step 2: Load it from `Wall.astro`**

Append to `site/src/components/Wall.astro`, after the closing `</div>`:

```astro
<script>
  import "../scripts/wall";
</script>
```

- [ ] **Step 3: Build, run tests, try it in the browser**

Run: `cd site && npm test && npm run build`. Expected: both succeed.

Start the preview. Create `.claude/launch.json` if it is missing:

```json
{ "version": "0.0.1", "configurations": [{ "name": "site", "runtimeExecutable": "npm", "runtimeArgs": ["--prefix", "site", "run", "preview"], "port": 4321 }] }
```

`.claude/` stays out of the commit. Use `preview_start` with name `site`, then open `http://localhost:4321/historical-bird-plates/`. Check each of these:
1. Type `owl`. The count drops; every tile shown is an owl or has "owl" in a name; the URL becomes `?q=owl`.
2. Press *Misnamed* on its own. The count reads `62 plates`.
3. Arrange *By family*. Family headings appear, such as `Owls · Strigidae`, with *Not identified* last.
4. Arrange *By colour*. One group, running from red through green to grey.
5. Reload with `?flag=m&arrange=taxonomy`. The state is restored: the pill is pressed and the select shows *By family*.
6. Drag the tile size slider. The rows change height and the setting survives a reload.
7. Open `/historical-bird-plates/gould-asia/`. There are no folio pills; *In plate order* groups by volume; *By family* works.

Check `read_console_messages` for errors: there should be none.

- [ ] **Step 4: Commit**

```bash
git add site/src/scripts/wall.ts site/src/components/Wall.astro
git commit -m "Site: search, filters and arrangements on the wall"
```

---

### Task 7: Plate pages

**Files:**
- Create:
  - `site/src/components/PlateViewer.astro`, `site/src/components/SpeciesBlock.astro`, `site/src/components/PlateStrip.astro`;
  - `site/src/scripts/viewer.ts`, `site/src/scripts/pager.ts`;
  - `site/src/pages/[folio]/[plate].astro`.

**Interfaces:**
- Consumes: `data.ts`, `seo.ts`, `links.ts`, `Layout.astro`.
- Produces:
  - `PlateStrip.astro`, with props `{ plates: Plate[]; height: number }`, which Task 8 uses;
  - plate pages at `/<folio>/<slug>/`;
  - prev and next links marked `rel="prev"` and `rel="next"`.

- [ ] **Step 1: `PlateStrip.astro`**

```astro
---
import { folioOf, imageSrc, plateHref } from "../lib/data";
import { altText } from "../lib/seo";
import type { Plate } from "../lib/types";

interface Props {
  plates: Plate[];
  height: number;
}
const { plates, height } = Astro.props;
---
<ul class="strip" style={`--strip-h:${height}px`}>
  {plates.map((p) => {
    const f = folioOf(p);
    const ar = p.image ? p.image.thumb[0] / p.image.thumb[1] : 0.75;
    return (
      <li style={`--ar:${ar.toFixed(4)}`}>
        <a href={plateHref(p)}>
          {p.image ? (
            <img
              src={imageSrc(p, "thumb")}
              srcset={`${imageSrc(p, "thumb")} ${p.image.thumb[0]}w, ${imageSrc(p, "crop")} ${p.image.crop[0]}w`}
              sizes={`${Math.round(ar * height)}px`}
              width={p.image.thumb[0]}
              height={p.image.thumb[1]}
              alt={altText(p, f)}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span class="missing">Not yet in the image release</span>
          )}
          <span class="strip-cap">
            <span>{f.short}, {f.years}</span>
            <span>{p.label}</span>
            {p.printed.name && <span class="strip-printed">“{p.printed.name}”</span>}
          </span>
        </a>
      </li>
    );
  })}
</ul>
```

- [ ] **Step 2: `SpeciesBlock.astro`**

```astro
---
import { speciesByCode, speciesHref } from "../lib/data";
import { outlinks } from "../lib/links";
import type { Identification } from "../lib/types";

interface Props {
  s: Identification;
  several: boolean;
}
const { s, several } = Astro.props;
const sp = s.code ? speciesByCode.get(s.code) : undefined;
const CONFIDENCE: Record<string, string> = {
  high: "Certain", judged: "Judged", medium: "Open, leaning", low: "Open, uncertain", none: "Not identified",
};
const FORM: Record<string, string> = {
  subspecies: "Shown as a subspecies", variant: "A variant", "pre-split": "Drawn before a split",
};
---
<div class="ident">
  {several && s.figure && <p class="eyebrow">Figure {s.figure}</p>}
  {several && s.printed_name && <p class="small">Printed “{s.printed_name}”</p>}
  <p class="ident-name">{sp ? <a href={speciesHref(sp)}>{s.common}</a> : "Not identified"}</p>
  {s.scientific && <p class="sci">{s.scientific}</p>}
  <ul class="facts">
    {CONFIDENCE[s.confidence] && <li>{CONFIDENCE[s.confidence]}</li>}
    {s.form && <li>{FORM[s.form] ?? s.form}</li>}
    {s.caption_checked === "yes" && <li>Checked against the engraved caption</li>}
    {sp && <li>{sp.family_common} · <i>{sp.family}</i></li>}
    {sp?.extinct && <li>Extinct</li>}
  </ul>
  {s.reason && <><h3>Why</h3><p>{s.reason}</p></>}
  {s.sources && <><h3>Sources</h3><p class="small">{s.sources}</p></>}
  {sp && <ul class="outlinks">{outlinks(s).map((l) => <li><a href={l.href}>{l.label}</a></li>)}</ul>}
</div>
```

- [ ] **Step 3: `PlateViewer.astro` and `viewer.ts`**

`site/src/components/PlateViewer.astro`:

```astro
---
import { imageSrc } from "../lib/data";
import { altText } from "../lib/seo";
import type { Folio, Plate } from "../lib/types";

interface Props {
  plate: Plate;
  folio: Folio;
}
const { plate: p, folio: f } = Astro.props;
const img = p.image!;
---
<figure class="viewer" data-viewer>
  <div class="stage" data-stage>
    <img data-cut="crop" src={imageSrc(p, "crop")} width={img.crop[0]} height={img.crop[1]} alt={altText(p, f)}
      fetchpriority="high" draggable="false" style="view-transition-name: plate" />
    <img data-cut="sheet" src={imageSrc(p, "sheet")} width={img.sheet[0]} height={img.sheet[1]}
      alt={`The whole sheet of ${p.label.toLowerCase()}, with its engraved caption`} loading="lazy" draggable="false" hidden />
  </div>
  <figcaption class="viewer-bar">
    <span class="segmented" role="group" aria-label="Show">
      <button type="button" data-show="crop" aria-pressed="true">Plate</button>
      <button type="button" data-show="sheet" aria-pressed="false">Full sheet</button>
    </span>
    <span class="zoom" role="group" aria-label="Zoom">
      <button type="button" data-zoom="out" aria-label="Zoom out">−</button>
      <button type="button" data-zoom="in" aria-label="Zoom in">+</button>
      <button type="button" data-zoom="reset" hidden>Reset</button>
    </span>
    {p.original && <a href={p.original}>Full resolution</a>}
    <span class="credit">{f.credit}</span>
  </figcaption>
</figure>
<script>
  import "../scripts/viewer";
</script>
```

`site/src/scripts/viewer.ts`:

```ts
/** Zoom and pan on the plate. Pinch, ctrl- or ⌘-scroll, double-click and the buttons zoom; drag pans. */
for (const root of document.querySelectorAll<HTMLElement>("[data-viewer]")) viewer(root);

function viewer(root: HTMLElement): void {
  const stage = root.querySelector<HTMLElement>("[data-stage]")!;
  const reset = root.querySelector<HTMLButtonElement>("[data-zoom=reset]")!;
  const pointers = new Map<number, { x: number; y: number }>();
  let scale = 1;
  let x = 0;
  let y = 0;

  const image = (): HTMLImageElement => stage.querySelector<HTMLImageElement>("img:not([hidden])")!;
  const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));

  function apply(): void {
    const img = image();
    const mx = ((scale - 1) * img.offsetWidth) / 2;
    const my = ((scale - 1) * img.offsetHeight) / 2;
    x = clamp(x, -mx, mx);
    y = clamp(y, -my, my);
    img.style.transform = scale === 1 ? "" : `translate(${x}px, ${y}px) scale(${scale})`;
    stage.classList.toggle("zoomed", scale > 1);
    reset.hidden = scale === 1;
  }

  /** Zoom by factor, keeping the point under (cx, cy) where it is. */
  function zoomAt(factor: number, cx: number, cy: number): void {
    const img = image();
    const r = stage.getBoundingClientRect();
    const px = cx - (r.left + img.offsetLeft + img.offsetWidth / 2);
    const py = cy - (r.top + img.offsetTop + img.offsetHeight / 2);
    const next = clamp(scale * factor, 1, 8);
    x = px - ((px - x) * next) / scale;
    y = py - ((py - y) * next) / scale;
    scale = next;
    if (scale === 1) x = y = 0;
    apply();
  }

  const centre = (): [number, number] => {
    const r = stage.getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2];
  };

  stage.addEventListener("wheel", (e) => {
    if (!e.ctrlKey && !e.metaKey) return; // plain scrolling scrolls the page; a trackpad pinch arrives with ctrlKey
    e.preventDefault();
    zoomAt(Math.exp(-clamp(e.deltaY, -50, 50) * 0.01), e.clientX, e.clientY);
  }, { passive: false });
  stage.addEventListener("dblclick", (e) => zoomAt(scale > 1 ? 1 / scale : 2.5, e.clientX, e.clientY));
  stage.addEventListener("pointerdown", (e) => {
    if (scale === 1 && e.pointerType !== "mouse") return; // let a finger scroll the page
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener("pointermove", (e) => {
    const last = pointers.get(e.pointerId);
    if (!last) return;
    if (pointers.size === 1 && scale > 1) {
      x += e.clientX - last.x;
      y += e.clientY - last.y;
      apply();
    } else if (pointers.size === 2) {
      const other = [...pointers.entries()].find(([id]) => id !== e.pointerId)![1];
      const before = Math.hypot(last.x - other.x, last.y - other.y);
      const after = Math.hypot(e.clientX - other.x, e.clientY - other.y);
      if (before > 0) zoomAt(after / before, (e.clientX + other.x) / 2, (e.clientY + other.y) / 2);
    }
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  });
  for (const type of ["pointerup", "pointercancel"] as const) stage.addEventListener(type, (e) => pointers.delete(e.pointerId));

  root.querySelector("[data-zoom=in]")!.addEventListener("click", () => zoomAt(1.6, ...centre()));
  root.querySelector("[data-zoom=out]")!.addEventListener("click", () => zoomAt(1 / 1.6, ...centre()));
  reset.addEventListener("click", () => zoomAt(1 / scale, ...centre()));

  for (const button of root.querySelectorAll<HTMLButtonElement>("[data-show]")) {
    button.addEventListener("click", () => {
      image().style.transform = "";
      scale = 1;
      x = y = 0;
      for (const img of stage.querySelectorAll<HTMLImageElement>("img")) img.hidden = img.dataset.cut !== button.dataset.show;
      for (const b of root.querySelectorAll<HTMLButtonElement>("[data-show]")) b.setAttribute("aria-pressed", String(b === button));
      apply();
    });
  }
  window.addEventListener("resize", apply);
}
```

`site/src/scripts/pager.ts`:

```ts
/** ← and → go to the previous and next plate. */
document.addEventListener("keydown", (e) => {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented) return;
  if ((e.target as HTMLElement).closest("input, select, textarea, [contenteditable]")) return;
  const rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : "";
  const link = rel ? document.querySelector<HTMLAnchorElement>(`a[rel="${rel}"]`) : null;
  if (link) location.href = link.href;
});
```

- [ ] **Step 4: The plate page, `site/src/pages/[folio]/[plate].astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
import PlateStrip from "../../components/PlateStrip.astro";
import PlateViewer from "../../components/PlateViewer.astro";
import SpeciesBlock from "../../components/SpeciesBlock.astro";
import { absolute, folioHref, folioOf, href, imageSrc, plateById, plateHref, plates, speciesByCode, speciesHref } from "../../lib/data";
import { REPO } from "../../lib/links";
import { identified, norm, plateDescription, plateJsonLd, plateTitle, shown } from "../../lib/seo";
import type { Plate } from "../../lib/types";

export function getStaticPaths() {
  return plates.map((p, i) => {
    const prev = plates[i - 1];
    const next = plates[i + 1];
    return {
      params: { folio: p.folio, plate: p.slug },
      props: { p, prev: prev?.folio === p.folio ? prev : undefined, next: next?.folio === p.folio ? next : undefined },
    };
  });
}

interface Props {
  p: Plate;
  prev?: Plate;
  next?: Plate;
}
const { p, prev, next } = Astro.props;
const f = folioOf(p);
const url = absolute(plateHref(p));
const image = p.image ? absolute(imageSrc(p, "crop")) : undefined;
const ids = identified(p);
const others = [...new Set(ids.flatMap((s) => speciesByCode.get(s.code)!.plates))]
  .filter((id) => id !== p.id)
  .map((id) => plateById.get(id)!);
const printedDiffers = ids.length > 0 && p.printed.name && norm(p.printed.name) !== norm(shown(p));
const scanLabel = f.id === "havell" ? "The plate at audubon.org" : "The scan at the Biodiversity Heritage Library";
const issue = `${REPO}/issues/new?title=${encodeURIComponent(`${f.short} ${p.key}: ${p.printed.name}`)}`;
---
<Layout title={plateTitle(p, f)} description={plateDescription(p, f)} image={image} jsonld={plateJsonLd(p, f, url, image)}>
  <nav class="crumbs" aria-label="Breadcrumb">
    <span><a href={href()}>Plates</a> / <a href={folioHref(f)}>{f.cite}</a> / <span aria-current="page">{p.label}</span></span>
    <span class="pager">
      {prev && <a rel="prev" href={plateHref(prev)}>← {prev.key}</a>}
      {next && <a rel="next" href={plateHref(next)}>{next.key} →</a>}
    </span>
  </nav>
  <header class="plate-head">
    <p class="eyebrow">{f.cite} · {p.label}{!p.group && p.volume ? `, volume ${p.volume}` : ""}</p>
    <h1>{ids.length ? shown(p) : `“${p.printed.name}”`}</h1>
    {printedDiffers && <p class="printed-as">Printed “{p.printed.name}”</p>}
    {!ids.length && <p class="printed-as">Not identified</p>}
  </header>
  <article class="plate">
    {p.image ? <PlateViewer plate={p} folio={f} /> : (
      <div class="viewer"><div class="stage"><p class="missing">This plate is not yet in the image release. <a href={p.scan}>{scanLabel}</a>.</p></div></div>
    )}
    <div class="plate-text">
      <section>
        <h2 class="eyebrow">Printed on the plate</h2>
        {p.printed.name && <p class="printed">“{p.printed.name}”</p>}
        {p.printed.latin && <p class="printed-latin">{p.printed.latin}</p>}
        {p.printed.caption && <p class="small">Engraved caption: {p.printed.caption}</p>}
        {p.printed.legend && <p class="small">{p.printed.legend}</p>}
      </section>
      {p.misnamed.length > 0 && (
        <p class="note">The printed name is now eBird's name for another bird: {p.misnamed.map((m, i) => {
          const s = speciesByCode.get(m.code);
          return <>{i > 0 && " and "}{s ? <a href={speciesHref(s)}>{m.name}</a> : m.name}</>;
        })}.</p>
      )}
      {p.open && (
        <p class="note">This identification is still open; the reasoning below says what would settle it. If you can, <a href={issue}>open an issue</a> with the evidence.</p>
      )}
      <section>
        <h2 class="eyebrow">Modern identification</h2>
        {p.species.map((s) => <SpeciesBlock s={s} several={p.species.length > 1} />)}
      </section>
      {p.scan && <ul class="outlinks"><li><a href={p.scan}>{scanLabel}</a></li></ul>}
    </div>
  </article>
  {others.length > 0 && (
    <section class="elsewhere">
      <h2>The same {ids.length > 1 ? "birds" : "bird"} on other plates</h2>
      <PlateStrip plates={others} height={200} />
    </section>
  )}
  <script>
    import "../../scripts/pager";
  </script>
</Layout>
```

- [ ] **Step 5: Build and check**

Run: `cd site && npm run build`
Expected:
- 2,462 plate pages;
- `dist/havell/121/index.html` has `<title>Snowy Owl · Audubon, The Birds of America, plate 121</title>` and `"@type":"VisualArtwork"`;
- `dist/gould-europe/427/index.html` contains `“Black-headed Gull” (Mediterranean Gull)` and links to `/historical-bird-plates/species/black-headed-gull/` (a link that breaks until Task 8 adds the species pages);
- `dist/gould-europe/132/index.html` contains `not yet in the image release`.

In the preview, check each of these:
1. `/havell/121/`: the image is visible. Double-click zooms; drag pans; *Reset* returns. *Full sheet* shows the caption. ← and → move between plates.
2. `/havell/399/`: three species blocks, each with *Figure* and its printed name.
3. `/havell/11/`: the heading is “Bird of Washington”, with *Not identified* and the open-question note.
4. Clicking a tile on the wall morphs into the plate image (Chrome and Safari).

- [ ] **Step 6: Commit**

```bash
git add site/src
git commit -m "Site: a page per plate, with a zoomable viewer"
```

---

### Task 8: Species pages and the species index

**Files:**
- Create: `site/src/pages/species/[slug].astro`, `site/src/pages/species/index.astro`

**Interfaces:**
- Consumes: `PlateStrip.astro`, `data.ts`, `seo.ts`, `links.ts` and `wall-core.ts`'s `fold` and `plural`.
- Produces: `/species/<slug>/` for all 1,762 species, and `/species/`.

- [ ] **Step 1: `site/src/pages/species/[slug].astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
import PlateStrip from "../../components/PlateStrip.astro";
import { absolute, folioOf, href, imageSrc, plateById, species, speciesHref } from "../../lib/data";
import { outlinks } from "../../lib/links";
import { speciesDescription, speciesJsonLd, speciesTitle } from "../../lib/seo";
import { plural } from "../../scripts/wall-core";
import type { Species } from "../../lib/types";

export function getStaticPaths() {
  return species.map((s) => ({ params: { slug: s.slug }, props: { s } }));
}

interface Props {
  s: Species;
}
const { s } = Astro.props;
const shownOn = s.plates.map((id) => plateById.get(id)!);
const printedAs = s.printed_as.map((id) => plateById.get(id)!);
const inFolios = [...new Set(shownOn.map(folioOf))];
const cover = shownOn.find((p) => p.image);
const image = cover ? absolute(imageSrc(cover, "crop")) : undefined;
---
<Layout title={speciesTitle(s)} description={speciesDescription(s, inFolios)} image={image} jsonld={speciesJsonLd(s, absolute(speciesHref(s)), image)}>
  <nav class="crumbs" aria-label="Breadcrumb">
    <span><a href={href()}>Plates</a> / <a href={href("species/")}>Species</a> / <span aria-current="page">{s.common}</span></span>
  </nav>
  <header class="plate-head">
    <p class="eyebrow">{s.family_common} · {s.family} · {s.order}</p>
    <h1>{s.common}</h1>
    <p class="sci">{s.scientific}</p>
    <p>{plural(shownOn.length, "plate")} in {plural(inFolios.length, "folio")}.{s.extinct && " Extinct."}</p>
  </header>
  <PlateStrip plates={shownOn} height={320} />
  {printedAs.length > 0 && (
    <section class="elsewhere">
      <h2>Printed as the {s.common}, but showing another bird</h2>
      <PlateStrip plates={printedAs} height={200} />
    </section>
  )}
  <ul class="outlinks">{outlinks(s).map((l) => <li><a href={l.href}>{l.label}</a></li>)}</ul>
</Layout>
```

- [ ] **Step 2: `site/src/pages/species/index.astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
import { species, speciesHref } from "../../lib/data";
import { fold, plural } from "../../scripts/wall-core";
import type { Species } from "../../lib/types";

const families: { family: string; common: string; list: Species[] }[] = [];
for (const s of species) {
  const last = families[families.length - 1];
  if (last && last.family === s.family) last.list.push(s);
  else families.push({ family: s.family, common: s.family_common, list: [s] });
}
---
<Layout title="Species · Historical bird plates" description={`${plural(species.length, "species")} in ${families.length} families, from Audubon's and Gould's plates, in eBird taxonomic order.`}>
  <header class="intro">
    <h1>Species</h1>
    <p class="lede">{species.length.toLocaleString("en")} species in {families.length} families, in eBird taxonomic order. The number is how many plates show each one.</p>
  </header>
  <label class="species-filter js-only">
    <span class="sr-only">Filter the species</span>
    <input type="search" data-species-filter placeholder="Owl, Strigidae, Bubo" autocomplete="off" />
  </label>
  <div class="families">
    {families.map((fam) => (
      <section class="family" data-family>
        <h2>{fam.common} <i class="small">{fam.family}</i></h2>
        <ul>
          {fam.list.map((s) => (
            <li data-text={` ${fold(`${s.common} ${s.scientific} ${s.family} ${s.family_common} ${s.code}`)} `}>
              <a href={speciesHref(s)}>{s.common}</a>
              <span class="n">{s.plates.length}</span>
            </li>
          ))}
        </ul>
      </section>
    ))}
  </div>
  <script>
    import { fold } from "../../scripts/wall-core";

    const input = document.querySelector<HTMLInputElement>("[data-species-filter]")!;
    const families = Array.from(document.querySelectorAll<HTMLElement>("[data-family]"));
    input.addEventListener("input", () => {
      const words = fold(input.value).split(" ").filter(Boolean);
      for (const family of families) {
        let any = false;
        for (const li of family.querySelectorAll<HTMLElement>("li")) {
          const hit = words.every((w) => li.dataset.text!.includes(` ${w}`));
          li.hidden = !hit;
          any ||= hit;
        }
        family.hidden = !any;
      }
    });
  </script>
</Layout>
```

- [ ] **Step 3: Build and check**

Run: `cd site && npm run build`
Expected:
- 1,762 species pages;
- `dist/species/snowy-owl/index.html` has its plates in folio order, with Audubon first;
- `dist/species/black-headed-gull/index.html` has the heading *Printed as the Black-headed Gull, but showing another bird*, with Europe 427 in that strip.

In the preview, check `/species/` filters as you type (for example `strig`).

- [ ] **Step 4: Commit**

```bash
git add site/src/pages/species
git commit -m "Site: a page per species, and the species index"
```

---

### Task 9: About and 404

**Files:**
- Create: `site/src/pages/about.astro`, `site/src/pages/404.astro`

**Interfaces:**
- Consumes: `Layout.astro`, `data.ts` and `links.ts`.
- Produces: `/about/` and `404.html`.

- [ ] **Step 1: `site/src/pages/about.astro`**

```astro
---
import Layout from "../layouts/Layout.astro";
import { folios, href, plates } from "../lib/data";
import { REPO } from "../lib/links";

const misnamed = plates.filter((p) => p.misnamed.length).length;
const open = plates.filter((p) => p.open).length;
---
<Layout title="About · Historical bird plates" description={`How ${plates.length.toLocaleString("en")} plates from Audubon's and Gould's folios were identified to modern species, how to get the data, and how to cite it.`}>
  <article class="prose">
    <h1>About</h1>
    <p class="lede">Every plate of five great nineteenth-century bird folios, matched to the bird it actually shows, in today's taxonomy, with the reasoning.</p>
    <p>Old plates name their birds the way their authors did, and many of those names now belong to other species: Gould's “Black-headed Gull” is today's Mediterranean Gull. {misnamed} plates carry a printed name that eBird now gives to a different bird. <a href={href("?flag=m")}>See them on the wall</a>.</p>

    <h2>How the plates were identified</h2>
    <ul>
      <li>Names and codes follow eBird/Clements 2025. Each identification also carries the IDs other tools join on: eBird, Wikidata, GBIF, Avibase and BirdNET.</li>
      <li>Gould's plates were checked against the engraved caption on the scan wherever it could be read, against Gould's own text, and against the University of Kansas catalogue.</li>
      <li>Audubon's were mapped from Wikimedia Commons and the Havell titles, and the hard cases checked one by one against audubon.org, the University of Pittsburgh and the New-York Historical Society.</li>
      <li>Each identification is certain, judged (a considered call, argued in its reasoning) or open. The {open} open plates each say what would settle them.</li>
    </ul>
    <p>Each folio's README has the full story, traps included:</p>
    <ul>
      {folios.map((f) => <li><a href={f.readme}>{f.author.split(" ").pop()}, <i>{f.title}</i></a></li>)}
    </ul>

    <h2>Get the data</h2>
    <p>The tables are CSV files on <a href={REPO}>GitHub</a>, described by a Frictionless <code>datapackage.json</code> and archived on <a href="https://doi.org/10.5281/zenodo.22964828">Zenodo</a>. The cleaned images, full sheets and art crops, are in each folio's GitHub release.</p>

    <h2>Cite</h2>
    <p>Riley, W. <i>Historical bird plates: modern identifications</i>. Zenodo. <a href="https://doi.org/10.5281/zenodo.22964828">doi:10.5281/zenodo.22964828</a>.</p>

    <h2>Licence and credit</h2>
    <ul>
      <li>The tables are dedicated to the public domain under CC0 1.0.</li>
      <li>The plates are public-domain works of the 1820s–80s. The cleaned images are marked with the Public Domain Mark.</li>
      <li>Gould scans: Smithsonian Libraries and Archives, via the Biodiversity Heritage Library.</li>
      <li>Havell scans: courtesy of the John James Audubon Center at Mill Grove, Montgomery County Audubon Collection, and Zebra Publishing.</li>
    </ul>

    <h2>Help</h2>
    <p>Think a plate is wrong, or can settle an open one? <a href={`${REPO}/issues`}>Open an issue</a> or a pull request with the evidence. The best evidence is the plate itself: the caption, the figure, the bird.</p>
  </article>
</Layout>
```

- [ ] **Step 2: `site/src/pages/404.astro`**

```astro
---
import Layout from "../layouts/Layout.astro";
import { href } from "../lib/data";
---
<Layout title="Not found · Historical bird plates" description="There is no page at this address.">
  <article class="prose">
    <h1>No plate here</h1>
    <p>There is no page at this address. <a href={href()}>Browse every plate</a>, or <a href={href("species/")}>look a bird up by name</a>.</p>
  </article>
</Layout>
```

- [ ] **Step 3: Build and commit**

Run: `cd site && npm run build`. Expected: `dist/about/index.html` and `dist/404.html` exist, and the sitemap doesn't list `404`.

```bash
git add site/src/pages/about.astro site/src/pages/404.astro
git commit -m "Site: about and not-found pages"
```

---

### Task 10: `site_check.py`, the check on a built site

**Files:**
- Create: `tools/site_check.py`
- Modify: `tools/test_site.py` (add the `Check` class)

**Interfaces:**
- Consumes: a built `site/dist/`.
- Produces: `check(dist: Path, images: bool = True) -> list[str]`, and the CLI `python3 tools/site_check.py DIST [--no-images]`, which exits 1 when there are problems.

- [ ] **Step 1: Write the failing tests**

In `tools/test_site.py`, add `import tempfile` to the imports, `import site_check  # noqa: E402` after `import site_data`, and this class before `if __name__ == "__main__":`:

```python
class Check(unittest.TestCase):
    SM = "http://www.sitemaps.org/schemas/sitemap/0.9"
    URL = "https://wr.github.io/historical-bird-plates/"

    def setUp(self) -> None:
        self.dist = Path(tempfile.mkdtemp())
        (self.dist / "sitemap-index.xml").write_text(
            f'<sitemapindex xmlns="{self.SM}"><sitemap><loc>{self.URL}sitemap-0.xml</loc></sitemap></sitemapindex>')
        (self.dist / "sitemap-0.xml").write_text(
            f'<urlset xmlns="{self.SM}"><url><loc>{self.URL}</loc></url><url><loc>{self.URL}havell/1/</loc></url></urlset>')
        (self.dist / "img" / "havell").mkdir(parents=True)
        (self.dist / "img" / "havell" / "1-thumb.webp").write_bytes(b"")

    def page(self, path: str, body: str = "", head: str = "") -> None:
        file = self.dist / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            f'<html><head><title>T</title><meta name="description" content="D">'
            f'<meta property="og:image" content="{self.URL}img/havell/1-thumb.webp">'
            f'<link rel="canonical" href="{self.URL}{path.removesuffix("index.html")}">{head}</head>'
            f"<body>{body}</body></html>")

    def test_a_good_site_passes(self) -> None:
        self.page("index.html",
                  '<a href="/historical-bird-plates/havell/1/">1</a><a href="#main">skip</a>'
                  '<img src="img/havell/1-thumb.webp" srcset="/historical-bird-plates/img/havell/1-thumb.webp 360w">'
                  '<a href="https://ebird.org/species/snoowl1">eBird</a>',
                  '<script type="application/ld+json">{"@type": "WebSite"}</script>')
        self.page("havell/1/index.html", '<a href="../../">home</a>')
        self.assertEqual(site_check.check(self.dist), [])

    def test_problems_are_named(self) -> None:
        self.page("index.html",
                  '<a href="/historical-bird-plates/havell/2/">2</a><a href="/elsewhere/">x</a>'
                  '<img src="img/havell/9-thumb.webp">',
                  '<script type="application/ld+json">{not json}</script>')
        (self.dist / "havell" / "1").mkdir(parents=True)
        (self.dist / "havell" / "1" / "index.html").write_text("<html><head></head><body></body></html>")
        errors = site_check.check(self.dist)
        for expected in ("index.html: broken link /historical-bird-plates/havell/2/",
                         "index.html: broken link /elsewhere/",
                         "index.html: broken link img/havell/9-thumb.webp",
                         "havell/1/index.html: no <title>", "havell/1/index.html: no description",
                         "havell/1/index.html: no og:image", "havell/1/index.html: no canonical URL"):
            self.assertIn(expected, errors)
        self.assertTrue(any(e.startswith("index.html: JSON-LD does not parse") for e in errors), errors)

    def test_unlisted_pages_and_skipped_images(self) -> None:
        self.page("index.html", '<img src="img/havell/9-thumb.webp">')
        self.page("about/index.html")
        self.assertEqual(site_check.check(self.dist, images=False),
                         [f"about/index.html: {self.URL}about/ is not in the sitemap"])

    def test_the_404_page_needs_no_canonical(self) -> None:
        self.page("index.html")
        (self.dist / "404.html").write_text(
            f'<html><head><title>Not found</title><meta name="description" content="D">'
            f'<meta property="og:image" content="{self.URL}img/havell/1-thumb.webp"></head><body></body></html>')
        self.assertEqual(site_check.check(self.dist), [])
```

Run: `python3 tools/test_site.py`
Expected: `ModuleNotFoundError: No module named 'site_check'`.

- [ ] **Step 2: Write `tools/site_check.py`**

```python
"""Check the built site before it's deployed.

    python3 tools/site_check.py site/dist              # every link, image and page
    python3 tools/site_check.py site/dist --no-images  # skip img/, for a build without the image tarball

Every internal href, src, srcset, data-index and og:image must name a file in the build. Every page
needs a title, a description, an og:image, and a canonical URL that the sitemap lists (404.html is
exempt from the canonical). Every JSON-LD block must parse. Standard library only.
"""
from __future__ import annotations

import json
import posixpath
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ORIGIN = "https://wr.github.io"
BASE = "/historical-bird-plates/"
SITEMAP = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"


class Page(HTMLParser):
    """The links, metadata and JSON-LD of one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.title = ""
        self.jsonld: list[str] = []
        self._in: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href", "")
        elif tag in ("a", "link") and a.get("href"):
            self.refs.append(a["href"])
        for key in ("src", "data-index"):
            if a.get(key):
                self.refs.append(a[key])
        if a.get("srcset"):
            self.refs += [part.split()[0] for part in a["srcset"].split(",") if part.strip()]
        if tag == "meta" and (a.get("property") or a.get("name")):
            self.meta[a.get("property") or a["name"]] = a.get("content", "")
        if tag == "title":
            self._in = "title"
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in = "script"
            self.jsonld.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == self._in:
            self._in = None

    def handle_data(self, data: str) -> None:
        if self._in == "title":
            self.title += data
        elif self._in == "script":
            self.jsonld[-1] += data


def target(dist: Path, page: Path, ref: str) -> Path | None:
    """The file in dist that ref names, or None when ref leaves the site or is only a fragment."""
    parts = urlsplit(ref)
    if parts.scheme and parts.scheme not in ("http", "https"):
        return None
    if parts.netloc and f"{parts.scheme}://{parts.netloc}" != ORIGIN:
        return None
    path = unquote(parts.path)
    if not path:
        return None
    if not path.startswith("/"):
        folder = page.parent.relative_to(dist).as_posix()
        here = BASE if folder == "." else f"{BASE}{folder}/"
        path = posixpath.normpath(posixpath.join(here, path)) + ("/" if path.endswith("/") else "")
    if not path.startswith(BASE):
        return dist / "_outside_base" / path.lstrip("/")  # never exists, so it is reported
    file = dist / path[len(BASE):]
    return file / "index.html" if path.endswith("/") or file.is_dir() else file


def sitemap(dist: Path) -> set[str]:
    """Every URL the sitemap lists."""
    index = dist / "sitemap-index.xml"
    if not index.exists():
        return set()
    urls: set[str] = set()
    for loc in ET.parse(index).iter(SITEMAP):
        part = dist / urlsplit(loc.text or "").path[len(BASE):]
        urls |= {u.text or "" for u in ET.parse(part).iter(SITEMAP)}
    return urls


def check(dist: Path, images: bool = True) -> list[str]:
    errors: list[str] = []
    listed = sitemap(dist)
    if not listed:
        errors.append("sitemap-index.xml: missing or empty")
    for file in sorted(dist.rglob("*.html")):
        name = file.relative_to(dist).as_posix()
        page = Page()
        page.feed(file.read_text(encoding="utf-8"))
        refs = page.refs + ([page.meta["og:image"]] if page.meta.get("og:image") else [])
        for ref in dict.fromkeys(refs):
            found = target(dist, file, ref)
            if found is None or (not images and found.relative_to(dist).parts[:1] == ("img",)):
                continue
            if not found.is_file():
                errors.append(f"{name}: broken link {ref}")
        if not page.title.strip():
            errors.append(f"{name}: no <title>")
        for key in ("description", "og:image"):
            if not page.meta.get(key):
                errors.append(f"{name}: no {key}")
        if name != "404.html":
            if not page.canonical:
                errors.append(f"{name}: no canonical URL")
            elif page.canonical not in listed:
                errors.append(f"{name}: {page.canonical} is not in the sitemap")
        for block in page.jsonld:
            try:
                json.loads(block)
            except ValueError as e:
                errors.append(f"{name}: JSON-LD does not parse ({e})")
    return errors


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    dist = Path(args[0])
    errors = check(dist, images="--no-images" not in sys.argv)
    for e in errors[:200]:
        print(e, file=sys.stderr)
    if len(errors) > 200:
        print(f"… and {len(errors) - 200} more", file=sys.stderr)
    print(f"{sum(1 for _ in dist.rglob('*.html'))} pages, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the tests**

Run: `python3 tools/test_site.py`
Expected: `Ran 19 tests … OK`.

- [ ] **Step 4: Check the real build**

Run: `cd site && npm run build && cd .. && python3 tools/site_check.py site/dist`
Expected: about 4,235 pages and `0 problems`. That count is 2,462 plates, 1,762 species, 5 folios, the home page, the species index, about and 404. `site/public/img/` is present locally, so the images are checked too.

Fix any problem it reports in the page that causes it, not in the checker, unless the checker is plainly wrong. A real broken link is a bug.

- [ ] **Step 5: Commit**

```bash
git add tools/site_check.py tools/test_site.py
git commit -m "site_check.py: every link resolves and every page has its metadata"
```

---

### Task 11: CI: test on every push, deploy from `main`

**Files:**
- Modify: `.github/workflows/validate.yml`
- Create: `.github/workflows/pages.yml`

**Interfaces:**
- Consumes:
  - `tools/test_site.py`;
  - `site/` with its `npm test` and `npm run build` scripts;
  - `tools/site_check.py`;
  - the `release` field in `images.json`.
- Produces: a `site` job on every push and PR, and a Pages deployment on push to `main`.

- [ ] **Step 1: Confirm the action versions**

Run: `for a in actions/checkout actions/setup-python actions/setup-node actions/upload-pages-artifact actions/deploy-pages; do echo "$a $(gh api repos/$a/releases/latest --jq .tag_name)"; done`

On 2026-10-01 these were checkout v7, setup-python v7, setup-node v7, upload-pages-artifact v5 and deploy-pages v5. Use each one's current major in the new jobs. Leave the existing `validate` job's versions alone.

- [ ] **Step 2: `validate.yml`**

Replace the file with the following. The existing job gains one line; the `site` job is new.

```yaml
name: validate
on:
  push:
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python3 tools/validate.py
      - run: python3 tools/test_identify.py
      - run: python3 tools/test_site.py
  site:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v7
        with:
          node-version: 24
          cache: npm
          cache-dependency-path: site/package-lock.json
      - run: npm ci
        working-directory: site
      - run: npm test
        working-directory: site
      - run: npm run build
        working-directory: site
      - run: python3 tools/site_check.py site/dist --no-images
```

- [ ] **Step 3: `pages.yml`**

```yaml
name: pages
on:
  push:
    branches: [main]
    paths:
      - "site/**"
      - "*/plates.csv"
      - "*/species.csv"
      - "tools/site_*.py"
      - "tools/misnamed.py"
      - ".github/workflows/pages.yml"
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v7
        with:
          node-version: 24
          cache: npm
          cache-dependency-path: site/package-lock.json
      - run: npm ci && npm test && npm run build
        working-directory: site
      - name: Unpack the site images
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          release=$(python3 -c "import json; print(json.load(open('site/src/data/images.json'))['release'])")
          gh release download "$release" -p site-images.tar -O - | tar -x -C site/dist
      - run: python3 tools/site_check.py site/dist
      - uses: actions/upload-pages-artifact@v5
        with:
          path: site/dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v5
```

- [ ] **Step 4: Check the CI steps locally**

Run, from a clean state: `rm -rf site/node_modules site/dist && (cd site && npm ci && npm test && npm run build) && python3 tools/site_check.py site/dist --no-images`.
Expected: all pass, ending with `0 problems`. This is what the `site` job does, apart from the runner.

Then check the YAML parses: `python3 -c "import yaml" 2>/dev/null && python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/validate.yml', '.github/workflows/pages.yml')]; print('ok')" || ruby -ryaml -e 'puts YAML.load_file(".github/workflows/pages.yml").keys'`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/validate.yml .github/workflows/pages.yml
git commit -m "CI: test and build the site on every push; deploy it to Pages from main"
```

---

### Task 12: In the browser: the whole site, both colour schemes, phone and desktop; then the README

**Files:**
- Modify: whatever the review finds (most likely `site/src/styles/global.css`), and `README.md`.

**Interfaces:**
- Consumes: the built site with local images (`site/public/img/` from Task 3).
- Produces: fixes, and a README that links to the site.

- [ ] **Step 1: Load the design skill and review**

Invoke the `frontend-design` skill for its review guidance. Then serve the build (`preview_start` with name `site`) and review these pages:

| Page | Check |
|---|---|
| `/` | The wall at 375 px (`resize_window` preset `mobile`) and at desktop width. Tiles fill rows with no gaps and the last row isn't stretched. Hover captions are legible. Controls stay sticky and don't cover content on a phone. |
| `/` in dark mode (`resize_window` with `colorScheme: "dark"`) | Every text has contrast; tile placeholders aren't glaring. |
| `/havell/121/` | The plate is the hero; the text column is readable; the viewer controls work by touch at 375 px (double-tap zoom, drag). |
| `/havell/399/`, `/gould-europe/427/`, `/havell/11/`, `/gould-europe/132/` | The multi-species, misnamed, unidentified and missing-image layouts. |
| `/species/snowy-owl/`, `/species/` | The strip at equal heights, wrapping on a phone; the family columns; the filter. |
| `/about/`, `/does-not-exist/` | Prose measure; the 404 page. |

Keyboard: Tab through the home page. The skip link appears first; pills and the select are reachable; focus is visible; Enter on a tile opens the plate.

Fix what's wrong in the CSS or the components, keeping to the global constraints (tokens, contrast, no new colours outside the token set). Run `npm run build && python3 ../tools/site_check.py dist` after the fixes.

- [ ] **Step 2: Measure the weight**

With the preview open, use `read_network_requests` on `/`. Before scrolling:
- `index.html` should be under 250 KB on the wire (the preview server may not compress, so judge the raw size against about 1.2 MB);
- `wall.json` should be under 700 KB raw;
- only on-screen thumbnails should load.

Note the numbers in the commit message.

- [ ] **Step 3: The README**

In `README.md`, under the first paragraph (the one ending "…and are released CC0."), add:

```markdown
**Browse the plates:** [wr.github.io/historical-bird-plates](https://wr.github.io/historical-bird-plates/), every plate with its identification and reasoning, searchable by printed or modern name.
```

And after the `### Validation` section, add:

````markdown
### The site

[`site/`](site/) is the [Astro](https://astro.build) site at [wr.github.io/historical-bird-plates](https://wr.github.io/historical-bird-plates/). GitHub Actions rebuilds and deploys it on every push to `main` that touches the tables or the site.

```sh
python3 tools/site_data.py               # the tables and the eBird taxonomy, joined into site/src/data/plates.json
python3 tools/site_images.py fetch       # the published WebP images, into site/public/img/
cd site && npm ci && npm run dev         # serve it at localhost:4321/historical-bird-plates/
```

`python3 tools/site_images.py build` remakes the images and `site/src/data/images.json` from the folio releases. A new set is published as a new `site-images-vN` release.
````

- [ ] **Step 4: Commit**

```bash
git add -A site/src README.md
git commit -m "Site: review fixes; README links to the site"
```

---

### Task 13: Publish (each step needs the user's yes)

**Files:** none, apart from the user-approved actions below.

- [ ] **Step 1: Ask to publish the image release**

Tell the user the tarball's size (`ls -lh .cache/site-images.tar`) and ask in chat:

> Publish `site-images-v1` to wr/historical-bird-plates with `site-images.tar` (NNN MB)? It's public as soon as it's up.

Only on a clear yes, run:

```bash
gh release create site-images-v1 .cache/site-images.tar -R wr/historical-bird-plates \
  --title "Plate explorer: site images (v1)" \
  --notes "WebP images for the plate explorer at https://wr.github.io/historical-bird-plates/: a 480 px thumb, a 1600 px crop and a 1000 px full sheet of every plate, at img/<folio>/<slug>-<cut>.webp. Made by tools/site_images.py from the folio releases. Public Domain Mark 1.0."
```

Then check it round-trips: `mv site/public/img .cache/img-local && python3 tools/site_images.py fetch && diff -rq site/public/img .cache/img-local && rm -rf .cache/img-local`. Expected: no differences.

- [ ] **Step 2: Ask to switch on GitHub Pages**

Ask in chat:

> Switch on GitHub Pages for wr/historical-bird-plates, built by GitHub Actions? The site will be public at wr.github.io/historical-bird-plates once `main` deploys.

Only on a clear yes, run: `gh api -X POST repos/wr/historical-bird-plates/pages -f build_type=workflow`.
Expected: a JSON response with `"build_type": "workflow"`.

- [ ] **Step 3: Ask to push and open a PR**

Ask in chat whether to push the branch and open a PR. On a yes:
1. `git push -u origin HEAD`.
2. `gh pr create` with a body that says:
   - what the site is;
   - where the spec and plan are;
   - what CI checks;
   - that merging deploys.

   Don't add attribution lines.
3. Bind the PR with the `ccd_pr` tools: `get_status`, then `bind_pr` if needed. Report the CI status. Offer Auto-fix if CI fails. Don't enable auto-merge.

- [ ] **Step 4: After the user merges**

Once the user says it's merged, wait for the `pages` workflow (`gh run list -w pages -L 1`; `gh run watch` on that run). Then open `https://wr.github.io/historical-bird-plates/` in the browser pane and confirm three things:
- the wall loads with images;
- `/havell/121/` renders;
- `https://wr.github.io/historical-bird-plates/sitemap-index.xml` lists URLs.

Report the live URL.

---

## Self-review against the spec

| Spec requirement | Task |
|---|---|
| Wall: search, arrange (folio, taxonomy, colour), folio and flag filters, count, slider, justified rows, crawlable links, query-string state, empty state | 5, 6 |
| Folio pages: intro, credit, links, the wall pre-filtered | 5 |
| Plate page: viewer (crop and sheet, zoom, pan, full resolution), printed against modern, why, sources, outbound links, per-figure blocks, misnamed and open notes, same species elsewhere, credit, prev and next with keys | 7 |
| Species page: family and order, plates side by side in folio order, printed-as strip, outbound links, extinct | 8 |
| Species index grouped by family, with a filter | 8 |
| About; 404 | 9 |
| Titles, descriptions, canonical, Open Graph, JSON-LD (VisualArtwork, Taxon, WebSite), sitemap, robots | 4, 5, 7, 8 |
| Alt text, `aria-pressed`, live count, keyboard, focus, contrast, reduced motion | 4 to 7, 12 |
| `site_data.py`, `site_images.py` (cuts, colour, budget, tarball, fetch), `images.json` committed | 1, 2, 3 |
| `test_site.py` in `validate.yml`; `site_check.py` before deploy; browser checks | 1, 2, 3, 10, 11, 12 |
| `pages.yml` deploy; Pages switched on; release published; each confirmed first | 11, 13 |
| Look: print room, paper tones, serif names, plates as the only colour, dark mode | 4, 12 |
