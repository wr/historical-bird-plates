"""Tests for quickstatements.py's statements, on fixtures; no network.

    python3 tools/test_quickstatements.py
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quickstatements as qs  # noqa: E402

QIDS = {"John Gould": "Q313787", "Elizabeth Gould": "Q253875", "Edward Lear": "Q309759",
        "Charles Joseph Hullmandel": "Q376691", "Robert Havell Jr.": "Q2157495"}
URL = "https://www.biodiversitylibrary.org/page/42174243"
REF = f'\tS854\t"{URL}"\tS1683\ten:"Drawn on Stone by E. Lear | Printed by C. Hullmandel"'


def credit(name: str, role: str) -> dict:
    return {"name": name, "role": role}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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

    def test_a_plate_with_no_credits_gives_no_lines(self):
        self.assertEqual(qs.creator_lines("LAST", [], QIDS, URL, "x"), [])


class ScanUrl(unittest.TestCase):
    PLATE = {"page_url": URL, "image_url": "https://www.audubon.org/gone.jpg", "sheet_asset": "sheet-037.jpg"}

    def test_a_havell_plate_cites_its_sheet_in_the_release(self):
        self.assertEqual(qs.scan_url("havell", self.PLATE),
                         "https://github.com/wr/historical-bird-plates/releases/download/havell-v1/sheet-037.jpg")

    def test_a_gould_plate_cites_its_bhl_page(self):
        self.assertEqual(qs.scan_url("gould-europe", self.PLATE), URL)

    def test_no_url_is_blank_rather_than_the_old_image_url(self):
        self.assertEqual(qs.scan_url("havell", {"image_url": "https://www.audubon.org/gone.jpg"}), "")
        self.assertEqual(qs.scan_url("gould-asia", {"image_url": "https://www.audubon.org/gone.jpg"}), "")


class Fixture(unittest.TestCase):
    """A repository root of our own, so that no real data is read."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patch = mock.patch.object(qs, "ROOT", self.root)
        patch.start()
        self.addCleanup(patch.stop)


class Credited(Fixture):
    def test_a_folio_numbered_per_volume_is_keyed_by_volume_and_plate(self):
        write(self.root / "gould-asia" / "credits.csv",
              "volume,plate,name,role,as_printed\n"
              "I,3,John Gould,drew,x\n"
              "II,3,Edward Lear,lithographed,y\n")
        self.assertEqual(sorted(qs.credited("gould-asia", True)), [("I", "3"), ("II", "3")])
        self.assertEqual(qs.credited("gould-asia", True)[("II", "3")][0]["name"], "Edward Lear")

    def test_a_folio_numbered_straight_through_is_keyed_by_plate_alone(self):
        write(self.root / "gould-europe" / "credits.csv",
              "plate,name,role,as_printed\n"
              "37,Edward Lear,lithographed,x\n"
              "37,Charles Joseph Hullmandel,printed,x\n")
        by = qs.credited("gould-europe", False)
        self.assertEqual(list(by), [("", "37")])
        self.assertEqual([c["role"] for c in by[("", "37")]], ["lithographed", "printed"])

    def test_artist_qids_leaves_out_a_name_without_one(self):
        write(self.root / "artists.csv",
              "name,kind,wikidata,note\nJohn Gould,person,Q313787,\nT. Walter,person,,\n")
        self.assertEqual(qs.artist_qids(), {"John Gould": "Q313787"})


class Batch(Fixture):
    """batch() on a two-plate Havell folio: one credited, one with no credit line."""
    SHEET = "https://github.com/wr/historical-bird-plates/releases/download/havell-v1/sheet-001.jpg"

    def setUp(self):
        super().setUp()
        write(self.root / "artists.csv",
              "name,kind,wikidata,note\nJohn James Audubon,person,Q182882,\nRobert Havell Jr.,person,Q2157495,\n")
        write(self.root / "havell" / "plates.csv",
              "plate,title,legend,imprint,image_url,sheet_asset,crop_asset,notes\n"
              "1,Wild Turkey,,Drawn from nature by J. J. Audubon | Retouched by R. Havell Junr.,"
              "https://www.audubon.org/a.jpg,sheet-001.jpg,crop-001.jpg,\n"
              "2,Other Bird,,,https://www.audubon.org/b.jpg,sheet-002.jpg,crop-002.jpg,\n")
        write(self.root / "havell" / "species.csv",
              "plate,scientific,common,wikidata,confidence,printed_name\n"
              "1,Meleagris gallopavo,Wild Turkey,Q43365,high,Wild Turkey\n"
              "2,Aves aliqua,Other Bird,Q5113,high,Other Bird\n")
        write(self.root / "havell" / "credits.csv",
              "plate,name,role,as_printed\n"
              "1,John James Audubon,drew,x\n"
              "1,Robert Havell Jr.,retouched,x\n")
        self.blocks, _, _ = qs.batch("havell", None, None, False)

    def test_the_credit_line_gives_the_creators_and_replaces_the_folios_fixed_artist(self):
        creators = [line for line in self.blocks[0] if "\tP170\t" in line]
        self.assertEqual(
            creators,
            [f'LAST\tP170\tQ182882\tP3831\tQ15296811\tS854\t"{self.SHEET}"\tS1683\ten:"Drawn from nature by J. J. Audubon | Retouched by R. Havell Junr."',
             f'LAST\tP170\tQ2157495\tS854\t"{self.SHEET}"\tS1683\ten:"Drawn from nature by J. J. Audubon | Retouched by R. Havell Junr."'])

    def test_a_havell_reference_is_the_release_sheet_never_audubon_org(self):
        self.assertFalse(any("audubon.org" in line for block in self.blocks for line in block))

    def test_a_plate_with_no_credit_line_gets_no_creator_statement(self):
        self.assertFalse(any("\tP170\t" in line or "\tP872\t" in line for line in self.blocks[1]))


if __name__ == "__main__":
    unittest.main()
