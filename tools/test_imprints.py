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

SHADE = {".": 0, "-": 1, "+": 2, "#": 3}


def mask(*rows: str) -> tuple[bytes, int]:
    """A mask drawn in characters: . paper, - faint ink, + ink, # dark ink."""
    return bytes(SHADE[c] for row in rows for c in row), len(rows[0])


def paint(width: int, height: int, *marks: tuple[int, int, int, int, str]) -> bytes:
    """A mask of `width` x `height` with rectangles of letters: (x0, y0, x1, y1, shade), each
    letter two columns of ink and one of paper."""
    px = bytearray(width * height)
    for x0, y0, x1, y1, shade in marks:
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x - x0) % 3 != 2:
                    px[y * width + x] = SHADE[shade]
    return bytes(px)


def line(x0: int, y0: int, x1: int, y1: int, ink: int = 0, dark: int = -1) -> list[int]:
    """A found line; by default half its box is ink, a third of that dark."""
    ink = ink or (x1 - x0) * (y1 - y0) // 2
    return [x0, y0, x1, y1, ink, ink // 3 if dark < 0 else dark]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Blobs(unittest.TestCase):
    def test_ink_close_along_a_row_joins_and_dark_ink_is_counted(self):
        m, w = mask("##..++......#",
                    "##..........#")
        found, runs = imprints.blobs(m, w, gap=2, longest=50)
        self.assertEqual(sorted(found), [[0, 0, 6, 2, 6, 4], [12, 0, 13, 2, 2, 2]])
        self.assertEqual(len(runs), 4)

    def test_rows_touching_join_one_blob(self):
        m, w = mask("#....",
                    ".#...",
                    "..#..")
        found, _ = imprints.blobs(m, w, gap=0, longest=50)
        self.assertEqual(found, [[0, 0, 3, 3, 3, 3]])

    def test_a_solid_run_longer_than_any_letter_is_a_rule_and_left_out(self):
        m, w = mask("..##.##.....",
                    "############")
        found, _ = imprints.blobs(m, w, gap=1, longest=8)
        self.assertEqual(found, [[2, 0, 7, 1, 4, 4]])

    def test_faint_ink_counts_only_when_asked(self):
        m, w = mask("--++..")
        self.assertEqual(imprints.blobs(m, w, gap=1, longest=50)[0], [[2, 0, 4, 1, 2, 0]])
        self.assertEqual(imprints.blobs(m, w, gap=1, longest=50, least=1)[0], [[0, 0, 4, 1, 4, 0]])

    def test_floor_is_the_lowest_row_of_art_in_each_band_of_columns(self):
        m, w = mask("######..",
                    "##......",
                    "......##")
        found, runs = imprints.blobs(m, w, gap=0, longest=50)
        art = {i for i, b in enumerate(found) if b[0] == 0}
        self.assertEqual(imprints.floor(runs, art, w, step=2), [1, 0, 0, -1, -1])


class Lines(unittest.TestCase):
    def test_level_blobs_near_each_other_make_a_line(self):
        found = [[0, 0, 10, 5, 20, 5], [12, 1, 20, 5, 10, 2], [40, 0, 50, 5, 20, 0], [21, 8, 30, 13, 9, 9]]
        self.assertEqual(imprints.lines(found, reach=5, tallest=5),
                         [[0, 0, 20, 5, 30, 7], [40, 0, 50, 5, 20, 0], [21, 8, 30, 13, 9, 9]])

    def test_the_caption_is_the_lowest_block_across_the_centre(self):
        title, latin = line(350, 800, 650, 810), line(400, 815, 600, 823)
        found = [line(300, 400, 700, 410), title, latin, line(150, 818, 380, 824), line(480, 900, 520, 905)]
        self.assertEqual(imprints.caption(found, 1000, 1), [title, latin])

    def test_a_line_across_the_centre_but_not_centred_is_not_the_caption(self):
        title, edge = line(350, 800, 650, 810), line(70, 900, 560, 905)    # the page's edge, say
        self.assertEqual(imprints.caption([title, edge], 1000, 1), [title])


class Corner(unittest.TestCase):
    """A sheet 1000 wide, in units of 1 px."""
    caption = [line(350, 800, 650, 810), line(400, 815, 600, 823)]

    def test_lowest_small_text_in_each_half_not_the_caption_nor_pencil_nor_art(self):
        left, right = line(150, 818, 380, 824), line(650, 819, 800, 825)
        found = self.caption + [
            left, right,
            line(100, 900, 160, 910, dark=0),     # a pencilled number: no dark ink
            line(200, 700, 260, 706),            # in the art, above the caption
            line(610, 817, 640, 823)]            # the caption's last word, level with the right line
        for side, want in (("left", left), ("right", right)):
            with self.subTest(side=side):
                self.assertEqual(imprints.corner(found, side, 1000, 1, "lowest", cap_top=800), [want])

    def test_a_credit_line_is_20_to_240_units_long_and_at_most_9_5_tall(self):
        for L, ok in ((line(100, 800, 118, 806), False),     # a pencilled number, or a stroke of the art
                      (line(100, 800, 122, 806), True),
                      (line(100, 800, 122, 806, dark=3), False),   # short, with little dark ink: pencil
                      (line(100, 800, 130, 806), True),
                      (line(100, 800, 130, 806, dark=3), True),
                      (line(100, 800, 340, 806), True),
                      (line(100, 800, 360, 806), False),     # the page's edge
                      (line(100, 800, 300, 809), True),
                      (line(100, 800, 300, 811), False)):    # a caption's capitals
            with self.subTest(L=L):
                self.assertEqual(imprints.textlike(L, 1), ok)

    def test_a_line_with_art_just_above_it_in_its_columns_is_in_the_art(self):
        low = [-1] * 1001
        for k in range(150, 300):
            low[k] = 815
        found = [line(150, 818, 380, 824)]
        self.assertEqual(imprints.corner(found, "left", 1000, 1, "lowest", low, 1), [])
        low[150:300] = [800] * 150
        self.assertEqual(imprints.corner(found, "left", 1000, 1, "lowest", low, 1), found)

    def test_outermost_takes_the_credit_line_over_a_title_below_it(self):
        credit, title = line(100, 700, 300, 706), line(120, 720, 280, 728)
        self.assertEqual(imprints.corner([credit, title], "left", 1000, 1, "outermost"), [credit])
        self.assertEqual(imprints.corner([credit, title], "left", 1000, 1, "lowest"), [title])

    def test_outermost_passes_over_a_strip_of_the_art_with_art_below_it(self):
        low = [-1] * 1001
        low[50:500] = [760] * 450                     # the art's foot, at 760, over columns 50-500
        strip_of_art, credit = line(50, 700, 480, 710), line(100, 765, 300, 771)
        self.assertEqual(imprints.corner([strip_of_art, credit], "left", 1000, 1, "outermost", low, 1), [credit])

    def test_lines_stacked_in_a_corner_are_taken_together(self):
        a, b = line(600, 700, 800, 706), line(610, 709, 790, 715)
        self.assertEqual(imprints.corner([b, a, line(620, 760, 780, 766)], "right", 1000, 1, "outermost"), [a, b])

    def test_a_band_keeps_only_lines_level_with_it(self):
        found = [line(150, 818, 380, 824), line(150, 860, 380, 866)]
        self.assertEqual(imprints.corner(found, "left", 1000, 1, "lowest", band=(810, 830)), found[:1])


class CreditLines(unittest.TestCase):
    """A mask 200 x 40, in units of 1 px: a caption across the centre, credit lines below."""

    def test_both_corners_below_the_caption_not_the_pencilled_number(self):
        m = paint(200, 40, (70, 10, 130, 14, "#"), (20, 20, 60, 24, "#"), (140, 20, 180, 24, "#"),
                  (25, 32, 45, 36, "+"))
        left, right, cap = imprints.credit_lines(m, 200, 1, "lowest")
        self.assertEqual([L[:4] for L in left], [[20, 20, 60, 24]])
        self.assertEqual([L[:4] for L in right], [[140, 20, 180, 24]])
        self.assertEqual([L[:4] for L in cap], [[70, 10, 129, 14]])

    def test_a_faint_line_is_found_level_with_the_other_corners(self):
        m = paint(200, 40, (70, 10, 130, 14, "#"), (20, 20, 60, 24, "-"), (41, 21, 43, 22, "#"),
                  (140, 20, 180, 24, "#"))
        left, right, _ = imprints.credit_lines(m, 200, 1, "lowest")
        self.assertEqual([L[:4] for L in left], [[20, 20, 60, 24]])
        self.assertEqual([L[:4] for L in right], [[140, 20, 180, 24]])

    def test_a_line_found_takes_in_its_faint_ends(self):
        m = paint(200, 40, (70, 10, 130, 14, "#"), (24, 20, 60, 24, "#"), (12, 20, 24, 24, "-"),
                  (60, 20, 72, 24, "-"), (140, 20, 180, 24, "#"))
        left, _, _ = imprints.credit_lines(m, 200, 1, "lowest")
        self.assertEqual([L[:4] for L in left], [[12, 20, 71, 24]])

    def test_a_faint_line_is_not_taken_from_art_cut_by_the_band(self):
        art = (145, 2, 196, 18, "#")        # art down to row 18 in the right corner, which has no line
        m = paint(200, 40, (70, 4, 130, 8, "#"), (20, 20, 60, 24, "#"), art)
        self.assertEqual(imprints.credit_lines(m, 200, 1, "lowest")[1], [])

    def test_a_line_takes_in_faint_ink_only_up_to_a_credit_line_s_size(self):
        m = paint(1000, 40, (450, 10, 550, 14, "#"), (24, 30, 60, 34, "#"), (12, 30, 24, 34, "-"),
                  (60, 30, 480, 34, "-"), (940, 30, 980, 34, "#"))     # faint ink along the foot, 420 long
        left, _, _ = imprints.credit_lines(m, 1000, 1, "lowest")
        self.assertEqual([L[:4] for L in left], [[24, 30, 59, 34]])

    def test_faint_ink_without_a_trace_of_dark_is_shadow_or_pencil(self):
        m = paint(200, 40, (70, 10, 130, 14, "#"), (20, 20, 60, 24, "-"), (140, 20, 180, 24, "#"))
        self.assertEqual(imprints.credit_lines(m, 200, 1, "lowest")[0], [])

    def test_lines_on_a_ragged_page_edge_at_the_foot_are_found_above_it(self):
        """The edge is the last ink; rows below it are blank (shade blanks a solid foot)."""
        edge = bytes(SHADE["-" if x % 4 else "#"] for x in range(1000)) * 3
        m = paint(1000, 37, (20, 30, 60, 37, "#"), (940, 30, 980, 37, "#")) + edge + bytes(2000)
        left, right, _ = imprints.credit_lines(m, 1000, 1, "lowest")
        self.assertEqual([L[:4] for L in left], [[20, 30, 60, 37]])
        self.assertEqual([L[:4] for L in right], [[940, 30, 980, 37]])

    def test_lines_touching_specks_along_the_foot_are_found_without_them(self):
        m = bytearray(paint(1000, 40, (20, 32, 80, 37, "#"), (920, 32, 980, 37, "#")))
        for x in range(0, 1000, 15):                    # specks along the page's edge, joining the lines
            for y in (36, 37):
                m[y * 1000 + x] = SHADE["#"]
        left, right, _ = imprints.credit_lines(bytes(m), 1000, 1, "lowest")
        self.assertEqual([(L[0], L[1], L[2]) for L in left], [(20, 32, 79)])
        self.assertEqual([(L[0], L[1], L[2]) for L in right], [(920, 32, 979)])

    def test_level_with_the_other_corner_a_line_may_sit_close_under_the_art(self):
        m = paint(200, 40, (70, 4, 130, 8, "#"), (20, 20, 60, 24, "#"), (140, 20, 180, 24, "#"),
                  (140, 1, 181, 17, "#"))           # art ending 3 units above the right line
        left, right, _ = imprints.credit_lines(m, 200, 1, "lowest")
        self.assertEqual([L[:4] for L in right], [[140, 20, 180, 24]])

    def test_a_level_pair_just_above_the_caption_is_taken_one_alone_is_not(self):
        pair = paint(200, 40, (70, 30, 130, 34, "#"), (20, 20, 60, 24, "#"), (140, 20, 180, 24, "#"))
        left, right, _ = imprints.credit_lines(pair, 200, 1, "lowest")
        self.assertEqual(([L[:4] for L in left], [L[:4] for L in right]), ([[20, 20, 60, 24]], [[140, 20, 180, 24]]))
        alone = paint(200, 40, (70, 30, 130, 34, "#"), (20, 20, 60, 24, "#"))
        self.assertEqual(imprints.credit_lines(alone, 200, 1, "lowest")[:2], ([], []))
        lopsided = paint(200, 40, (70, 30, 130, 34, "#"), (20, 20, 60, 24, "#"), (120, 20, 150, 24, "#"))
        self.assertEqual(imprints.credit_lines(lopsided, 200, 1, "lowest")[:2], ([], []))

    def test_nothing_is_found_where_there_is_nothing(self):
        m = paint(200, 40, (70, 10, 130, 14, "#"))
        self.assertEqual(imprints.credit_lines(m, 200, 1, "lowest")[:2], ([], []))


class Boxes(unittest.TestCase):
    def test_a_box_is_the_lines_at_full_size_with_a_margin_wider_at_the_ends(self):
        self.assertEqual(imprints.box([line(100, 50, 300, 60), line(110, 62, 290, 70)], 2.0, 1000),
                         [176, 2088, 624, 2152])

    def test_a_wide_box_is_scaled_no_smaller_than_three_quarters_then_cut_at_its_inner_end(self):
        self.assertEqual(imprints.fit([0, 0, 1900, 100], "left"), ([0, 0, 1900, 100], 1.0))
        self.assertEqual(imprints.fit([0, 0, 2400, 100], "left"), ([0, 0, 2400, 100], 1900 / 2400))
        self.assertEqual(imprints.fit([100, 0, 3100, 100], "left"), ([100, 0, 2633, 100], 0.75))
        self.assertEqual(imprints.fit([100, 0, 3100, 100], "right"), ([567, 0, 3100, 100], 0.75))
        self.assertEqual(imprints.fit([0, 0, 500, 1000], "left"), ([0, 200, 500, 1000], 0.75))

    def test_no_line_found_a_strip_level_with_the_other_corner_mirrored(self):
        self.assertEqual(imprints.strip("left", 5000, 3500, other=[3800, 3300, 4200, 3340]),
                         [550, 3100, 2450, 3500])
        self.assertEqual(imprints.strip("right", 5000, 3500, other=[800, 3300, 1500, 3340]),
                         [2550, 3100, 4450, 3500])

    def test_the_strip_is_mirrored_across_the_caption_not_the_sheet(self):
        self.assertEqual(imprints.strip("right", 3600, 5500, other=[1000, 4900, 1600, 4940], centre=1900),
                         [1900, 4720, 2980, 5120])

    def test_no_line_found_on_either_side_a_strip_below_the_caption_or_at_the_foot(self):
        self.assertEqual(imprints.strip("left", 3600, 5500, level=(5000, 5040)), [360, 5000, 1800, 5400])
        self.assertEqual(imprints.strip("right", 3600, 5500), [1800, 5100, 3240, 5500])


class Sheets(unittest.TestCase):
    def test_blocks_fill_a_sheet_until_the_next_would_make_it_too_tall(self):
        self.assertEqual(imprints.pack([900, 900, 300, 1500, 100]), [[0, 1], [2, 3, 4]])
        self.assertEqual(imprints.pack([2500, 10]), [[0], [1]])

    def test_never_more_than_twelve_blocks_to_a_sheet(self):
        self.assertEqual([len(s) for s in imprints.pack([10] * 13)], [12, 1])

    def test_crops_side_by_side_if_they_fit_else_one_above_the_other(self):
        self.assertEqual(imprints.layout((900, 60), (800, 50)), (True, 34 + 60 + 16))
        self.assertEqual(imprints.layout((1300, 60), (800, 50)), (False, 34 + 60 + 10 + 50 + 16))


class Check(unittest.TestCase):
    def test_a_line_that_fits_is_one_segment(self):
        self.assertEqual(imprints.segments(1388, 1388), [(0, 1388)])
        self.assertEqual(imprints.segments(300, 1388), [(0, 300)])

    def test_a_long_line_is_cut_into_the_fewest_equal_segments_overlapping_by_120(self):
        self.assertEqual(imprints.OVERLAP, 120)
        self.assertEqual(imprints.segments(2400, 1388), [(0, 1260), (1140, 2400)])
        segs = imprints.segments(7600, 1388)
        self.assertEqual(len(segs), 6)
        self.assertEqual((segs[0][0], segs[-1][1]), (0, 7600))
        for (a, b), (c, d) in zip(segs, segs[1:]):
            self.assertEqual(b - c, 120)
        self.assertTrue(all(b - a <= 1388 for a, b in segs))
        self.assertEqual(len(imprints.segments(1389, 1388)), 2)

    def test_tiles_go_band_by_band_left_to_right(self):
        self.assertEqual(imprints.tiles((2400, 320), 1388, 667), [[0, 0, 1260, 320], [1140, 0, 2400, 320]])
        self.assertEqual(imprints.tiles((2400, 1600), 1388, 667), [
            [0, 0, 1260, 613], [1140, 0, 2400, 613],
            [0, 493, 1260, 1107], [1140, 493, 2400, 1107],
            [0, 987, 1260, 1600], [1140, 987, 2400, 1600]])

    @staticmethod
    def tall(blocks, page):
        return 2 * imprints.PAD + sum(blocks[b][0] + sum(imprints.LABEL + blocks[b][1][i] + imprints.GAP for i in parts)
                                      for b, parts in page)

    def test_an_image_takes_whole_blocks_while_they_fit(self):
        # 1400 x 1,100,000 is 785 rows, 773 inside the margins; a part takes 26 + h + 10
        blocks = [(40, [100]), (40, [100, 100]), (40, [300]), (40, [100])]   # 176, 312, 376, 176
        self.assertEqual(imprints.check_layout(blocks), [[(0, [0]), (1, [0, 1])], [(2, [0]), (3, [0])]])
        self.assertEqual(imprints.check_layout([(40, [100]), (40, [697])]), [[(0, [0])], [(1, [0])]])
        self.assertEqual(self.tall([(40, [697])], [(0, [0])]), 785)

    def test_a_block_too_tall_for_any_image_goes_onto_images_of_its_own(self):
        blocks = [(40, [100]), (70, [300, 300, 300, 300]), (40, [100]), (40, [100])]   # 70 + 4 x 336
        self.assertEqual(imprints.check_layout(blocks),
                         [[(0, [0])], [(1, [0, 1])], [(1, [2, 3])], [(2, [0]), (3, [0])]])
        self.assertEqual(imprints.check_layout([(40, [698])]), [[(0, [0])]])   # 774 rows: alone, all the same

    def test_no_image_is_over_the_limit(self):
        blocks = [(40, [100]), (70, [600] * 3), (40, [50] * 30), (100, [320, 320]), (40, [10])] * 3
        pages = imprints.check_layout(blocks)
        for page in pages:
            self.assertLessEqual(1400 * self.tall(blocks, page), 1_100_000)
        seen = [(b, i) for page in pages for b, parts in page for i in parts]
        self.assertEqual(seen, [(b, i) for b, (_, parts) in enumerate(blocks) for i in range(len(parts))])

    def test_text_wraps_at_spaces(self):
        self.assertEqual(imprints.wrap("aa bb cc", lambda s: len(s) <= 5), ["aa bb", "cc"])
        self.assertEqual(imprints.wrap("aaaaaaa b", lambda s: len(s) <= 5), ["aaaaaaa", "b"])


class Normalise(unittest.TestCase):
    def test_a_space_after_each_stop_and_comma_and_around_ampersand(self):
        self.assertEqual(imprints.normalise("J.Gould & H.C.Richter, del et lith. | Walter,Imp."),
                         "J. Gould & H. C. Richter, del et lith. | Walter, Imp.")
        self.assertEqual(imprints.normalise("Drawn from Nature& on Stone by J &E. Gould."),
                         "Drawn from Nature & on Stone by J. & E. Gould.")
        self.assertEqual(imprints.normalise("J.&E. Gould del et lith."), "J. & E. Gould del et lith.")
        self.assertEqual(imprints.normalise("J.J. Audubon F.R.S. F.L.S."), "J. J. Audubon F. R. S. F. L. S.")

    def test_and_run_into_a_capital_is_split_off(self):
        self.assertEqual(imprints.normalise("J.GouldandH.C.Richter del."), "J. Gould and H. C. Richter del.")
        self.assertEqual(imprints.normalise("J.Gould,andH.C.Richter"), "J. Gould, and H. C. Richter")
        self.assertEqual(imprints.normalise("Hullmandel and Walton Imp."), "Hullmandel and Walton Imp.")

    def test_no_space_before_a_mark_and_none_at_a_line_s_end(self):
        self.assertEqual(imprints.normalise("Drawn by J & E. Gould . |  Printed by C. Hullmandel. "),
                         "Drawn by J. & E. Gould. | Printed by C. Hullmandel.")
        self.assertEqual(imprints.normalise("E. Lear del: et lith:"), "E. Lear del. et lith.")   # Ruling 25
        self.assertEqual(imprints.normalise("del.,et"), "del., et")
        self.assertEqual(imprints.normalise("J & .E. Gould"), "J &. E. Gould")   # a mark keeps to what precedes it

    def test_words_of_a_wording_run_together_take_a_space(self):
        for line, spaced in (("Drawnfrom Nature & onStoneby J. & E. Gould", "Drawn from Nature & on Stone by J. & E. Gould"),
                             ("Drawnfromnature & on stone by", "Drawn from nature & on stone by"),
                             ("J. Gould and H. CRichter delet lith", "J. Gould and H. C. Richter del et lith"),
                             ("E. Lear deletlith.", "E. Lear del et lith."),
                             ("Engravedby R. Havell", "Engraved by R. Havell"),
                             ("Drawn on Stone fromaDrawing by Edwd. Lear", "Drawn on Stone from a Drawing by Edwd. Lear")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), spaced)

    def test_by_run_into_a_capital_takes_a_space(self):
        self.assertEqual(imprints.normalise("Drawn on Stone byJ. Gould"), "Drawn on Stone by J. Gould")
        self.assertEqual(imprints.normalise("Drawn on StonebyE. Lear"), "Drawn on Stone by E. Lear")
        self.assertEqual(imprints.normalise("Printed by C.Hullmandel"), "Printed by C. Hullmandel")

    def test_only_words_of_a_wording_are_split(self):
        self.assertEqual(imprints.wording_pairs(["Drawn on Stone by", "del. et lith."]),
                         {("drawn", "on"), ("on", "stone"), ("stone", "by"), ("del", "et"), ("et", "lith")})
        for run in ("Hullmandel", "Walter", "WalterImp", "Drawnby", "nearby", "Byron", "Stone", "HCRichter"):
            with self.subTest(run=run):
                self.assertEqual(imprints.run_apart(run), run)

    def test_every_initial_is_written_with_a_stop_and_a_space(self):
        for line, written in (("J Wolf & HCRichter, del et lith.", "J. Wolf & H. C. Richter, del et lith."),
                              ("H.CRichter", "H. C. Richter"),
                              ("J & E Gould", "J. & E. Gould"),
                              ("W.H.Lizars Edinr.", "W. H. Lizars Edinr."),
                              ("J.J. Audubon F. R. S. F. L. S.", "J. J. Audubon F. R. S. F. L. S."),
                              ("I & E. Gould", "I. & E. Gould"),
                              ("C C. Hullmandel", "C. C. Hullmandel"),
                              ("J. Gould & HC. Richter, del et lith.", "J. Gould & H. C. Richter, del et lith."),
                              ("JGould andHCRichter: del. et lith.", "J. Gould and H. C. Richter: del. et lith."),
                              ("J.Wolf & WHart,del et lith.", "J. Wolf & W. Hart, del et lith."),
                              ("Drawn on Stone by ELear", "Drawn on Stone by E. Lear"),
                              ("E Lear del et lithog", "E. Lear del et lithog"),
                              ("Printed by C Hullmandel", "Printed by C. Hullmandel")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), written)

    def test_a_comma_or_colon_directly_after_an_initial_is_a_stop(self):
        for line, written in (("J, Gould", "J. Gould"),
                              ("H. C, Richter", "H. C. Richter"),
                              ("J: Gould", "J. Gould"),
                              ("C: Hullmandel", "C. Hullmandel"),
                              ("J,Gould and H.C,Richter del et lith.", "J. Gould and H. C. Richter del et lith."),
                              ("J, Gould and H. C, Richter del et lith. | Hullmandel & Walton Imp.",
                               "J. Gould and H. C. Richter del et lith. | Hullmandel & Walton Imp."),
                              ("J & E. Gould del: | C: Hullmandel Imp:", "J. & E. Gould del. | C. Hullmandel Imp."),
                              ("J, & E, Gould", "J. & E. Gould"),
                              ("Drawn on Stone by E: Lear", "Drawn on Stone by E. Lear")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), written)

    def test_a_comma_after_a_name_is_left(self):
        for line in ("J. Gould and H. C. Richter, del et lith.", "H. C. Richter, del.", "Walter, Imp.",
                     "J. Gould, and H. C. Richter", "J. Gould, E, del."):   # an initial with nothing after it to join
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), line)

    def test_the_mark_after_an_abbreviation_is_a_stop(self):
        for line, written in (("J. Gould and H. C. Richter delt,", "J. Gould and H. C. Richter delt."),
                              ("C. Hullmandel Impt,", "C. Hullmandel Impt."),
                              ("C. Hullmandel Imp,", "C. Hullmandel Imp."),
                              ("Walter, Imp:", "Walter, Imp."),
                              ("J. & E. Gould del: et lith:", "J. & E. Gould del. et lith."),
                              ("J. Gould and H. C. Richter, del; et lithog:", "J. Gould and H. C. Richter, del. et lithog."),
                              ("J. Gould and H. C. Richter delt, et lith, | Hullmandel & Walton Imp:",
                               "J. Gould and H. C. Richter delt. et lith. | Hullmandel & Walton Imp."),
                              ("J. Gould and H. C. Richter DEL: et LITH:", "J. Gould and H. C. Richter DEL. et LITH."),
                              ("Drawn on Stone by I & E. Gould from a Drawing by Edwd, Lear.",
                               "Drawn on Stone by I. & E. Gould from a Drawing by Edwd. Lear."),
                              ("W.H.Lizars Edinr, | Retouched by R. Havell Junr:", "W. H. Lizars Edinr. | Retouched by R. Havell Junr."),
                              ("del :et lith ;", "del. et lith.")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), written)

    def test_a_mark_that_is_not_there_stays_absent_and_other_marks_stay(self):
        for line in ("del et lith", "J. Gould and H. C. Richter del | C. Hullmandel Imp",
                     "J. Gould and H. C. Richter, del et lith.", "H. C. Richter, del.", "Walter, Imp.",
                     "J. Gould and H. C. Richter del., et lith.", "J. Gould and H. C. Richter del. et lith.",
                     "Imperial", "Delta, Junrock", "J. Gould, and H. C. Richter"):   # only whole abbreviations count
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), line)

    def test_an_all_capitals_word_is_not_split_into_initials(self):
        for line in ("LONDON Published", "PLATE Drawn", "LONDON. Published", "PLATE. Drawn by J. Gould",
                     "PUBLISHED & Printed", "LONDON and Paris"):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), line)
        for line, written in (("HC Richter", "H. C. Richter"), ("J.J. Audubon FRS.", "J. J. Audubon F. R. S."),
                              ("W. H. Lizars FRS. Edinr.", "W. H. Lizars F. R. S. Edinr."), ("HCRichter", "H. C. Richter"),
                              ("WHF Smith", "W. H. F. Smith")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), written)

    def test_a_stop_after_a_run_of_capitals_is_kept(self):
        for line, written in (("by HC.", "by H. C."), ("J.J. Audubon FRS.", "J. J. Audubon F. R. S."),
                              ("FRS. FLS.", "F. R. S. F. L. S."), ("HC. del et lith.", "H. C. del et lith."),
                              ("J.J. Audubon FRS. del", "J. J. Audubon F. R. S. del")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), written)

    def test_capitals_run_together_before_a_name_are_initials(self):
        for line, written in (("J. Gould and HC Richter del et lith.", "J. Gould and H. C. Richter del et lith."),
                              ("J. Gould & HC Richter, del et lith.", "J. Gould & H. C. Richter, del et lith."),
                              ("WH Lizars Edinr.", "W. H. Lizars Edinr."),
                              ("J. Gould and HC & E. Gould", "J. Gould and H. C. & E. Gould")):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), written)
        for line in ("Plate IV Fig. 2", "CC Hullmandel Imp.", "HC del et lith", "Plate XII Richter"):   # numerals; lowercase after
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), line)

    def test_a_roman_numeral_and_the_article_a_are_not_initials(self):
        for line in ("Plate IV.", "Plate IV. fig. 2", "Plate XII. del", "from A Drawing by E. Lear", "A Drawing"):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), line)
        self.assertEqual(imprints.normalise("A Smith del."), "A. Smith del.")   # before a name, A is an initial

    def test_capitals_beginning_words_and_lowercase_abbreviations_are_untouched(self):
        for line in ("Drawn from life and on stone by", "Walter & Cohn, Imp", "Hullmandel & Walton Imp.",
                     "Engraved, Printed & Coloured by R. Havell Junr.", "J. Gould del et lith", "del et lith"):
            with self.subTest(line=line):
                self.assertEqual(imprints.normalise(line), line)
        self.assertEqual(imprints.initials("Richter Imp. Drawn"), "Richter Imp. Drawn")
        self.assertEqual(imprints.initials("J"), "J")   # a capital with nothing after it is not taken for an initial

    def test_normalising_twice_changes_nothing(self):
        for line in ("J.Gould &H.C.Richter,del et lith | Walter,Imp.", "J.J. Audubon F.R.S. F.L.S.", "J & .E. Gould",
                     "J Wolf & HCRichter, del et lith.", "C C. Hullmandel", "J, Gould and H. C, Richter del:",
                     "C: Hullmandel Imp:", "J. Gould and HC Richter del"):
            with self.subTest(line=line):
                once = imprints.normalise(line)
                self.assertEqual(imprints.normalise(once), once)


class Record(unittest.TestCase):
    def test_a_rerun_keeps_read_and_note_only_once_a_reading_was_applied(self):
        self.assertEqual(imprints.carried({"read": "eye", "note": "faint"}), {"read": "eye", "note": "faint"})
        self.assertEqual(imprints.carried({"read": "", "note": "no credit line found in the left corner"}),
                         {"read": "", "note": ""})
        self.assertEqual(imprints.carried({}), {"read": "", "note": ""})

    def test_draft_joins_left_then_right(self):
        self.assertEqual(imprints.draft_text([{"text": "a"}], [{"text": "b"}, {"text": " c "}]), "a | b | c")


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

    def test_a_note_about_a_credit_line_goes_into_plates_csv_once(self):
        readings = [{"plate": "37", "imprint": "Printed by C. Hullmandel", "read": "scan",
                     "note": "left credit line cut off at the sheet's foot"},
                    {"plate": "38", "imprint": "Drawn on Stone by E. Lear", "read": "eye", "note": "stop after Lear faint"}]
        imprints.apply(self.d, readings)
        imprints.apply(self.d, readings)
        plates = read_csv(self.d / "plates.csv")
        self.assertEqual([p["notes"] for p in plates], ["left credit line cut off at the sheet's foot", "an older note"])
        self.assertEqual([r["note"] for r in read_csv(self.d / "sources" / "imprints.csv")],
                         ["left credit line cut off at the sheet's foot", "stop after Lear faint"])

    def test_only_the_parts_of_a_note_about_a_credit_line_go_into_plates_csv(self):
        readings = [{"plate": "37", "imprint": "Printed by C. Hullmandel", "read": "scan",
                     "note": "left credit line cut off at the sheet's foot; no separate stop after C visible"}]
        imprints.apply(self.d, readings)
        imprints.apply(self.d, readings)
        self.assertEqual(read_csv(self.d / "plates.csv")[0]["notes"], "left credit line cut off at the sheet's foot")
        self.assertEqual(read_csv(self.d / "sources" / "imprints.csv")[0]["note"],
                         "left credit line cut off at the sheet's foot; no separate stop after C visible")

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
