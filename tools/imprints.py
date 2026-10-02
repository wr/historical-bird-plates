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
