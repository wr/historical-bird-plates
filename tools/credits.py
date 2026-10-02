"""Write each folio's credits.csv from the credit lines in its plates.csv.

    python3 tools/credits.py                          # write every folio's credits.csv
    python3 tools/credits.py --check                  # exit 1 if any is out of date
    python3 tools/credits.py --totals gould-europe    # plates per name and role

A plate's `imprint` is its credit lines verbatim, joined with " | ". Each line
is a wording and the names it credits: "Drawn on Stone by E. Lear",
"J. Gould & H.C. Richter del. et lith.", "C. Hullmandel Imp.". BEFORE and
AFTER give the roles a wording stands for, written before or after the names;
a line holding two credits is split before a wording in WITHIN ("Drawn on Stone
by I & E. Gould from a Drawing by Edwd. Lear."), and so is one holding a wording written
after the names and then more names ("J.Wolf del. H.C.Richter lith."). NAMES gives the people or
firms a name form stands for, and FOLIO_NAMES the name forms that stand for
someone in one folio only. Wordings match with case, full stops, commas and
spacing folded ("del. et lith." is "del et lith"); name forms with full stops,
commas and spacing dropped ("H. C. Richter" is "H.C.Richter"). A line whose
wording or name is in neither table is an error: check the variant on the
plate, then add it.

Joint credits stay joint: "J. Gould & H.C. Richter del. et lith." credits both
men with drawing and lithographing, because that is all the plate says.

A place and a date after the names ("R.Havell, London 1831.", "R.Havell & Son. London._1828.")
belong to the line, which keeps them in the imprint, but not to the name.

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
    "Drawn from Nature and on Stone by": ("drew", "lithographed"),
    "Drawn on Stone from Nature by": ("drew", "lithographed"),
    "Drawn on Stone from Life by": ("drew", "lithographed"),
    "Drawn on Stone by": ("lithographed",),
    "Drawn from Nature by": ("drew",),
    # "Published" is not one of ROLES: Audubon published his own plates, and the wording gives him "drew".
    "Drawn from Nature and Published by": ("drew",),
    "Drawn from Nature & Published by": ("drew",),
    "Drawn by": ("drew",),
    "Engraved, Printed & Coloured by": ("engraved", "printed", "coloured"),
    "Engraved, Printed and Coloured by": ("engraved", "printed", "coloured"),
    "Engraved: Printed and Coloured by": ("engraved", "printed", "coloured"),  # Havell 396, a colon after Engraved
    "Engraved, Printed & Colotured by": ("engraved", "printed", "coloured"),  # Havell 296, as engraved
    "Engraved by": ("engraved",),
    "Printed & Coloured by": ("printed", "coloured"),
    "Printed and Coloured by": ("printed", "coloured"),
    "Coloured by": ("coloured",),
    "Retouched by": ("retouched",),
    "Printed by": ("printed",),
    "from a Drawing by": ("drew",),
}
# A wording that begins a second credit inside a line, which is split before it:
# "Drawn on Stone by I & E. Gould from a Drawing by Edwd. Lear.", "Engraved by R.Havell.Junr.
# Printed & Coloured by R.Havell. Senr. London. 1828." Each is in BEFORE too.
WITHIN = ("from a Drawing by", "Printed & Coloured by", "Printed and Coloured by")
# A wording written after the names -> the roles it gives them.
AFTER = {
    "del. et lith.": ("drew", "lithographed"),
    "del. et lith:": ("drew", "lithographed"),
    "del: et lith.": ("drew", "lithographed"),
    "del: et lith:": ("drew", "lithographed"),
    "del. et lithog.": ("drew", "lithographed"),
    "del. et lithog:": ("drew", "lithographed"),
    "del: et lithog:": ("drew", "lithographed"),
    "delt. et lith.": ("drew", "lithographed"),
    "del.": ("drew",),
    "del:": ("drew",),
    "delt.": ("drew",),
    "lith.": ("lithographed",),
    "lithog.": ("lithographed",),
    "Imp.": ("printed",),
    "Imp:": ("printed",),
    "Impt.": ("printed",),
}
# A name form as printed -> who it is: names in artists.csv.
NAMES = {
    "J. & E. Gould": ("John Gould", "Elizabeth Gould"),
    "J. Gould": ("John Gould",),
    "I. Gould": ("John Gould",),
    "I & E. Gould": ("John Gould", "Elizabeth Gould"),
    "J. Gould H.C. Richter": ("John Gould", "Henry Constantine Richter"),
    "E. Lear": ("Edward Lear",),
    "Edwd. Lear": ("Edward Lear",),
    "Waterhouse Hawkins": ("Benjamin Waterhouse Hawkins",),
    "H.C. Richter": ("Henry Constantine Richter",),
    "J. Wolf": ("Joseph Wolf",),
    "W. Hart": ("William Matthew Hart",),
    "C. Hullmandel": ("Charles Joseph Hullmandel",),
    "Hullmandel & Walton": ("Hullmandel & Walton",),
    "Hullmandel and Walton": ("Hullmandel & Walton",),
    "Walter": ("Walter",),
    "T. Walter": ("T. Walter",),
    "Walter & Cohn": ("Walter & Cohn",),
    "J.J. Audubon F.R.S. F.L.S.": ("John James Audubon",),
    "John J. Audubon F.R.S. F.L.S.": ("John James Audubon",),
    "John J. Audubon F.R.S. M.W.S.": ("John James Audubon",),
    "John J. Audubon F.R.S.E. M.W.S.": ("John James Audubon",),
    "John J. Audubon F.R.S.E. F.L.S. M.W.S.": ("John James Audubon",),
    "J.J. Audubon F.R.S.E.": ("John James Audubon",),
    "J.J. Audubon F.R.S.E. M.W.S.": ("John James Audubon",),
    "Lucy Audubon": ("Lucy Audubon",),
    "W.H. Lizars Edinr.": ("William Home Lizars",),
    "R. Havell Junr.": ("Robert Havell Jr.",),
    "Robt. Havell Junr.": ("Robert Havell Jr.",),
    "R. Havell Senr.": ("Robert Havell Sr.",),
    "R. Havell Sen.": ("Robert Havell Sr.",),
    "R. Havell & Son": ("Robert Havell & Son",),
    "R. Havell and Son": ("Robert Havell & Son",),
}
# A name form that stands for someone in one folio only -> who it is there. Looked up
# after NAMES, and only when a folio is given.
FOLIO_NAMES = {
    # Great Britain III.61: the initial before "Gould" is cut off at the sheet's edge. The
    # Birds of Great Britain is 1862-73, after Elizabeth Gould's death in 1841, and every
    # other plate of it that can be read reads J. Gould.
    "gould-britain": {"Gould": ("John Gould",)},
    # Europe 202: the printer's name did not print past "Hullman": one broken trace of a
    # letter follows it, then blank paper, mid-page. Every other plate of The Birds of Europe
    # that names its printer reads C. Hullmandel.
    "gould-europe": {"C. Hullman": ("Charles Joseph Hullmandel",)},
    "gould-australia": {
        # Australia V.8 and VII.5: the initial before "Gould" is cut off at the sheet's edge (V.8)
        # or did not print (VII.5). Every other line of The Birds of Australia that names Richter
        # with a Gould reads J. Gould (once I. Gould), never J. & E. Gould. A bare "Gould" is not
        # mapped on its own: a J. & E. Gould line that had lost its initials would read the same.
        "Gould and H.C. Richter": ("John Gould", "Henry Constantine Richter"),
        # Australia IV.3: the printer's line is faint, and no C shows before "Hullmandel", only a
        # dot; it reads "Hullmandel Imp.", not Hullmandel & Walton. Every other plate of the folio
        # printed by Hullmandel alone reads C. Hullmandel.
        "Hullmandel": ("Charles Joseph Hullmandel",),
        # Australia IV.93: a stray C is engraved before "C.Hullmandel Imp.", with a gap after it.
        "C C. Hullmandel": ("Charles Joseph Hullmandel",),
    },
    "havell": {
        # A bare "R. Havell" or "Robt. Havell", with no "Junr.", is the son. The partnership of father and
        # son was dissolved in 1828, and at his father's death the son, who had signed "R. Havell Junr.",
        # "designated himself Robert Havell" (Williams 1916, "Robert Havell, Junior, Engraver of Audubon's
        # 'The Birds of America'", Print-Collector's Quarterly 6(3), pp. 242-243; Low 2002, p. 2, dates the
        # death 1831, Williams and Lane 1832). The father is "Senr." and the firm "& Son" wherever a plate
        # names them, so a line with neither names the son. 58 of the plates that read this way come before
        # plate 106, the first dated 1831 (11, 12, 16, 21, 23, 31, and the undated 51-105): the father was
        # then alive, and the reading rests on the dissolution of the partnership alone.
        "R. Havell": ("Robert Havell Jr.",),
        "Robt. Havell": ("Robert Havell Jr.",),
        # Audubon's postnominals as engraved where they differ from every other plate of the folio. Each is
        # the whole form, checked on the sheet.
        "John J. Audubon E.R.S.E. M.W.S.": ("John James Audubon",),    # plate 10: an E where the F is
        "John J. Audubon F.R.S.E.L.S.": ("John James Audubon",),       # plate 60: an E where F.L.S. has its F
        "John J. Audubon F.R.S.P.L.S.": ("John James Audubon",),       # plate 88: a P where F.L.S. has its F
        "John J. Audnbon F.R.S. F.L.S.": ("John James Audubon",),      # plate 51: an n for the second u
        "J.J. Aududon F.R.S. F.L.S.": ("John James Audubon",),         # plate 167: a d for the b
        "J.J. Aububon F.R.S. F.L.S.": ("John James Audubon",),         # plates 216 and 251: a b for the d
        "J.J. Aubudon F.R.S. F.L.S.": ("John James Audubon",),         # plate 244: the b and d swapped
        "J.J. Audubon F.R.S. F.L": ("John James Audubon",),            # plate 286: no final S is printed
        "J.J. Audubon": ("John James Audubon",),                       # plate 291: no postnominals are printed
        "John J. Audubon F.R.S's. L. & E. F.L.S. &c.": ("John James Audubon",),   # plate 95
    },
    "gould-asia": {
        # Asia VI.74 and VII.40: the line begins at "Wolf" with blank paper to its left, so no
        # initial is engraved. Every other line of The Birds of Asia that names a Wolf reads J. Wolf.
        "Wolf": ("Joseph Wolf",),
        # Asia VII.13: "J.Wolf and Hart", no initial engraved before Hart. Every other line of the
        # folio that names a Hart reads W. Hart.
        "Hart": ("William Matthew Hart",),
        # Asia IV.5: the faint line reads "J.Gould and C.H.Richter" on the scan, the initials in
        # the wrong order. Every other Richter of the folio is H.C. Richter.
        "C.H. Richter": ("Henry Constantine Richter",),
        # Asia IV.26: the initial before "Gould" is an H on the scan (3x), not a J. The plate is
        # a Gould and Richter plate of the same part as IV.25 and IV.31, which read J.Gould.
        "H. Gould": ("John Gould",),
        # Asia III.4: the printer's line is engraved "Hulmandel & Walton Imp" (one l), at 2x on the
        # scan; every other plate with this printer reads Hullmandel & Walton.
        "Hulmandel & Walton": ("Hullmandel & Walton",),
    },
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
_WITHIN = re.compile(r"\s+(?=(?:" + "|".join(wording_pattern(w) for w in WITHIN) + r")[\s.,])", re.I)
# Longest first, so "del. et lith." is tried before "del.".
_BEFORE = [(re.compile(rf"^{wording_pattern(w)}[\s.,]+(?P<names>.+?)[\s,]*$", re.I), roles)
           for w, roles in sorted(BEFORE.items(), key=lambda x: -len(x[0]))]
_AFTER = [(re.compile(rf"^(?P<names>.+?)(?:[,:]\s*|\.(?=\S)|\s+){wording_pattern(w)}[\s.,]*$", re.I), roles)
          for w, roles in sorted(AFTER.items(), key=lambda x: -len(x[0]))]


# A wording written after names, then a capitalised word: the line holds a second credit
# ("J.Wolf del. H.C.Richter lith."). The wording must start a word, so "Hullmandel Imp." stays whole.
_THEN = re.compile(r"^(?P<head>.+?(?<![A-Za-z])(?i:" + "|".join(wording_pattern(w) for w in sorted(AFTER, key=len, reverse=True))
                   + r")[.,:]*)\s+(?P<tail>[A-Z].*)$")


# A line that ends in a bare "Engraved" has not split a credit: "Engraved, Printed & Coloured by
# R. Havell" is one wording, though "Printed & Coloured by" is also a WITHIN wording.
_BARE_ENGRAVED = re.compile(r"(?<![A-Za-z])Engraved[.,:]*$", re.I)
# The place and date at the end of a credit's names: "R.Havell, London. 1833.", "R.Havell. 1834",
# "R.Havell & Son. London._1828." (a low dash is written _). Taken off the names, never off the line.
_PLACE_DATE = re.compile(r"[\s.,:_]*(?:(?<![A-Za-z])London(?![A-Za-z])[\s.,:_]*)?"
                         r"(?:(?<![0-9])1[89][0-9]{2}(?![0-9]))?[\s.,:_]*$", re.I)


def credit_parts(line: str) -> list[str]:
    """The credits a line holds, as separate strings: split before a wording in WITHIN, and
    after a wording written after names when more names follow."""
    pieces: list[str] = []
    for part in _WITHIN.split(line):
        if pieces and _BARE_ENGRAVED.search(pieces[-1]):
            pieces[-1] += " " + part
        else:
            pieces.append(part)
    out = []
    for part in pieces:
        while (m := _THEN.match(part)):
            out.append(m.group("head"))
            part = m.group("tail")
        out.append(part)
    return out


def split_line(line: str) -> tuple[tuple[str, ...], str]:
    """A credit line's roles and the names they belong to, as printed, without a place and
    date after them ("R.Havell, London 1831." gives "R.Havell")."""
    for pattern, roles in _BEFORE + _AFTER:
        m = pattern.match(line)
        if m:
            names = m.group("names").strip()
            tail = _PLACE_DATE.search(names)
            if tail and re.search(r"[A-Za-z0-9]", tail.group()):
                names = names[:tail.start()]
            return roles, names
    raise UnknownCredit(f"no known wording in {line!r}")


def known_names(folio: str | None = None) -> dict[str, tuple[str, ...]]:
    """Name keys -> people: NAMES, then the folio's FOLIO_NAMES, if a folio is given."""
    extra = {name_key(k): v for k, v in FOLIO_NAMES.get(folio, {}).items()} if folio else {}
    return {**extra, **_NAMES}


def name_forms(names: str, known: dict[str, tuple[str, ...]] = _NAMES) -> list[str]:
    """The name forms in a line's names: the whole if the table has it ("J. & E. Gould",
    "Walter & Cohn"), else each part between "&" or "and". An "and" may touch a stop or
    comma before it, or the capital after it ("J. Gould,and", "andH.C. Richter"), or carry a
    stop of its own ("J. Gould and. H. C. Richter", Asia IV.9)."""
    if name_key(names) in known:
        return [names]
    parts = [p.strip(" ,") for p in re.split(r"\s*&\s*|\s+and\.?\s+|(?<=[.,])\s*and\s*|\s*and(?=[A-Z])", names)]
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
        for part in credit_parts(line):
            roles, names = split_line(part)
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
