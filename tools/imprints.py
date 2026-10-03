"""Read the credit lines engraved on each plate: crop them, draft them with OCR,
lay them out for reading by eye, and write the readings into plates.csv.

    python3 tools/imprints.py crop gould-europe                 # crops and OCR drafts -> sources/imprints.csv
    python3 tools/imprints.py sheets gould-europe               # contact sheets of the crops, for reading
    python3 tools/imprints.py draft gould-europe                # a readings file, prefilled from the drafts
    python3 tools/imprints.py scan gould-europe 132 418         # hard cases: the unaltered scan's corners
    python3 tools/imprints.py check gould-europe [--zoom 4]     # each recorded imprint over its crops, enlarged
    python3 tools/imprints.py apply gould-europe READINGS.csv   # write the readings; regenerate credits.csv

Sheets are read from the folio's release, downloaded into ASSETS/<release>/.
Crops, contact sheets, scans, check images and the readings file go to
ASSETS/<release>-imprints/, never into the repo.

`check` is for checking what was recorded, down to the stops. Each plate with an
imprint gets a block: its tag and imprint as plates.csv has them, then its left
crop and its right crop with contrast raised, enlarged ZOOM times (or --zoom N).
An enlarged crop wider than an image is cut into segments overlapping by OVERLAP
px, shown in order; one too tall is cut into bands the same way. An image takes
as many whole blocks as fit; a block too big for one image goes onto images of
its own, its head repeated on each. No image is wider than CHECK[0] or larger than
CHECK[1] pixels, so none is shown scaled down. The images are check/001.png,
002.png and so on (a digit more past 999); check/index.csv lists every image
each plate is on, in plates.csv order.

`crop` finds the credit lines by ink, not by OCR. On a half-size grey copy of
the lower half of the sheet, each pixel is graded by how much darker it is than
the paper around it, so the gutter's shadow and a foxed margin drop out. Ink is
joined into blobs, and blobs level with each other into lines. In each half of
the sheet the credit line is the lowest line of small text (Gould: it sits
level with the caption or below it), or the outermost (Havell: the title often
sits below the credit lines). A line across the centre is the caption; a line
with art just above it is in the art, like a signature on the stone; a line
with no dark ink is pencil. A corner left empty is looked at again, faint ink
counted, level with the other corner's line. Each crop is the lines at full
size and a margin. Where no line is found, the crop is a strip where it should
be, and the record's note says so: that plate is read from the scan.

A readings file has the columns volume (where the folio numbers per volume),
plate, imprint, read and note, one row per plate (others, such as `sheet`, are
ignored). `read` is eye (read off the crop), scan (read off the unaltered scan)
or none (nothing can be read; `note` says why, with the words "credit line").

An imprint's spacing follows one convention, not the engraver's gaps, which run
from touching to wide with nothing between to tell them apart (`normalise`, which
`apply` runs). In each line: whitespace collapsed; no space before a stop,
comma, semicolon or colon, and one after it unless the line ends there or another
of them follows; one space each side of & ("&c." is a word, not an & and a c, and is
left whole); and "and" run into a capital split off ("GouldandH." is "Gould and H.").
Words of a known wording (any in credits.BEFORE
or AFTER) that run together take one space between them ("Drawnfrom" is "Drawn
from", "onStone" "on Stone", "delet lith" "del et lith"), and so does "by" run into
a capital ("byJ. Gould"). So "J.Gould &H.C.Richter,del" is written "J. Gould &
H. C. Richter, del". Other letters that run together with no mark between
("Hullmandel") are left as they are. Initials are written by convention too: every
capital standing as an initial, before a name, another initial, & or and, or glued
to a name, is written with a stop and a space ("J Wolf & HCRichter" is "J. Wolf &
H. C. Richter", "J & E Gould" "J. & E. Gould"), because the stops after initials
are fused with the letters' serifs at the scans' resolution and cannot be read.
A comma or colon directly after an initial is such a stop, misread ("J, Gould" is
"J. Gould", "C: Hullmandel" "C. Hullmandel"); one after a name ("Richter, del.")
is not. The mark after an abbreviation (del, delt, lith, lithog, Imp, Impt, Edwd,
Edinr, Junr, Senr) is written as a stop too: "delt," is "delt.", "Imp:" "Imp.", "del: et
lith:" "del. et lith."; the engraver's variants of that mark do not converge, and a
mark that is not there stays absent ("del et lith" is unchanged). Every other stop,
and commas, colons, capitals, & or and, and spelling are as engraved.

Needs Pillow, and macOS for the OCR (tools/ocr.swift, compiled into .cache/ on
first use). `apply`, the line finding and the layout of the contact sheets need
neither.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import credits  # noqa: E402

ROOT = credits.ROOT
CACHE = ROOT / ".cache"
ASSETS = Path.home() / "Projects" / "historical-bird-plates-assets"
RELEASE = {"havell": "havell-v1", "gould-europe": "gould-europe-v1", "gould-australia": "gould-australia-v1",
           "gould-britain": "gould-britain-v2", "gould-asia": "gould-asia-v1"}
UA = {"User-Agent": "historical-bird-plates imprints (+https://github.com/wr/historical-bird-plates)"}
BAND = 0.35             # scan: the bottom of the scan shown for a hard case
REGION = 0.5            # crop: the lower part of the sheet searched for credit lines
SHADES = (18, 30, 80)   # faint ink, ink, dark ink: this much darker than the paper around it, of 255
RULE = {"havell": "outermost"}   # which line of a corner is its credit line; "lowest" for the rest
CROP = (1900, 600)      # a crop's largest size, px, once scaled
STRIP = (1900, 400)     # where no credit line is found, the strip cropped instead
LEAST = 0.75            # a crop is never scaled smaller than this
SHEET = 2000            # a contact sheet's width, and its greatest height, px
PER_SHEET = 12          # plates per contact sheet, at most
CHECK = (1400, 1_100_000)   # check: an image's greatest width, px, and greatest size, pixels in all
ZOOM = 4                # check: a crop is enlarged by this, unless --zoom says otherwise
OVERLAP = 120           # check: tiles of an enlarged crop overlap by this, px: a letter at 4x
LABEL, GAP, PAD = 26, 10, 6  # check: the label over each part of a crop, the space under it, the margin, px
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
#
# Finding the lines works on a mask: one byte per pixel of the working copy, in
# rows of `width`, 0 for paper, 1 faint ink, 2 ink, 3 dark ink. A blob or a line
# is [x0, y0, x1, y1, ink, dark] (x1, y1 exclusive; ink and dark count pixels).
# Sizes are in units: a thousandth of the sheet's long side, in pixels of the
# working copy.

def blobs(mask: bytes, width: int, gap: int, longest: int, least: int = 2):
    """Connected pieces of ink in a mask, counting pixels of shade `least` or more. Ink
    closer than `gap` px along a row is joined; a solid run longer than `longest` px is a
    rule or the sheet's edge, and is left out. Returns the blobs and the runs of ink they
    are made of, (y, x0, x1, blob index)."""
    pattern = re.compile(b"[" + bytes([least]) + b"-\x03]+")
    parent: list[int] = []

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs, prev = [], []
    for y in range(len(mask) // width):
        row: list[list[int]] = []
        for m in pattern.finditer(mask, y * width, (y + 1) * width):
            a, b = m.start() - y * width, m.end() - y * width
            if b - a > longest:
                continue
            dark = m.group().count(3)
            if row and a - row[-1][1] <= gap:
                row[-1][1:] = [b, row[-1][2] + b - a, row[-1][3] + dark]
            else:
                row.append([a, b, b - a, dark])
        here, j = [], 0
        for a, b, ink, dark in row:
            i = len(parent)
            parent.append(i)
            while j < len(prev) and prev[j][1] < a:
                j += 1
            k = j
            while k < len(prev) and prev[k][0] <= b:
                ri, rk = find(i), find(prev[k][2])
                if ri != rk:
                    parent[ri] = rk
                k += 1
            here.append((a, b, i))
            runs.append((y, a, b, i, ink, dark))
        prev = here
    index: dict[int, int] = {}
    found: list[list[int]] = []
    labelled = []
    for y, a, b, i, ink, dark in runs:
        r = find(i)
        if r not in index:
            index[r] = len(found)
            found.append([a, y, b, y + 1, 0, 0])
        c = found[index[r]]
        c[0], c[2], c[3], c[4], c[5] = min(c[0], a), max(c[2], b), y + 1, c[4] + ink, c[5] + dark
        labelled.append((y, a, b, index[r]))
    return found, labelled


def floor(runs: list[tuple[int, int, int, int]], art: set[int], width: int, step: int) -> list[int]:
    """The lowest row of art (the blobs numbered in `art`) in each band of `step` columns,
    -1 where there is none."""
    low = [-1] * (width // step + 1)
    for y, a, b, i in runs:
        if i in art:
            for k in range(a // step, (b - 1) // step + 1):
                low[k] = max(low[k], y)
    return low


def lines(found: list[list[int]], reach: float, tallest: float) -> list[list[int]]:
    """Blobs level with each other (overlapping by half the smaller's height) and no farther
    apart than `reach`, or 2.5 letter heights, joined into lines, top to bottom. No blob is
    taller than `tallest`."""
    found = sorted(found, key=lambda c: c[0])
    parent = list(range(len(found)))
    most = max(reach, 2.5 * tallest)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(found):
        for j in range(i + 1, len(found)):
            b = found[j]
            if b[0] - a[2] > most:
                break
            if b[0] - a[2] > max(reach, 2.5 * max(a[3] - a[1], b[3] - b[1])):
                continue
            if min(a[3], b[3]) - max(a[1], b[1]) >= 0.5 * min(a[3] - a[1], b[3] - b[1]):
                parent[find(i)] = find(j)
    out: dict[int, list[int]] = {}
    for i, c in enumerate(found):
        L = out.setdefault(find(i), [c[0], c[1], c[2], c[3], 0, 0])
        L[:] = [min(L[0], c[0]), min(L[1], c[1]), max(L[2], c[2]), max(L[3], c[3]), L[4] + c[4], L[5] + c[5]]
    return sorted(out.values(), key=lambda L: (L[1], L[0]))


def caption(found: list[list[int]], width: int, unit: float) -> list[list[int]]:
    """The caption: the lowest block of lines of text across the centre of the sheet and
    centred on it (within a tenth of its width), top to bottom."""
    cx = width / 2
    across = sorted((L for L in found if L[0] < cx < L[2] and abs((L[0] + L[2]) / 2 - cx) <= 0.1 * width
                     and 0.1 * width <= L[2] - L[0] <= 0.6 * width and 2.5 * unit <= L[3] - L[1] <= 12 * unit),
                    key=lambda L: -L[3])
    block = across[:1]
    for L in across[1:]:
        if min(b[1] for b in block) - L[3] <= 1.5 * max(L[3] - L[1], block[-1][3] - block[-1][1]):
            block.append(L)
    return sorted(block, key=lambda L: L[1])


def textlike(L: list[int], unit: float, faint: bool = False) -> bool:
    """A credit line: 2.5 to 9.5 units tall (from 2 if faint; a caption's capitals are
    taller), 20 to 240 units and three letter heights long (shorter is a pencilled number
    or a stroke of the art, longer the page's edge), inked over 6 % of its box, and with
    some dark ink, which pencil and shadow have not: 2 % of its ink, or if faint a trace;
    under 25 units long, a tenth of its ink (a short line of pencil is a plate number)."""
    x0, y0, x1, y1, ink, dark = L
    h, w = y1 - y0, x1 - x0
    return ((2 if faint else 2.5) * unit <= h <= 9.5 * unit and max(20 * unit, 3 * h) <= w <= 240 * unit
            and ink >= 0.06 * w * h and dark >= (2 if faint else max(3, 0.02 * ink))
            and (w >= 25 * unit or dark >= 0.1 * ink))


def corner(found: list[list[int]], side: str, width: int, unit: float, rule: str,
           low: list[int] | None = None, step: int = 1, cap_top: int | None = None,
           band: tuple[float, float] | None = None, faint: bool = False,
           clear: float | None = None) -> list[list[int]]:
    """The credit lines in one corner, top to bottom, among lines of small text in that half
    of the sheet; a line across the centre is the caption.

    In its own columns, the art (`low`, its lowest row per `step` columns) must end `clear`
    units above a line: by default 10 for rule 'lowest', which also wants it not above the
    caption (`cap_top`), and 0 for 'outermost'. Rule 'lowest' (Gould) takes the lowest
    line, and of lines level with it the outermost; rule 'outermost' (Havell, whose credit
    lines sit close under the art) takes the line reaching farthest to the sheet's edge.
    Lines stacked on the one taken, of its size, come with it. With a `band` (y0, y1),
    only lines level with it count."""
    cx = width / 2
    cands = []
    for L in found:
        x0, y0, x1, y1 = L[:4]
        if not textlike(L, unit, faint) or x0 < cx < x1 or (side == "left") != (x1 <= cx):
            continue
        if band is not None and not (y0 < band[1] and y1 > band[0]):
            continue
        if rule == "lowest" and cap_top is not None and y1 <= cap_top:
            continue
        if low is not None:
            by = (10 if rule == "lowest" else 0) if clear is None else clear
            ks = range(x0 // step, (x1 - 1) // step + 1)
            if sum(low[k] > y0 - by * unit for k in ks) > 0.1 * len(ks):
                continue
        cands.append(L)
    if not cands:
        return []
    outer = (lambda L: -L[0]) if side == "left" else (lambda L: L[2])
    if rule == "lowest":
        bottom = max(cands, key=lambda L: L[3])
        best = max((L for L in cands if min(L[3], bottom[3]) > max(L[1], bottom[1])), key=outer)
    else:
        best = max(cands, key=outer)
    chosen = [best]
    grew = True
    while grew:
        grew = False
        for L in cands:
            if L in chosen:
                continue
            for c in chosen:
                hc, hl = c[3] - c[1], L[3] - L[1]
                if (max(L[1] - c[3], c[1] - L[3]) <= 0.8 * max(hc, hl)
                        and min(L[2], c[2]) - max(L[0], c[0]) > 0.3 * min(L[2] - L[0], c[2] - c[0])
                        and max(hc, hl) <= 1.35 * min(hc, hl)):
                    chosen.append(L)
                    grew = True
                    break
    return sorted(chosen, key=lambda L: L[1])


def credit_lines(mask: bytes, width: int, unit: float, rule: str = "lowest"):
    """Both corners' credit lines in a mask of the lower part of a sheet, and the caption:
    (left, right, caption), each a list of lines top to bottom.

    Blobs taller than 12 units with enough ink are art. A corner left empty is looked at
    again, faint ink counted, level with the other corner's line (Gould sets the two
    level) or, if neither was found, below the caption's last line; then just above a
    ragged page edge at the foot, with and without its specks. A line found takes in the
    faint ink level with it and touching it, such as a worn first or last word, while it
    stays the size of a credit line."""
    height = len(mask) // width
    gap, longest = max(2, round(2.5 * unit)), round(40 * unit)
    found, runs = blobs(mask, width, gap, longest)
    text, art = [], set()
    for i, (x0, y0, x1, y1, ink, dark) in enumerate(found):
        if y1 - y0 > 12 * unit:
            if ink >= 150 * unit * unit and x1 - x0 >= 20 * unit and y1 < height - 1 and 1 < x0 and x1 < width - 1:
                art.add(i)
        elif ink >= unit * unit and not (y1 >= height - 1 and x1 - x0 > width / 3):
            text.append(found[i])
    step = max(1, round(2 * unit))
    low = floor(runs, art, width, step)
    found_lines = lines(text, 16 * unit, 12 * unit)
    cap = caption(found_lines, width, unit)
    cap_top = cap[0][1] if cap else None

    def faint(y0: float, y1: float, least: float = 0) -> list[list[int]]:
        """The lines in rows y0 to y1, faint ink counted; blobs under `least` tall left out."""
        lo, hi = max(0, int(y0)), min(height, int(y1) + 1)
        return lines([[x0, a + lo, x1, b + lo, ink, dark]
                      for x0, a, x1, b, ink, dark in blobs(mask[lo * width:hi * width], width, gap, longest, 1)[0]
                      if 1 < x0 and x1 < width - 1 and least <= b - a <= 12 * unit and ink >= unit * unit / 2],
                     16 * unit, 12 * unit)

    out = {s: corner(found_lines, s, width, unit, rule, low, step, cap_top) for s in ("left", "right")}
    for side, ls in out.items():
        if not ls:
            continue
        y0, y1 = min(L[1] for L in ls), max(L[3] for L in ls)
        wider = [F for F in faint(y0 - (y1 - y0), y1 + (y1 - y0))
                 if (F[2] <= width / 2 if side == "left" else F[0] >= width / 2)]
        for L in ls:
            for F in wider:
                grown = [min(L[0], F[0]), min(L[1], F[1]), max(L[2], F[2]), max(L[3], F[3])]
                if (min(L[3], F[3]) - max(L[1], F[1]) >= 0.5 * min(L[3] - L[1], F[3] - F[1])
                        and F[0] < L[2] and F[2] > L[0]
                        and grown[2] - grown[0] <= 240 * unit and grown[3] - grown[1] <= 9.5 * unit):
                    L[:4] = grown
    # Both empty: the credit lines may sit above a low caption. A pair of lines, one in each
    # half, level with each other and set about the caption's centre (to a tenth of the
    # sheet's width), no more than 25 units above its top, is taken.
    if rule == "lowest" and cap and not out["left"] and not out["right"]:
        centre = (cap[-1][0] + cap[-1][2]) / 2
        above = (cap_top - 25 * unit, cap_top)
        left, right = (corner(found_lines, s, width, unit, rule, low, step, band=above) for s in ("left", "right"))
        if (left and right and min(left[-1][3], right[-1][3]) - max(left[-1][1], right[-1][1])
                >= 0.5 * min(left[-1][3] - left[-1][1], right[-1][3] - right[-1][1])
                and abs((centre - left[-1][0]) - (right[-1][2] - centre)) <= 0.1 * width):
            out["left"], out["right"] = left, right
    for side, other in (("left", "right"), ("right", "left")):
        if out[side] or rule != "lowest":
            continue
        if out[other]:
            y0, y1 = min(L[1] for L in out[other]), max(L[3] for L in out[other])
            band = (y0 - 2 * (y1 - y0), y1 + (y1 - y0))
        elif cap:
            h = cap[-1][3] - cap[-1][1]
            band = (cap[-1][1], cap[-1][3] + 8 * h)
        else:
            continue
        out[side] = corner(faint(*band), side, width, unit, rule, low, step, band=band, faint=True, clear=0)
    # Lines sitting on a ragged page edge at the foot join its specks into one line across
    # the sheet. Still missing, they are looked for again just above the edge: the last
    # rows with ink that are more than 8 % inked.
    if rule == "lowest" and not (out["left"] and out["right"]):
        inked = lambda y: width - mask[y * width:(y + 1) * width].count(0)
        cut = height
        while cut > height - 40 * unit and inked(cut - 1) == 0:
            cut -= 1
        while cut > height - 40 * unit and inked(cut - 1) > 0.08 * width:
            cut -= 1
        if cut < height:
            band = (cut - 15 * unit, cut - 1)
            for side in ("left", "right"):
                if not out[side]:
                    out[side] = corner(faint(*band), side, width, unit, rule, low, step, cap_top, band, True, 0)
        # Or the line touches the edge's specks, which join it into one line across the
        # sheet: look again without them (blobs under 2.5 units tall), in the 10 units
        # above the last ink, for a line 40 units long or more, no more than 7 tall (a word
        # of the caption is taller), a hundredth of it dark.
        foot = height
        while foot > 0 and not any(mask[(foot - 1) * width:foot * width]):
            foot -= 1
        band = (foot - 10 * unit, foot)
        found_foot = [L for L in faint(foot - 20 * unit, foot, least=2.5 * unit)
                      if L[3] >= band[0] and L[2] - L[0] >= 40 * unit and L[3] - L[1] <= 7 * unit
                      and L[5] >= 0.01 * L[4]]
        for side in ("left", "right"):
            if not out[side]:
                out[side] = corner(found_foot, side, width, unit, rule, low, step, cap_top, band, True, 0)
    return out["left"], out["right"], cap


def box(found: list[list[int]], scale: float, top: int) -> list[int]:
    """A crop box at full size around lines found on the working copy (`scale` times
    smaller, its mask starting `top` rows down): the lines and a margin of 0.6 letter
    heights above and below, 1.2 at the ends (for a faint first or last letter), at
    least 8 px."""
    h = max(L[3] - L[1] for L in found) * scale
    dx, dy = max(8, round(1.2 * h)), max(8, round(0.6 * h))
    return [round(min(L[0] for L in found) * scale) - dx, round((min(L[1] for L in found) + top) * scale) - dy,
            round(max(L[2] for L in found) * scale) + dx, round((max(L[3] for L in found) + top) * scale) + dy]


def fit(b: list[int], side: str, most: tuple[int, int] = CROP, least: float = LEAST) -> tuple[list[int], float]:
    """A crop box and the scale that brings it within `most`, never below `least`. Too big
    even at `least`, the box is cut: a left crop keeps its left end, a right crop its right
    end, and both keep their foot."""
    x0, y0, x1, y1 = b
    scale = min(1.0, most[0] / (x1 - x0), most[1] / (y1 - y0))
    if scale >= least:
        return [x0, y0, x1, y1], scale
    w, h = int(most[0] / least), int(most[1] / least)
    if x1 - x0 > w:
        x0, x1 = (x0, x0 + w) if side == "left" else (x1 - w, x1)
    if y1 - y0 > h:
        y0 = y1 - h
    return [x0, y0, x1, y1], least


def strip(side: str, width: int, height: int, other: list[int] | None = None,
          level: tuple[int, int] | None = None, centre: int | None = None,
          size: tuple[int, int] = STRIP) -> list[int]:
    """Where a corner's credit line should be, when none was found: a strip of at most
    `size` in that half of the sheet (the half's edge is the caption's `centre`, if known).
    It is level with the other corner's line (`other`, its box), reaching a little past
    that line's outer end mirrored across the centre; else it runs down from the top of
    `level` (the caption's last line, y0 and y1); else it is at the foot of the sheet."""
    w, h = size
    cx = width // 2 if centre is None else centre
    if other is not None:
        y0, pad = (other[1] + other[3]) // 2 - h // 2, width // 20
        outer = 2 * cx - (other[2] if side == "left" else other[0])
    else:
        y0, pad = (level[0] if level else height - h), 0
        outer = width // 10 if side == "left" else width - width // 10
    y0 = max(0, min(y0, height - h))
    if side == "left":
        x0 = max(0, min(outer - pad, cx - w // 4))
        x1 = min(cx, x0 + w)
    else:
        x1 = min(width, max(outer + pad, cx + w // 4))
        x0 = max(cx, x1 - w)
    return [x0, y0, x1, min(height, y0 + h)]


def layout(left: tuple[int, int], right: tuple[int, int], width: int = SHEET) -> tuple[bool, int]:
    """How a plate's two crops (each width, height) sit in its block on a contact sheet:
    side by side if they fit, else one above the other; and the block's height, with its
    label above and a rule below."""
    beside = left[0] + 20 + right[0] <= width
    return beside, 34 + (max(left[1], right[1]) if beside else left[1] + 10 + right[1]) + 16


def pack(heights: list[int], limit: int = SHEET, most: int = PER_SHEET) -> list[list[int]]:
    """Blocks onto contact sheets, in order: a sheet takes blocks until the next would make
    it taller than `limit`, and never more than `most`. Each sheet's block numbers."""
    out: list[list[int]] = []
    tall = 0
    for i, h in enumerate(heights):
        if out and out[-1] and (tall + h > limit or len(out[-1]) == most):
            out.append([])
            tall = 0
        if not out:
            out.append([])
        out[-1].append(i)
        tall += h
    return out


def segments(length: int, most: int, overlap: int = OVERLAP) -> list[tuple[int, int]]:
    """`length` px cut into the fewest equal segments no longer than `most`, each
    overlapping the next by `overlap`: each segment's start and end. Whole if it fits."""
    if length <= most:
        return [(0, length)]
    n = -(-(length - overlap) // (most - overlap))
    size = (length + (n - 1) * overlap) / n
    return [(round(i * (size - overlap)), length if i == n - 1 else round(i * (size - overlap) + size))
            for i in range(n)]


def tiles(size: tuple[int, int], width: int, height: int, overlap: int = OVERLAP) -> list[list[int]]:
    """An enlarged crop (width, height) cut into tiles no bigger than `width` by `height`,
    overlapping by `overlap`: each tile's box, band by band from the top, left to right
    in each band, as a line is read."""
    return [[x0, y0, x1, y1] for y0, y1 in segments(size[1], height, overlap)
            for x0, x1 in segments(size[0], width, overlap)]


def check_layout(blocks: list[tuple[int, list[int]]], size: tuple[int, int] = CHECK,
                 pad: int = PAD) -> list[list[tuple[int, list[int]]]]:
    """Plates' blocks onto check images size[0] wide and at most size[1] pixels, in order.
    A block is its head's height and its parts' heights (each part a tile under its
    label). An image takes whole blocks while they fit; a block too tall for any image
    goes onto images of its own, its parts in order, its head repeated on each. Each
    image's (block number, its part numbers) in order."""
    most = size[1] // size[0] - 2 * pad
    out: list[list[tuple[int, list[int]]]] = []
    room = 0
    for b, (head, parts) in enumerate(blocks):
        tall = head + sum(LABEL + h + GAP for h in parts)
        if tall <= most:
            if out and tall <= room:
                out[-1].append((b, list(range(len(parts)))))
                room -= tall
            else:
                out.append([(b, list(range(len(parts))))])
                room = most - tall
            continue
        page, used = [], head
        for i, h in enumerate(parts):
            if page and used + LABEL + h + GAP > most:
                out.append([(b, page)])
                page, used = [], head
            page.append(i)
            used += LABEL + h + GAP
        out.append([(b, page)])
        room = 0
    return out


def carried(old: dict) -> dict:
    """What a new crop keeps of a plate's old record: its read and note, once a reading was
    applied; otherwise nothing."""
    return {"read": old["read"], "note": old.get("note", "")} if old.get("read") else {"read": "", "note": ""}


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


def wording_pairs(wordings) -> set[tuple[str, str]]:
    """Each two words (runs of letters) next to each other in a wording, casefolded."""
    out = set()
    for w in wordings:
        words = [x.casefold() for x in re.findall(r"[A-Za-z]+", w)]
        out |= set(zip(words, words[1:]))
    return out


PAIRS = wording_pairs(list(credits.BEFORE) + list(credits.AFTER))


def run_apart(run: str, pairs: set[tuple[str, str]] = PAIRS) -> str:
    """A run of letters that is two or more words of a wording run together, spaced
    ("Drawnfrom" is "Drawn from", "onStoneby" "on Stone by"), or ending in "by" run into
    a capital ("byJ", "StonebyJ"); any other run as it is. Case is kept."""
    low = run.casefold()
    words = sorted({w for pair in pairs for w in pair}, key=len, reverse=True)

    def split(i: int, prev: str | None) -> list[int] | None:
        for w in words:
            if not low.startswith(w, i) or (prev is not None and (prev, w) not in pairs):
                continue
            j = i + len(w)
            if j == len(low):
                return [j] if prev is not None else None
            if w == "by" and run[j].isupper():
                return [j]
            rest = split(j, w)
            if rest is not None:
                return [j] + rest
        return None

    cuts = split(0, None)
    if not cuts:
        return run
    bounds = [0] + cuts + ([len(run)] if cuts[-1] < len(run) else [])
    return " ".join(run[a:b] for a, b in zip(bounds, bounds[1:]))


# The capitalised words of the name forms in credits.NAMES and FOLIO_NAMES ("Audubon", "Havell", "Lizars"):
# a single capital glued to the end of one, "AudubonF,", is the initial after it.
NAME_WORDS = {w for form in [*credits.NAMES, *(k for table in credits.FOLIO_NAMES.values() for k in table)]
              for w in re.findall(r"[A-Z][a-z]{3,}", form)}

# The abbreviations of a credit line: the mark after one is written as a stop (normalise_line).
ABBREVIATIONS = ("del", "delt", "lith", "lithog", "Imp", "Impt", "Edwd", "Edinr", "Junr", "Senr", "Sen")
ABBREVIATED_WORDS = {a.casefold() for a in ABBREVIATIONS}   # "DEL." and "IMP." are not initials
ABBREVIATED = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted(ABBREVIATIONS, key=len, reverse=True))
                         + r")[,:;](?![.,;:])", re.I)


def normalise_line(line: str) -> str:
    """One credit line spaced by the convention in the module's docstring."""
    s = " ".join(line.split())
    s = re.sub(r"[A-Za-z]+", lambda m: run_apart(m.group()), s)
    s = re.sub(r"\s*&(c(?![A-Za-z]))?\s*", lambda m: " &c " if m.group(1) else " & ", s)   # "&c." is one word
    s = re.sub(r"\s+(?=[.,;:])", "", s)
    s = re.sub(r"([.,;:])(?=[^\s.,;:])", r"\1 ", s)
    s = re.sub(r"(?<=[a-z])and(?=[A-Z])", " and ", s)
    s = re.sub(r"\band(?=[A-Z])", "and ", s)
    s = ABBREVIATED.sub(r"\1.", s)
    return initials(" ".join(s.split()))


def initials(line: str) -> str:
    """Every initial written "X. ": a lone capital, with a stop, a comma, a colon or
    nothing after it, followed by another initial, & or and, "&c." (a word, but one that
    follows initials as & does: "F.L.S &c." is "F. L. S. &c."), or a capitalised word
    ("J, Gould" is "J. Gould", "C: Hullmandel" "C. Hullmandel"; a comma after a name,
    "Richter, del.", is left); and two or three capitals run together ("HC Richter",
    "HCRichter", "HC. Richter", "JGould", "FRS." are "H. C. Richter", "J. Gould",
    "F. R. S."), also before another initial ("FRS F. L. S." is "F. R. S. F. L. S."),
    except a Roman numeral with no stop before a name; a longer run is an
    all-capitals word ("LONDON Published"), left as it is. A single capital glued to the
    end of a name of credits.NAMES or FOLIO_NAMES is split off ("AudubonF, R." is
    "Audubon F. R."). Words
    that begin with a capital ("Drawn", "Imp.") and lowercase abbreviations are left as
    they are, and so are a Roman numeral with a stop that ends the line or comes before
    a lowercase word ("Plate IV."), and the article A before a word of a wording
    ("A Drawing")."""
    words = {w for pair in PAIRS for w in pair}
    raw = line.split()
    tokens = []
    for i, tok in enumerate(raw):
        after = raw[i + 1] if i + 1 < len(raw) else ""
        glued = re.fullmatch(r"([A-Z]{1,3})([A-Z][a-z]\S*)", tok)
        ended = re.fullmatch(r"([A-Z][a-z]{3,})([A-Z][.,:;]?)", tok)
        if ended and ended.group(1) in NAME_WORDS:
            tokens += [ended.group(1), ended.group(2)]
        elif glued:
            tokens += list(glued.group(1)) + [glued.group(2)]
        elif re.fullmatch(r"[IVXLC]{2,}\.", tok) and not re.match(r"[A-Z&]|and$", after):
            tokens.append(tok)
        elif re.fullmatch(r"[A-Z]{2,3}\.", tok) and tok[:-1].casefold() not in ABBREVIATED_WORDS:
            tokens += list(tok[:-2]) + [tok[-2:]]
        elif re.fullmatch(r"[A-Z]{2,3}", tok) and not re.fullmatch(r"[IVXLCDM]+", tok) \
                and tok.casefold() not in ABBREVIATED_WORDS and re.match(r"[A-Z][a-z]|&$|and$|[A-Z][.,:]?$", after):
            tokens += list(tok)
        else:
            tokens.append(tok)
    lone = lambda t: re.fullmatch(r"[A-Z][.,:]?", t)
    nxt = lambda t: lone(t) or t in ("&", "and") or re.fullmatch(r"&c\.?", t) or re.match(r"[A-Z][a-z]", t)
    article = lambda t, n: t == "A" and re.sub(r"[^A-Za-z]", "", n).casefold() in words
    out = []
    for i, tok in enumerate(tokens):
        if lone(tok) and i + 1 < len(tokens) and nxt(tokens[i + 1]) and not article(tok, tokens[i + 1]):
            tok = tok[0] + "."
        out.append(tok)
    return " ".join(out)


def normalise(imprint: str) -> str:
    """An imprint's lines, each spaced by the convention, joined with " | "."""
    return " | ".join(normalise_line(p) for p in imprint.split("|") if p.strip())


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def apply(folder: Path, readings: list[dict]) -> None:
    """Write readings into plates.csv (imprint, and each part of a reading's note that is
    about a credit line, such as one cut off or unreadable) and sources/imprints.csv
    (read, note), then regenerate credits.csv. A note's parts are split at "; ", and a
    part is added to plates.csv's notes once, after any already there; the other parts,
    about the reading, stay in the record. Every row is checked first; if any is wrong,
    nothing is written."""
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
                credits.parse(imprint, folder.name)
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
        for part in (x.strip() for x in r.get("note", "").split("; ")):
            if "credit line" in part and part not in p["notes"]:
                p["notes"] = f"{p['notes']}; {part}" if p["notes"] else part
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


def shade(sheet: Path) -> tuple[bytes, int, int, float, float]:
    """The mask credit_lines reads, from the lower part (REGION) of a half-size grey copy of
    a sheet: each pixel graded (SHADES) by how much darker it is than the paper around it,
    as a share of the paper's lightness. Columns at the sides and rows at the foot that are
    mostly ink, the sheet's edge and the gutter's shadow, are blanked, so a line beside
    them stays apart; so is what lies beyond the page, dark ground reaching the sheet's
    border, with the page's edge along it. Returns the mask, its width, the row of the copy
    it starts at, the copy's scale (full size over copy) and the unit."""
    from PIL import Image, ImageDraw, ImageFilter, ImageMath
    with Image.open(sheet) as im:
        size = im.size
        im.draft("L", (size[0] // 2, size[1] // 2))
        im = im.convert("L")
    w, h = im.size
    top = int(h * (1 - REGION))
    part = im.crop((0, top, w, h))
    paper = part.reduce(4).filter(ImageFilter.MaxFilter(3)).resize(part.size, Image.BILINEAR)
    graded = ImageMath.lambda_eval(
        lambda a: a["convert"](a["max"](255 * (a["p"] - a["i"]) / (a["p"] + 1), 0), "L"), p=paper, i=part)
    faint, ink, dark = SHADES
    mask = graded.point(lambda v: 0 if v <= faint else 1 if v <= ink else 2 if v <= dark else 3)
    inked = mask.point(lambda v: 255 if v >= 2 else 0)
    cols = inked.resize((w, 1), Image.BOX).tobytes()
    rows = inked.resize((1, mask.height), Image.BOX).tobytes()
    a, b, c = 0, w, mask.height
    while a < w // 12 and cols[a] > 12:
        a += 1
    while b > w - w // 12 and cols[b - 1] > 12:
        b -= 1
    while c > mask.height - mask.height // 12 and rows[c - 1] > 100:
        c -= 1
    for x0, y0, x1, y1 in ((0, 0, a, mask.height), (b, 0, w, mask.height), (0, c, w, mask.height)):
        if x1 > x0 and y1 > y0:
            mask.paste(0, (x0, y0, x1, y1))
    ground = part.reduce(8).point(lambda v: 255 if v < 60 else 0)
    gw, gh = ground.size
    for x, y in [(x, 0) for x in range(gw)] + [(x, gh - 1) for x in range(gw)] + \
                [(0, y) for y in range(gh)] + [(gw - 1, y) for y in range(gh)]:
        if ground.getpixel((x, y)) == 255:
            ImageDraw.floodfill(ground, (x, y), 128)
    ground = ground.point(lambda v: 255 if v == 128 else 0)
    if ground.getbbox():
        mask.paste(0, mask=ground.filter(ImageFilter.MaxFilter(5)).resize(mask.size, Image.NEAREST))
    return mask.tobytes(), w, top, size[0] / w, max(w, h) / 1000


def locate(sheet: Path, rule: str) -> tuple[dict[str, list[int]], dict[str, bool]]:
    """Each corner's crop box on a sheet, at full size, and whether a credit line was found
    there; where none was, the box is a strip where it should be."""
    from PIL import Image
    mask, width, top, scale, unit = shade(sheet)
    left, right, cap = credit_lines(mask, width, unit, rule)
    with Image.open(sheet) as im:
        w, h = im.size
    found = {"left": left, "right": right}
    boxes = {}
    for side, ls in found.items():
        if ls:
            b = box(ls, scale, top)
            boxes[side] = [max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3])]
    level = (round((cap[-1][1] + top) * scale), round((cap[-1][3] + top) * scale)) if cap else None
    centre = round((cap[-1][0] + cap[-1][2]) / 2 * scale) if cap else None
    for side, other in (("left", "right"), ("right", "left")):
        if not found[side]:
            boxes[side] = strip(side, w, h, boxes[other] if found[other] else None, level, centre)
    return boxes, {side: bool(ls) for side, ls in found.items()}


def cut(job: tuple[str, str, str, str]) -> tuple[dict[str, list[int]], dict[str, bool]]:
    """One sheet's two crops, saved: job is (sheet, rule, left crop's path, right crop's
    path). Returns the boxes cut and whether each corner's line was found."""
    from PIL import Image, ImageOps
    sheet, rule, *paths = job
    boxes, found = locate(Path(sheet), rule)
    with Image.open(sheet) as im:
        im = im.convert("L")
        for side, path in zip(("left", "right"), paths):
            boxes[side], scale = fit(boxes[side], side)
            part = ImageOps.autocontrast(im.crop(boxes[side]), cutoff=1)
            if scale < 1:
                part = part.resize((round(part.width * scale), round(part.height * scale)), Image.LANCZOS)
            part.save(path)
    return boxes, found


def crop(folio: str) -> None:
    folder, out = ROOT / folio, work(folio)
    volumes = credits.per_volume(folder)
    (out / "crops").mkdir(exist_ok=True)
    _, plates = credits.read(folder / "plates.csv")
    record_path = folder / "sources" / "imprints.csv"
    old = {}
    if record_path.exists():
        old = {credits.tag(x, volumes): x for x in credits.read(record_path)[1]}
    rule = RULE.get(folio, "lowest")
    rows, jobs = [], []
    for p in plates:
        t = credits.tag(p, volumes)
        row = {"volume": p.get("volume", ""), "plate": p["plate"], "leaf": p.get("leaf", ""),
               **carried(old.get(t, {}))}
        rows.append(row)
        sheet = ASSETS / RELEASE[folio] / p["sheet_asset"] if p["sheet_asset"] else None
        if not sheet or not sheet.exists():
            row["note"] = row["note"] or "no sheet in the release; read from the scan"
            continue
        jobs.append((row, (str(sheet), rule, str(out / "crops" / f"{t}-L.png"), str(out / "crops" / f"{t}-R.png"))))
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(cut, [job for _, job in jobs], chunksize=4))
    missing = 0
    for (row, _), (boxes, found) in zip(jobs, results):
        lost = [side for side in ("left", "right") if not found[side]]
        missing += len(lost)
        for side in ("left", "right"):
            row[f"{side}_box"] = " ".join(map(str, boxes[side]))
        if not row["read"]:
            row["note"] = "; ".join(f"no credit line found in the {side} corner" for side in lost)
    # Each crop's draft; a pencilled plate number (digits only) is dropped.
    texts = ocr([Path(p) for _, job in jobs for p in job[2:]])
    read = lambda p: [x for x in sorted(texts.get(p, []), key=lambda x: x["box"][1])
                      if not x["text"].replace(" ", "").isdigit()]
    for row, job in jobs:
        row["ocr"] = draft_text(read(job[2]), read(job[3]))
    record_cols = (["volume"] if volumes else []) + RECORD
    record_path.parent.mkdir(exist_ok=True)
    write_csv(record_path, record_cols, rows)
    print(f"{folio}: {len(jobs)} sheets cropped, {len(rows) - len(jobs)} without a sheet, "
          f"{missing} corners with no credit line found -> {record_path}")


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
    """Contact sheets of the crops, SHEET px wide and no taller (unless one block is), at
    most PER_SHEET plates each. Every crop is at the size it was cut. A run's sheets
    replace the last run's, which may have been more."""
    from PIL import Image, ImageDraw, ImageFont
    folder, out = ROOT / folio, work(folio)
    volumes = credits.per_volume(folder)
    (out / "sheets").mkdir(exist_ok=True)
    for old in (out / "sheets").glob(f"{folio}-[0-9][0-9][0-9].png"):
        old.unlink()
    font = ImageFont.load_default(size=22)
    blank = (SHEET // 2 - 10, 40)
    blocks = []
    for r in ordered(folio):
        t = credits.tag(r, volumes)
        paths = [out / "crops" / f"{t}-{side}.png" for side in "LR"]
        sizes = []
        for path in paths:
            if path.exists():
                with Image.open(path) as im:
                    sizes.append(im.size)
            else:
                sizes.append(blank)
        blocks.append((t, r, paths, *layout(*sizes)))
    groups = pack([b[-1] for b in blocks])
    index = []
    for n, group in enumerate(groups, 1):
        sheet = Image.new("L", (SHEET, sum(blocks[i][-1] for i in group)), 255)
        d = ImageDraw.Draw(sheet)
        y = 0
        for i in group:
            t, r, paths, beside, height = blocks[i]
            note = f"   note: {r['note']}" if r["note"] else ""
            d.text((6, y + 4), f"{t}   draft: {r['ocr'] or '(nothing read)'}{note}", fill=0, font=font)
            crops = [Image.open(p).convert("L") if p.exists() else Image.new("L", blank, 255) for p in paths]
            sheet.paste(crops[0], (0, y + 34))
            sheet.paste(crops[1], (SHEET - crops[1].width, y + 34 + (0 if beside else crops[0].height + 10)))
            d.line((0, y + height - 2, SHEET, y + height - 2), fill=160, width=2)
            y += height
        name = f"{folio}-{n:03d}.png"
        sheet.save(out / "sheets" / name)
        index += [{"sheet": name, "plate": blocks[i][0]} for i in group]
    write_csv(out / "sheets" / "index.csv", ["sheet", "plate"], index)
    print(f"{folio}: {len(index)} plates on {len(groups)} sheets -> {out / 'sheets'}")


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


def wrap(text: str, fits) -> list[str]:
    """Text in lines, each as long as `fits` allows, broken at spaces."""
    lines: list[str] = []
    for word in text.split(" "):
        if lines and fits(f"{lines[-1]} {word}"):
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def check(folio: str, zoom: int = ZOOM) -> None:
    """Check images of every plate with an imprint, several plates to an image, as the
    module's docstring says. A run's images replace the last run's."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    if zoom < 1:
        raise SystemExit("--zoom must be 1 or more")
    folder, out = ROOT / folio, work(folio)
    volumes = credits.per_volume(folder)
    (out / "check").mkdir(exist_ok=True)
    for old in (out / "check").glob("*.png"):
        old.unlink()
    font, small = ImageFont.load_default(size=24), ImageFont.load_default(size=18)
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    room = CHECK[0] - 2 * PAD
    most = CHECK[1] // CHECK[0] - 2 * PAD
    plates = []   # (tag, head lines, [(label, tile)])
    for p in credits.read(folder / "plates.csv")[1]:
        if not p.get("imprint"):
            continue
        t = credits.tag(p, volumes)
        lines = wrap(f"{t}   {p['imprint']}", lambda s: measure.textlength(s, font=font) <= room)
        head = 6 + 30 * len(lines) + 4
        parts = []
        for side, name in (("L", "left"), ("R", "right")):
            path = out / "crops" / f"{t}-{side}.png"
            if not path.exists():
                continue
            with Image.open(path) as im:
                crop = ImageOps.autocontrast(im.convert("L"), cutoff=1)
            big = crop.resize((crop.width * zoom, crop.height * zoom), Image.LANCZOS)
            boxes = tiles(big.size, room, max(most - head - LABEL - GAP, 2 * OVERLAP + 1))
            for n, b in enumerate(boxes, 1):
                label = f"{name} crop, x{zoom}"
                if len(boxes) > 1:
                    label += f", part {n} of {len(boxes)}: x {b[0]}-{b[2]}, y {b[1]}-{b[3]} of {big.width} x {big.height}"
                parts.append((label, big.crop(b)))
        plates.append((t, lines, parts))
    pages = check_layout([(6 + 30 * len(lines) + 4, [tile.height for _, tile in parts]) for _, lines, parts in plates])
    digits = max(3, len(str(len(pages))))
    index = []
    for n, page in enumerate(pages, 1):
        name = f"{n:0{digits}d}.png"
        height = 2 * PAD + sum(6 + 30 * len(plates[b][1]) + 4 + sum(LABEL + plates[b][2][i][1].height + GAP for i in parts)
                               for b, parts in page)
        image = Image.new("L", (CHECK[0], height), 255)
        d = ImageDraw.Draw(image)
        y = PAD
        for k, (b, parts) in enumerate(page):
            t, lines, tiles_ = plates[b]
            if k:
                d.line([(0, y), (CHECK[0], y)], fill=120, width=2)
            for j, line in enumerate(lines):
                d.text((PAD, y + 6 + 30 * j), line, fill=0, font=font)
            y += 6 + 30 * len(lines) + 4
            for i in parts:
                label, tile = tiles_[i]
                d.text((PAD, y + 3), label, fill=90, font=small)
                image.paste(tile, (PAD, y + LABEL))
                y += LABEL + tile.height + GAP
            index.append({"tag": t, "file": name})
        image.save(out / "check" / name)
    write_csv(out / "check" / "index.csv", ["tag", "file"], index)
    print(f"{folio}: {len(plates)} plates in {len(pages)} check images at x{zoom} -> {out / 'check'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["crop", "sheets", "draft", "scan", "check", "apply"])
    ap.add_argument("folio", choices=credits.FOLIOS)
    ap.add_argument("rest", nargs="*", help="scan: plate tags; apply: the readings file")
    ap.add_argument("--zoom", type=int, default=ZOOM, help=f"check: enlarge each crop this many times (default {ZOOM})")
    args = ap.parse_args()
    if args.command == "crop":
        crop(args.folio)
    elif args.command == "sheets":
        sheets(args.folio)
    elif args.command == "draft":
        draft(args.folio)
    elif args.command == "scan":
        scan(args.folio, args.rest)
    elif args.command == "check":
        check(args.folio, args.zoom)
    else:
        apply(ROOT / args.folio, credits.read(Path(args.rest[0]))[1])
        print(f"{args.folio}: readings applied; credits.csv regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
