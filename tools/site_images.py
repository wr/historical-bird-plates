"""Make the plate explorer's images: three WebP cuts of every plate, and the plate's colour.

    python3 tools/site_images.py build   # cut every plate into site/public/img/, then write
                                         # site/src/data/images.json and .cache/site-images.tar
    python3 tools/site_images.py fetch   # unpack the published tarball into site/public/img/

Each plate's crop and sheet come from its folio's image release; Australia's and Asia's crops come
from crops.zip, downloaded once into .cache/. A plate whose three WebPs are already in
site/public/img/ is not cut again and keeps its entry in images.json, so a stopped build resumes and
an unchanged plate's colour never drifts. Resuming goes by the files being there, not by what they
were cut from: when a new folio release changes a file under the same name, delete that plate's three
WebPs before rebuilding.

build needs Pillow with WebP; fetch needs only the standard library. CI never runs this: the site's
build reads only images.json.
"""
from __future__ import annotations

import colorsys
import http.client
import io
import json
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None  # full sheets run to tens of megapixels, from our own releases: no bomb guard
except ImportError:  # fetch needs no Pillow; build says so if it's missing
    Image = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_data  # noqa: E402

CACHE = site_data.ROOT / ".cache"
PUBLIC = site_data.ROOT / "site" / "public"
OUT = PUBLIC / "img"
TAR = CACHE / "site-images.tar"
IMAGES = site_data.DATA / "images.json"
RELEASE = "site-images-v1"
CUTS = {"thumb": (480, 70), "crop": (1600, 70), "sheet": (1000, 65)}  # long edge in px, WebP quality
BUDGET = 850_000_000  # GitHub Pages publishes at most 1 GB
ZIPPED = {"gould-australia", "gould-asia"}
UA = {"User-Agent": "historical-bird-plates site_images (+https://github.com/wr/historical-bird-plates)"}


def colour(im: Image.Image) -> dict:
    """The plate's colour, as {"colour": "#rrggbb", "hue": degrees or None, "light": 0-1}.

    The paper is masked first: the border's median tone (the crops' white margin) and the two
    commonest tones that are light and nearly grey (a sheet's own paper, where it shows). Of the
    rest, pixels with real chroma vote for one of 24 hue bins, weighted by chroma squared so a
    vivid patch outvotes a wash; the winning bin's weighted mean is the colour. Under 3% of pixels
    voting means an engraved grey or a white bird: hue None, and the mean of the non-paper pixels,
    so the colour arrangement can sort it by lightness.
    """
    small = im.convert("RGB")
    small.thumbnail((160, 160))
    w, h = small.size
    px = small.load()
    pixels = [px[x, y] for y in range(h) for x in range(w)]
    border = [px[x, y] for x in range(w) for y in (0, h - 1)] + [px[x, y] for y in range(h) for x in (0, w - 1)]
    paper = [tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))]
    for q, _ in Counter((r >> 4, g >> 4, b >> 4) for r, g, b in pixels).most_common(2):
        tone = tuple(v * 16 + 8 for v in q)
        if max(tone) > 0.6 * 255 and max(tone) - min(tone) < 0.25 * 255:
            paper.append(tone)
    ink: list[tuple[int, int, int]] = []
    votes = [[0.0, 0.0, 0.0, 0.0] for _ in range(24)]
    voters = 0
    for r, g, b in pixels:
        if any(max(abs(r - t[0]), abs(g - t[1]), abs(b - t[2])) < 30 for t in paper):
            continue
        ink.append((r, g, b))
        chroma = (max(r, g, b) - min(r, g, b)) / 255
        if chroma < 0.12:
            continue
        voters += 1
        k = int(colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 24) % 24
        weight = chroma * chroma
        votes[k][0] += weight
        votes[k][1] += r * weight
        votes[k][2] += g * weight
        votes[k][3] += b * weight
    if voters < 0.03 * len(pixels):
        pool = ink or paper[:1]
        rgb = tuple(round(sum(c[i] for c in pool) / len(pool)) for i in range(3))
        hue = None
    else:
        # Choose winning bin by circular sum: bin k-1, k, k+1 modulo 24
        best_k = max(range(24), key=lambda k: votes[k][0] + votes[(k - 1) % 24][0] + votes[(k + 1) % 24][0])
        # Colour is weighted RGB mean over the three bins
        w = votes[best_k][0] + votes[(best_k - 1) % 24][0] + votes[(best_k + 1) % 24][0]
        rgb = tuple(round((votes[best_k][i] + votes[(best_k - 1) % 24][i] + votes[(best_k + 1) % 24][i]) / w) for i in (1, 2, 3))
        hue = round(colorsys.rgb_to_hls(*(v / 255 for v in rgb))[0] * 360) % 360
    light = colorsys.rgb_to_hls(*(v / 255 for v in rgb))[1]
    return {"colour": "#%02x%02x%02x" % rgb, "hue": hue, "light": round(light, 3)}


def cut(im: Image.Image, long_edge: int) -> Image.Image:
    """A copy no longer than long_edge on its long side; never enlarged."""
    out = im.convert("RGB")
    out.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
    return out


def _with_retry(fn):
    """Execute function with retries for transient errors; raise on persistent failure."""
    sleeps = [5, 15]
    for attempt in range(3):
        try:
            return fn()
        except (urllib.error.URLError, http.client.IncompleteRead, TimeoutError, ConnectionError):
            if attempt < 2:
                time.sleep(sleeps[attempt])
            else:
                raise


def download(url: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")

    def download_with_stream():
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
            content_length = r.headers.get("Content-Length")
            bytes_written = 0
            with open(part, "wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)  # 1 MiB chunks
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)
            if content_length is not None and bytes_written != int(content_length):
                part.unlink()
                raise http.client.IncompleteRead(bytes_written, int(content_length))

    _with_retry(download_with_stream)
    part.replace(path)
    return path


def crops_zip(folio: dict) -> Path:
    path = CACHE / "releases" / folio["release"] / "crops.zip"
    if not path.exists():
        download(f"{site_data.REPO}/releases/download/{folio['release']}/crops.zip", path)
    return path


def asset(folio: dict, name: str) -> bytes:
    """One file of the folio's image release; zipped crops are read from the cached crops.zip."""
    if name.startswith("crop-") and folio["id"] in ZIPPED:
        with zipfile.ZipFile(crops_zip(folio)) as z:
            return z.read(next(m for m in z.namelist() if m.rsplit("/", 1)[-1] == name))
    url = f"{site_data.REPO}/releases/download/{folio['release']}/{name}"
    def fetch():
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
            return r.read()
    return _with_retry(fetch)


def make(folio: dict, row: dict, slug: str, known: dict | None) -> dict:
    """Cut one plate's three images, unless they're already cut; return its images.json entry.

    known is the plate's entry in the images.json being replaced, if it has one. A plate already
    cut keeps it; a plate cut but not yet listed has its entry read back from the files.
    """
    paths = {name: OUT / folio["id"] / f"{slug}-{name}.webp" for name in CUTS}
    if all(p.exists() for p in paths.values()):
        if known:
            return known
        entry = {}
        for name in ("thumb", "crop", "sheet"):
            with Image.open(paths[name]) as im:
                entry[name] = list(im.size)
        with Image.open(paths["crop"]) as crop_im:
            entry.update(colour(crop_im))
        return entry
    # Otherwise download and cut
    paths["crop"].parent.mkdir(parents=True, exist_ok=True)
    crop = Image.open(io.BytesIO(asset(folio, row["crop_asset"])))
    sheet = Image.open(io.BytesIO(asset(folio, row["sheet_asset"])))
    entry = {}
    for name, source in (("thumb", crop), ("crop", crop), ("sheet", sheet)):
        long_edge, quality = CUTS[name]
        out = cut(source, long_edge)
        # Save atomically to .part then rename
        part = paths[name].with_name(paths[name].name + ".part")
        out.save(part, "WEBP", quality=quality, method=6)
        part.replace(paths[name])
        entry[name] = list(out.size)
    # Compute colour from the 1600px crop cut
    crop_cut = cut(crop, CUTS["crop"][0])
    entry.update(colour(crop_cut))
    print(f"{folio['id']}/{slug}", flush=True)
    return entry


def build() -> int:
    if Image is None:
        print("site_images.py build needs Pillow with WebP: python3 -m pip install Pillow", file=sys.stderr)
        return 1
    for folio in site_data.FOLIOS:
        if folio["id"] in ZIPPED:
            crops_zip(folio)  # once, before the threads start
    known = site_data.load_images()
    jobs = [(folio, row, slug, known.get(f"{folio['id']}/{slug}"))
            for folio, row, _, slug in site_data.plate_rows() if row["crop_asset"]]
    with ThreadPoolExecutor(8) as pool:
        entries = list(pool.map(lambda j: make(*j), jobs))
    plates = {f"{folio['id']}/{slug}": entry for (folio, _, slug, _), entry in zip(jobs, entries)}
    size = sum(p.stat().st_size for p in OUT.rglob("*.webp"))
    if size > BUDGET:
        print(f"the images come to {size / 1e6:.0f} MB, over the {BUDGET / 1e6:.0f} MB budget", file=sys.stderr)
        return 1
    lines = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}" for k, v in plates.items())
    IMAGES.write_text(f'{{\n "release": "{RELEASE}",\n "plates": {{\n{lines}\n }}\n}}\n', encoding="utf-8")
    with tarfile.open(TAR, "w") as tar:
        tar.add(OUT, arcname="img")
    print(f"{len(plates)} plates, {size / 1e6:.0f} MB; wrote site/src/data/images.json and .cache/site-images.tar")
    return 0


def fetch() -> int:
    release = json.loads(IMAGES.read_text(encoding="utf-8"))["release"]
    download(f"{site_data.REPO}/releases/download/{release}/site-images.tar", TAR)
    with tarfile.open(TAR) as tar:
        tar.extractall(PUBLIC, filter="data")
    print(f"unpacked {release} into site/public/img/")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        return build()
    if command == "fetch":
        return fetch()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
