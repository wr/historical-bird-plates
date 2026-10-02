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
