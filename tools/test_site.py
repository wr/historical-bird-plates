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
        self.assertEqual(site_data.slugify("Baudin's Black-Cockatoo"), "baudins-black-cockatoo")
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
