# Plate explorer: design

A public website for browsing every plate in the dataset: a wall of all 2,462 plates, a page per plate, a page per species. It is built from the CSVs in this repo and served from GitHub Pages at `https://wr.github.io/historical-bird-plates/`.

Approved 2026-10-01, with a wireframe of the wall, plate page and species page.

## Goals

- Let anyone see the plates: all five folios in one place, searchable and filterable.
- Put the dataset's work on show: the printed name against the modern identification, the reasoning, the 62 plates whose printed name now means another bird.
- Be found by search engines: a real, indexable page for every plate and every species.
- Stay downstream of the data. The CSVs are the source of truth. The site never edits them and is rebuilt from them on every push to `main`.

## Non-goals

Family pages, deep-zoom tiles, Gould's text, translations, a custom domain, user accounts or comments. Any of these can come later. None is needed now.

## The numbers it is built on

| | |
|---|---:|
| Plates | 2,462 (havell 435, gould-europe 449, gould-australia 681, gould-asia 530, gould-britain 367) |
| Species rows | 2,552, of which 14 have no eBird code (the open questions) |
| Species | 1,762, all at eBird category `species` |
| Families | 153 |
| Sheets with more than one species | 58 |
| Extinct species (eBird `EXTINCT`) | 12 |

## Architecture

```
CSVs ─┐
      ├─ tools/site.py ──────────► site/src/data/plates.json (generated, gitignored)
eBird ┘        ▲                              │
               │                              ▼
site/src/data/images.json ◄─ tools/site_images.py      site/ (Astro) ── astro build ──► site/dist/
 (committed: size, colour)        │                                                        │
                                  ▼                                                        ▼
                 release site-images-v1: site-images.tar ──── extracted into ──► site/dist/img/
                                                                                           │
                                                          tools/check_site.py ◄────────────┤
                                                                                           ▼
                                                                                GitHub Pages
```

Python owns the data and the images. Astro only renders. No logic about identifications, names or taxonomy is reimplemented in JavaScript.

### `tools/site_images.py`: images (run locally, rarely)

- Downloads every folio's crops and sheets from its image release into `.cache/` (about 1.4 GB of crops). Australia and Asia crops come out of `crops.zip`. Plate-to-file mapping is `plates.csv`'s `crop_asset` and `sheet_asset`.
- Writes three WebP derivatives per plate:
  - `thumb`: 480 px on the long edge, for the wall;
  - `crop`: 1600 px on the long edge, for plate pages and large wall tiles;
  - `sheet`: 1200 px on the long edge, for the plate page's full-sheet view.
- Computes each crop's dominant colour. Paper is masked out first: pixels close to the tone sampled from the crop's border, and any pixel with low saturation and high lightness. The colour is the mean of the most populated saturation-weighted hue bin. Plates with almost no colour left after masking (engraved greys, browns) are flagged so the colour arrangement can put them last, sorted by lightness.
- Writes `site/src/data/images.json` (committed): for every plate, the pixel size of each derivative and the colour (hex, hue, flag). This is what the site needs at build time. The images themselves are not.
- Packs the derivatives into `site-images.tar`, with paths `img/<folio>/<slug>-thumb.webp`, `-crop.webp` and `-sheet.webp`.
- Budget, asserted by the script: total under 850 MB, so the site stays under the 1 GB Pages limit.
- `site_images.py fetch` downloads and unpacks the published tarball into `site/public/img/` (gitignored) for local development, without regenerating anything.
- Needs Pillow with WebP support. It is the only tool in `tools/` with a third-party dependency, and CI never runs it.

The release tag the site uses is written once, in `images.json` (`"release": "site-images-v1"`). Regenerating after a crop changes means publishing `site-images-v2` and committing the new `images.json`.

### `tools/site.py`: data (run in CI and locally)

Standard library only. It reads the five folios' `plates.csv` and `species.csv`, the eBird 2025 taxonomy (through `validate.py`'s `fetch`, into `.cache/`) and `images.json`, then writes `site/src/data/plates.json`:

- `folios`: id, title, author, years, plate count, intro paragraph, credit line, links to the folio README, tables and image release.
- `plates`: one record per plate, in folio order, with:
  - `folio`, `volume`, `plate`, `slug`, `url`;
  - the printed names (`list_name` or `title`, the caption name where there is one, the Latin);
  - `species`: one entry per `species.csv` row (figure, printed name and Latin, scientific, common, eBird code, confidence, form, caption checked, reason, sources, Wikidata, GBIF, Avibase, BirdNET label, species slug);
  - flags: `misnamed` (computed by `misnamed.py`'s own function, imported), `extinct`, `open` (any row with confidence `medium`, `low` or `none`), `multi` (more than one species);
  - taxonomy of the first identified species: `taxon_order`, `family_sci`, `family_common`, `order`;
  - images: the three paths and sizes, and the colour, from `images.json`;
  - outbound links: BHL page or audubon.org image, the full-resolution sheet in the release.
- `species`: one record per eBird code: slug, common, scientific, family, order, taxon order, extinct, outbound IDs, the plates showing it, and the plates *printed* under its name that show another bird.

Folio intros and credit lines live in `tools/site.py` as data, condensed from each folio README. The Havell credit line is the one audubon.org asks for.

### URLs

| Page | URL |
|---|---|
| Wall | `/` |
| Folio | `/havell/`, `/gould-europe/`, `/gould-australia/`, `/gould-asia/`, `/gould-britain/` |
| Plate, numbered straight through | `/havell/121/`, `/gould-europe/427/` |
| Plate, numbered by volume | `/gould-asia/i-1/`, `/gould-australia/supp-18/` |
| Species index | `/species/` |
| Species | `/species/snowy-owl/` (eBird common name, slugified; unique in eBird) |
| About and data | `/about/` |

All URLs are prefixed with Astro's `base` (`/historical-bird-plates/`), and every internal link is built from `import.meta.env.BASE_URL`.

### `site/`: the Astro project

- Pages: `index.astro`, `[folio]/index.astro`, `[folio]/[plate].astro`, `species/index.astro`, `species/[slug].astro`, `about.astro`, `404.astro`. Static output only, with `getStaticPaths` over `plates.json`.
- Components: `Layout` (head, header, footer), `Seo` (title, description, canonical, Open Graph, JSON-LD), `Wall` (the server-rendered tiles), `Tile`, `PlateViewer`, `SpeciesBlock`, `Filters`.
- One client script, `wall.ts`, bundled by Astro. The plate viewer has its own small script, `viewer.ts`.
- Integrations: `@astrojs/sitemap`. No UI framework.

## The pages

### Wall (`/`)

- **Header:** site name, then Folios, Species, About and Data.
- **Controls:** search box; arrange menu (folio order, taxonomy, colour); filter pills for folio and for the flags (misnamed, extinct, open question, several species); count of matching plates; tile-size slider.
- **Tiles:** every plate is rendered at build time as `<a href="/havell/121/"><img …></a>`, grouped by folio with a header per group. Crawlers and readers without JavaScript see the whole wall and can follow every link.
- **Justified rows**, in CSS only. Each tile is `flex: <aspect> 1 calc(<aspect> * var(--row-h))`, the image fills it, and a trailing spacer with a huge `flex-grow` keeps the last row from stretching. The slider sets `--row-h` (100–360 px). The `img` has `srcset` with the thumb and the crop at their real widths, so large tiles get the sharper image. Images are `loading="lazy"` with explicit `width` and `height`, so nothing shifts.
- **Hover and focus:** the tile shows the modern common name, and the printed name when it differs.
- **`wall.ts`:**
  - reads a compact index embedded in the page (`<script type="application/json">`: per plate, the search text, flags, folio, taxon order, family and hue);
  - filters by hiding tiles;
  - re-arranges by moving the existing tile nodes into new groups. Taxonomy groups by family, in eBird taxonomic order, with a header naming the family and its plate count. Colour makes one group sorted by hue, with the colourless plates last by lightness.
  - Search is case- and accent-insensitive and matches the printed and modern English names, the printed and modern Latin, and the eBird code.
  - State lives in the query string (`?q=owl&folio=havell&arrange=taxonomy&flag=misnamed`) through `replaceState`, so a filtered wall can be shared.
- **Empty result:** "No plates match. Clear filters" (a link).

### Folio page (`/havell/`)

Title, years, plate count, intro paragraph, credit line, links to the README, tables and image release. Below them sits the wall, pre-filtered to the folio and without the folio pills.

### Plate page (`/havell/121/`)

- **Breadcrumb:** Wall / folio / plate. Previous and next plate links, also bound to ← and →.
- **Viewer:** the 1600 px crop with *Crop* and *Full sheet* toggles (the sheet shows the engraved caption). Wheel or pinch zooms; drag pans; double-click resets. A *Full resolution* link goes to the original sheet in the release.
- **Beside the image:**
  - "Printed on the plate": the list or title name, the caption, the Latin;
  - "Modern identification": the common name (linking to its species page), the scientific name, and pills for confidence, form, caption-checked and family;
  - "Why": `reason`;
  - "Sources": `sources`;
  - outbound links to eBird, Wikidata, GBIF, Avibase and BHL (or audubon.org);
  - on a sheet with several species, one block per species, keyed by figure.
- **Flags, said in words:** "The printed name is now eBird's name for another bird: Laughing Gull." "Open question: …" (the reason, which says what would decide it).
- **Footer strip:** the same species in the other folios, as small tiles linking to those plates and to the species page.
- **Credit line** for the folio's scans.

### Species page (`/species/snowy-owl/`)

Family and order; common and scientific name; extinct note where it applies. Then every plate of the species side by side at equal height, ordered by folio publication date, each with its folio, year range, plate number and printed name. A second strip lists plates printed under this bird's name that show a different bird. Outbound links: eBird, Wikidata, GBIF, Avibase, and BirdNET where it has a label.

### Species index (`/species/`)

All 1,762 species, grouped by family in taxonomic order, each with its plate count. Mainly so every species page is one link from a crawlable page; a filter box narrows the list.

### About (`/about/`)

What the dataset is, how plates were identified (condensed from the README), how to get the tables and images, how to cite (from `CITATION.cff`), and the credits and rights for each folio's scans.

## Look

A museum print room. Warm paper tones in light mode and a deep neutral in dark mode, both from CSS custom properties with `prefers-color-scheme`. A serif for names and headings, a quiet sans for the controls and data. The plates are the only colour on the page; chrome stays neutral. The visual direction is set at implementation time with the frontend-design skill, within this brief.

## Search indexing

On every page:

- `<title>`. Plate: "Snowy Owl · Audubon, *The Birds of America*, plate 121". When the printed name differs it leads: "'Black-headed Gull' (Mediterranean Gull) · Gould, *The Birds of Europe*, plate 427". Species: "Snowy Owl in nineteenth-century bird plates".
- `meta description`, built from the identification and the first sentence of the reason.
- `link rel="canonical"`.
- Open Graph and Twitter card, with the crop as the image, as an absolute URL.
- JSON-LD:
  - plate pages: `VisualArtwork` (name, creator, `dateCreated` as the folio's year range, `isPartOf` the `Book`, `about` a `Taxon` with `sameAs` Wikidata and eBird, `image`, `license` Public Domain Mark);
  - species pages: `Taxon`;
  - the wall: `WebSite`.

Also `sitemap.xml` (every page) and `robots.txt` (allow all; points to the sitemap).

## Accessibility

- Every image has alt text: "Plate 121 of Audubon's *The Birds of America*: Snowy Owl (*Bubo scandiacus*)".
- Filters are real buttons with `aria-pressed`; the result count is announced through a polite live region.
- Every control is reachable and operable by keyboard; focus is visible.
- Contrast meets WCAG AA in both colour schemes.
- `prefers-reduced-motion` turns off view transitions.

## Deployment

`.github/workflows/pages.yml`, on push to `main` when `site/**`, any `plates.csv` or `species.csv`, or `tools/site*.py` changes, and on manual dispatch:

1. Set up Python 3.12; run `python3 tools/site.py`.
2. Set up Node (LTS); `npm ci` and `npm run build` in `site/`.
3. Download `site-images.tar` from the release named in `images.json`; unpack it into `site/dist/`.
4. Run `python3 tools/check_site.py site/dist`.
5. `actions/upload-pages-artifact` and `actions/deploy-pages`.

GitHub Pages has to be switched on once, in the repo settings, with "GitHub Actions" as the source.

## Testing

- `tools/test_site.py`, in `test_identify.py`'s unittest style, runs in `validate.yml` next to it. Checks:
  - `site.py` emits 2,462 plates, each once, with unique slugs;
  - every plate has an `images.json` entry;
  - every eBird code resolves in the taxonomy;
  - species slugs are unique;
  - the plates flagged `misnamed` are exactly the ones `misnamed.py` lists;
  - every plate's species link names a species record.
- `tools/check_site.py dist/` runs in the Pages workflow before deploy. It is standard library only and parses the built HTML. Checks:
  - every internal `href` and `src` resolves to a file in `dist/`;
  - the sitemap lists every plate and species page;
  - every page has a title, description, canonical and `og:image`;
  - JSON-LD parses.
- In the browser, against `astro preview`:
  - the wall at phone and desktop widths, in both colour schemes;
  - each arrangement, a search, a filter and a shared query-string URL;
  - a single-species plate, a multi-species plate, a misnamed plate and an open question;
  - a species page with plates in three folios.

## Public actions, each to be confirmed first

1. Publishing the `site-images-v1` release.
2. Switching on GitHub Pages in the repo settings.
3. Merging to `main`, which deploys.
