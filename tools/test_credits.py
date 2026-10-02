"""Tests for credits.py.

    python3 tools/test_credits.py
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import credits  # noqa: E402
from credits import Credit, UnknownCredit, parse  # noqa: E402


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def names_roles(credits_: list[Credit]) -> list[tuple[str, str]]:
    return [(c.name, c.role) for c in credits_]


class Parse(unittest.TestCase):
    def test_wording_before_names(self):
        self.assertEqual(parse("Drawn on Stone by E. Lear | Printed by C. Hullmandel"), [
            Credit("Edward Lear", "lithographed", "E. Lear"),
            Credit("Charles Joseph Hullmandel", "printed", "C. Hullmandel")])

    def test_joint_credit_stays_joint(self):
        self.assertEqual(parse("Drawn from Nature & on Stone by J. & E. Gould"), [
            Credit("John Gould", "drew", "J. & E. Gould"),
            Credit("John Gould", "lithographed", "J. & E. Gould"),
            Credit("Elizabeth Gould", "drew", "J. & E. Gould"),
            Credit("Elizabeth Gould", "lithographed", "J. & E. Gould")])

    def test_wording_after_names_split_on_ampersand_and_and(self):
        self.assertEqual(parse("J.Wolf & HCRichter, del et lith. | Walter & Cohn Imp."), [
            Credit("Joseph Wolf", "drew", "J.Wolf"),
            Credit("Joseph Wolf", "lithographed", "J.Wolf"),
            Credit("Henry Constantine Richter", "drew", "HCRichter"),
            Credit("Henry Constantine Richter", "lithographed", "HCRichter"),
            Credit("Walter & Cohn", "printed", "Walter & Cohn")])
        self.assertEqual(parse("J. Gould and H.C. Richter del."), [
            Credit("John Gould", "drew", "J. Gould"),
            Credit("Henry Constantine Richter", "drew", "H.C. Richter")])

    def test_case_punctuation_and_spacing_fold(self):
        self.assertEqual(names_roles(parse("drawn from nature  &  on stone by J.&E.Gould")),
                         names_roles(parse("Drawn from Nature & on Stone by J. & E. Gould")))
        self.assertEqual(names_roles(parse("J.Gould &H.C.Richter,del et lith | Walter,Imp.")),
                         names_roles(parse("J. Gould & H.C. Richter, del et lith. | Walter, Imp.")))
        self.assertEqual(names_roles(parse("J.Gould & H.C.Richter, del et lith. | Walter.Imp.")),  # Australia Supp.7
                         names_roles(parse("J.Gould & H.C.Richter, del et lith. | Walter. Imp.")))
        with self.assertRaises(UnknownCredit):
            parse("J.Gould & H.C.Richter, del et lith. | WalterImp.")

    def test_a_line_with_two_credits_is_split_before_the_second_wording(self):
        self.assertEqual(names_roles(parse(  # Australia V.45
            "Drawn on Stone by I & E. Gould from a Drawing by Edwd. Lear. | Printed by C. Hullmandel.")), [
            ("John Gould", "lithographed"), ("Elizabeth Gould", "lithographed"), ("Edward Lear", "drew"),
            ("Charles Joseph Hullmandel", "printed")])

    def test_a_line_with_two_credits_is_split_after_the_first_wording(self):
        self.assertEqual(names_roles(parse(  # Asia I.7
            "J.Wolf del. H.C.Richter lith. | Hullmandel & Walton Imp.")), [
            ("Joseph Wolf", "drew"), ("Henry Constantine Richter", "lithographed"),
            ("Hullmandel & Walton", "printed")])
        self.assertEqual(names_roles(parse("J. Wolf, del. H.C.Richter, lith. | Hullmandel & Walton, Imp")),  # Asia VII.39
                         names_roles(parse("J.Wolf del. H.C.Richter lith. | Hullmandel & Walton Imp.")))
        # a wording inside a name, or one followed by lower-case words, splits nothing
        for line in ("Hullmandel Imp.", "J.Gould and H.C.Richter, del. et lith.", "J.Gould & W.Hart del et lith"):
            with self.subTest(line=line):
                self.assertEqual(credits.credit_parts(line), [line])
        self.assertEqual(credits.credit_parts("J.Wolf del. H.C.Richter lith."), ["J.Wolf del.", "H.C.Richter lith."])

    def test_havell_lines_keep_their_abbreviations(self):
        self.assertEqual(parse("Drawn from nature by J.J. Audubon F.R.S. F.L.S. | Engraved by W.H. Lizars Edinr. "
                               "| Retouched by R. Havell Junr."), [
            Credit("John James Audubon", "drew", "J.J. Audubon F.R.S. F.L.S."),
            Credit("William Home Lizars", "engraved", "W.H. Lizars Edinr."),
            Credit("Robert Havell Jr.", "retouched", "R. Havell Junr.")])

    def test_one_line_gives_several_roles(self):
        self.assertEqual(names_roles(parse("Engraved, Printed & Coloured by R. Havell Junr.")), [
            ("Robert Havell Jr.", "engraved"), ("Robert Havell Jr.", "printed"), ("Robert Havell Jr.", "coloured")])

    def test_a_repeated_credit_is_kept_once(self):
        self.assertEqual(names_roles(parse("Engraved by R. Havell Junr. | Engraved, Printed & Coloured by R. Havell Junr.")), [
            ("Robert Havell Jr.", "engraved"), ("Robert Havell Jr.", "printed"), ("Robert Havell Jr.", "coloured")])

    def test_unknown_wording_or_name_is_an_error(self):
        for imprint in ("Sketched by J. Gould", "Drawn on Stone by J. Smith",
                        "J. Gould & J. Smith del. et lith.", "Printed by C. Hullmandel | ", "",
                        "Drawn on Stone by E. Lear 2", "Drawn on Stone by E. Lear?"):
            with self.subTest(imprint=imprint), self.assertRaises(UnknownCredit):
                parse(imprint)

    def test_and_may_touch_a_stop_or_the_next_capital(self):
        for line in ("J.Gould andH.C.Richter, del. et lith.", "J. Gould,and H.CRichter, del et lith,",
                     "J. Gould.and H. CRichter, del. et lith", "J.GouldandH.C.Richter, del. et lith.",
                     "J. Gould and. H. C. Richter, del. et lith."):
            with self.subTest(line=line):
                self.assertEqual([c.name for c in parse(line)], ["John Gould", "John Gould", "Henry Constantine Richter",
                                                                  "Henry Constantine Richter"])
        self.assertEqual(names_roles(parse("Printed by C. Hullmandel")), [("Charles Joseph Hullmandel", "printed")])

    def test_a_colon_may_stand_before_a_wording_written_after_the_names(self):
        self.assertEqual(parse("J.Gould and H.C.Richter:del.et lith"),
                         parse("J.Gould and H.C.Richter, del. et lith"))

    def test_a_folio_s_own_name_forms_count_in_that_folio_only(self):
        line = "Gould & H. C Richter, del. et lith. | Walter, Imp."  # Great Britain III.61
        self.assertEqual(names_roles(parse(line, "gould-britain")), [
            ("John Gould", "drew"), ("John Gould", "lithographed"),
            ("Henry Constantine Richter", "drew"), ("Henry Constantine Richter", "lithographed"),
            ("Walter", "printed")])
        for folio in (None, "gould-europe", "gould-australia", "gould-asia", "havell"):
            with self.subTest(folio=folio), self.assertRaises(UnknownCredit):
                parse(line, folio)
        with self.assertRaises(UnknownCredit):
            parse("Drawn from Life & on Stone by Gould", "gould-europe")
        line = "Drawn from Nature & on stone by J & E. Gould. | Printed by C. Hullman"  # Europe 202
        self.assertEqual(names_roles(parse(line, "gould-europe"))[-1], ("Charles Joseph Hullmandel", "printed"))
        for folio in (None, "gould-britain", "gould-australia", "gould-asia", "havell"):
            with self.subTest(folio=folio), self.assertRaises(UnknownCredit):
                parse(line, folio)
        for line, last, also in (("Gould and H.C.Richter del et lith. | Hullmandel & Walton Imp.",  # Australia V.8
                                  ("Hullmandel & Walton", "printed"), ("gould-britain",)),  # its own bare Gould
                                 ("Hullmandel Imp.", ("Charles Joseph Hullmandel", "printed"), ()),  # Australia IV.3
                                 ("J&E Gould del et lith: | C C.Hullmandel Imp.",  # Australia IV.93
                                  ("Charles Joseph Hullmandel", "printed"), ())):
            self.assertEqual(names_roles(parse(line, "gould-australia"))[-1], last)
            for folio in (None, "gould-britain", "gould-europe", "gould-asia", "havell"):
                if folio in also:
                    continue
                with self.subTest(line=line, folio=folio), self.assertRaises(UnknownCredit):
                    parse(line, folio)
        self.assertEqual(names_roles(parse("Gould and H.C.Richter del et lith.", "gould-australia")), [
            ("John Gould", "drew"), ("John Gould", "lithographed"),
            ("Henry Constantine Richter", "drew"), ("Henry Constantine Richter", "lithographed")])
        with self.assertRaises(UnknownCredit):  # a bare Gould alone could be J. & E. Gould with its initials lost
            parse("Gould del.", "gould-australia")

    def test_asia_s_own_name_forms(self):
        for line, last in (("Wolf and H.C.Richter del. et lith. | Hullmandel & Walton, Imp.",  # VI.74
                            ("Hullmandel & Walton", "printed")),
                           ("J.Wolf and Hart del et lith. | Walter, Imp.", ("Walter", "printed")),  # VII.13
                           ("J.Gould and C.H.Richter, del. et lith. | Hullmandel & Walton, Imp",  # IV.5
                            ("Hullmandel & Walton", "printed")),
                           ("H. Gould, and H.C.Richter, del et lith. | Walter Imp.", ("Walter", "printed")),  # IV.26
                           ("J.Gould and H.C.Richter del et lith | Hulmandel & Walton Imp",  # III.4
                            ("Hullmandel & Walton", "printed"))):
            self.assertEqual(names_roles(parse(line, "gould-asia"))[-1], last)
            for folio in (None, "gould-britain", "gould-europe", "gould-australia", "havell"):
                with self.subTest(line=line, folio=folio), self.assertRaises(UnknownCredit):
                    parse(line, folio)
        self.assertEqual(names_roles(parse("Wolf and H.C.Richter del. et lith.", "gould-asia"))[0], ("Joseph Wolf", "drew"))
        self.assertEqual(names_roles(parse("J.Wolf and Hart del et lith.", "gould-asia"))[2:],
                         [("William Matthew Hart", "drew"), ("William Matthew Hart", "lithographed")])
        for line in ("Wolf del.", "Hart del. et lith.", "H. Gould del."):  # a bare surname or a stray initial stands alone nowhere
            with self.subTest(line=line):
                self.assertRaises(UnknownCredit, parse, line)

    def test_seen_on_the_plates(self):
        """Every wording found on the plates parses. Add each new variant here."""
        for imprint in ("Drawn from Life & on Stone by J. & E. Gould | Printed by C. Hullmandel",
                        "J. Gould and H.C. Richter del. et lith. | Hullmandel & Walton Imp.",
                        "J. Gould & H.C. Richter del et lith. | Walter Imp.",
                        "J. Gould & W. Hart del. et lith. | Walter Imp.",
                        "J.Gould &H.C.Richter,del et lith | Walter,Imp.",
                        "J.Gould andH.C.Richter, del. et lith. | Walter & Cohn, Imp.",
                        "J. Gould,and H.CRichter, del et lith, | Walter, Imp.",
                        "J. Gould.and H. CRichter, del. et lith | Walter,Imp.",
                        "J.GouldandH.C.Richter, del. et lith. | Walter & Cohn, Imp.",
                        "J.Gould and H.C.Richter:del.et lith | Walter & Cohn, Imp.",
                        "J.Gould & H.C.Richter: del et lith. | Walter Imp",
                        "Drawn from Life and on Stone by J & E. Gould. | Printed by C. Hullmandel.",
                        "Drawn on Stone from Life by J & E. Gould. | Printed by C. Hullmandel.",
                        "Drawn on Stone from Nature by J & E. Gould. | Printed by C.Hullmandel.",
                        "E. Lear del et lithog. | Printed by C. Hullmandel.",
                        "E.Lear del et lith: | Printed by C.Hullmandel.",
                        "E. Lear del et lithog: | Printed by C.Hullmandel.",
                        "E.Lear del: et lith. | Printed by C. Hullmandel.",
                        "E. Lear del: et lith: | Printed by C.Hullmandel",
                        "E. Lear del: et lithog: | Printed by C. Hullmandel.",
                        "Drawn from Nature & on Stone by J & E. Gould. | Printed by C.Hullmandel.",
                        "Drawn from Life & on Stone by E. Lear | Printed by C. Hullmandel.",
                        "J. Gould and H.C.Richter delt. | C. Hullmandel Imp.",
                        "J. Gould and H.C.Richter delt. | C.Hullmandel Impt.",
                        "J. Gould and H.C.Richter delt, et lith. | Hullmandel & Walton Imp.",
                        "J. Gould and H.C.Richter lithog. | C. Hullmandel Imp.",
                        "J & E. Gould del: | C.Hullmandel Imp:",
                        "J & E. Gould del: | C: Hullmandel Imp:",
                        "I. Gould and H. C. Richter delt. | C. Hullmandel Impt.",
                        "J:Gould and H.C.Richter del et lith. | Hullmandel & Walton Imp.",
                        "J.Gould H.C.Richter, del. et lith. | Hullmandel & Walton, Imp.",
                        "J. Gould and H.C.Richter del et lith. | Hullmandel and Walton Imp.",
                        "Drawn from Nature and on Stone by Waterhouse Hawkins. | Hullmandel & Walton Imp.",
                        "Drawn on Stone by I & E. Gould from a Drawing by Edwd. Lear. | Printed by C. Hullmandel.",
                        "J.Gould & H.C.Richter, del et lith. | Walter.Imp.",
                        "J.Gould and H.C.Richter, del. et lith. | T. Walter, Imp.",  # Asia I.69
                        "W.Hart del. et lith. | Walter imp.",  # Asia IV.17
                        "J. Gould, and H.C.Richter, del, et, lith, | Walter, Imp.",  # Asia VII.19
                        "J.Gould.H.C.Richter, del. et lith. | Walter & Cohn, Imp.",  # Asia VI.72
                        "J.Wolf and H.C.Richter, del. et lith. | Walter & Cohn, Imp.",  # Asia I.10
                        "J.Gould & W.Hart. del et lith | Walter, Imp",  # Asia V.32
                        "J.Gould and H.C.Richter del et lith | Hullmandel & Walton Imp.",  # Asia II.22
                        "Drawn from nature by J.J. Audubon F.R.S. F.L.S. | Engraved, Printed & Coloured by R. Havell Junr."):
            with self.subTest(imprint=imprint):
                self.assertTrue(parse(imprint))


class Tables(unittest.TestCase):
    def test_every_name_is_in_artists_csv(self):
        with open(credits.ROOT / "artists.csv", newline="", encoding="utf-8") as f:
            known = {r["name"] for r in csv.DictReader(f)}
        tables = [credits.NAMES] + list(credits.FOLIO_NAMES.values())
        for form, people in (x for table in tables for x in table.items()):
            for person in people:
                self.assertIn(person, known, f"{form} -> {person}")

    def test_folio_names_are_for_known_folios(self):
        self.assertTrue(set(credits.FOLIO_NAMES) <= set(credits.FOLIOS))

    def test_every_role_is_known(self):
        for table in (credits.BEFORE, credits.AFTER):
            for wording, roles in table.items():
                self.assertTrue(set(roles) <= set(credits.ROLES), wording)


class Files(unittest.TestCase):
    def folio(self, plates: list[dict], per_volume: bool) -> Path:
        d = Path(tempfile.mkdtemp())
        vol = ["volume"] if per_volume else []
        write_csv(d / "plates.csv", vol + ["plate", "imprint", "notes"], plates)
        write_csv(d / "species.csv", vol + ["plate", "scientific"], [])
        return d

    def test_rows_follow_plates_and_skip_empty_imprints(self):
        d = self.folio([{"volume": "I", "plate": "1", "imprint": "J. Gould and H.C. Richter del."},
                        {"volume": "I", "plate": "2", "imprint": "", "notes": "credit line cut off"}], True)
        self.assertEqual(credits.rows(d), [
            {"volume": "I", "plate": "1", "name": "John Gould", "role": "drew", "as_printed": "J. Gould"},
            {"volume": "I", "plate": "1", "name": "Henry Constantine Richter", "role": "drew",
             "as_printed": "H.C. Richter"}])

    def test_no_volume_column_for_a_folio_numbered_straight_through(self):
        d = self.folio([{"plate": "37", "imprint": "Drawn on Stone by E. Lear"}], False)
        self.assertEqual(credits.columns(d), ["plate", "name", "role", "as_printed"])
        self.assertEqual(credits.render(d), "plate,name,role,as_printed\n37,Edward Lear,lithographed,E. Lear\n")

    def test_write_reports_a_change_once(self):
        d = self.folio([{"plate": "37", "imprint": "Drawn on Stone by E. Lear"}], False)
        self.assertTrue(credits.write(d))
        self.assertFalse(credits.write(d))

    def test_totals_count_plates(self):
        d = self.folio([{"plate": "1", "imprint": "Drawn on Stone by E. Lear"},
                        {"plate": "2", "imprint": "Drawn on Stone by E. Lear | Printed by C. Hullmandel"}], False)
        self.assertEqual(credits.totals(d)[("Edward Lear", "lithographed")], 2)
        self.assertEqual(credits.totals(d)[("Charles Joseph Hullmandel", "printed")], 1)

    def test_rows_use_the_folio_s_own_name_forms(self):
        for folio, ok in (("gould-britain", True), ("gould-europe", False)):
            d = Path(tempfile.mkdtemp()) / folio
            d.mkdir()
            write_csv(d / "plates.csv", ["plate", "imprint"], [{"plate": "1", "imprint": "Gould & H. C Richter del."}])
            write_csv(d / "species.csv", ["plate", "scientific"], [])
            with self.subTest(folio=folio):
                if ok:
                    self.assertEqual([r["name"] for r in credits.rows(d)], ["John Gould", "Henry Constantine Richter"])
                else:
                    self.assertRaises(UnknownCredit, credits.rows, d)

    def test_an_error_names_the_plate(self):
        d = self.folio([{"volume": "IV", "plate": "5", "imprint": "Sketched by J. Gould"}], True)
        with self.assertRaisesRegex(UnknownCredit, r"plate IV\.5"):
            credits.rows(d)


if __name__ == "__main__":
    unittest.main()
