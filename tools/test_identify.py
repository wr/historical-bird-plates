"""Tests for identify.py, on a copy of the dataset and a stand-in for GBIF.

    python tools/test_identify.py
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

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


def taxon(key: int, name: str, status: str = "ACCEPTED", rank: str = "SPECIES", accepted: int = 0, **more) -> dict:
    """A GBIF Backbone record, as /v1/species/{key} gives it."""
    r = {"key": key, "canonicalName": name, "rank": rank, "taxonomicStatus": status, "class": "Aves",
         "datasetKey": identify.BACKBONE, **more}
    return {**r, "acceptedKey": accepted} if accepted else r


class GbifRule(unittest.TestCase):
    """Keys are GBIF's own for these birds (October 2026), save in the made-up second half of one test."""

    def rule(self, sci: str, wikidata_key: str, *records: dict) -> str:
        by_key = {str(r["key"]): r for r in records}

        def get(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
            path = url.removeprefix(identify.GBIF)
            if path.startswith("?"):
                q = urllib.parse.parse_qs(path[1:])
                self.assertEqual(q["datasetKey"], [identify.BACKBONE])
                return json.dumps({"results": [r for r in records if r["canonicalName"] == q["name"][0]],
                                   "endOfRecords": True}).encode()
            if path not in by_key:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return json.dumps(by_key[path]).encode()

        with mock.patch.object(identify, "get", get):
            return identify.Ids._accepted(sci, wikidata_key)

    def test_accepted_key_preferred_over_a_doubtful_one(self) -> None:
        # Wikidata gives the Dark-eyed Junco's doubtful key; the accepted one holds the occurrences.
        self.assertEqual(self.rule("Junco hyemalis", "2492010", taxon(9362842, "Junco hyemalis"),
                                   taxon(2492010, "Junco hyemalis", "DOUBTFUL")), "9362842")

    def test_doubtful_key_only_when_it_is_the_names_only_species_key(self) -> None:
        tit = taxon(2495000, "Aegithalos caudatus", "DOUBTFUL")
        self.assertEqual(self.rule("Aegithalos caudatus", "2495000", tit), "2495000")
        # A second species-rank key for the name, even one the rule rejects, makes the doubtful one a guess.
        self.assertEqual(self.rule("Aegithalos caudatus", "2495000", tit,
                                   taxon(1, "Aegithalos caudatus", "SYNONYM", accepted=2),
                                   taxon(2, "Aegithalos glaucogularis")), "")

    def test_subspecies_key_rejected(self) -> None:
        self.assertEqual(self.rule("Lagopus scotica", "5227742",
                                   taxon(5227742, "Lagopus lagopus scotica", rank="SUBSPECIES")), "")

    def test_synonym_of_a_subspecies_rejected(self) -> None:
        # The subspecies' last word is the queried epithet, so the epithet check alone would let it through.
        self.assertEqual(self.rule("Eudynamys orientalis", "",
                                   taxon(10995397, "Eudynamys orientalis", "HOMOTYPIC_SYNONYM", accepted=6170364),
                                   taxon(6170364, "Eudynamys scolopaceus orientalis", rank="SUBSPECIES")), "")

    def test_synonym_of_a_species_with_another_epithet_rejected(self) -> None:
        self.assertEqual(self.rule("Cracticus argenteus", "7340483",
                                   taxon(7340483, "Cracticus argenteus", "SYNONYM", accepted=2489440),
                                   taxon(2489440, "Cracticus torquatus")), "")

    def test_synonym_of_the_same_epithet_in_another_genus_followed(self) -> None:
        self.assertEqual(self.rule("Tribonyx mortierii", "2474776",
                                   taxon(2474776, "Tribonyx mortierii", "SYNONYM", accepted=9003282),
                                   taxon(9003282, "Gallinula mortierii")), "9003282")
        # The new genus may change the epithet's gender ending, which is the same epithet.
        self.assertEqual(self.rule("Ardenna grisea", "8249990",
                                   taxon(8249990, "Ardenna grisea", "HOMOTYPIC_SYNONYM", accepted=5739277),
                                   taxon(5739277, "Puffinus griseus")), "5739277")
        self.assertTrue(identify.same_epithet("nigrum", "niger"))
        self.assertTrue(identify.same_epithet("sinense", "sinensis"))
        self.assertFalse(identify.same_epithet("melanocephala", "melanoleuca"))

    def test_wikidata_key_when_gbif_lacks_the_name(self) -> None:
        self.assertEqual(self.rule("Anarhynchus bicinctus", "2480294", taxon(2480294, "Charadrius bicinctus")),
                         "2480294")
        # Unless the Backbone has deleted it.
        self.assertEqual(self.rule("Anarhynchus mongolus", "2480298",
                                   taxon(2480298, "Charadrius mongolus", deleted="2019-09-06")), "")

    def test_cache_from_the_old_rule_is_not_read(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "gbif.json").write_text(json.dumps({"2492010": "2492010"}))
        with mock.patch.object(identify, "CACHE", tmp):
            ids = identify.Ids(None)
            self.assertEqual(ids.gbif_cache, {})
            ids.cache["Junco hyemalis"] = {"wikidata": "Q525818", "gbif": "2492010", "avibase": ""}
            ids.gbif_cache[ids.slot("Junco hyemalis")] = "9362842"
            ids.save()
            self.assertEqual(identify.Ids(None).gbif("Junco hyemalis"), "9362842")


if __name__ == "__main__":
    unittest.main()
