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

try:
    from PIL import Image, ImageDraw
    import site_images
except ImportError:  # Pillow is needed only to make the images
    site_images = None

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


@unittest.skipUnless(site_images, "needs Pillow")
class Images(unittest.TestCase):
    def canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = Image.new("RGB", (400, 500), (255, 255, 255))
        return im, ImageDraw.Draw(im)

    def test_a_red_bird_on_white(self) -> None:
        im, draw = self.canvas()
        draw.ellipse([100, 100, 300, 400], fill=(200, 30, 40))
        c = site_images.colour(im)
        self.assertTrue(c["hue"] is not None and (c["hue"] < 10 or c["hue"] > 350), c)

    def test_cream_paper_inside_a_white_margin_is_masked(self) -> None:
        im, draw = self.canvas()
        draw.rectangle([20, 20, 380, 480], fill=(218, 204, 177))  # a Havell sheet's paper
        draw.ellipse([120, 150, 280, 350], fill=(40, 90, 170))
        c = site_images.colour(im)
        self.assertTrue(c["hue"] is not None and 200 <= c["hue"] <= 230, c)

    def test_a_grey_engraving_has_no_hue(self) -> None:
        im, draw = self.canvas()
        draw.ellipse([100, 100, 300, 400], fill=(90, 90, 92))
        c = site_images.colour(im)
        self.assertIsNone(c["hue"])
        self.assertLess(c["light"], 0.5)

    def test_cut_never_enlarges(self) -> None:
        self.assertEqual(site_images.cut(Image.new("RGB", (3000, 2000)), 480).size, (480, 320))
        self.assertEqual(site_images.cut(Image.new("RGB", (300, 200)), 480).size, (300, 200))

    def test_red_shaded_across_the_hue_wrap_beats_a_larger_green(self) -> None:
        im = Image.new("RGB", (400, 500), (255, 255, 255))
        draw = ImageDraw.Draw(im)
        draw.rectangle([50, 50, 150, 150], fill=(200, 30, 45))  # red shaded towards magenta
        draw.rectangle([150, 50, 250, 150], fill=(200, 45, 30))  # red shaded towards orange
        draw.rectangle([50, 200, 350, 300], fill=(40, 160, 60))  # larger green area
        c = site_images.colour(im)
        self.assertTrue(c["hue"] is not None and (c["hue"] < 10 or c["hue"] > 350), c)

    def test_a_plate_already_cut_is_not_cut_again(self) -> None:
        import tempfile
        import unittest.mock
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            with unittest.mock.patch.object(site_images, "OUT", tmppath):
                with unittest.mock.patch.object(site_images, "asset", side_effect=AssertionError("downloaded")):
                    # Create three webp files for a plate
                    folio = site_data.FOLIOS[0]
                    slug = "1"
                    folio_dir = tmppath / folio["id"]
                    folio_dir.mkdir(parents=True)
                    for cut_name, size in [("thumb", (480, 360)), ("crop", (1600, 1200)), ("sheet", (1000, 750))]:
                        im = Image.new("RGB", size, (255, 255, 255))
                        draw = ImageDraw.Draw(im)
                        # Draw a red ellipse
                        draw.ellipse([10, 10, size[0] - 10, size[1] - 10], fill=(200, 30, 40))
                        im.save(folio_dir / f"{slug}-{cut_name}.webp", "WEBP")
                    # Call make() - should not call asset() and should not raise
                    entry = site_images.make(folio, {"crop_asset": "x", "sheet_asset": "y"}, slug)
                    # Verify sizes match
                    self.assertEqual(entry["thumb"], [480, 360])
                    self.assertEqual(entry["crop"], [1600, 1200])
                    self.assertEqual(entry["sheet"], [1000, 750])
                    # Verify it detected the red colour
                    self.assertTrue(entry["hue"] is not None and (entry["hue"] < 10 or entry["hue"] > 350), entry)

    def test_a_short_download_is_retried_then_kept_out(self) -> None:
        import io
        import tempfile
        import unittest.mock
        import http.client
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "x.zip"

            # Create a mock response with Content-Length=10 but only 4 bytes of body
            def create_mock_response(*args, **kwargs):
                mock_response = unittest.mock.MagicMock()
                mock_response.headers.get.return_value = "10"  # Content-Length: 10
                # read() returns 4 bytes first, then empty to signal end of stream
                mock_response.read.side_effect = [b"1234", b""]
                mock_response.__enter__.return_value = mock_response
                mock_response.__exit__.return_value = None
                return mock_response

            urlopen_mock = unittest.mock.MagicMock(side_effect=create_mock_response)
            sleep_mock = unittest.mock.MagicMock()

            with unittest.mock.patch("site_images.urllib.request.urlopen", urlopen_mock):
                with unittest.mock.patch("site_images.time.sleep", sleep_mock):
                    # Call download() - should raise IncompleteRead after 3 attempts
                    with self.assertRaises(http.client.IncompleteRead):
                        site_images.download("https://example.invalid/x.zip", zip_path)

            # Verify urlopen was called 3 times (3 retries)
            self.assertEqual(urlopen_mock.call_count, 3)

            # Verify neither x.zip nor x.zip.part exist
            self.assertFalse(zip_path.exists())
            self.assertFalse((tmppath / "x.zip.part").exists())


if __name__ == "__main__":
    unittest.main()
