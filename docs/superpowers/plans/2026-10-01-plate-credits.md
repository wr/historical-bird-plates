# Plate Credits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record, for every plate of the five folios, the credit line engraved on it (who drew, lithographed or engraved it and who printed it), and use it to correct the creators of the plate items on Wikidata.

**Architecture:** The verbatim credit line is the record (`imprint` in each `plates.csv`). `tools/credits.py` turns it into a per-folio `credits.csv` (plate × name × role) through explicit wording and name tables. `artists.csv` maps names to Wikidata. `tools/imprints.py` is the reading workbench: crops, OCR drafts, contact sheets, readings applied. `tools/quickstatements.py` writes creators from `credits.csv`, and a `--fix-creators` batch corrects existing items.

**Tech Stack:** Python 3.12+ standard library for the repo tools and tests (CI runs 3.12). Pillow and macOS Vision (via a small Swift CLI) only for the reading workbench. QuickStatements V1 for Wikidata.

**Spec:** `docs/superpowers/specs/2026-10-01-plate-credits-design.md`

## Global Constraints

- The credit line is recorded verbatim: spelling, abbreviations, capitals and punctuation as engraved, whitespace normalised, superscripts inline (`Edinr`, `Junr`). Lines are joined with ` | `, in this order: left corner top to bottom, then centre, then right corner top to bottom.
- The caption (bird name, Latin, legend) is never part of `imprint`.
- Nothing per plate is claimed beyond the credit line's words; joint credits stay joint.
- An unrecognised wording or name is an error, never a guess. Add the variant to the table only after checking it on the plate.
- Roles: `drew`, `lithographed`, `engraved`, `retouched`, `printed`, `coloured` (British spelling throughout, as the repo uses).
- An empty `imprint` always has a reason in `notes` containing the words `credit line`.
- Repo tools and their tests are standard library only. `tools/imprints.py` may use Pillow and macOS, but importing it must not need them.
- CSVs: UTF-8, `\n` line endings, `csv.DictWriter` defaults (minimal quoting). Every `plates.csv` round-trips byte-identical through `csv.DictReader`/`DictWriter(lineterminator="\n")`; this was checked on 2026-10-01.
- `datapackage.json` is written with `json.dumps(pkg, indent=2, ensure_ascii=False) + "\n"`; this round-trips byte-identical.
- Nothing is sent to Wikidata by any tool. Batches are written to files for Wells to review and run in QuickStatements.
- The commenter is not named anywhere.
- Commit messages follow the repo's style: a plain sentence, often `Folio: what changed` (e.g. `Great Britain: images from the gould-britain-v2 release`). No attribution lines.
- Crops, contact sheets, downloaded scans and readings files live outside the repo, under `~/Projects/historical-bird-plates-assets/<release>-imprints/`, or in `.cache/` (git-ignored). Check `.gitignore` has `.cache/` before relying on it.

## File structure

| File | Responsibility |
|---|---|
| `artists.csv` (new) | One row per person or firm named on a credit line: `name`, `kind`, `wikidata`, `note` |
| `tools/credits.py` (new) | Wording and name tables; `parse(imprint)`; `rows`/`render`/`write`/`totals` per folio; CLI that writes or checks every `credits.csv` |
| `tools/test_credits.py` (new) | Tests for `credits.py` |
| `<folio>/credits.csv` (new, generated) | Plate × name × role, from `imprint` |
| `<folio>/plates.csv` | New `imprint` column |
| `datapackage.json` | `imprint` field; `<folio>-credits` and `artists` resources |
| `tools/validate.py` | Checks for the new column and tables |
| `tools/ocr.swift` (new) | macOS Vision OCR: prints text lines and boxes as JSON |
| `tools/imprints.py` (new) | Reading workbench: `crop`, `sheets`, `draft`, `scan`, `apply` |
| `tools/test_imprints.py` (new) | Tests for the pure parts of `imprints.py` (no Pillow) |
| `<folio>/sources/imprints.csv` (new) | Working record of the reading: crop boxes, OCR draft, how it was read |
| `tools/quickstatements.py` | Creators and printer from `credits.csv`; `--fix-creators` |
| `tools/test_quickstatements.py` (new) | Tests for the statement builders and the per-item fix. These sit here rather than in `test_credits.py`, as the spec had it, because they test `quickstatements.py`. |
| `.github/workflows/validate.yml` | Runs the three new test files |
| `README.md`, `<folio>/README.md`, `CITATION.cff`, `.zenodo.json` | Documentation |

## Reading protocol (used by Tasks 4–8)

The reading tasks share this protocol. Each one gives its folio, its release and what to expect.

1. **Crop and draft:** `python3 tools/imprints.py crop FOLIO`. This writes the crops and `FOLIO/sources/imprints.csv`, with the OCR draft per plate.
2. **Contact sheets:** `python3 tools/imprints.py sheets FOLIO`. This writes `~/Projects/historical-bird-plates-assets/RELEASE-imprints/sheets/FOLIO-NNN.png`, 12 plates per sheet, grouped by drafted wording. Each block shows the plate, its draft text, and the left- and right-corner crops at full size.
3. **Readings file:** `python3 tools/imprints.py draft FOLIO`. This writes `…/RELEASE-imprints/readings.csv`: `volume, plate, sheet, imprint, read, note`, with `imprint` prefilled by the draft snapped to known wordings, and `read` blank.
4. **Read by eye.** Split the contact sheets into batches of about 10. Dispatch one reader subagent per batch, in parallel. Give each reader:
   - the paths of its contact sheets;
   - its rows of `readings.csv` (those whose `sheet` is in its batch);
   - these rules:
     - Open every contact sheet with the Read tool and look at every crop.
     - For each plate, write the credit line exactly as engraved into `imprint`, following the Global Constraints. Where the draft is right, keep it; where it differs from the crop in any letter, stop, comma or capital, correct it.
     - Set `read` to `eye`.
     - If a crop does not show a credit line clearly (faint, cut, or the crop missed it), set `read` to `scan` and leave `imprint` as the draft. These go to step 5.
     - If the corner crops show caption text or a pencil number instead of a credit line, say so in `note`, and set `read` to `scan`.
     - If one corner's line can be read and the other can't even on the scan (step 5), record the line that can be read and say which is missing in `note` (`right credit line cut off`). A plate that lacks its artist's line is never given one by guess.
     - Return the rows as CSV, nothing else.
   
   Merge the returned rows into `readings.csv`. Then compare the merged `imprint` with the OCR draft for every row: list each row where they differ, and look at that crop again yourself before accepting it.
5. **Hard cases:** for every row with `read` = `scan`, run `python3 tools/imprints.py scan FOLIO TAG …` (tags like `132` or `IV.59`). This writes the left and right corners of the unaltered scan, with contrast raised, to `…/RELEASE-imprints/scans/`.
   - Read those images and set `imprint` and `read` = `scan`.
   - If the line still can't be read: `imprint` empty, `read` = `none`, and a `note` with the words `credit line` (e.g. `credit line cut off by the binding`, `no credit line engraved`).
6. **New wordings and names:** `python3 tools/imprints.py apply FOLIO …/readings.csv` refuses any wording or name not in the tables of `tools/credits.py`, and lists each. For each one:
   1. Look at the plate again (the crop, or the scan) and confirm the reading.
   2. Add the wording to `BEFORE` or `AFTER`, or the name form to `NAMES`.
   3. Add any new person or firm to `artists.csv`. Find the Wikidata item with `wbsearchentities` and accept it only if its label and description fit (dates, trade). Otherwise leave `wikidata` blank.
   4. Add a test line for the new variant in `tools/test_credits.py` (`Parse.test_seen_on_the_plates`).

   Re-run `apply` until it succeeds.
7. **Check:** `python3 tools/validate.py --offline`, `python3 tools/test_credits.py`, and `python3 tools/credits.py --totals FOLIO`. Compare the totals with the task's expectations; a difference is explained in the task's report, never adjusted.
8. **Commit** `FOLIO/plates.csv`, `FOLIO/credits.csv`, `FOLIO/sources/imprints.csv`, plus `tools/credits.py`, `tools/test_credits.py` and `artists.csv` if they changed.

---

### Task 1: The credits model (`credits.py`, `artists.csv`)

**Files:**
- Create: `artists.csv`
- Create: `tools/credits.py`
- Create: `tools/test_credits.py`
- Modify: `.github/workflows/validate.yml`

**Interfaces:**
- Produces, in `tools/credits.py`:
  - `ROLES: tuple[str, ...]`, `FOLIOS: list[str]`
  - `BEFORE: dict[str, tuple[str, ...]]`, `AFTER: dict[str, tuple[str, ...]]`, `NAMES: dict[str, tuple[str, ...]]`
  - `@dataclass(frozen=True) class Credit: name: str; role: str; as_printed: str`
  - `class UnknownCredit(ValueError)`
  - `parse(imprint: str) -> list[Credit]`
  - `per_volume(folder: Path) -> bool`
  - `columns(folder: Path) -> list[str]`
  - `rows(folder: Path) -> list[dict]`
  - `render(folder: Path) -> str`
  - `write(folder: Path) -> bool` (True if the file changed)
  - `totals(folder: Path) -> collections.Counter` (`(name, role)` → number of plates)
  - `tag(plate_row: dict, per_volume: bool) -> str` (`"I.33"` or `"37"`)

- [ ] **Step 1: Write `artists.csv`**

```csv
name,kind,wikidata,note
John Gould,person,Q313787,Ornithologist; author and publisher of the Gould folios
Elizabeth Gould,person,Q253875,"Artist and lithographer; John Gould's wife, the principal artist of his early works"
Edward Lear,person,Q309759,Artist and lithographer
Henry Constantine Richter,person,Q1567083,Artist and lithographer
Joseph Wolf,person,Q1708274,Artist
William Matthew Hart,person,Q8015234,Artist and lithographer
Charles Joseph Hullmandel,person,Q376691,"Lithographic printer, London"
Hullmandel & Walton,firm,Q23872817,"Lithographic printers, London"
Walter,firm,,"Lithographic printer, named on the plates only as Walter"
Walter & Cohn,firm,,Lithographic printers
John James Audubon,person,Q182882,Naturalist and artist; author of The Birds of America
William Home Lizars,person,Q1616131,"Engraver, Edinburgh"
Robert Havell Jr.,person,Q2157495,"Engraver, printer and colourist, London"
```

- [ ] **Step 2: Write the failing tests**

`tools/test_credits.py`:

```python
"""Tests for credits.py.

    python3 tools/test_credits.py
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import credits  # noqa: E402
from credits import Credit, UnknownCredit, parse  # noqa: E402


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def names_roles(credits_: list[Credit]) -> list[tuple[str, str]]:
    return [(c.name, c.role) for c in credits_]


class Parse(unittest.TestCase):
    def test_wording_before_names(self):
        self.assertEqual(parse("Drawn on Stone by E. Lear | Printed by C. Hullmandel"), [
            Credit("Edward Lear", "lithographed", "E. Lear"),
            Credit("Charles Joseph Hullmandel", "printed", "C. Hullmandel")])

    def test_joint_credit_stays_joint(self):
        self.assertEqual(parse("Drawn from Nature & on Stone by J. & E. Gould"), [
            Credit("John Gould", "drew", "J. & E. Gould"),
            Credit("John Gould", "lithographed", "J. & E. Gould"),
            Credit("Elizabeth Gould", "drew", "J. & E. Gould"),
            Credit("Elizabeth Gould", "lithographed", "J. & E. Gould")])

    def test_wording_after_names_split_on_ampersand_and_and(self):
        self.assertEqual(parse("J.Wolf & HCRichter, del et lith. | Walter & Cohn Imp."), [
            Credit("Joseph Wolf", "drew", "J.Wolf"),
            Credit("Joseph Wolf", "lithographed", "J.Wolf"),
            Credit("Henry Constantine Richter", "drew", "HCRichter"),
            Credit("Henry Constantine Richter", "lithographed", "HCRichter"),
            Credit("Walter & Cohn", "printed", "Walter & Cohn")])
        self.assertEqual(parse("J. Gould and H.C. Richter del."), [
            Credit("John Gould", "drew", "J. Gould"),
            Credit("Henry Constantine Richter", "drew", "H.C. Richter")])

    def test_case_punctuation_and_spacing_fold(self):
        self.assertEqual(names_roles(parse("drawn from nature  &  on stone by J.&E.Gould")),
                         names_roles(parse("Drawn from Nature & on Stone by J. & E. Gould")))

    def test_havell_lines_keep_their_abbreviations(self):
        self.assertEqual(parse("Drawn from nature by J.J. Audubon F.R.S. F.L.S. | Engraved by W.H. Lizars Edinr. "
                               "| Retouched by R. Havell Junr."), [
            Credit("John James Audubon", "drew", "J.J. Audubon F.R.S. F.L.S."),
            Credit("William Home Lizars", "engraved", "W.H. Lizars Edinr."),
            Credit("Robert Havell Jr.", "retouched", "R. Havell Junr.")])

    def test_one_line_gives_several_roles(self):
        self.assertEqual(names_roles(parse("Engraved, Printed & Coloured by R. Havell Junr.")), [
            ("Robert Havell Jr.", "engraved"), ("Robert Havell Jr.", "printed"), ("Robert Havell Jr.", "coloured")])

    def test_a_repeated_credit_is_kept_once(self):
        self.assertEqual(names_roles(parse("Engraved by R. Havell Junr. | Engraved, Printed & Coloured by R. Havell Junr.")), [
            ("Robert Havell Jr.", "engraved"), ("Robert Havell Jr.", "printed"), ("Robert Havell Jr.", "coloured")])

    def test_unknown_wording_or_name_is_an_error(self):
        for imprint in ("Sketched by J. Gould", "Drawn on Stone by J. Smith",
                        "J. Gould & J. Smith del. et lith.", "Printed by C. Hullmandel | ", ""):
            with self.subTest(imprint=imprint), self.assertRaises(UnknownCredit):
                parse(imprint)

    def test_seen_on_the_plates(self):
        """Every wording found on the plates parses. Add each new variant here."""
        for imprint in ("Drawn from Life & on Stone by J. & E. Gould | Printed by C. Hullmandel",
                        "J. Gould and H.C. Richter del. et lith. | Hullmandel & Walton Imp.",
                        "J. Gould & H.C. Richter del et lith. | Walter Imp.",
                        "J. Gould & W. Hart del. et lith. | Walter Imp.",
                        "Drawn from nature by J.J. Audubon F.R.S. F.L.S. | Engraved, Printed & Coloured by R. Havell Junr."):
            with self.subTest(imprint=imprint):
                self.assertTrue(parse(imprint))


class Tables(unittest.TestCase):
    def test_every_name_is_in_artists_csv(self):
        with open(credits.ROOT / "artists.csv", newline="", encoding="utf-8") as f:
            known = {r["name"] for r in csv.DictReader(f)}
        for form, people in credits.NAMES.items():
            for person in people:
                self.assertIn(person, known, f"{form} -> {person}")

    def test_every_role_is_known(self):
        for table in (credits.BEFORE, credits.AFTER):
            for wording, roles in table.items():
                self.assertTrue(set(roles) <= set(credits.ROLES), wording)


class Files(unittest.TestCase):
    def folio(self, plates: list[dict], per_volume: bool) -> Path:
        d = Path(tempfile.mkdtemp())
        vol = ["volume"] if per_volume else []
        write_csv(d / "plates.csv", vol + ["plate", "imprint", "notes"], plates)
        write_csv(d / "species.csv", vol + ["plate", "scientific"], [])
        return d

    def test_rows_follow_plates_and_skip_empty_imprints(self):
        d = self.folio([{"volume": "I", "plate": "1", "imprint": "J. Gould and H.C. Richter del."},
                        {"volume": "I", "plate": "2", "imprint": "", "notes": "credit line cut off"}], True)
        self.assertEqual(credits.rows(d), [
            {"volume": "I", "plate": "1", "name": "John Gould", "role": "drew", "as_printed": "J. Gould"},
            {"volume": "I", "plate": "1", "name": "Henry Constantine Richter", "role": "drew",
             "as_printed": "H.C. Richter"}])

    def test_no_volume_column_for_a_folio_numbered_straight_through(self):
        d = self.folio([{"plate": "37", "imprint": "Drawn on Stone by E. Lear"}], False)
        self.assertEqual(credits.columns(d), ["plate", "name", "role", "as_printed"])
        self.assertEqual(credits.render(d), "plate,name,role,as_printed\n37,Edward Lear,lithographed,E. Lear\n")

    def test_write_reports_a_change_once(self):
        d = self.folio([{"plate": "37", "imprint": "Drawn on Stone by E. Lear"}], False)
        self.assertTrue(credits.write(d))
        self.assertFalse(credits.write(d))

    def test_totals_count_plates(self):
        d = self.folio([{"plate": "1", "imprint": "Drawn on Stone by E. Lear"},
                        {"plate": "2", "imprint": "Drawn on Stone by E. Lear | Printed by C. Hullmandel"}], False)
        self.assertEqual(credits.totals(d)[("Edward Lear", "lithographed")], 2)
        self.assertEqual(credits.totals(d)[("Charles Joseph Hullmandel", "printed")], 1)

    def test_an_error_names_the_plate(self):
        d = self.folio([{"volume": "IV", "plate": "5", "imprint": "Sketched by J. Gould"}], True)
        with self.assertRaisesRegex(UnknownCredit, r"plate IV\.5"):
            credits.rows(d)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 tools/test_credits.py`
Expected: FAIL: `ModuleNotFoundError: No module named 'credits'`

- [ ] **Step 4: Write `tools/credits.py`**

```python
"""Write each folio's credits.csv from the credit lines in its plates.csv.

    python3 tools/credits.py                          # write every folio's credits.csv
    python3 tools/credits.py --check                  # exit 1 if any is out of date
    python3 tools/credits.py --totals gould-europe    # plates per name and role

A plate's `imprint` is its credit lines verbatim, joined with " | ". Each line
is a wording and the names it credits: "Drawn on Stone by E. Lear",
"J. Gould & H.C. Richter del. et lith.", "C. Hullmandel Imp.". BEFORE and
AFTER give the roles a wording stands for, written before or after the names;
NAMES gives the people or firms a name form stands for. Wordings match with
case, full stops, commas and spacing folded ("del. et lith." is "del et lith");
name forms with everything but letters and "&" dropped ("H. C. Richter" is
"H.C.Richter"). A line whose wording or name is in neither table is an error:
check the variant on the plate, then add it.

Joint credits stay joint: "J. Gould & H.C. Richter del. et lith." credits both
men with drawing and lithographing, because that is all the plate says.

Standard library only.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLIOS = ["havell", "gould-europe", "gould-australia", "gould-asia", "gould-britain"]
ROLES = ("drew", "lithographed", "engraved", "retouched", "printed", "coloured")

# A wording written before the names -> the roles it gives them.
BEFORE = {
    "Drawn from Nature & on Stone by": ("drew", "lithographed"),
    "Drawn from Life & on Stone by": ("drew", "lithographed"),
    "Drawn on Stone by": ("lithographed",),
    "Drawn from Nature by": ("drew",),
    "Engraved, Printed & Coloured by": ("engraved", "printed", "coloured"),
    "Engraved by": ("engraved",),
    "Retouched by": ("retouched",),
    "Printed by": ("printed",),
}
# A wording written after the names -> the roles it gives them.
AFTER = {
    "del. et lith.": ("drew", "lithographed"),
    "del.": ("drew",),
    "lith.": ("lithographed",),
    "Imp.": ("printed",),
}
# A name form as printed -> who it is: names in artists.csv.
NAMES = {
    "J. & E. Gould": ("John Gould", "Elizabeth Gould"),
    "J. Gould": ("John Gould",),
    "E. Lear": ("Edward Lear",),
    "H.C. Richter": ("Henry Constantine Richter",),
    "J. Wolf": ("Joseph Wolf",),
    "W. Hart": ("William Matthew Hart",),
    "C. Hullmandel": ("Charles Joseph Hullmandel",),
    "Hullmandel & Walton": ("Hullmandel & Walton",),
    "Walter": ("Walter",),
    "Walter & Cohn": ("Walter & Cohn",),
    "J.J. Audubon F.R.S. F.L.S.": ("John James Audubon",),
    "W.H. Lizars Edinr.": ("William Home Lizars",),
    "R. Havell Junr.": ("Robert Havell Jr.",),
}


@dataclass(frozen=True)
class Credit:
    name: str
    role: str
    as_printed: str


class UnknownCredit(ValueError):
    """A credit line with a wording or name form the tables don't have."""


def name_key(s: str) -> str:
    return re.sub(r"[^a-z&]", "", s.casefold())


def wording_pattern(wording: str) -> str:
    tokens = " ".join(re.sub(r"[.,]", " ", wording).split()).split()
    return r"[\s.,]*".join(re.escape(t) for t in tokens)


_NAMES = {name_key(k): v for k, v in NAMES.items()}
# Longest first, so "del. et lith." is tried before "del.".
_BEFORE = [(re.compile(rf"^{wording_pattern(w)}[\s.,]+(?P<names>.+?)[\s,]*$", re.I), roles)
           for w, roles in sorted(BEFORE.items(), key=lambda x: -len(x[0]))]
_AFTER = [(re.compile(rf"^(?P<names>.+?),?\s+{wording_pattern(w)}[\s.,]*$", re.I), roles)
          for w, roles in sorted(AFTER.items(), key=lambda x: -len(x[0]))]


def split_line(line: str) -> tuple[tuple[str, ...], str]:
    """A credit line's roles and the names they belong to, as printed."""
    for pattern, roles in _BEFORE + _AFTER:
        m = pattern.match(line)
        if m:
            return roles, m.group("names").strip()
    raise UnknownCredit(f"no known wording in {line!r}")


def name_forms(names: str) -> list[str]:
    """The name forms in a line's names: the whole if the table has it ("J. & E. Gould",
    "Walter & Cohn"), else each part between "&" or "and"."""
    if name_key(names) in _NAMES:
        return [names]
    parts = [p.strip(" ,") for p in re.split(r"\s*&\s*|\s+and\s+", names)]
    unknown = [p for p in parts if name_key(p) not in _NAMES]
    if unknown:
        raise UnknownCredit(f"no known name for {', '.join(map(repr, unknown))} in {names!r}")
    return parts


def parse(imprint: str) -> list[Credit]:
    """The credits a plate's imprint gives, line by line, in order; each name and role once."""
    out: list[Credit] = []
    for line in imprint.split(" | "):
        line = line.strip()
        if not line:
            raise UnknownCredit(f"an empty line in {imprint!r}")
        roles, names = split_line(line)
        for form in name_forms(names):
            for person in _NAMES[name_key(form)]:
                for role in roles:
                    if not any(c.name == person and c.role == role for c in out):
                        out.append(Credit(person, role, form))
    return out


def read(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def per_volume(folder: Path) -> bool:
    """A folio numbered per volume keys its plates by volume and number, as species.csv shows."""
    return "volume" in read(folder / "species.csv")[0]


def tag(p: dict, volumes: bool) -> str:
    return f"{p['volume']}.{p['plate']}" if volumes else p["plate"]


def columns(folder: Path) -> list[str]:
    return (["volume"] if per_volume(folder) else []) + ["plate", "name", "role", "as_printed"]


def rows(folder: Path) -> list[dict]:
    volumes = per_volume(folder)
    out = []
    for p in read(folder / "plates.csv")[1]:
        if not p.get("imprint"):
            continue
        try:
            found = parse(p["imprint"])
        except UnknownCredit as e:
            raise UnknownCredit(f"{folder.name} plate {tag(p, volumes)}: {e}") from None
        for c in found:
            row = {"plate": p["plate"], "name": c.name, "role": c.role, "as_printed": c.as_printed}
            out.append({"volume": p["volume"], **row} if volumes else row)
    return out


def render(folder: Path) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=columns(folder), lineterminator="\n")
    w.writeheader()
    w.writerows(rows(folder))
    return out.getvalue()


def write(folder: Path) -> bool:
    path, text = folder / "credits.csv", render(folder)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def totals(folder: Path) -> collections.Counter:
    """Plates per (name, role)."""
    key = (lambda r: (r["volume"], r["plate"])) if per_volume(folder) else (lambda r: r["plate"])
    return collections.Counter((n, role) for (_, n, role) in {(key(r), r["name"], r["role"]) for r in rows(folder)})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folios", nargs="*", default=FOLIOS)
    ap.add_argument("--check", action="store_true", help="exit 1 if any credits.csv is out of date")
    ap.add_argument("--totals", action="store_true", help="print plates per name and role")
    args = ap.parse_args()
    stale = []
    for name in args.folios:
        folder = ROOT / name
        if args.totals:
            for (person, role), n in sorted(totals(folder).items(), key=lambda x: (-x[1], x[0])):
                print(f"{name}\t{person}\t{role}\t{n}")
        elif args.check:
            path = folder / "credits.csv"
            if not path.exists() or path.read_text(encoding="utf-8") != render(folder):
                stale.append(name)
        elif write(folder):
            print(f"{name}/credits.csv written")
    if stale:
        print("out of date: " + ", ".join(stale) + "; run python3 tools/credits.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 tools/test_credits.py`
Expected: `OK` (16 tests). If `test_case_punctuation_and_spacing_fold` or the `J.Wolf & HCRichter, del et lith.` case fails, check that `_AFTER`'s pattern allows the comma (`,?\s+`) and that the names group stops before it.

- [ ] **Step 6: Add the test to CI**

In `.github/workflows/validate.yml`, after the `test_identify.py` line, add:

```yaml
      - run: python3 tools/test_credits.py
```

- [ ] **Step 7: Commit**

```bash
git add artists.csv tools/credits.py tools/test_credits.py .github/workflows/validate.yml
git commit -m "credits.py: who each plate's credit line names, and for what"
```

---

### Task 2: The schema, the `imprint` column and the validator

**Files:**
- Modify: `havell/plates.csv`, `gould-europe/plates.csv`, `gould-australia/plates.csv`, `gould-britain/plates.csv`, `gould-asia/plates.csv` (new empty column)
- Create: `<folio>/credits.csv` ×5 (header only for now)
- Modify: `datapackage.json`
- Modify: `tools/validate.py`

**Interfaces:**
- Consumes: `credits.render`, `credits.UnknownCredit`, `credits.ROLES` (Task 1).
- Produces: every `plates.csv` has `imprint` after its caption column (`legend` in `havell`, `caption_latin` elsewhere); `datapackage.json` has resources `<folio>-credits` and `artists`; `validate.py` checks them.

- [ ] **Step 1: Add the column and the resources**

Run once from the repo root (a one-off, not committed):

```bash
python3 - <<'EOF'
import csv, json
from pathlib import Path
AFTER = {"havell": "legend", "gould-europe": "caption_latin", "gould-australia": "caption_latin",
         "gould-asia": "caption_latin", "gould-britain": "caption_latin"}
IMPRINT = ("The plate's credit lines, verbatim: the left corner, then the centre, then the right corner, "
           "each top to bottom, joined with \" | \". They name who drew, lithographed or engraved the plate "
           "and who printed it. Empty where none can be read, with the reason in notes.")
for folio, after in AFTER.items():
    p = Path(folio) / "plates.csv"
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f); cols = list(r.fieldnames); rows = list(r)
    cols.insert(cols.index(after) + 1, "imprint")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n"); w.writeheader()
        w.writerows({c: row.get(c, "") for c in cols} for row in rows)
pkg = json.loads(Path("datapackage.json").read_text(encoding="utf-8"))
res = pkg["resources"]
for folio, after in AFTER.items():
    plates = next(x for x in res if x["name"] == f"{folio}-plates")
    fields = plates["schema"]["fields"]
    i = next(i for i, x in enumerate(fields) if x["name"] == after)
    fields.insert(i + 1, {"name": "imprint", "type": "string", "description": IMPRINT})
    species = next(x for x in res if x["name"] == f"{folio}-species")
    per_volume = any(x["name"] == "volume" for x in species["schema"]["fields"])
    key = (["volume"] if per_volume else []) + ["plate"]
    cfields = [dict(next(x for x in fields if x["name"] == k)) for k in key] + [
        {"name": "name", "type": "string", "description": "Who the credit line names, as in artists.csv."},
        {"name": "role", "type": "string", "constraints": {"enum": ["drew", "lithographed", "engraved",
         "retouched", "printed", "coloured"]}, "description": "What the credit line says they did: drew "
         "(del., Drawn from Nature), lithographed (lith., on Stone), engraved, retouched, printed (Imp., "
         "Printed by) or coloured. A joint credit gives every name every role."},
        {"name": "as_printed", "type": "string", "description": "The name as the plate gives it; both rows "
         "from \"J. & E. Gould\" carry J. & E. Gould."}]
    last = max(i for i, x in enumerate(res) if x["name"].startswith(folio + "-"))
    res.insert(last + 1, {
        "name": f"{folio}-credits", "path": f"{folio}/credits.csv",
        "title": plates["title"].removesuffix(": plates") + ": plate credits",
        "description": "One row per plate, name and role, generated from plates.csv's imprint by tools/credits.py.",
        "format": "csv", "mediatype": "text/csv", "encoding": "utf-8",
        "schema": {"fields": cfields, "foreignKeys": [
            {"fields": "name", "reference": {"resource": "artists", "fields": "name"}},
            {"fields": key, "reference": {"resource": f"{folio}-plates", "fields": key}}]}})
res.append({
    "name": "artists", "path": "artists.csv", "title": "People and firms named on the plates' credit lines",
    "format": "csv", "mediatype": "text/csv", "encoding": "utf-8",
    "schema": {"fields": [
        {"name": "name", "type": "string", "description": "Full name, as credits.csv uses it."},
        {"name": "kind", "type": "string", "constraints": {"enum": ["person", "firm"]}},
        {"name": "wikidata", "type": "string", "description": "Wikidata item; blank if Wikidata has none."},
        {"name": "note", "type": "string", "description": "Who they were, in a line."}],
        "primaryKey": ["name"]}})
pkg["description"] = pkg["description"].rstrip(".") + ", and each plate's engraved credit line."
Path("datapackage.json").write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
EOF
python3 tools/credits.py
git diff --stat
```

Expected: five `plates.csv` changed (each line gains one comma), `datapackage.json` changed, five `credits.csv` written, each just `plate,name,role,as_printed` or `volume,plate,name,role,as_printed`. Check one `plates.csv` diff by eye: `git diff gould-europe/plates.csv | head -8`. Only the header gains `imprint`, and every row gains an empty field after `caption_latin`.

- [ ] **Step 2: Run the validator before extending it**

Run: `python3 tools/validate.py --offline`
Expected: passes on the existing checks, because the column lists came from `datapackage.json`. The new tables aren't checked yet.

- [ ] **Step 3: Extend `tools/validate.py`**

Add to the docstring's list of checks:

```
  - credits.csv has the declared columns and is what tools/credits.py writes from plates.csv's imprint;
    every name in it is in artists.csv, every role a known role
  - artists.csv has the declared columns, one row per name, kind person or firm, a well-formed wikidata id
```

Below the imports, add:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
import credits  # noqa: E402
```

Next to `CAPTION_CHECKED`, add:

```python
KIND = {"person", "firm"}
```

At the start of `validate()`, after `fields = schema_fields()`:

```python
    artist_cols, artists = read(ROOT / "artists.csv")
    if "artists.csv" not in fields:
        errors.append("artists.csv: not declared in datapackage.json")
    elif artist_cols != fields["artists.csv"]:
        errors.append(f"artists.csv: columns {artist_cols} != datapackage.json {fields['artists.csv']}")
    artist_names = [a["name"] for a in artists]
    if len(artist_names) != len(set(artist_names)):
        errors.append("artists.csv: a name appears twice")
    for i, a in enumerate(artists, start=2):
        if a["kind"] not in KIND:
            errors.append(f"artists.csv:{i}: kind {a['kind']!r} not one of {sorted(KIND)}")
        if a["wikidata"] and not re.fullmatch(ID_PATTERNS["wikidata"], a["wikidata"]):
            errors.append(f"artists.csv:{i}: malformed wikidata {a['wikidata']!r}")
```

Change the per-folio table loop to cover `credits.csv` and a missing file:

```python
        for table in ("plates.csv", "species.csv", "credits.csv"):
            rel = f"{name}/{table}"
            if rel not in fields:
                errors.append(f"{rel}: not declared in datapackage.json")
                continue
            if not (folder / table).exists():
                errors.append(f"{rel}: missing; run python3 tools/credits.py")
                continue
            cols, _ = read(folder / table)
            if cols != fields[rel]:
                errors.append(f"{rel}: columns {cols} != datapackage.json {fields[rel]}")
```

After the species loop, before the `print(f"{name}: …")` line, add:

```python
        if (folder / "credits.csv").exists():
            try:
                if (folder / "credits.csv").read_text(encoding="utf-8") != credits.render(folder):
                    errors.append(f"{name}/credits.csv: out of date with plates.csv's imprint; "
                                  "run python3 tools/credits.py")
            except credits.UnknownCredit as e:
                errors.append(f"{name}/plates.csv: {e}")
            for i, c in enumerate(read(folder / "credits.csv")[1], start=2):
                if c["name"] not in artist_names:
                    errors.append(f"{name}/credits.csv:{i}: {c['name']!r} is not in artists.csv")
                if c["role"] not in credits.ROLES:
                    errors.append(f"{name}/credits.csv:{i}: role {c['role']!r} not one of {list(credits.ROLES)}")
```

(A non-empty `imprint` always yields at least one credit or an `UnknownCredit`, so "every plate with an imprint has a credit" holds by construction.)

- [ ] **Step 4: Check that the validator catches each fault**

Run each of these and confirm the named error appears, then restore with `git checkout -- <file>` (or re-run `python3 tools/credits.py`):

```bash
python3 tools/validate.py --offline                                             # expect: ok
printf '1,Nobody,drew,X\n' >> gould-europe/credits.csv && python3 tools/validate.py --offline | grep credits; python3 tools/credits.py
sed -i '' 's/^Walter,firm,/Walter,shop,/' artists.csv && python3 tools/validate.py --offline | grep artists; git checkout -- artists.csv
```

Expected:
- the second command reports `gould-europe/credits.csv: out of date…` and `'Nobody' is not in artists.csv`;
- the third reports `kind 'shop' not one of ['firm', 'person']`;
- a final `python3 tools/validate.py --offline` prints `ok`.

- [ ] **Step 5: Run the full validator and the tests**

Run: `python3 tools/validate.py && python3 tools/test_credits.py && python3 tools/test_identify.py`
Expected: `ok`, `OK`, `OK`.

- [ ] **Step 6: Commit**

```bash
git add */plates.csv */credits.csv datapackage.json tools/validate.py
git commit -m "Every plate gets an imprint column, and every folio a credits table"
```

---

### Task 3: The reading workbench (`imprints.py`, `ocr.swift`)

**Files:**
- Create: `tools/ocr.swift`
- Create: `tools/imprints.py`
- Create: `tools/test_imprints.py`
- Modify: `.github/workflows/validate.yml`

**Interfaces:**
- Consumes: `credits.parse`, `credits.UnknownCredit`, `credits.write`, `credits.per_volume`, `credits.tag`, `credits.read`, `credits.FOLIOS` (Task 1); the `imprint` column (Task 2).
- Produces, in `tools/imprints.py`:
  - CLI `crop|sheets|draft|scan|apply`
  - `lowest(lines: list[dict]) -> list[dict]`
  - `corners(lines: list[dict], width: int) -> tuple[list[dict], list[dict]]`
  - `guess(side: str, other: list[dict], width: int, height: int) -> list[int]`
  - `draft_text(left: list[dict], right: list[dict]) -> str`
  - `snap(text: str, known: list[str]) -> str`
  - `apply(folder: Path, readings: list[dict]) -> None` (raises `SystemExit` listing every problem, before writing anything)
  - `SEED: list[str]`, `READ = {"eye", "scan", "none"}`, `RELEASE: dict[str, str]`, `ASSETS: Path`
- `FOLIO/sources/imprints.csv` columns: `[volume,] plate, leaf, left_box, right_box, ocr, read, note`.

- [ ] **Step 1: Write the failing tests**

`tools/test_imprints.py`:

```python
"""Tests for the parts of imprints.py that need no images.

    python3 tools/test_imprints.py
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import imprints  # noqa: E402


def line(text: str, x0: int, y0: int, x1: int, y1: int) -> dict:
    return {"text": text, "box": [x0, y0, x1, y1]}


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Corners(unittest.TestCase):
    def test_corner_lines_kept_caption_and_pencil_numbers_dropped(self):
        lines = [line("AQUILA FUCOSA: Cuv.", 1400, 100, 2300, 160),
                 line("C. Hullmandel Imp.", 2900, 130, 3300, 160),
                 line("J. Gould and H.C. Richter del.", 500, 130, 1200, 160),
                 line("37", 300, 300, 360, 360),
                 line("Retouched by R. Havell Junr.", 3000, 170, 3600, 200),
                 line("Engraved by W.H. Lizars Edinr.", 3000, 120, 3600, 150),
                 line("E. Lear del.", 3100, -1600, 3400, -1570)]
        left, right = imprints.corners(lines, 3700)
        self.assertEqual([x["text"] for x in left], ["J. Gould and H.C. Richter del."])
        self.assertEqual([x["text"] for x in right],
                         ["Engraved by W.H. Lizars Edinr.", "C. Hullmandel Imp.", "Retouched by R. Havell Junr."])

    def test_a_missing_corner_is_looked_for_level_with_the_other(self):
        self.assertEqual(imprints.guess("left", [line("Printed by C. Hullmandel", 2900, 1000, 3300, 1030)], 3700, 1900),
                         [74, 940, 1776, 1090])
        self.assertEqual(imprints.guess("right", [], 3700, 2000), [1924, 1100, 3626, 2000])

    def test_draft_joins_left_then_right(self):
        self.assertEqual(imprints.draft_text([line("a", 0, 0, 1, 1)], [line("b", 0, 0, 1, 1), line("c", 0, 2, 1, 3)]),
                         "a | b | c")


class Snap(unittest.TestCase):
    def test_close_ocr_snaps_to_a_known_line_each_line_alone(self):
        known = ["Drawn from Life & on Stone by J. & E. Gould", "Printed by C. Hullmandel"]
        self.assertEqual(imprints.snap("Drawn from Tite & on Stone by I & E. Goutà. | Printed by C.Hallmandel", known),
                         "Drawn from Life & on Stone by J. & E. Gould | Printed by C. Hullmandel")

    def test_far_text_is_left_as_read(self):
        self.assertEqual(imprints.snap("Drawn on Stone by E. Lear", ["Printed by C. Hullmandel"]),
                         "Drawn on Stone by E. Lear")


class Apply(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sources").mkdir()
        write_csv(self.d / "species.csv", ["plate", "scientific"], [])
        write_csv(self.d / "plates.csv", ["plate", "caption_latin", "imprint", "notes"],
                  [{"plate": "37", "notes": ""}, {"plate": "38", "notes": "an older note"}])
        write_csv(self.d / "sources" / "imprints.csv", ["plate", "leaf", "left_box", "right_box", "ocr", "read", "note"],
                  [{"plate": "37", "ocr": "Drawn on Stone by E.Lear"}, {"plate": "38"}])

    def test_writes_imprint_note_record_and_credits(self):
        imprints.apply(self.d, [
            {"plate": "37", "imprint": "Drawn on Stone  by E. Lear |  Printed by C. Hullmandel", "read": "eye", "note": ""},
            {"plate": "38", "imprint": "", "read": "none", "note": "credit line cut off by the binding"}])
        plates = read_csv(self.d / "plates.csv")
        self.assertEqual(plates[0]["imprint"], "Drawn on Stone by E. Lear | Printed by C. Hullmandel")
        self.assertEqual(plates[1]["notes"], "an older note; credit line cut off by the binding")
        record = read_csv(self.d / "sources" / "imprints.csv")
        self.assertEqual([r["read"] for r in record], ["eye", "none"])
        self.assertIn("37,Edward Lear,lithographed,E. Lear", (self.d / "credits.csv").read_text(encoding="utf-8"))

    def test_refuses_everything_if_one_row_is_wrong(self):
        before = (self.d / "plates.csv").read_text(encoding="utf-8")
        for bad in ({"plate": "37", "imprint": "Sketched by J. Gould", "read": "eye", "note": ""},
                    {"plate": "37", "imprint": "", "read": "none", "note": "faint"},
                    {"plate": "37", "imprint": "Drawn on Stone by E. Lear", "read": "", "note": ""},
                    {"plate": "99", "imprint": "Drawn on Stone by E. Lear", "read": "eye", "note": ""}):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                imprints.apply(self.d, [{"plate": "38", "imprint": "Printed by C. Hullmandel", "read": "eye",
                                         "note": ""}, bad])
            self.assertEqual((self.d / "plates.csv").read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 tools/test_imprints.py`
Expected: FAIL: `ModuleNotFoundError: No module named 'imprints'`

- [ ] **Step 3: Write `tools/ocr.swift`**

```swift
// What macOS Vision reads in each image: one JSON object per image per line of output,
// {"path": "...", "lines": [{"text": "...", "box": [x0, y0, x1, y1]}]}, boxes in pixels from the top left.
//
//     swiftc -O tools/ocr.swift -o .cache/ocr && .cache/ocr IMAGE...
//
// tools/imprints.py compiles and runs it.
import Foundation
import ImageIO
import Vision

for path in CommandLine.arguments.dropFirst() {
    var lines: [[String: Any]] = []
    if let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
       let image = CGImageSourceCreateImageAtIndex(source, 0, nil) {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        try? VNImageRequestHandler(cgImage: image).perform([request])
        let w = Double(image.width), h = Double(image.height)
        for observation in request.results ?? [] {
            guard let text = observation.topCandidates(1).first?.string else { continue }
            let b = observation.boundingBox  // normalised, origin bottom left
            lines.append(["text": text,
                          "box": [Int(b.minX * w), Int((1 - b.maxY) * h), Int(b.maxX * w), Int((1 - b.minY) * h)]])
        }
    }
    let data = try! JSONSerialization.data(withJSONObject: ["path": path, "lines": lines])
    print(String(data: data, encoding: .utf8)!)
}
```

- [ ] **Step 4: Write `tools/imprints.py`**

```python
"""Read the credit lines engraved on each plate: crop them, draft them with OCR,
lay them out for reading by eye, and write the readings into plates.csv.

    python3 tools/imprints.py crop gould-europe                 # crops and OCR drafts -> sources/imprints.csv
    python3 tools/imprints.py sheets gould-europe               # contact sheets of the crops, for reading
    python3 tools/imprints.py draft gould-europe                # a readings file, prefilled from the drafts
    python3 tools/imprints.py scan gould-europe 132 418         # hard cases: the unaltered scan's corners
    python3 tools/imprints.py apply gould-europe READINGS.csv   # write the readings; regenerate credits.csv

Sheets are read from the folio's release, downloaded into ASSETS/<release>/.
Crops, contact sheets, scans and the readings file go to
ASSETS/<release>-imprints/, never into the repo.

A readings file has the columns volume (where the folio numbers per volume),
plate, imprint, read and note, one row per plate (others, such as `sheet`, are
ignored). `read` is eye (read off the crop), scan (read off the unaltered scan)
or none (nothing can be read; `note` says why, with the words "credit line").

Needs Pillow, and macOS for the OCR (tools/ocr.swift, compiled into .cache/ on
first use). `apply` and the functions it uses need neither.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import credits  # noqa: E402

ROOT = credits.ROOT
CACHE = ROOT / ".cache"
ASSETS = Path.home() / "Projects" / "historical-bird-plates-assets"
RELEASE = {"havell": "havell-v1", "gould-europe": "gould-europe-v1", "gould-australia": "gould-australia-v1",
           "gould-britain": "gould-britain-v2", "gould-asia": "gould-asia-v1"}
UA = {"User-Agent": "historical-bird-plates imprints (+https://github.com/wr/historical-bird-plates)"}
BAND = 0.35       # the bottom of the sheet searched for credit lines
PER_SHEET = 12    # plates per contact sheet
READ = {"eye", "scan", "none"}
RECORD = ["plate", "leaf", "left_box", "right_box", "ocr", "read", "note"]
# Credit lines seen before any plate was read, to snap OCR drafts to. Lines in
# any plates.csv imprint are added to these.
SEED = [
    "Drawn from Life & on Stone by J. & E. Gould", "Drawn from Nature & on Stone by J. & E. Gould",
    "Drawn on Stone by E. Lear", "Printed by C. Hullmandel", "C. Hullmandel Imp.", "Hullmandel & Walton Imp.",
    "J. Gould and H.C. Richter del.", "J. Gould and H.C. Richter del. et lith.", "J. Gould & H.C. Richter del. et lith.",
    "J. Wolf & H.C. Richter del. et lith.", "J. Gould & W. Hart del. et lith.", "Walter Imp.", "Walter & Cohn Imp.",
    "Drawn from nature by J.J. Audubon F.R.S. F.L.S.", "Engraved by W.H. Lizars Edinr.",
    "Retouched by R. Havell Junr.", "Engraved, Printed & Coloured by R. Havell",
]


# --- pure: no images -----------------------------------------------------------

def lowest(lines: list[dict]) -> list[dict]:
    """A corner's credit lines: its lowest line and any stacked just above it, top to
    bottom. Text higher up is in the art, such as a signature on the stone."""
    if not lines:
        return []
    bottom = max(x["box"][3] for x in lines)
    height = sorted(x["box"][3] - x["box"][1] for x in lines)[len(lines) // 2]
    return sorted((x for x in lines if x["box"][1] >= bottom - 3.5 * height), key=lambda x: x["box"][1])


def corners(lines: list[dict], width: int) -> tuple[list[dict], list[dict]]:
    """The credit lines in the sheet's left and right corners, each top to bottom. The
    caption sits between them; a pencilled plate number (digits only) is dropped."""
    lines = [x for x in lines if not x["text"].replace(" ", "").isdigit()]
    left = [x for x in lines if x["box"][0] < 0.30 * width and x["box"][2] < 0.50 * width]
    right = [x for x in lines if x["box"][2] > 0.70 * width and x["box"][0] > 0.50 * width]
    return lowest(left), lowest(right)


def guess(side: str, other: list[dict], width: int, height: int) -> list[int]:
    """Where a corner's credit line should be when OCR found none there: level with the
    other corner's lines, across that half of the sheet; else across the bottom of the band."""
    x0, x1 = (int(0.02 * width), int(0.48 * width)) if side == "left" else (int(0.52 * width), int(0.98 * width))
    if other:
        tall = max(x["box"][3] - x["box"][1] for x in other)
        return [x0, min(x["box"][1] for x in other) - 2 * tall, x1, max(x["box"][3] for x in other) + 2 * tall]
    return [x0, int(0.55 * height), x1, height]


def draft_text(left: list[dict], right: list[dict]) -> str:
    return " | ".join(x["text"].strip() for x in left + right if x["text"].strip())


def snap(text: str, known: list[str]) -> str:
    """Each line of an OCR draft replaced by the known credit line it is closest to,
    if it is close (ratio 0.75 or more); otherwise left as OCR read it."""
    out = []
    for part in (p.strip() for p in text.split("|")):
        best = max(known, key=lambda k: difflib.SequenceMatcher(None, part.casefold(), k.casefold()).ratio(),
                   default=part)
        close = difflib.SequenceMatcher(None, part.casefold(), best.casefold()).ratio() >= 0.75
        out.append(best if close else part)
    return " | ".join(p for p in out if p)


def normalise(imprint: str) -> str:
    return " | ".join(" ".join(p.split()) for p in imprint.split("|") if p.strip())


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def apply(folder: Path, readings: list[dict]) -> None:
    """Write readings into plates.csv (imprint, and notes for an unreadable line) and
    sources/imprints.csv (read, note), then regenerate credits.csv. Every row is
    checked first; if any is wrong, nothing is written."""
    volumes = credits.per_volume(folder)
    key = lambda r: (r.get("volume", "") if volumes else "", r["plate"])
    show = lambda k: ".".join(x for x in k if x)
    plate_cols, plates = credits.read(folder / "plates.csv")
    known = {key(p) for p in plates}
    problems = []
    for r in readings:
        k, where = key(r), f"plate {show(key(r))}"
        imprint = normalise(r.get("imprint", ""))
        if k not in known:
            problems.append(f"{where}: not in plates.csv")
        if r.get("read", "") not in READ:
            problems.append(f"{where}: read {r.get('read', '')!r} not one of {sorted(READ)}")
        elif r["read"] == "none":
            if imprint:
                problems.append(f"{where}: read none, but an imprint is given")
            if "credit line" not in r.get("note", ""):
                problems.append(f"{where}: read none needs a note with the words 'credit line'")
        elif not imprint:
            problems.append(f"{where}: no imprint; if nothing can be read, read none")
        else:
            try:
                credits.parse(imprint)
            except credits.UnknownCredit as e:
                problems.append(f"{where}: {e}")
    if problems:
        raise SystemExit("\n".join(problems))
    by = {key(r): r for r in readings}
    for p in plates:
        r = by.get(key(p))
        if r is None:
            continue
        p["imprint"] = normalise(r["imprint"])
        if r["read"] == "none" and r["note"] not in p["notes"]:
            p["notes"] = f"{p['notes']}; {r['note']}" if p["notes"] else r["note"]
    write_csv(folder / "plates.csv", plate_cols, plates)
    record_path = folder / "sources" / "imprints.csv"
    if record_path.exists():
        record_cols, record = credits.read(record_path)
        for x in record:
            r = by.get(key(x))
            if r is not None:
                x["read"], x["note"] = r["read"], r.get("note", "")
        write_csv(record_path, record_cols, record)
    credits.write(folder)


# --- images --------------------------------------------------------------------

def ocr_binary() -> Path:
    src, binary = ROOT / "tools" / "ocr.swift", CACHE / "ocr"
    if not binary.exists() or binary.stat().st_mtime < src.stat().st_mtime:
        CACHE.mkdir(exist_ok=True)
        subprocess.run(["swiftc", "-O", str(src), "-o", str(binary)], check=True)
    return binary


def ocr(paths: list[Path]) -> dict[str, list[dict]]:
    """Path -> its OCR lines, four processes at a time."""
    binary = ocr_binary()
    chunks = [paths[i:i + 25] for i in range(0, len(paths), 25)]

    def run(chunk: list[Path]) -> list[dict]:
        out = subprocess.run([str(binary), *map(str, chunk)], capture_output=True, text=True, check=True).stdout
        return [json.loads(x) for x in out.splitlines() if x.strip()]

    with ThreadPoolExecutor(4) as pool:
        return {r["path"]: r["lines"] for results in pool.map(run, chunks) for r in results}


def work(folio: str) -> Path:
    d = ASSETS / f"{RELEASE[folio]}-imprints"
    d.mkdir(parents=True, exist_ok=True)
    return d


def union(lines: list[dict], pad: int) -> list[int] | None:
    if not lines:
        return None
    return [min(x["box"][0] for x in lines) - pad, min(x["box"][1] for x in lines) - pad,
            max(x["box"][2] for x in lines) + pad, max(x["box"][3] for x in lines) + pad]


def crop(folio: str) -> None:
    from PIL import Image, ImageOps
    folder, out = ROOT / folio, work(folio)
    volumes = credits.per_volume(folder)
    (out / "crops").mkdir(exist_ok=True)
    _, plates = credits.read(folder / "plates.csv")
    record_path = folder / "sources" / "imprints.csv"
    old = {}
    if record_path.exists():
        old = {credits.tag(x, volumes): x for x in credits.read(record_path)[1]}
    rows, todo, retry, texts = [], [], [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for p in plates:
            t = credits.tag(p, volumes)
            row = {"volume": p.get("volume", ""), "plate": p["plate"], "leaf": p.get("leaf", ""),
                   "read": old.get(t, {}).get("read", ""), "note": old.get(t, {}).get("note", "")}
            rows.append(row)
            sheet = ASSETS / RELEASE[folio] / p["sheet_asset"] if p["sheet_asset"] else None
            if not sheet or not sheet.exists():
                row["note"] = row["note"] or "no sheet in the release; read from the scan"
                continue
            with Image.open(sheet) as im:
                w, h = im.size
                top = int(h * (1 - BAND))
                band = Path(tmp) / f"{t}.jpg"
                im.crop((0, top, w, h)).convert("RGB").save(band, quality=95)
            todo.append((row, sheet, w, h, top, band, t))
        found = ocr([x[5] for x in todo])
        for row, sheet, w, h, top, band, t in todo:
            left, right = corners(found.get(str(band), []), w)
            texts[id(row)] = {"left": [x["text"] for x in left], "right": [x["text"] for x in right]}
            with Image.open(sheet) as im:
                for side, own, other in (("left", left, right), ("right", right, left)):
                    tall = max([x["box"][3] - x["box"][1] for x in own] or [20])
                    box = union(own, max(12, int(0.6 * tall))) or guess(side, other, w, h - top)
                    box = [max(0, box[0]), max(0, box[1] + top), min(w, box[2]), min(h, box[3] + top)]
                    row[f"{side}_box"] = " ".join(map(str, box))
                    path = out / "crops" / f"{t}-{side[0].upper()}.png"
                    ImageOps.autocontrast(im.crop(box).convert("L"), cutoff=1).save(path)
                    if not own:
                        retry.append((row, side, path))
    # A faint line OCR missed on the whole band is often read on its own crop.
    again = ocr([path for _, _, path in retry])
    for row, side, path in retry:
        lines = [x for x in sorted(again.get(str(path), []), key=lambda x: x["box"][1])
                 if not x["text"].replace(" ", "").isdigit()]
        texts[id(row)][side] = [x["text"] for x in lines]
        if not lines:
            row["note"] = row["note"] or f"OCR found no text in the {side} corner"
    for row in rows:
        if id(row) in texts:
            row["ocr"] = " | ".join(x.strip() for x in texts[id(row)]["left"] + texts[id(row)]["right"] if x.strip())
    record_cols = (["volume"] if volumes else []) + RECORD
    record_path.parent.mkdir(exist_ok=True)
    write_csv(record_path, record_cols, rows)
    print(f"{folio}: {len(todo)} sheets cropped, {len(rows) - len(todo)} without a sheet, "
          f"{len(retry)} corners OCR'd again -> {record_path}")


def known_lines() -> list[str]:
    lines = list(SEED)
    for folio in credits.FOLIOS:
        if not (ROOT / folio / "plates.csv").exists():
            continue
        for p in credits.read(ROOT / folio / "plates.csv")[1]:
            lines += [x.strip() for x in p.get("imprint", "").split(" | ") if x.strip()]
    return list(dict.fromkeys(lines))


def ordered(folio: str) -> list[dict]:
    """The record's rows, grouped by drafted wording, so that an odd one stands out."""
    folder = ROOT / folio
    _, record = credits.read(folder / "sources" / "imprints.csv")
    known = known_lines()
    for r in record:
        r["snapped"] = snap(r["ocr"], known) if r["ocr"] else ""
    return [r for _, r in sorted(enumerate(record), key=lambda x: (x[1]["snapped"], x[0]))]


def sheets(folio: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    folder, out = ROOT / folio, work(folio)
    volumes = credits.per_volume(folder)
    (out / "sheets").mkdir(exist_ok=True)
    font = ImageFont.load_default(size=22)
    rows, width, half = ordered(folio), 1800, 890
    index = []
    for n in range(0, len(rows), PER_SHEET):
        blocks = []
        for r in rows[n:n + PER_SHEET]:
            t = credits.tag(r, volumes)
            crops = []
            for side in "LR":
                path = out / "crops" / f"{t}-{side}.png"
                im = Image.open(path) if path.exists() else Image.new("L", (half, 40), 255)
                if im.width > width:
                    im = im.resize((width, int(im.height * width / im.width)))
                if im.height > 400:   # a whole corner, where neither OCR pass found a line
                    im = im.resize((int(im.width * 400 / im.height), 400))
                crops.append(im)
            # Side by side if they fit; else one above the other, each at full size.
            beside = crops[0].width + crops[1].width + 20 <= width
            body = max(c.height for c in crops) if beside else crops[0].height + 10 + crops[1].height
            height = 34 + body + 16
            block = Image.new("L", (width, height), 255)
            d = ImageDraw.Draw(block)
            d.text((6, 4), f"{t}   draft: {r['ocr'] or '(nothing read)'}", fill=0, font=font)
            block.paste(crops[0], (0, 34))
            block.paste(crops[1], (width - crops[1].width, 34 if beside else 34 + crops[0].height + 10))
            d.line((0, height - 2, width, height - 2), fill=160, width=2)
            blocks.append(block)
        sheet = Image.new("L", (width, sum(b.height for b in blocks)), 255)
        y = 0
        for b in blocks:
            sheet.paste(b, (0, y))
            y += b.height
        name = f"{folio}-{n // PER_SHEET + 1:03d}.png"
        sheet.save(out / "sheets" / name)
        index += [{"sheet": name, "plate": credits.tag(r, volumes)} for r in rows[n:n + PER_SHEET]]
    write_csv(out / "sheets" / "index.csv", ["sheet", "plate"], index)
    print(f"{folio}: {len(index)} plates on {(len(rows) + PER_SHEET - 1) // PER_SHEET} sheets -> {out / 'sheets'}")


def draft(folio: str) -> None:
    folder, out = ROOT / folio, work(folio)
    volumes = credits.per_volume(folder)
    sheet_of = {x["plate"]: x["sheet"] for x in credits.read(out / "sheets" / "index.csv")[1]}
    rows = [{"volume": r.get("volume", ""), "plate": r["plate"], "sheet": sheet_of.get(credits.tag(r, volumes), ""),
             "imprint": r["snapped"], "read": "", "note": r["note"]} for r in ordered(folio)]
    cols = (["volume"] if volumes else []) + ["plate", "sheet", "imprint", "read", "note"]
    write_csv(out / "readings.csv", cols, rows)
    print(f"{folio}: {len(rows)} rows -> {out / 'readings.csv'}")


def scan(folio: str, tags: list[str]) -> None:
    from PIL import Image, ImageOps
    folder, out = ROOT / folio, work(folio) / "scans"
    out.mkdir(exist_ok=True)
    volumes = credits.per_volume(folder)
    by = {credits.tag(p, volumes): p for p in credits.read(folder / "plates.csv")[1]}
    for t in tags:
        p = by[t]
        url = p.get("scan_url") or p.get("image_url")
        path = CACHE / "scans" / url.rsplit("/", 1)[1]
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                path.write_bytes(r.read())
        im = Image.open(path).convert("L")
        if p.get("rotate") and int(p["rotate"]):
            im = im.rotate(int(p["rotate"]), expand=True)  # counter-clockwise, as plates.csv gives it
        w, h = im.size
        top = int(h * (1 - BAND))
        for side, box in (("L", (0, top, w // 2, h)), ("R", (w // 2, top, w, h))):
            part = ImageOps.autocontrast(im.crop(box), cutoff=1)
            part = part.resize((1600, int(part.height * 1600 / part.width)))
            part.save(out / f"{t}-{side}.png")
            print(out / f"{t}-{side}.png")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["crop", "sheets", "draft", "scan", "apply"])
    ap.add_argument("folio", choices=credits.FOLIOS)
    ap.add_argument("rest", nargs="*", help="scan: plate tags; apply: the readings file")
    args = ap.parse_args()
    if args.command == "crop":
        crop(args.folio)
    elif args.command == "sheets":
        sheets(args.folio)
    elif args.command == "draft":
        draft(args.folio)
    elif args.command == "scan":
        scan(args.folio, args.rest)
    else:
        apply(ROOT / args.folio, credits.read(Path(args.rest[0]))[1])
        print(f"{args.folio}: readings applied; credits.csv regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 tools/test_imprints.py`
Expected: `OK` (7 tests). If `test_close_ocr_snaps…` fails because `C.Hallmandel` falls under 0.75, print the ratio and lower the threshold only if every SEED line stays at least 0.1 below 0.75 against every other.

- [ ] **Step 6: Try the workbench on three Europe plates**

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "tools")
import imprints, credits
# A scratch copy of Europe with three plates: 1 (J. & E. Gould), 37 (Lear), 100 (pencil number under the line).
import shutil, tempfile, csv
from pathlib import Path
tmp = Path(tempfile.mkdtemp()); shutil.copytree("gould-europe", tmp / "gould-europe", ignore=shutil.ignore_patterns("img"))
cols, rows = credits.read(tmp / "gould-europe" / "plates.csv")
imprints.write_csv(tmp / "gould-europe" / "plates.csv", cols, [r for r in rows if r["plate"] in {"1", "37", "100"}])
imprints.ROOT = tmp; credits.ROOT = tmp
imprints.crop("gould-europe"); imprints.sheets("gould-europe"); imprints.draft("gould-europe")
print(open(tmp / "gould-europe" / "sources" / "imprints.csv").read())
EOF
```

Then open `~/Projects/historical-bird-plates-assets/gould-europe-v1-imprints/sheets/gould-europe-001.png` with the Read tool. Expected:
- three blocks;
- each shows a legible credit line in its left crop ("Drawn from Life & on Stone by J. & E. Gould"; "Drawn on Stone by E. Lear"; "Drawn from Nature & on Stone by J. & E. Gould") and "Printed by C. Hullmandel" in its right crop;
- plate 37's right crop holds only the credit line, not Lear's signature in the art ("E. Lear del.");
- plate 100's faint left line, which OCR misses on the whole band, is legible at full size in its crop, and its draft comes from the second OCR pass;
- the draft above each is close.

Fix the crop rules if a corner crop shows the caption or misses the line, then delete the scratch crops: `rm -r ~/Projects/historical-bird-plates-assets/gould-europe-v1-imprints`.

- [ ] **Step 7: Try `scan` on Europe 132 (no sheet in the release)**

Run: `python3 tools/imprints.py scan gould-europe 132`
Expected: two PNGs under `…/gould-europe-v1-imprints/scans/`, and the credit line legible in the left one when opened with Read. Delete the folder afterwards, as in Step 6.

- [ ] **Step 8: Add the test to CI and commit**

In `.github/workflows/validate.yml`, add after the `test_credits.py` line:

```yaml
      - run: python3 tools/test_imprints.py
```

```bash
git add tools/ocr.swift tools/imprints.py tools/test_imprints.py .github/workflows/validate.yml
git commit -m "imprints.py: crop, draft and read each plate's credit line"
```

---

### Task 4: Read *The Birds of Europe* (449 plates)

**Files:**
- Modify: `gould-europe/plates.csv`, `gould-europe/credits.csv`
- Create: `gould-europe/sources/imprints.csv`
- Maybe modify: `tools/credits.py`, `tools/test_credits.py`, `artists.csv`

**Interfaces:**
- Consumes: `tools/imprints.py` CLI (Task 3), `tools/credits.py` (Task 1).
- Produces: every `gould-europe/plates.csv` row has `imprint`, or an empty `imprint` with a `credit line` note.

- [ ] **Step 1: Crop and draft:** `python3 tools/imprints.py crop gould-europe`. Expected: `gould-europe: 448 sheets cropped, 1 without a sheet`; the one without is plate 132.
- [ ] **Step 2: Contact sheets and readings file:** `python3 tools/imprints.py sheets gould-europe && python3 tools/imprints.py draft gould-europe`. Expected: 449 plates on 38 sheets.
- [ ] **Step 3: Read by eye,** as in steps 4–5 of the Reading protocol: about 4 reader subagents of ~10 sheets each, then a check of every row whose reading differs from its draft.
  - Plate 132: `scan`.
  - Plates 447 and 448 share one sheet (leaf 302) and so one credit line: give both the same `imprint`.
- [ ] **Step 4: Apply:** `python3 tools/imprints.py apply gould-europe ~/Projects/historical-bird-plates-assets/gould-europe-v1-imprints/readings.csv`. Handle each new wording or name as in step 6 of the protocol, and re-run until it prints `readings applied`.
- [ ] **Step 5: Check:** `python3 tools/validate.py --offline && python3 tools/test_credits.py && python3 tools/credits.py --totals gould-europe`. Expected:
  - Edward Lear credited on about 68 plates (the figure usually given for his part in *The Birds of Europe*);
  - John and Elizabeth Gould on nearly all the rest;
  - the printer Charles Joseph Hullmandel throughout.
  
  Report the totals; explain any plate whose credit is neither Lear's nor the Goulds'.
- [ ] **Step 6: Commit**

```bash
git add gould-europe/plates.csv gould-europe/credits.csv gould-europe/sources/imprints.csv tools/credits.py tools/test_credits.py artists.csv
git commit -m "Europe: every plate's credit line read; Lear's plates and the Goulds'"
```

---

### Task 5: Read *The Birds of Australia* and *Supplement* (681 plates)

**Files:**
- Modify: `gould-australia/plates.csv`, `gould-australia/credits.csv`
- Create: `gould-australia/sources/imprints.csv`
- Maybe modify: `tools/credits.py`, `tools/test_credits.py`, `artists.csv`

**Interfaces:**
- Consumes: `tools/imprints.py` CLI, `tools/credits.py`.
- Produces: every `gould-australia/plates.csv` row has `imprint`, or an empty one with a `credit line` note.

- [ ] **Step 1: Crop and draft:** `python3 tools/imprints.py crop gould-australia`. Expected: `681 sheets cropped, 0 without a sheet`.
- [ ] **Step 2: Contact sheets and readings file:** `python3 tools/imprints.py sheets gould-australia && python3 tools/imprints.py draft gould-australia`. Expected: 681 plates on 57 sheets.
- [ ] **Step 3: Read by eye,** as in steps 4–5 of the Reading protocol: about 6 readers.
  - Faint lines are expected in this volume (III.50 and V.1 were faint on the cleaned sheets); send them to `scan`.
  - The `caption_ocr` column of `gould-australia/sources/plate-leaves.csv` holds an earlier OCR of the bottom strip. It may help with a hard case, but it is not a reading.
- [ ] **Step 4: Apply:** `python3 tools/imprints.py apply gould-australia ~/Projects/historical-bird-plates-assets/gould-australia-v1-imprints/readings.csv`, handling new wordings and names as in step 6 of the protocol.
- [ ] **Step 5: Check:** `python3 tools/validate.py --offline && python3 tools/test_credits.py && python3 tools/credits.py --totals gould-australia`. Expected:
  - John Gould with H. C. Richter on most plates;
  - "J. & E. Gould" on the plates drawn before Elizabeth Gould's death in 1841, bound through the volumes, not first;
  - printers Hullmandel, Hullmandel & Walton, and later Walter for the *Supplement*.
  
  Report the totals and the count of Elizabeth Gould's plates for the README.
- [ ] **Step 6: Commit**

```bash
git add gould-australia/plates.csv gould-australia/credits.csv gould-australia/sources/imprints.csv tools/credits.py tools/test_credits.py artists.csv
git commit -m "Australia: every plate's credit line read; Elizabeth Gould's plates and Richter's"
```

---

### Task 6: Read *The Birds of Great Britain* (367 plates)

**Files:**
- Modify: `gould-britain/plates.csv`, `gould-britain/credits.csv`
- Create: `gould-britain/sources/imprints.csv`
- Maybe modify: `tools/credits.py`, `tools/test_credits.py`, `artists.csv`

**Interfaces:**
- Consumes: `tools/imprints.py` CLI, `tools/credits.py`.
- Produces: every `gould-britain/plates.csv` row has `imprint`, or an empty one with a `credit line` note.

- [ ] **Step 1: Crop and draft:** `python3 tools/imprints.py crop gould-britain`. This reads from `gould-britain-v2`. Expected: `367 sheets cropped`.
- [ ] **Step 2: Contact sheets and readings file:** `python3 tools/imprints.py sheets gould-britain && python3 tools/imprints.py draft gould-britain`. Expected: 367 plates on 31 sheets.
- [ ] **Step 3: Read by eye,** as in steps 4–5 of the Reading protocol: about 3 readers.
- [ ] **Step 4: Apply:** `python3 tools/imprints.py apply gould-britain ~/Projects/historical-bird-plates-assets/gould-britain-v2-imprints/readings.csv`, handling new wordings and names as in step 6 of the protocol.
- [ ] **Step 5: Check:** `python3 tools/validate.py --offline && python3 tools/test_credits.py && python3 tools/credits.py --totals gould-britain`. Expected:
  - credits shared between Gould, Wolf, Richter and Hart: "J. Wolf & H.C. Richter" (I.1), "J. Gould & W. Hart" (II.40), "J. Gould and H.C. Richter" (III.60);
  - printers Walter and Walter & Cohn.
  
  Report the totals, and the number of plates that don't name Gould.
- [ ] **Step 6: Commit**

```bash
git add gould-britain/plates.csv gould-britain/credits.csv gould-britain/sources/imprints.csv tools/credits.py tools/test_credits.py artists.csv
git commit -m "Great Britain: every plate's credit line read; Wolf, Richter and Hart"
```

---

### Task 7: Read *The Birds of Asia* (530 plates)

**Files:**
- Modify: `gould-asia/plates.csv`, `gould-asia/credits.csv`
- Create: `gould-asia/sources/imprints.csv`
- Maybe modify: `tools/credits.py`, `tools/test_credits.py`, `artists.csv`

**Interfaces:**
- Consumes: `tools/imprints.py` CLI, `tools/credits.py`.
- Produces: every `gould-asia/plates.csv` row has `imprint`, or an empty one with a `credit line` note.

- [ ] **Step 1: Download the sheets**

```bash
df -h ~ | tail -1        # needs 4 GB free; 24 GB were free on 2026-10-01
mkdir -p ~/Projects/historical-bird-plates-assets/gould-asia-v1
gh release download gould-asia-v1 -R wr/historical-bird-plates -p 'sheet-*' -p 'SHA256SUMS' -D ~/Projects/historical-bird-plates-assets/gould-asia-v1
cd ~/Projects/historical-bird-plates-assets/gould-asia-v1 && grep ' sheet-' SHA256SUMS | shasum -a 256 -c --quiet && ls sheet-* | wc -l; cd -
```

Expected: no checksum failures, `530`.

- [ ] **Step 2: Crop and draft:** `python3 tools/imprints.py crop gould-asia`. Expected: `530 sheets cropped`.
- [ ] **Step 3: Contact sheets and readings file:** `python3 tools/imprints.py sheets gould-asia && python3 tools/imprints.py draft gould-asia`. Expected: 530 plates on 45 sheets.
- [ ] **Step 4: Read by eye,** as in steps 4–5 of the Reading protocol: about 5 readers.
  - Expect new names: the later parts were finished by R. B. Sharpe after Gould's death in 1881, with other artists, and possibly other printers such as Mintern Bros. (Q47008735).
  - VI.2 and VI.3 were swapped in the List (commit `dbbf4d6`): read each plate's own sheet.
- [ ] **Step 5: Apply:** `python3 tools/imprints.py apply gould-asia ~/Projects/historical-bird-plates-assets/gould-asia-v1-imprints/readings.csv`, handling new wordings and names as in step 6 of the protocol.
- [ ] **Step 6: Check:** `python3 tools/validate.py --offline && python3 tools/test_credits.py && python3 tools/credits.py --totals gould-asia`. Expected: Gould with Richter, Wolf with Richter, Gould with Hart, and later Hart alone or with others. Report the totals and every name new to `artists.csv`.
- [ ] **Step 7: Commit**

```bash
git add gould-asia/plates.csv gould-asia/credits.csv gould-asia/sources/imprints.csv tools/credits.py tools/test_credits.py artists.csv
git commit -m "Asia: every plate's credit line read; Richter, Wolf, Hart and the plates after Gould"
```

---

### Task 8: Read *The Birds of America*, Havell edition (435 plates)

**Files:**
- Modify: `havell/plates.csv`, `havell/credits.csv`
- Create: `havell/sources/imprints.csv`
- Maybe modify: `tools/credits.py`, `tools/test_credits.py`, `artists.csv`

**Interfaces:**
- Consumes: `tools/imprints.py` CLI, `tools/credits.py`.
- Produces: every `havell/plates.csv` row has `imprint`, or an empty one with a `credit line` note.

- [ ] **Step 1: Crop and draft:** `python3 tools/imprints.py crop havell`. Expected: `435 sheets cropped`.
  - Havell sheets are audubon.org's scans at up to 6636 px wide, with the art running close to the credit lines on many plates.
  - Open the first two contact sheets before going on, and check that the corner crops hold the credit lines, not the caption or the art. Widen or narrow `corners()`' thresholds only if they don't, and re-run Task 3's tests.
- [ ] **Step 2: Contact sheets and readings file:** `python3 tools/imprints.py sheets havell && python3 tools/imprints.py draft havell`. Expected: 435 plates on 37 sheets.
- [ ] **Step 3: Read by eye,** as in steps 4–5 of the Reading protocol: about 4 readers.
  - The right corner often holds two lines (plate 1: "Engraved by W.H. Lizars Edinr." over "Retouched by R. Havell Junr.").
  - Some early plates may read "R. Havell & Son". A date or a "London" in the line is part of it: record it verbatim.
  - The scan for a hard case is `image_url`, the same audubon.org image, so a line unreadable on the sheet will rarely be readable there. Use `read` = `none` with a note when that happens.
- [ ] **Step 4: Decide the Havell name forms.** A bare "R. Havell" (without "Junr.") is the son unless the line says "& Son". Before mapping it, confirm this in the Havell literature: Robert Havell Sr. worked with his son on the early plates, and the "& Son" credit and the son's sole credit come in turn.
  - Map `R. Havell` → `Robert Havell Jr.` only with that confirmed. Map `R. Havell & Son` → a firm row `Robert Havell & Son` in `artists.csv` (look for a Wikidata item; else blank).
  - Write the source in the README note (Task 11).
  - If the source doesn't settle it, map `R. Havell` to a firm-free row `R. Havell` (kind `person`, no QID), and say so in the report.
- [ ] **Step 5: Apply:** `python3 tools/imprints.py apply havell ~/Projects/historical-bird-plates-assets/havell-v1-imprints/readings.csv`, handling new wordings and names as in step 6 of the protocol.
- [ ] **Step 6: Check:** `python3 tools/validate.py --offline && python3 tools/test_credits.py && python3 tools/credits.py --totals havell`. Expected:
  - John James Audubon `drew` on every plate whose line was read;
  - W. H. Lizars `engraved` on the first plates (about 10), and Havell `retouched` on those;
  - Havell `engraved`, `printed` and `coloured` from then on.
  
  Report the totals.
- [ ] **Step 7: Commit**

```bash
git add havell/plates.csv havell/credits.csv havell/sources/imprints.csv tools/credits.py tools/test_credits.py artists.csv
git commit -m "Havell: every plate's credit line read; Lizars and the Havells"
```

---

### Task 9: Wikidata: creators from the credit line for new items

**Files:**
- Modify: `tools/quickstatements.py`
- Create: `tools/test_quickstatements.py`
- Modify: `.github/workflows/validate.yml`

**Interfaces:**
- Consumes: `artists.csv`, `<folio>/credits.csv`, `plates.csv` `imprint`, `page_url` / `image_url`.
- Produces, in `tools/quickstatements.py`:
  - `ROLE_ITEM: dict[str, str]`
  - `artist_qids() -> dict[str, str]`
  - `credited(folder: str, per_volume: bool) -> dict[tuple[str, str], list[dict]]`
  - `creator_lines(subject: str, plate_credits: list[dict], qids: dict[str, str], url: str, imprint: str) -> list[str]`

- [ ] **Step 1: Write the failing tests**

`tools/test_quickstatements.py`:

```python
"""Tests for quickstatements.py's statements, on fixtures; no network.

    python3 tools/test_quickstatements.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quickstatements as qs  # noqa: E402

QIDS = {"John Gould": "Q313787", "Elizabeth Gould": "Q253875", "Edward Lear": "Q309759",
        "Charles Joseph Hullmandel": "Q376691", "Robert Havell Jr.": "Q2157495"}
URL = "https://www.biodiversitylibrary.org/page/42174243"
REF = f'\tS854\t"{URL}"\tS1683\ten:"Drawn on Stone by E. Lear | Printed by C. Hullmandel"'


def credit(name: str, role: str) -> dict:
    return {"name": name, "role": role}


class CreatorLines(unittest.TestCase):
    def test_roles_qualify_creator_and_the_printer_is_printed_by(self):
        lines = qs.creator_lines("LAST", [credit("Edward Lear", "lithographed"),
                                          credit("Charles Joseph Hullmandel", "printed")],
                                 QIDS, URL, "Drawn on Stone by E. Lear | Printed by C. Hullmandel")
        self.assertEqual(lines, [f"LAST\tP170\tQ309759\tP3831\tQ16947657{REF}",
                                 f"LAST\tP872\tQ376691{REF}"])

    def test_a_joint_credit_gives_each_name_both_roles(self):
        lines = qs.creator_lines("LAST", [credit("John Gould", "drew"), credit("John Gould", "lithographed"),
                                          credit("Elizabeth Gould", "drew"), credit("Elizabeth Gould", "lithographed")],
                                 QIDS, URL, "x")
        self.assertEqual([x.split("\t")[:7] for x in lines],
                         [["LAST", "P170", "Q313787", "P3831", "Q15296811", "P3831", "Q16947657"],
                          ["LAST", "P170", "Q253875", "P3831", "Q15296811", "P3831", "Q16947657"]])

    def test_retouched_has_no_role_item_and_a_name_without_a_qid_is_left_out(self):
        lines = qs.creator_lines("LAST", [credit("Robert Havell Jr.", "retouched"), credit("Walter", "printed")],
                                 QIDS, URL, "x")
        self.assertEqual([x.split("\t")[:4] for x in lines], [["LAST", "P170", "Q2157495", "S854"]])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 tools/test_quickstatements.py`
Expected: FAIL: `AttributeError: module 'quickstatements' has no attribute 'creator_lines'`

- [ ] **Step 3: Add the statement builders to `tools/quickstatements.py`**

Below `LIST_ARTICLE = …`, add:

```python
DRAFTSPERSON, LITHOGRAPHER, ENGRAVER, COLORIST = "Q15296811", "Q16947657", "Q329439", "Q1111648"
# credits.csv role -> the item that qualifies `creator` (P3831, object of statement has role).
# "retouched" has none: Wikidata's retoucher (Q33383789) is a photographic trade, so a
# retoucher is a creator with no role rather than a wrong one. "printed" is `printed by`.
ROLE_ITEM = {"drew": DRAFTSPERSON, "lithographed": LITHOGRAPHER, "engraved": ENGRAVER, "coloured": COLORIST}
```

After `def clean(…)`, add:

```python
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
```

- [ ] **Step 4: Use them in `batch()`**

In `batch()`:
- After `per_volume = …`, add `creds, qids = credited(folder, per_volume), artist_qids()`.
- In the `CREATE` block, delete the line `f"LAST\tP170\t{artist}"]` and close the list on the line before it (`f"LAST\tP361{part}"]`).
- After `subject = …` is set in both branches (just before `if printed:`), add:

```python
        url = p.get("page_url") or p.get("image_url") or ""
        if p.get("imprint") and url:
            block += creator_lines(subject, creds.get(k, []), qids, url, p["imprint"])
```

The folio's fixed `artist` stays in `FOLIOS`: `existing()` still uses it to recognise other people's unnumbered prints of the plate.

In the module docstring, replace `creator, title, …` with `creators and printer from the plate's credit line (credits.csv), each referenced to the scan, title, …`. In the README's description of `tools/quickstatements.py`, make the same change in Task 11.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 tools/test_quickstatements.py`
Expected: `OK` (3 tests).

- [ ] **Step 6: Check a real batch by eye**

Run: `python3 tools/quickstatements.py gould-europe --plates 37,100 --no-check`
Expected: two `CREATE` blocks.
- Plate 37 has `LAST\tP170\tQ309759\tP3831\tQ16947657\tS854\t"https://www.biodiversitylibrary.org/page/…"\tS1683\ten:"…"` and `LAST\tP872\tQ376691…`.
- Plate 100 has two `P170` lines (John and Elizabeth Gould), each with two roles.
- Neither has a bare `LAST\tP170\tQ313787`.

- [ ] **Step 7: Add the test to CI and commit**

In `.github/workflows/validate.yml`, add after the `test_imprints.py` line:

```yaml
      - run: python3 tools/test_quickstatements.py
```

```bash
git add tools/quickstatements.py tools/test_quickstatements.py .github/workflows/validate.yml
git commit -m "quickstatements.py: creators from the credit line, with their roles and the printer"
```

---

### Task 10: Wikidata: the correction batch (`--fix-creators`)

**Files:**
- Modify: `tools/quickstatements.py`
- Modify: `tools/test_quickstatements.py`

**Interfaces:**
- Consumes: `creator_lines`, `credited`, `artist_qids`, `ROLE_ITEM` (Task 9); `existing()`'s API reads.
- Produces, in `tools/quickstatements.py`:
  - `value(snak: dict)`
  - `entities(work: str) -> dict[str, dict]`
  - `plate_items(ents: dict, work: str, volumes: bool) -> dict[tuple[str, str], list[tuple[str, dict]]]`
  - `ours(claims: dict) -> bool`
  - `fix_item(qid: str, claims: dict, plate_credits: list[dict], qids: dict[str, str], url: str, imprint: str) -> tuple[list[str], list[str]]`
  - `fix(folder: str, only: set | None, limit: int | None) -> tuple[list[list[str]], list[str]]`
  - CLI flag `--fix-creators`

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_quickstatements.py`, before `if __name__ == "__main__":`:

```python
def item(p170: list[dict], depicts_ref: str = qs.REPO + "/tree/main/gould-europe") -> dict:
    """An item's claims, as wbgetentities gives them."""
    snak = lambda qid: {"datavalue": {"value": {"id": qid}}}
    return {"P170": p170,
            "P180": [{"mainsnak": snak("Q1"), "references": [{"snaks": {"P854": [{"datavalue": {"value": depicts_ref}}]}}]}]}


def creator(qid: str, references: list | None = None) -> dict:
    s = {"mainsnak": {"datavalue": {"value": {"id": qid}}}}
    if references:
        s["references"] = references
    return s


LEAR = [credit("Edward Lear", "lithographed"), credit("Charles Joseph Hullmandel", "printed")]
GOULDS = [credit("John Gould", "drew"), credit("John Gould", "lithographed"),
          credit("Elizabeth Gould", "drew"), credit("Elizabeth Gould", "lithographed")]


class FixItem(unittest.TestCase):
    def test_ours_is_an_item_whose_depicts_cites_this_dataset(self):
        self.assertTrue(qs.ours(item([])))
        self.assertFalse(qs.ours(item([], depicts_ref="https://example.org/catalogue")))

    def test_an_unreferenced_gould_the_line_does_not_name_is_removed(self):
        lines, reports = qs.fix_item("Q9", item([creator(qs.GOULD)]), LEAR, QIDS, URL, "imprint")
        self.assertIn("-Q9\tP170\tQ313787", lines)
        self.assertTrue(any(x.startswith("Q9\tP170\tQ309759\tP3831\tQ16947657") for x in lines))
        self.assertTrue(any(x.startswith("Q9\tP872\tQ376691") for x in lines))
        self.assertEqual(reports, [])

    def test_a_referenced_gould_is_kept_and_reported(self):
        ref = [{"snaks": {"P248": [{"datavalue": {"value": {"id": "Q5"}}}]}}]
        lines, reports = qs.fix_item("Q9", item([creator(qs.GOULD, ref)]), LEAR, QIDS, URL, "imprint")
        self.assertNotIn("-Q9\tP170\tQ313787", lines)
        self.assertEqual(len(reports), 1)

    def test_a_gould_the_line_names_gets_roles_not_removed(self):
        lines, _ = qs.fix_item("Q9", item([creator(qs.GOULD)]), GOULDS, QIDS, URL, "imprint")
        self.assertNotIn("-Q9\tP170\tQ313787", lines)
        self.assertTrue(any(x.startswith("Q9\tP170\tQ313787\tP3831\tQ15296811\tP3831\tQ16947657") for x in lines))

    def test_a_statement_already_referenced_to_the_scan_is_not_repeated(self):
        done = [{"snaks": {"P854": [{"datavalue": {"value": URL}}]}}]
        lines, _ = qs.fix_item("Q9", item([creator("Q309759", done)]), LEAR, QIDS, URL, "imprint")
        self.assertFalse(any(x.startswith("Q9\tP170\tQ309759") for x in lines))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 tools/test_quickstatements.py`
Expected: FAIL: `AttributeError: module 'quickstatements' has no attribute 'ours'`

- [ ] **Step 3: Record a batch to compare the refactor against**

Run: `python3 tools/quickstatements.py gould-australia --limit 5 > .cache/qs-before.txt 2>&1; tail -1 .cache/qs-before.txt`
Expected: a summary line such as `0 new items, 0 existing items given their plate, N skipped as already on Wikidata`.

- [ ] **Step 4: Factor the entity fetch out of `existing()`**

Above `existing()`, add:

```python
def value(snak: dict):
    return snak.get("datavalue", {}).get("value")


def entities(work: str) -> dict[str, dict]:
    """Every item that is part of the work, by QID, with its claims and English label.
    Pages sorted by relevance shift under an index that is still updating, so an item
    can come twice and another not at all; creation order holds still."""
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
    out = {}
    for i in range(0, len(qids), 50):
        out.update(api(action="wbgetentities", ids="|".join(qids[i:i + 50]),
                       props="claims|labels", languages="en")["entities"])
    return out
```

In `existing()`:
- Replace everything from `# Pages sorted by relevance…` through the `wbgetentities` loop header with `nums, pages, unnumbered = set(), set(), collections.defaultdict(list)` and `for qid, e in entities(work).items():`.
- Dedent the loop body by one level, and delete the local `value = lambda …` (the module-level `value` replaces it).

The body is otherwise unchanged.

- [ ] **Step 5: Confirm the refactor changed nothing**

Run: `python3 tools/quickstatements.py gould-australia --limit 5 > .cache/qs-after.txt 2>&1; diff .cache/qs-before.txt .cache/qs-after.txt && echo same`
Expected: `same`.

- [ ] **Step 6: Add the correction functions**

After `existing()`, add:

```python
def plate_items(ents: dict, work: str, volumes: bool) -> dict[tuple[str, str], list[tuple[str, dict]]]:
    """Items that are part of the work, by (volume, plate number) as their P361 qualifiers give them."""
    out: dict = collections.defaultdict(list)
    for qid, e in ents.items():
        claims = e.get("claims", {})
        for s in claims.get("P361", []):
            if (value(s["mainsnak"]) or {}).get("id") != work:
                continue
            qual = s.get("qualifiers", {})
            vol = next((value(x) for x in qual.get("P478", []) if value(x)), "")
            for x in qual.get("P1545", []):
                if value(x):
                    out[(volume_key(vol) if volumes else "", value(x))].append((qid, claims))
    return out


def ours(claims: dict) -> bool:
    """Made from this dataset: a `depicts` referenced to this repository."""
    return any(str(value(x) or "").startswith(REPO)
               for s in claims.get("P180", []) for ref in s.get("references", [])
               for x in ref.get("snaks", {}).get("P854", []))


def fix_item(qid: str, claims: dict, plate_credits: list[dict], qids: dict[str, str], url: str,
             imprint: str) -> tuple[list[str], list[str]]:
    """The edits that bring one item's creators into line with its plate's credit line, and
    what to report. A creator the line doesn't name is removed only if unreferenced, as this
    dataset's own statements were; a referenced one is someone else's claim and stays."""
    def at_scan(prop: str, target: str) -> bool:
        return any((value(s["mainsnak"]) or {}).get("id") == target
                   and any(value(x) == url for ref in s.get("references", [])
                           for x in ref.get("snaks", {}).get("P854", []))
                   for s in claims.get(prop, []))
    lines = [x for x in creator_lines(qid, plate_credits, qids, url, imprint)
             if not at_scan(x.split("\t")[1], x.split("\t")[2])]
    named = {qids.get(c["name"]) for c in plate_credits if c["role"] != "printed"}
    reports = []
    for s in claims.get("P170", []):
        v = (value(s["mainsnak"]) or {}).get("id")
        if v in ARTIST and v not in named:
            if s.get("references"):
                reports.append(f"{qid}: keeps creator {ARTIST[v]}, which someone else has referenced")
            else:
                lines.append(f"-{qid}\tP170\t{v}")
    return lines, reports


def fix(folder: str, only: set | None, limit: int | None) -> tuple[list[list[str]], list[str]]:
    """A correction batch for the plate items this dataset made: one block per item."""
    work = FOLIOS[folder][0]
    plates = read(ROOT / folder / "plates.csv")
    species = read(ROOT / folder / "species.csv")
    per_volume = bool(species) and "volume" in species[0]
    creds, qids = credited(folder, per_volume), artist_qids()
    works = {work} | {w for (f, _), (w, _) in SEPARATE.items() if f == folder}
    items = {w: plate_items(entities(w), w, per_volume and w == work) for w in works}
    blocks, reports = [], []
    for p in plates:
        vol = p.get("volume", "") if per_volume else ""
        n = p["plate"]
        tag = f"{vol}.{n}" if vol else n
        if only and tag not in only:
            continue
        on = SEPARATE.get((folder, vol), (work,))[0]
        mine = [(qid, claims) for qid, claims in items[on].get((volume_key(vol) if on == work else "", n), [])
                if ours(claims)]
        if not mine:
            continue
        if not any(c["role"] != "printed" for c in creds.get((vol, n), [])):
            # No credit line read, or only the printer's: no evidence about the artist.
            reports.append(f"plate {tag}: no artist's credit line read; {', '.join(x for x, _ in mine)} left as it is")
            continue
        url = p.get("page_url") or p.get("image_url") or ""
        for qid, claims in mine:
            lines, rep = fix_item(qid, claims, creds.get((vol, n), []), qids, url, p["imprint"])
            reports += rep
            if lines:
                blocks.append(lines)
        if limit and len(blocks) >= limit:
            break
    return blocks, reports
```

- [ ] **Step 7: Add the flag**

In `main()`, after the `--chunk`/`-o` arguments:

```python
    ap.add_argument("--fix-creators", action="store_true",
                    help="instead: a batch correcting the creators of the plate items this dataset made")
```

Replace `blocks, skipped, adopted = batch(…)` with:

```python
    if args.fix_creators:
        blocks, reports = fix(args.folio, only, args.limit)
        for r in reports:
            print(r, file=sys.stderr)
    else:
        blocks, skipped, adopted = batch(args.folio, only, args.limit, not args.no_check)
```

Replace the closing summary with:

```python
    if args.fix_creators:
        print(f"{len(blocks)} items to correct, {sum(len(b) for b in blocks)} edits", file=sys.stderr)
    else:
        created = len(blocks) - adopted
        print(f"{created} new items, {adopted} existing items given their plate, "
              f"{skipped} skipped as already on Wikidata", file=sys.stderr)
```

Add to the module docstring's usage block:

```
    python3 tools/quickstatements.py gould-europe --fix-creators --chunk 80 -o fix-europe   # correct existing items
```

Add a paragraph to the docstring:

```
--fix-creators writes a batch for the plate items this dataset already made (those
whose `depicts` cites this repository): each credited artist and the printer are
added from the credit line, and a `creator: John Gould` (or Audubon) the line does
not name is removed if it is unreferenced. Plates with no artist's credit line read
are left as they are.
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 tools/test_quickstatements.py`
Expected: `OK` (8 tests).

- [ ] **Step 9: Write the real batches and check them**

```bash
mkdir -p ~/Projects/historical-bird-plates-assets/wikidata
for f in gould-europe gould-australia gould-asia gould-britain havell; do
  python3 tools/quickstatements.py $f --fix-creators --chunk 80 -o ~/Projects/historical-bird-plates-assets/wikidata/fix-$f 2> ~/Projects/historical-bird-plates-assets/wikidata/fix-$f.log
  tail -1 ~/Projects/historical-bird-plates-assets/wikidata/fix-$f.log
done
```

Expected item counts are close to the 2026-10-01 tallies of this dataset's items: Europe 392, Australia 558 + Supplement 76, Asia 269, Great Britain 7, Havell 399. The total is about 5,000–7,000 edits. Then:

```bash
grep -h '^-Q' ~/Projects/historical-bird-plates-assets/wikidata/fix-*.qs | awk '{print $3}' | sort | uniq -c
grep -h 'keeps creator' ~/Projects/historical-bird-plates-assets/wikidata/fix-*.log | wc -l
```

Check:
- removals are only of Q313787 (Gould) and Q182882 (Audubon);
- the Gould removals match the plates whose credit line doesn't name him (from `credits.csv`);
- there are no Audubon removals unless a Havell line failed to name him.

- [ ] **Step 10: The sandbox check (Wells, in QuickStatements)**

QuickStatements needs Wells's Wikidata login, so this is his step. Give Wells this two-line batch for the Wikidata Sandbox item (Q4115189), to confirm that QuickStatements merges roles and a reference onto an existing `creator` statement rather than adding a second one:

```
Q4115189	P170	Q313787
Q4115189	P170	Q313787	P3831	Q15296811	P3831	Q16947657	S854	"https://www.biodiversitylibrary.org/page/42174243"	S1683	en:"Drawn from Life & on Stone by J. & E. Gould"
```

Expected on Q4115189: one `creator: John Gould` statement, with both roles and the reference.
- If QuickStatements made two statements instead, change `fix_item` to emit `-QID P170 Q313787` before the full line where the existing statement is unreferenced, update the tests, and re-run Step 9.
- Ask Wells to undo the sandbox edits afterwards.

- [ ] **Step 11: Commit**

```bash
git add tools/quickstatements.py tools/test_quickstatements.py
git commit -m "quickstatements.py --fix-creators: correct the creators of the plates already on Wikidata"
```

Then tell Wells where the batches are (`~/Projects/historical-bird-plates-assets/wikidata/fix-*.qs`), the edit count, and that they run one file after another in QuickStatements, as the existing batches do.

---

### Task 11: The READMEs, citation metadata, and the last check

**Files:**
- Modify: `README.md`, `havell/README.md`, `gould-europe/README.md`, `gould-australia/README.md`, `gould-asia/README.md`, `gould-britain/README.md`
- Modify: `CITATION.cff`, `.zenodo.json`
- Modify: `tools/validate.py`

**Interfaces:**
- Consumes: `python3 tools/credits.py --totals` for every folio; the reading reports of Tasks 4–8.

- [ ] **Step 1: Require a reason for every empty credit line**

In `tools/validate.py`, in the per-folio section, after the line `per_volume = "volume" in species_cols`, add:

```python
        for p in plates:
            if not p.get("imprint") and "credit line" not in p.get("notes", ""):
                plate = ".".join(x for x in (p.get("volume", "") if per_volume else "", p["plate"]) if x)
                errors.append(f"{name}/plates.csv: plate {plate} has no imprint and no note saying why "
                              "(a note with the words 'credit line')")
```

Add `- an empty imprint has a note with the words "credit line"` to the docstring's list.

Run: `python3 tools/validate.py --offline`
Expected: `ok`. Any error here is a plate missed in Tasks 4–8: go back and read it.

- [ ] **Step 2: Gather the facts the READMEs need**

1. Run `python3 tools/credits.py --totals` and keep its output.
2. Dispatch a researcher subagent to establish, each with a citation (author, title, year, and the page or chapter):
   - (a) how many plates of *The Birds of Europe* Edward Lear drew;
   - (b) the division of labour between John and Elizabeth Gould: his sketches, her finished drawings and lithographs;
   - (c) when H. C. Richter began working for Gould, and his part after Elizabeth Gould's death in 1841;
   - (d) Joseph Wolf's and William Hart's parts in *Asia* and *Great Britain*;
   - (e) R. B. Sharpe completing *Asia* after Gould's death in 1881, and who drew those plates;
   - (f) W. H. Lizars's first ten plates of *The Birds of America* and the move to Robert Havell Jr.; the Havells' "& Son" period;
   - (g) the parts of Joseph Mason, George Lehman, Maria Martin and John Woodhouse Audubon in the Havell plates (backgrounds, plants, later birds);
   - (h) "Walter" and "Walter & Cohn", the printers.
   
   Preferred sources: Sauer, *John Gould the Bird Man: A Chronology and Bibliography* (1982); Tree, *The Ruling Passion of John Gould* (1991); McEvey, *John Gould's Contribution to British Art* (1973) or his writing on Elizabeth Gould; Hyman, *Edward Lear's Birds* (1980); Fries, *The Double Elephant Folio* (1973); Audubon's *Ornithological Biography* (1831–39).
   
   The researcher returns each fact with its citation, or "not established". A fact without a citation is left out of the READMEs.

- [ ] **Step 3: Write "Who made the plates" in each folio README**

Insert it before `## How the plates were identified`. Structure:

```markdown
## Who made the plates

Every plate is credited on its face, in small engraved lines below the art: on the left who drew it and put it on stone, on the right who printed it. `imprint` in `plates.csv` gives them verbatim; `credits.csv` gives one row per plate, name and role, read from them by `tools/credits.py`.

| Credit line | Plates |
|---|---:|
| <each distinct artist line, as printed, most common first> | <n> |

| Printer | Plates |
|---|---:|
| <each printer> | <n> |

<one paragraph, cited: what the lines don't show. For a Gould folio, who did what in a joint credit, using fact (b) and the folio's own facts (a), (c), (d) or (e). For Havell, Lizars and the Havells, then Mason, Lehman, Martin and John Woodhouse Audubon (f, g). Name the source after each claim, e.g. "(Tree 1991, ch. 4)".>

<If any plate has no credit line read: "N plates have no credit line read; notes says why for each.">

Sources: <full references for the citations above>.
```

The counts come from `credits.py --totals` and from `imprint` (group the left-corner lines by their exact text with a short script). Each folio README's opening sentence names its artists (Europe line 3, Australia line 3, Asia line 3, Great Britain line 3, Havell line 3). Correct it to agree with the counts. For example, Havell's line credits only Robert Havell Jr.; it should name Lizars for the first plates.

- [ ] **Step 4: The root README**

- **Opening:** after the second paragraph, add one paragraph: every plate also carries its engraved credit line, read off the plate and given verbatim with who it names and for what. Gould's plates were drawn and put on stone by Elizabeth Gould, Edward Lear, H. C. Richter, Joseph Wolf and William Hart as well as by Gould himself; Audubon's were engraved by W. H. Lizars and Robert Havell Jr. Use the totals for any number.
- **Folio list:** after each folio's `… plates · … identified …` line, add a line `Credit lines: <the two or three most frequent artist names with their plate counts>`, e.g. `Credit lines: John and Elizabeth Gould 379 · Edward Lear 68`, with real numbers.
- **Tables** table: in the `plates.csv` row's key columns, add `` `imprint` (the plate's credit lines, verbatim) ``. Add rows:
  - `| credits.csv | plate × name × role | volume, plate, name, role (drew, lithographed, engraved, retouched, printed, coloured), as_printed; generated from imprint by tools/credits.py |`
  - `| artists.csv (root) | person or firm on a credit line | name, kind, wikidata, note |`
- **Contributing:** add a bullet: `**Fix a credit line:** correct imprint in that folio's plates.csv, as engraved, and run python3 tools/credits.py. A new wording or name must be added to the tables in tools/credits.py first, and a new person or firm to artists.csv.`
- **Validation:** add a bullet: `that every credits.csv is what tools/credits.py writes from imprint, and every name is in artists.csv;`
- **quickstatements paragraph:** replace `creator,` with `creators and printer from the credit line, each referenced to the scan,`, and add a sentence on `--fix-creators`.
- **Acknowledgements,** first bullet: `- **A reader of the r/birding announcement:** pointed out that many plates published under Gould's name were drawn by others, Elizabeth Gould first among them, and should be credited. The credit lines in plates.csv and credits.csv are the answer.`

- [ ] **Step 5: Citation metadata**

- `CITATION.cff`: in the `abstract`, after `with eBird, Wikidata, GBIF, Avibase and BirdNET identifiers,`, add `each plate's engraved credit line (who drew, lithographed or engraved and printed it),`.
- `.zenodo.json`: in `description`, after the sentence ending `unresolved plates are kept with the reason.`, add `Each plate's engraved credit line is given verbatim, with the artists, engravers and printers it names and their roles.`. Add `"Elizabeth Gould"` and `"Edward Lear"` to `keywords`.

Check `.zenodo.json` still parses: `python3 -c "import json; json.load(open('.zenodo.json'))"`.

- [ ] **Step 6: Final checks**

Run: `python3 tools/validate.py && python3 tools/test_credits.py && python3 tools/test_imprints.py && python3 tools/test_quickstatements.py && python3 tools/test_identify.py && python3 tools/credits.py --check`
Expected: `ok`, then `OK` four times, and no `out of date` line.

Proof-read the six README diffs with `git diff README.md */README.md`:
- no number that disagrees with `--totals`;
- no claim without a source;
- the commenter not named.

- [ ] **Step 7: Commit**

```bash
git add README.md */README.md CITATION.cff .zenodo.json tools/validate.py
git commit -m "READMEs: who made the plates, from their credit lines"
```
