"""Tests for quickstatements.py's statements, on fixtures; no network.

    python3 tools/test_quickstatements.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quickstatements as qs  # noqa: E402

QIDS = {"John Gould": "Q313787", "Elizabeth Gould": "Q253875", "Edward Lear": "Q309759",
        "Charles Joseph Hullmandel": "Q376691", "Robert Havell Jr.": "Q2157495"}
URL = "https://www.biodiversitylibrary.org/page/42174243"
REF = f'\tS854\t"{URL}"\tS1683\ten:"Drawn on Stone by E. Lear | Printed by C. Hullmandel"'


def credit(name: str, role: str) -> dict:
    return {"name": name, "role": role}


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


if __name__ == "__main__":
    unittest.main()
