"""Tests for the plate explorer's tools: site_data.py, site_images.py and site_check.py.

    python3 tools/test_site.py

The data tests build from the real tables. The tests that cut images need Pillow and are skipped
without it.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import misnamed  # noqa: E402
import site_check  # noqa: E402
import site_data  # noqa: E402
import site_images  # noqa: E402  (imports without Pillow: only cutting needs it)

try:
    from PIL import Image, ImageDraw
except ImportError:  # Pillow is needed only to cut the images
    Image = None

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

    def test_every_plate_in_a_release_has_its_images(self) -> None:
        unreleased = [f"{folio['id']}/{slug}" for folio, row, _, slug in site_data.plate_rows() if not row["crop_asset"]]
        self.assertEqual([p["id"] for p in DATA["plates"] if not p["image"]], unreleased)
        p = PLATE["havell/121"]["image"]
        self.assertEqual(max(p["thumb"]), 480)
        self.assertIsNone(p["hue"])  # a white owl

    def test_a_plate_credited_apart_from_its_folio(self) -> None:
        p = PLATE["havell/165"]
        self.assertEqual(p["credit"], "University of Pittsburgh, via Wikimedia Commons.")
        self.assertTrue(p["original"].endswith("/havell-v2/sheet-165.jpg"), p["original"])
        self.assertEqual(PLATE["havell/121"]["credit"], "")
        self.assertLessEqual({f"{folio}/{key}" for folio, key in site_data.CREDITS}, set(PLATE))

    def test_every_plate_credits_what_credits_csv_says(self) -> None:
        table = {f["id"]: site_data.read(site_data.ROOT / f["id"] / "credits.csv") for f in site_data.FOLIOS}
        for folio, row, _, slug in site_data.plate_rows():
            p = PLATE[f"{folio['id']}/{slug}"]
            want = {(r["name"], r["role"]) for r in table[folio["id"]]
                    if r["plate"] == row["plate"] and r.get("volume", row.get("volume")) == row.get("volume")}
            got = {(c["name"], role) for c in p["credits"] for role in c["roles"]}
            self.assertEqual(got, want, p["id"])
            self.assertEqual(p["imprint"], row["imprint"], p["id"])
            self.assertEqual(bool(p["imprint_note"]), not row["imprint"], p["id"])

    def test_a_plate_drawn_by_lear(self) -> None:
        p = PLATE["gould-europe/3"]
        self.assertEqual(p["imprint"], "E. Lear del et lithog. | Printed by C. Hullmandel.")
        self.assertEqual(p["credits"], [
            {"name": "Edward Lear", "slug": "edward-lear", "roles": ["drew", "lithographed"]},
            {"name": "Charles Joseph Hullmandel", "slug": "charles-joseph-hullmandel", "roles": ["printed"]},
        ])
        self.assertEqual(p["imprint_note"], "")

    def test_roles_in_credits_py_order(self) -> None:
        self.assertEqual([(c["name"], c["roles"]) for c in PLATE["havell/1"]["credits"]], [
            ("John James Audubon", ["drew"]), ("William Home Lizars", ["engraved"]), ("Robert Havell Jr.", ["retouched"]),
        ])

    def test_a_plate_with_no_credit_line_says_why(self) -> None:
        p = PLATE["gould-europe/247"]
        self.assertEqual((p["imprint"], p["credits"]), ("", []))
        self.assertEqual(p["imprint_note"], "credit lines cut off: the sheet ends in the caption")

    def test_every_artist_once_with_their_plates(self) -> None:
        listed = [r["name"] for r in site_data.read(site_data.ROOT / "artists.csv")]
        self.assertEqual([a["name"] for a in DATA["artists"]], listed)
        slugs = [a["slug"] for a in DATA["artists"]]
        self.assertEqual(len(slugs), len(set(slugs)))
        for a in DATA["artists"]:
            self.assertTrue(a["plates"], a["name"])
            self.assertEqual(a["plates"], [p["id"] for p in DATA["plates"] if any(c["name"] == a["name"] for c in p["credits"])])
            self.assertEqual(a["folios"], list(dict.fromkeys(PLATE[pid]["folio"] for pid in a["plates"])))

    def test_an_artist(self) -> None:
        lear = next(a for a in DATA["artists"] if a["name"] == "Edward Lear")
        self.assertEqual((lear["slug"], lear["kind"], lear["wikidata"]), ("edward-lear", "person", "Q309759"))
        self.assertEqual(lear["roles"], {"drew": 54, "lithographed": 52})
        self.assertEqual(lear["folios"], ["gould-europe", "gould-australia"])
        firm = next(a for a in DATA["artists"] if a["name"] == "Hullmandel & Walton")
        self.assertEqual((firm["slug"], firm["kind"]), ("hullmandel-walton", "firm"))


@unittest.skipUnless(Image, "needs Pillow")
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
                    entry = site_images.make(folio, {"crop_asset": "x", "sheet_asset": "y"}, slug, None)
                    # Verify sizes match
                    self.assertEqual(entry["thumb"], [480, 360])
                    self.assertEqual(entry["crop"], [1600, 1200])
                    self.assertEqual(entry["sheet"], [1000, 750])
                    # Verify it detected the red colour
                    self.assertTrue(entry["hue"] is not None and (entry["hue"] < 10 or entry["hue"] > 350), entry)

    def test_a_plate_already_cut_keeps_its_entry(self) -> None:
        known = {"thumb": [1, 2], "crop": [3, 4], "sheet": [5, 6], "colour": "#123456", "hue": 210, "light": 0.2}
        with tempfile.TemporaryDirectory() as tmpdir:
            folio = site_data.FOLIOS[0]
            (Path(tmpdir) / folio["id"]).mkdir()
            for cut_name in site_images.CUTS:
                Image.new("RGB", (8, 8), (200, 30, 40)).save(Path(tmpdir) / folio["id"] / f"1-{cut_name}.webp", "WEBP")
            with unittest.mock.patch.object(site_images, "OUT", Path(tmpdir)), \
                 unittest.mock.patch.object(site_images, "asset", side_effect=AssertionError("downloaded")):
                self.assertEqual(site_images.make(folio, {"crop_asset": "x", "sheet_asset": "y"}, "1", dict(known)),
                                 known)


class Fetch(unittest.TestCase):
    def test_site_images_imports_without_pillow(self) -> None:
        code = "import sys; sys.modules['PIL'] = None; import site_images; print(site_images.Image)"
        out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parent,
                             capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "None")

    def test_build_without_pillow_says_so(self) -> None:
        err = io.StringIO()
        with unittest.mock.patch.object(site_images, "Image", None), contextlib.redirect_stderr(err):
            self.assertEqual(site_images.build(), 1)
        self.assertIn("needs Pillow", err.getvalue())

    def test_a_short_download_is_retried_then_kept_out(self) -> None:
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


class Check(unittest.TestCase):
    SM = "http://www.sitemaps.org/schemas/sitemap/0.9"
    URL = "https://wr.github.io/historical-bird-plates/"

    def setUp(self) -> None:
        self.dist = Path(tempfile.mkdtemp())
        (self.dist / "sitemap-index.xml").write_text(
            f'<sitemapindex xmlns="{self.SM}"><sitemap><loc>{self.URL}sitemap-0.xml</loc></sitemap></sitemapindex>')
        (self.dist / "sitemap-0.xml").write_text(
            f'<urlset xmlns="{self.SM}"><url><loc>{self.URL}</loc></url><url><loc>{self.URL}havell/1/</loc></url></urlset>')
        (self.dist / "img" / "havell").mkdir(parents=True)
        (self.dist / "img" / "havell" / "1-thumb.webp").write_bytes(b"")

    def page(self, path: str, body: str = "", head: str = "") -> None:
        file = self.dist / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            f'<html><head><title>T</title><meta name="description" content="D">'
            f'<meta property="og:image" content="{self.URL}img/havell/1-thumb.webp">'
            f'<link rel="canonical" href="{self.URL}{path.removesuffix("index.html")}">{head}</head>'
            f"<body>{body}</body></html>")

    def test_a_good_site_passes(self) -> None:
        self.page("index.html",
                  '<a href="/historical-bird-plates/havell/1/">1</a><a href="#main">skip</a>'
                  '<img src="img/havell/1-thumb.webp" srcset="/historical-bird-plates/img/havell/1-thumb.webp 360w">'
                  '<a href="https://ebird.org/species/snoowl1">eBird</a>',
                  '<script type="application/ld+json">{"@type": "WebSite"}</script>')
        self.page("havell/1/index.html", '<a href="../../">home</a>')
        self.assertEqual(site_check.check(self.dist), [])

    def test_problems_are_named(self) -> None:
        self.page("index.html",
                  '<a href="/historical-bird-plates/havell/2/">2</a><a href="/elsewhere/">x</a>'
                  '<img src="img/havell/9-thumb.webp">',
                  '<script type="application/ld+json">{not json}</script>')
        (self.dist / "havell" / "1").mkdir(parents=True)
        (self.dist / "havell" / "1" / "index.html").write_text("<html><head></head><body></body></html>")
        errors = site_check.check(self.dist)
        for expected in ("index.html: broken link /historical-bird-plates/havell/2/",
                         "index.html: broken link /elsewhere/",
                         "index.html: broken link img/havell/9-thumb.webp",
                         "havell/1/index.html: no <title>", "havell/1/index.html: no description",
                         "havell/1/index.html: no og:image", "havell/1/index.html: no canonical URL"):
            self.assertIn(expected, errors)
        self.assertTrue(any(e.startswith("index.html: JSON-LD does not parse") for e in errors), errors)

    def test_unlisted_pages_and_skipped_images(self) -> None:
        self.page("index.html", '<img src="img/havell/9-thumb.webp">')
        self.page("about/index.html")
        self.assertEqual(site_check.check(self.dist, images=False),
                         [f"about/index.html: {self.URL}about/ is not in the sitemap"])

    def bare(self, path: str, canonical: str, og_image: str) -> None:
        """A page whose canonical and og:image are exactly as given."""
        file = self.dist / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            f'<html><head><title>T</title><meta name="description" content="D">'
            f'<meta property="og:image" content="{og_image}">'
            f'<link rel="canonical" href="{canonical}"></head><body></body></html>')

    def test_a_canonical_pointing_elsewhere_is_reported(self) -> None:
        self.page("index.html")
        self.bare("havell/1/index.html", self.URL, f"{self.URL}img/havell/1-thumb.webp")
        self.assertEqual(site_check.check(self.dist),
                         [f"havell/1/index.html: canonical {self.URL} is not this page's URL"])

    def test_an_off_site_og_image_or_canonical_is_reported(self) -> None:
        local = "http://localhost:4321/historical-bird-plates/"
        self.bare("index.html", local, f"{self.URL}img/havell/1-thumb.webp")
        self.bare("havell/1/index.html", f"{self.URL}havell/1/", "https://example.com/x.png")
        self.assertEqual(site_check.check(self.dist),
                         ["havell/1/index.html: og:image https://example.com/x.png is not on the site",
                          f"index.html: canonical {local} is not this page's URL"])

    def test_the_404_page_needs_no_canonical(self) -> None:
        self.page("index.html")
        (self.dist / "404.html").write_text(
            f'<html><head><title>Not found</title><meta name="description" content="D">'
            f'<meta property="og:image" content="{self.URL}img/havell/1-thumb.webp"></head><body></body></html>')
        self.assertEqual(site_check.check(self.dist), [])


if __name__ == "__main__":
    unittest.main()
