"""Tests for identify.py, on a copy of the dataset.

    python tools/test_identify.py
"""
from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import identify  # noqa: E402

REAL = identify.ROOT


def rows(root: Path, book: str) -> list[dict]:
    with open(root / book / "species.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Apply(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        for book in ("havell", "gould-asia"):
            shutil.copytree(REAL / book, self.tmp / book, ignore=shutil.ignore_patterns("img"))
        identify.ROOT = self.tmp

    def tearDown(self) -> None:
        identify.ROOT = REAL
        shutil.rmtree(self.tmp)

    def decide(self, *decisions: dict) -> None:
        path = self.tmp / "decisions.csv"
        cols = identify.DECISION_COLUMNS + sorted({k for d in decisions for k in d} - set(identify.DECISION_COLUMNS))
        identify.write(path, cols, [dict(d) for d in decisions])
        identify.apply(path, dry_run=False)

    def test_known_species_takes_the_dataset_ids(self) -> None:
        # The Wild Turkey is already in the dataset (plate 1), so its ids are copied exactly.
        turkey = next(r for r in rows(REAL, "havell") if r["plate"] == "1")
        self.decide({"book": "havell", "volume": "", "plate": "6", "figure": "", "scientific": "Meleagris gallopavo",
                     "form": "", "confidence": "high", "caption_checked": "", "reason": "test", "sources": "test"})
        six = [r for r in rows(self.tmp, "havell") if r["plate"] == "6"]
        self.assertEqual(len(six), 1)
        for c in ("common", "ebird_code", "wikidata", "gbif", "avibase", "birdnet_label"):
            self.assertEqual(six[0][c], turkey[c], c)
        self.assertEqual(six[0]["printed_name"], "Great American Hen & Young")

    def test_other_plates_untouched_and_order_kept(self) -> None:
        before = rows(self.tmp, "gould-asia")
        self.decide({"book": "gould-asia", "volume": "I", "plate": "3", "figure": "", "scientific": "Falco peregrinus",
                     "form": "subspecies", "confidence": "high", "caption_checked": "yes", "reason": "test",
                     "sources": "test"})
        after = rows(self.tmp, "gould-asia")
        self.assertEqual(len(before), len(after))
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual([(after[i]["volume"], after[i]["plate"]) for i in changed], [("I", "3")])
        self.assertEqual(after[changed[0]]["form"], "subspecies")

    def test_a_plate_can_become_two_rows_and_is_logged(self) -> None:
        base = {"book": "havell", "volume": "", "plate": "6", "form": "", "confidence": "high",
                "caption_checked": "", "reason": "test", "sources": "test"}
        self.decide({**base, "figure": "1.", "scientific": "Meleagris gallopavo"},
                    {**base, "figure": "2.", "scientific": "Meleagris gallopavo"})
        self.assertEqual(len([r for r in rows(self.tmp, "havell") if r["plate"] == "6"]), 2)
        with open(self.tmp / "havell" / "sources" / "decisions.csv", newline="") as f:
            log = list(csv.DictReader(f))
        self.assertEqual([x["figure"] for x in log[-2:]], ["1.", "2."])

    def test_open_row_needs_a_reason(self) -> None:
        with self.assertRaises(SystemExit):
            self.decide({"book": "havell", "volume": "", "plate": "6", "figure": "", "scientific": "", "form": "",
                         "confidence": "none", "caption_checked": "", "reason": "", "sources": ""})

    def test_unknown_species_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            self.decide({"book": "havell", "volume": "", "plate": "6", "figure": "", "scientific": "Avis imaginaria",
                         "form": "", "confidence": "high", "caption_checked": "", "reason": "x", "sources": "x"})


if __name__ == "__main__":
    unittest.main()
