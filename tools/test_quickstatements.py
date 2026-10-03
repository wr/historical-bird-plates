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
                         "https://github.com/wr/historical-bird-plates/releases/download/havell-v2/sheet-037.jpg")

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
    SHEET = "https://github.com/wr/historical-bird-plates/releases/download/havell-v2/sheet-001.jpg"

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


def item(p170: list[dict]) -> dict:
    """An item's claims, as wbgetentities gives them."""
    return {"P170": p170}


def creator(qid: str, references: list | None = None) -> dict:
    s = {"mainsnak": {"datavalue": {"value": {"id": qid}}}}
    if references:
        s["references"] = references
    return s


LEAR = [credit("Edward Lear", "lithographed"), credit("Charles Joseph Hullmandel", "printed")]
GOULDS = [credit("John Gould", "drew"), credit("John Gould", "lithographed"),
          credit("Elizabeth Gould", "drew"), credit("Elizabeth Gould", "lithographed")]


class FixItem(unittest.TestCase):
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

    def test_one_referenced_statement_among_same_value_duplicates_keeps_them_all(self):
        # QuickStatements removes the last match, which could be the referenced one.
        ref = [{"snaks": {"P248": [{"datavalue": {"value": {"id": "Q5"}}}]}}]
        for statements in ([creator(qs.GOULD), creator(qs.GOULD, ref)], [creator(qs.GOULD, ref), creator(qs.GOULD)]):
            lines, reports = qs.fix_item("Q9", item(statements), LEAR, QIDS, URL, "imprint")
            self.assertFalse(any(x.startswith("-") for x in lines))
            self.assertEqual(len(reports), 1)

    def test_unreferenced_duplicates_are_each_removed(self):
        lines, _ = qs.fix_item("Q9", item([creator(qs.GOULD), creator(qs.GOULD)]), LEAR, QIDS, URL, "imprint")
        self.assertEqual(lines.count("-Q9\tP170\tQ313787"), 2)

    def test_a_statement_already_referenced_to_the_scan_is_not_repeated(self):
        done = [{"snaks": {"P854": [{"datavalue": {"value": URL}}]}}]
        lines, _ = qs.fix_item("Q9", item([creator("Q309759", done)]), LEAR, QIDS, URL, "imprint")
        self.assertFalse(any(x.startswith("Q9\tP170\tQ309759") for x in lines))


class Created(unittest.TestCase):
    def setUp(self):
        qs.created.cache_clear()
        self.addCleanup(qs.created.cache_clear)

    def contribs(self, *pages):
        """api() answering with these pages of the account's page creations, one per call."""
        answers = [{"query": {"usercontribs": [{"title": t} for t in titles]},
                    **({"continue": {"uccontinue": f"next{i}"}} if i < len(pages) - 1 else {})}
                   for i, titles in enumerate(pages)]
        return mock.patch.object(qs, "api", side_effect=answers)

    def test_the_account_s_new_pages_are_read_page_by_page(self):
        with self.contribs(["Q1", "Q2"], ["Q3"]) as api:
            self.assertEqual(qs.created(), {"Q1", "Q2", "Q3"})
        first, second = (c.kwargs for c in api.call_args_list)
        self.assertEqual((first["ucuser"], first["ucshow"], first["ucnamespace"]), (qs.ACCOUNT, "new", 0))
        self.assertNotIn("uccontinue", first)
        self.assertEqual(second["uccontinue"], "next0")

    def test_it_is_read_once_per_run(self):
        with self.contribs(["Q1"]) as api:
            qs.created()
            qs.created()
        self.assertEqual(api.call_count, 1)

    def test_an_account_with_no_creations_is_an_error_not_an_empty_set(self):
        with self.contribs([]), self.assertRaises(SystemExit):
            qs.created()


def plate_item(work: str, plate: str, volume: str = "", p170: list | None = None) -> dict:
    """An entity part of `work` as plate `plate`, as wbgetentities gives it."""
    snak = lambda v: {"datavalue": {"value": v}}
    qual = {"P1545": [snak(plate)]}
    if volume:
        qual["P478"] = [snak(volume)]
    return {"claims": {"P361": [{"mainsnak": snak({"id": work}), "qualifiers": qual}],
                       "P170": [creator(qs.GOULD)] if p170 is None else p170}}


class Fix(Fixture):
    """fix() on a folio of four plates: Lear's with a printer, one with only a printer's line,
    one whose item another editor made, and the Goulds' own; and on the Havell folio."""
    EUROPE = "Q51448070"

    def setUp(self):
        super().setUp()
        write(self.root / "artists.csv",
              "name,kind,wikidata,note\nJohn Gould,person,Q313787,\nEdward Lear,person,Q309759,\n"
              "Charles Joseph Hullmandel,person,Q376691,\nJohn James Audubon,person,Q182882,\n"
              "Robert Havell Jr.,person,Q2157495,\nWilliam Matthew Hart,person,Q1,\n")
        write(self.root / "gould-europe" / "plates.csv",
              "plate,page_url,image_url,imprint\n"
              "1,https://bhl/1,https://other/1.jpg,Lear\n"
              "2,https://bhl/2,,Printed\n"
              "3,https://bhl/3,,Lear\n"
              "4,https://bhl/4,,Gould\n"
              "5,,https://other/5.jpg,Lear\n")
        write(self.root / "gould-europe" / "species.csv", "plate,scientific\n1,Aves aliqua\n")
        write(self.root / "gould-europe" / "credits.csv",
              "plate,name,role,as_printed\n"
              "1,Edward Lear,lithographed,x\n1,Charles Joseph Hullmandel,printed,x\n"
              "2,Charles Joseph Hullmandel,printed,x\n"
              "3,Edward Lear,lithographed,x\n"
              "4,John Gould,drew,x\n"
              "5,Edward Lear,lithographed,x\n")
        # Plates 1 to 5 are items Q11 to Q15; Q13 is another editor's.
        self.ents = {self.EUROPE: {f"Q1{n}": plate_item(self.EUROPE, str(n)) for n in (1, 2, 3, 4, 5)}}
        self.made = {"Q11", "Q12", "Q14", "Q15"}
        for target, new in (("entities", lambda work: self.ents[work]), ("created", lambda: self.made)):
            patch = mock.patch.object(qs, target, side_effect=new)
            patch.start()
            self.addCleanup(patch.stop)

    def subjects(self, blocks):
        return [b[0].lstrip("-").split("\t")[0] for b in blocks]

    def test_the_credit_line_is_applied_to_the_items_the_account_made(self):
        blocks, _ = qs.fix("gould-europe", None, None)
        self.assertEqual(self.subjects(blocks), ["Q11", "Q14"])
        self.assertIn("-Q11\tP170\tQ313787", blocks[0])
        self.assertTrue(any(x.startswith("Q11\tP170\tQ309759\tP3831\tQ16947657") for x in blocks[0]))
        self.assertTrue(any(x.startswith("Q11\tP872\tQ376691") for x in blocks[0]))
        self.assertFalse(any(x.startswith("-") for x in blocks[1]))   # Gould is the plate's artist

    def test_a_plate_whose_credits_name_no_artist_is_left_alone_and_reported(self):
        blocks, reports = qs.fix("gould-europe", None, None)
        self.assertNotIn("Q12", self.subjects(blocks))
        self.assertIn("plate 2: no artist's credit line read; Q12 left as it is", reports)

    def test_an_item_the_account_did_not_make_is_left_alone_and_listed(self):
        blocks, reports = qs.fix("gould-europe", None, None)
        self.assertNotIn("Q13", self.subjects(blocks))
        self.assertIn("plate 3: Q13 is not ours, left alone", reports)

    def test_an_item_the_account_made_but_the_dataset_has_no_plate_for_is_not_touched(self):
        self.ents[self.EUROPE]["Q99"] = plate_item(self.EUROPE, "99")
        self.made.add("Q99")
        blocks, _ = qs.fix("gould-europe", None, None)
        self.assertNotIn("Q99", self.subjects(blocks))

    def test_the_reference_is_the_scan_url_and_a_plate_without_one_is_reported_not_written(self):
        blocks, reports = qs.fix("gould-europe", None, None)
        refs = {x.split("\t")[-3] for b in blocks for x in b if not x.startswith("-")}
        self.assertEqual(refs, {'"https://bhl/1"', '"https://bhl/4"'})     # never image_url
        self.assertNotIn("Q15", self.subjects(blocks))
        self.assertTrue(any(r.startswith("plate 5:") and "Q15" in r for r in reports))
        self.assertFalse(any('""' in x for b in blocks for x in b))

    def test_limit_is_a_number_of_items(self):
        blocks, _ = qs.fix("gould-europe", None, 1)
        self.assertEqual(self.subjects(blocks), ["Q11"])

    def test_plates_picks_the_plates(self):
        blocks, reports = qs.fix("gould-europe", {"4"}, None)
        self.assertEqual(self.subjects(blocks), ["Q14"])
        self.assertEqual(reports, [])


class FixSeparateWork(Fixture):
    """The Supplement is its own work on Wikidata, and its plates are numbered afresh."""
    MAIN, SUPP = "Q967304", "Q51382318"

    def setUp(self):
        super().setUp()
        write(self.root / "artists.csv",
              "name,kind,wikidata,note\nJohn Gould,person,Q313787,\nWilliam Matthew Hart,person,Q1,\n"
              "Henry Constantine Richter,person,Q2,\n")
        write(self.root / "gould-australia" / "plates.csv",
              "volume,plate,page_url,imprint\nVI,1,https://bhl/vi1,Richter\nSupp,1,https://bhl/supp1,Hart\n")
        write(self.root / "gould-australia" / "species.csv", "volume,plate,scientific\nVI,1,Aves aliqua\nSupp,1,Aves alia\n")
        write(self.root / "gould-australia" / "credits.csv",
              "volume,plate,name,role,as_printed\n"
              "VI,1,Henry Constantine Richter,drew,x\nSupp,1,William Matthew Hart,drew,x\n")
        ents = {self.MAIN: {"Q21": plate_item(self.MAIN, "1", "VI")},
                self.SUPP: {"Q22": plate_item(self.SUPP, "1")}}
        for target, new in (("entities", lambda work: ents[work]), ("created", lambda: {"Q21", "Q22"})):
            patch = mock.patch.object(qs, target, side_effect=new)
            patch.start()
            self.addCleanup(patch.stop)

    def test_each_plate_is_read_against_its_own_work_and_credits(self):
        blocks, reports = qs.fix("gould-australia", None, None)
        by = {b[0].lstrip("-").split("\t")[0]: b for b in blocks}
        self.assertEqual(sorted(by), ["Q21", "Q22"])
        self.assertTrue(any(x.startswith("Q21\tP170\tQ2\t") and '"https://bhl/vi1"' in x for x in by["Q21"]))
        self.assertTrue(any(x.startswith("Q22\tP170\tQ1\t") and '"https://bhl/supp1"' in x for x in by["Q22"]))
        self.assertEqual(reports, [])


class FixHavell(Fixture):
    WORK = "Q377817"

    def test_a_havell_plate_cites_its_sheet_in_the_release(self):
        write(self.root / "artists.csv",
              "name,kind,wikidata,note\nJohn James Audubon,person,Q182882,\nRobert Havell Jr.,person,Q2157495,\n")
        write(self.root / "havell" / "plates.csv",
              "plate,imprint,image_url,sheet_asset\n1,Drawn,https://www.audubon.org/a.jpg,sheet-001.jpg\n")
        write(self.root / "havell" / "species.csv", "plate,scientific\n1,Aves aliqua\n")
        write(self.root / "havell" / "credits.csv",
              "plate,name,role,as_printed\n1,John James Audubon,drew,x\n1,Robert Havell Jr.,engraved,x\n")
        ents = {"Q31": plate_item(self.WORK, "1", p170=[creator(qs.AUDUBON)])}
        with mock.patch.object(qs, "entities", return_value=ents), mock.patch.object(qs, "created", return_value={"Q31"}):
            blocks, _ = qs.fix("havell", None, None)
        self.assertEqual(len(blocks), 1)
        sheet = '"https://github.com/wr/historical-bird-plates/releases/download/havell-v2/sheet-001.jpg"'
        self.assertTrue(all(x.split("\t")[-3] == sheet for x in blocks[0]))
        self.assertFalse(any(x.startswith("-") for x in blocks[0]))   # Audubon is named


if __name__ == "__main__":
    unittest.main()
