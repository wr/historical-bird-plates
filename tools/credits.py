"""Write each folio's credits.csv from the credit lines in its plates.csv.

    python3 tools/credits.py                          # write every folio's credits.csv
    python3 tools/credits.py --check                  # exit 1 if any is out of date
    python3 tools/credits.py --totals gould-europe    # plates per name and role

A plate's `imprint` is its credit lines verbatim, joined with " | ". Each line
is a wording and the names it credits: "Drawn on Stone by E. Lear",
"J. Gould & H.C. Richter del. et lith.", "C. Hullmandel Imp.". BEFORE and
AFTER give the roles a wording stands for, written before or after the names;
NAMES gives the people or firms a name form stands for, and FOLIO_NAMES the
name forms that stand for someone in one folio only. Wordings match with
case, full stops, commas and spacing folded ("del. et lith." is "del et lith");
name forms with full stops, commas and spacing dropped ("H. C. Richter" is
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
    "Drawn from Life and on Stone by": ("drew", "lithographed"),
    "Drawn on Stone from Nature by": ("drew", "lithographed"),
    "Drawn on Stone from Life by": ("drew", "lithographed"),
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
    "del. et lith:": ("drew", "lithographed"),
    "del: et lith.": ("drew", "lithographed"),
    "del: et lith:": ("drew", "lithographed"),
    "del. et lithog.": ("drew", "lithographed"),
    "del. et lithog:": ("drew", "lithographed"),
    "del: et lithog:": ("drew", "lithographed"),
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
# A name form that stands for someone in one folio only -> who it is there. Looked up
# after NAMES, and only when a folio is given.
FOLIO_NAMES = {
    # Great Britain III.61: the initial before "Gould" is cut off at the sheet's edge. The
    # Birds of Great Britain is 1862-73, after Elizabeth Gould's death in 1841, and every
    # other plate of it that can be read reads J. Gould.
    "gould-britain": {"Gould": ("John Gould",)},
    # Europe 202: the printer's name did not print past "Hullman"; the paper after it is
    # blank, mid-page. Every other plate of The Birds of Europe that names its printer
    # reads C. Hullmandel.
    "gould-europe": {"C. Hullman": ("Charles Joseph Hullmandel",)},
}


@dataclass(frozen=True)
class Credit:
    name: str
    role: str
    as_printed: str


class UnknownCredit(ValueError):
    """A credit line with a wording or name form the tables don't have."""


def name_key(s: str) -> str:
    return re.sub(r"[.,\s]", "", s.casefold())


def wording_pattern(wording: str) -> str:
    tokens = " ".join(re.sub(r"[.,]", " ", wording).split()).split()
    return r"[\s.,]*".join(re.escape(t) for t in tokens)


_NAMES = {name_key(k): v for k, v in NAMES.items()}
# Longest first, so "del. et lith." is tried before "del.".
_BEFORE = [(re.compile(rf"^{wording_pattern(w)}[\s.,]+(?P<names>.+?)[\s,]*$", re.I), roles)
           for w, roles in sorted(BEFORE.items(), key=lambda x: -len(x[0]))]
_AFTER = [(re.compile(rf"^(?P<names>.+?)(?:,\s*|\s+){wording_pattern(w)}[\s.,]*$", re.I), roles)
          for w, roles in sorted(AFTER.items(), key=lambda x: -len(x[0]))]


def split_line(line: str) -> tuple[tuple[str, ...], str]:
    """A credit line's roles and the names they belong to, as printed."""
    for pattern, roles in _BEFORE + _AFTER:
        m = pattern.match(line)
        if m:
            return roles, m.group("names").strip()
    raise UnknownCredit(f"no known wording in {line!r}")


def known_names(folio: str | None = None) -> dict[str, tuple[str, ...]]:
    """Name keys -> people: NAMES, then the folio's FOLIO_NAMES, if a folio is given."""
    extra = {name_key(k): v for k, v in FOLIO_NAMES.get(folio, {}).items()} if folio else {}
    return {**extra, **_NAMES}


def name_forms(names: str, known: dict[str, tuple[str, ...]] = _NAMES) -> list[str]:
    """The name forms in a line's names: the whole if the table has it ("J. & E. Gould",
    "Walter & Cohn"), else each part between "&" or "and"."""
    if name_key(names) in known:
        return [names]
    parts = [p.strip(" ,") for p in re.split(r"\s*&\s*|\s+and\s+", names)]
    unknown = [p for p in parts if name_key(p) not in known]
    if unknown:
        raise UnknownCredit(f"no known name for {', '.join(map(repr, unknown))} in {names!r}")
    return parts


def parse(imprint: str, folio: str | None = None) -> list[Credit]:
    """The credits a plate's imprint gives, line by line, in order; each name and role once.
    Name forms are looked up in NAMES, then in the folio's FOLIO_NAMES if a folio is given."""
    known = known_names(folio)
    out: list[Credit] = []
    for line in imprint.split(" | "):
        line = line.strip()
        if not line:
            raise UnknownCredit(f"an empty line in {imprint!r}")
        roles, names = split_line(line)
        for form in name_forms(names, known):
            for person in known[name_key(form)]:
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
            found = parse(p["imprint"], folder.name)
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
    path.write_text(text, encoding="utf-8", newline="")
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
