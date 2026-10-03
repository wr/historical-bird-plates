"""Check the built site before it's deployed.

    python3 tools/site_check.py site/dist              # every link, image and page
    python3 tools/site_check.py site/dist --no-images  # skip img/, for a build without the image tarball

Every internal href, src, srcset, data-index and og:image must name a file in the build, and og:image
must be on the site. Every page needs a title, a description, an og:image, and a canonical URL that
is its own on the site's origin and that the sitemap lists (404.html is exempt from the canonical).
Every JSON-LD block must parse. Standard library only.
"""
from __future__ import annotations

import json
import posixpath
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ORIGIN = "https://wr.github.io"
BASE = "/historical-bird-plates/"
SITEMAP = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"


class Page(HTMLParser):
    """The links, metadata and JSON-LD of one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.title = ""
        self.jsonld: list[str] = []
        self._in: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href", "")
        elif tag in ("a", "link") and a.get("href"):
            self.refs.append(a["href"])
        for key in ("src", "data-index"):
            if a.get(key):
                self.refs.append(a[key])
        if a.get("srcset"):
            self.refs += [part.split()[0] for part in a["srcset"].split(",") if part.strip()]
        if tag == "meta" and (a.get("property") or a.get("name")):
            self.meta[a.get("property") or a["name"]] = a.get("content", "")
        if tag == "title":
            self._in = "title"
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in = "script"
            self.jsonld.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == self._in:
            self._in = None

    def handle_data(self, data: str) -> None:
        if self._in == "title":
            self.title += data
        elif self._in == "script":
            self.jsonld[-1] += data


def target(dist: Path, page: Path, ref: str) -> Path | None:
    """The file in dist that ref names, or None when ref leaves the site or is only a fragment."""
    parts = urlsplit(ref)
    if parts.scheme and parts.scheme not in ("http", "https"):
        return None
    if parts.netloc and f"{parts.scheme}://{parts.netloc}" != ORIGIN:
        return None
    path = unquote(parts.path)
    if not path:
        return None
    if not path.startswith("/"):
        folder = page.parent.relative_to(dist).as_posix()
        here = BASE if folder == "." else f"{BASE}{folder}/"
        path = posixpath.normpath(posixpath.join(here, path)) + ("/" if path.endswith("/") else "")
    if not path.startswith(BASE):
        return dist / "_outside_base" / path.lstrip("/")  # never exists, so it is reported
    file = dist / path[len(BASE):]
    return file / "index.html" if path.endswith("/") or file.is_dir() else file


def sitemap(dist: Path) -> set[str]:
    """Every URL the sitemap lists."""
    index = dist / "sitemap-index.xml"
    if not index.exists():
        return set()
    urls: set[str] = set()
    for loc in ET.parse(index).iter(SITEMAP):
        part = dist / urlsplit(loc.text or "").path[len(BASE):]
        urls |= {u.text or "" for u in ET.parse(part).iter(SITEMAP)}
    return urls


def check(dist: Path, images: bool = True) -> list[str]:
    errors: list[str] = []
    listed = sitemap(dist)
    if not listed:
        errors.append("sitemap-index.xml: missing or empty")
    for file in sorted(dist.rglob("*.html")):
        name = file.relative_to(dist).as_posix()
        page = Page()
        page.feed(file.read_text(encoding="utf-8"))
        og_image = page.meta.get("og:image", "")
        if og_image and not og_image.startswith(ORIGIN + BASE):
            errors.append(f"{name}: og:image {og_image} is not on the site")
            og_image = ""
        for ref in dict.fromkeys(page.refs + ([og_image] if og_image else [])):
            found = target(dist, file, ref)
            if found is None or (not images and found.relative_to(dist).parts[:1] == ("img",)):
                continue
            if not found.is_file():
                errors.append(f"{name}: broken link {ref}")
        if not page.title.strip():
            errors.append(f"{name}: no <title>")
        for key in ("description", "og:image"):
            if not page.meta.get(key):
                errors.append(f"{name}: no {key}")
        if name != "404.html":
            own = ORIGIN + BASE + name.removesuffix("index.html")
            if not page.canonical:
                errors.append(f"{name}: no canonical URL")
            elif page.canonical != own:
                errors.append(f"{name}: canonical {page.canonical} is not this page's URL")
            if own not in listed:
                errors.append(f"{name}: {own} is not in the sitemap")
        for block in page.jsonld:
            try:
                json.loads(block)
            except ValueError as e:
                errors.append(f"{name}: JSON-LD does not parse ({e})")
    return errors


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    dist = Path(args[0])
    errors = check(dist, images="--no-images" not in sys.argv)
    for e in errors[:200]:
        print(e, file=sys.stderr)
    if len(errors) > 200:
        print(f"… and {len(errors) - 200} more", file=sys.stderr)
    print(f"{sum(1 for _ in dist.rglob('*.html'))} pages, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
