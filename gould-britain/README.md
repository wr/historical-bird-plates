# John Gould, *The Birds of Great Britain* (1862–73)

Five volumes and 367 plates. Drawn and lithographed by John Gould (288 plates) or Joseph Wolf (55), each with H. C. Richter (312) or William Hart (31), hand-coloured, published in parts in London.

**Copy:** Smithsonian Libraries, scanned for the Biodiversity Heritage Library (BHL): [title 127814](https://www.biodiversitylibrary.org/bibliography/127814), BHL barcodes `birdsgreatbrita{1..5}goul`. Public domain. Credit: *Smithsonian Libraries and Archives, via the Biodiversity Heritage Library.*

## The plates

Every plate as its art crop, by volume and number. The full-size images are in the [`gould-britain-v2`](https://github.com/wr/historical-bird-plates/releases/tag/gould-britain-v2) release.

**Volume I, plates 1–37**

![Volume I, plates 1–37](img/plates-i-001-037.jpg)

**Volume II, plates 1–39**

![Volume II, plates 1–39](img/plates-ii-001-039.jpg)

**Volume II, plates 40–78**

![Volume II, plates 40–78](img/plates-ii-040-078.jpg)

**Volume III, plates 1–38**

![Volume III, plates 1–38](img/plates-iii-001-038.jpg)

**Volume III, plates 39–76**

![Volume III, plates 39–76](img/plates-iii-039-076.jpg)

**Volume IV, plates 1–45**

![Volume IV, plates 1–45](img/plates-iv-001-045.jpg)

**Volume IV, plates 46–90**

![Volume IV, plates 46–90](img/plates-iv-046-090.jpg)

**Volume V, plates 1–43**

![Volume V, plates 1–43](img/plates-v-001-043.jpg)

**Volume V, plates 44–86**

![Volume V, plates 44–86](img/plates-v-044-086.jpg)

## Files

- **`plates.csv`**: one row per plate. It holds:
  - `volume` and `plate`: Gould numbers his plates per volume, as each volume's List of Plates does ("Gt. Brit. iii. pl. 10"). The sheets carry no number. Together the two are the plate's key.
  - the List's English and Latin names, and the Latin name engraved on the plate;
  - where the plate is: BHL item, leaf, BHL PageID, and a link to the page;
  - `scan_url`, the unaltered JPEG 2000 on BHL's open-data bucket;
  - the two release images;
  - `imprint`, the plate's credit lines (see [Who made the plates](#who-made-the-plates)).
- **`species.csv`**: one row per plate and species. Two plates have a second bird: the cuckoos' foster parents (`figure` `foster parent`).
- **`credits.csv`**: one row per plate, name and role, from `imprint`.
- **`ku-disagreements.csv`**: the 74 plates where the Kansas catalogue differs, and the `kind` of each.
- **`sources/plate-leaves.csv`**: each plate's engraved caption as read, how it was read, where it starts, and the heading of the next text leaf.
- **`sources/ku-catalogue.csv`**: the Kansas catalogue's record for every plate.
- **`sources/decisions.csv`**: every identification as decided, in `tools/identify.py`'s log.
- **`sources/imprints.csv`**: how each plate's credit lines were read: where they are on the sheet, the OCR draft, whether they were read off the crop (`eye`) or the scan (`scan`) or not at all (`none`), and what the readers noted.
- **`sources/survey.csv`**: the first survey. For every plate it gives its leaf, the name as printed, a draft modern name, whether BirdNET V2.4 has it, and the matching plate of *The Birds of Europe* where there is one.

## Who made the plates

Every plate is credited on its face, in small engraved lines below the art: on the left who drew it and put it on stone, on the right who printed it. `imprint` in `plates.csv` gives them as engraved, with spacing, initials and the mark after an abbreviation written by one convention (see [Credit lines](../README.md#credit-lines)). `credits.csv` gives one row per plate, name and role, read from them by `tools/credits.py`.

Lines that differ only in capitals, stops, commas or colons are counted together, under their commonest form.

| Credit line | Credits | Plates |
|---|---|---:|
| J. Gould & H. C. Richter, del et lith. | John Gould and H. C. Richter: drew, lithographed | 164 |
| J. Gould and H. C. Richter, del. et lith. | John Gould and H. C. Richter: drew, lithographed | 96 |
| J. Wolf & H. C. Richter, del et lith. | Joseph Wolf and H. C. Richter: drew, lithographed | 28 |
| J. Gould & W. Hart, del et lith. | John Gould and William Hart: drew, lithographed | 27 |
| J. Wolf and H. C. Richter, del. et lith. | Joseph Wolf and H. C. Richter: drew, lithographed | 23 |
| J. Wolf & W. Hart, del et lith. | Joseph Wolf and William Hart: drew, lithographed | 4 |

One plate, III.61, reads "Gould & H. C. Richter, del. et lith." (see below). That makes H. C. Richter on 312 plates, John Gould on 288, Joseph Wolf on 55 and William Hart on 31. Every artist's line names two: Gould or Wolf, with Richter or Hart.

| Printer | Credit line | Plates |
|---|---|---:|
| Walter | Walter, Imp. | 258 |
| Walter & Cohn | Walter & Cohn, Imp. | 87 |

Who Walter and Walter & Cohn were is not established.

A joint line credits both names with every role it gives, because that is all it says. The sources say more:
- Gould's preface of 1873: "Mr. Wolf affords me the benefit of his talented pencil", and "Mr. Richter and Mr. Hart continue their services as heretofore" (Gould 1873, preface).
- Gould's own drawings "are never more than rough sketches", with colour notes for his artists (Australian Museum, "Gould the artist").
- Richter "produced over 300 of the 367 plates, sharing the lithography with William Hart" (Australian Museum, "Henry Constantine Richter"). The credit lines name him on 312.
- Wolf worked for Gould "on a freelance basis" (Australian Museum, "Josef Wolf"), and Richter and Hart put his drawings on stone (KU Libraries, "Joseph Wolf"; Australian Museum, "Josef Wolf"). Wolf and Hart share four plates: I.14, I.23, V.1 and V.58.

III.61's line begins "Gould &": its initial is cut off at the sheet's edge. It is credited to John Gould, a reading that rests on this folio alone (`FOLIO_NAMES` in `tools/credits.py`, and the plate's note). *The Birds of Great Britain* is of 1862–73, after Elizabeth Gould's death in 1841 (Australian Museum, "Henry Constantine Richter"), and every other line of it that names a Gould reads J. Gould.

19 plates have no credit line read; `notes` says why for each. All are bound sideways, and their lines are cut off at the sheet's foot: on 14 the sheet ends in the caption or the picture, and on 5 only the tops of the letters show. Eight more have one line only: the artist's on I.24, III.27 and IV.8, and the printer's on IV.21, IV.25, IV.41, IV.51 and V.51.

Sources:
- Gould, J. 1873. *The Birds of Great Britain*, vol. I, Preface (1 Nov 1873). [archive.org/details/birdsgreatbrita1goul](https://archive.org/details/birdsgreatbrita1goul)
- Australian Museum Research Library, *John Gould: illustrations and books*: "Gould the artist" (2021), [australian.museum](https://australian.museum/learn/collections/museum-archives-library/john-gould/gould-the-artist/); "Henry Constantine Richter (about 1821–1902)" (2018), [australian.museum](https://australian.museum/learn/collections/museum-archives-library/john-gould/henry-constantine-richter-about-1821-1902/); "Josef Wolf (1820–1899)" (2018), [australian.museum](https://australian.museum/learn/collections/museum-archives-library/john-gould/josef-wolf-1820-1899/).
- KU Libraries. "Joseph Wolf", in *John Gould: Bird Illustration in the Age of Darwin* (online exhibit). [exhibits.lib.ku.edu](https://exhibits.lib.ku.edu/exhibits/show/gould/art/joseph_wolf)

## How the plates were identified

1. **Numbering.** Each volume prints its own List of Plates: 37, 78, 76, 90 and 86 plates. The Smithsonian copy is bound in List order.
2. **Captions.** Every engraved caption was read on the scan: 360 with Apple's Vision OCR and 6 by eye, where the letters are too faint or too close to the binding. All 366 agree with the List. IV.63's caption is lost in the binding gutter of this copy; its text leaf and the bird identify it.
3. **Names.** Each plate was carried to its modern species through the caption, Gould's text and synonymy, and the same bird's caption-checked plate in *The Birds of Europe*, and the plate was looked at wherever the name, a split or a second bird left any doubt. 365 rows are `high` and four `judged`; none are open.
4. **Kansas.** The University of Kansas Spencer Library's copy (`ku-gould:9261`, `8935`, `8625`, `8257`, `7895`, vols. I–V) has a record for every plate. 74 differ from this table. Most are older genera, and 10 are a find-and-replace slip in Kansas's records (*Sturnus* for *Sterna*). Eight are errors, among them II.51 (Black Redstart for the Common), II.69 (the American Golden-crowned Kinglet for the Goldcrest), V.35 (Goosander for the Red-breasted Merganser) and V.71 (Arctic Tern for the Roseate).
5. **Modern names.** `scientific` and `common` are eBird/Clements 2025's. `birdnet_label` is BirdNET V2.4's label, where it has the bird.

Birds in the background that are not the plate's subject, such as the Bearded Tit on V.40 and the Kingfisher on V.34, have no row.

## Traps

These are the plates a careful reader would still get wrong.

- **Garden and Orphean Warblers:** II.62, printed *Curruca hortensis*, is BirdNET's exact label for the Western Orphean Warbler, but the bird is the Garden Warbler. II.61, *Curruca orphea*, is the Orphean: the Western, `judged`, for its brown back, apricot underparts and western sources.
- **Terns:** Gould's *Sterna paradisea* (V.71) is the Roseate Tern: rosy breast, dark bill. His *S. macrura* (V.72) is the Arctic Tern, today's *Sterna paradisaea*.
- **Melodious Warbler (II.71)** is the Icterine. *Ficedula hypolais* is Linnaeus's *hippolais*; Gould lists the Melodious, *polyglotta*, separately, and the plate shows the Icterine's long wingtip.
- **Spotted Eagle (I.3)** is the Greater, `judged`. The name covered both, but the young bird drawn after the Cornwall birds of 1860–61 has rows of large pale spots on every covert.
- **Bean-Goose (V.2)** is the Taiga Bean-Goose, `judged`: Gould's *segetum* and his Scandinavian range are the Taiga bird's, and the bill drawn at two-thirds life size leans the same way.
- **Dowitcher (IV.76):** Gould prints *Macrorhamphus griseus*, the Short-billed's name, but the summer bird figured, rufous to the vent and barred below, is the Long-billed (`judged`), and the British records are Long-billed.
- **Cattle Egret (IV.24):** Gould himself separates the eastern *coromandus*; his bird is the Western Cattle-Egret.
- **Crakes (IV.89, IV.90):** the Latin crosses. Gould's *Porzana pygmaea* is Baillon's Crake (*Zapornia pusilla*), and his "Olivaceous Crake", *P. minuta*, the Little Crake (*Z. parva*).
- **Hawk Owl (I.35):** *Surnia funerea* is the Hawk Owl, but Linnaeus's *Strix funerea* is now Tengmalm's Owl, I.36.
- **Reed Warblers (II.72, II.73):** Gould's *Calamoherpe arundinacea* is the Reed Warbler; today's *Acrocephalus arundinaceus* is his Thrush-Warbler.
- **Gyrfalcons (I.11–I.16):** six plates, one species. The Iceland and Greenland Falcons are `variant`, since Clements recognises no races.
- **Wagtails (III.1–III.5):** five plates, two species. III.4, Gould's Grey-headed *neglecta*, shows the white-browed Blue-headed nominate.
- **Redpolls (III.51, III.52):** eBird 2025 lumps them as Redpoll; BirdNET keeps Common and Lesser apart, so their labels differ.
- **Skuas (V.80, V.81):** here *parasiticus* is the Arctic Skua, as today, unlike *The Birds of Europe* 442.
- **Black-headed Gull (V.64)** is the modern Black-headed Gull, not the Mediterranean Gull that *Europe* 427 called by this name.
- **Great Shearwater (V.83):** the range in Gould's text is Cory's Shearwater's; the bird figured is a Great Shearwater.
- **Rock and Water Pipits (III.10, III.11):** *The Birds of Europe* has the two on one plate, as one species. This folio gives each its own plate.

## The images: release `gould-britain-v2`

Two images per plate, 367 plates, made as for *The Birds of Europe*. `manifest.json` and `SHA256SUMS` give each file's sha256.

- **`sheet-<barcode>-<leaf>.jpg`, the cleaned full sheet:**
  - The JPEG 2000 master, stood upright. Half the plates are bound sideways, and they are turned so the caption runs along the bottom. In `gould-britain-v1` ten were turned wrong: I.25, II.8, III.7, IV.62, IV.70 and IV.82 upside down, and IV.9, IV.37, IV.39 and V.57 on their side. v2 checks every one by reading its caption.
  - The paper is evened, and anything within 6 % of its tone becomes pure white.
  - The later volumes' painted backgrounds are kept.
- **`crop-<barcode>-<leaf>.jpg`, the art crop:** cut just above the read caption (`caption_top` in `sources/plate-leaves.csv`), with the right edge of upright plates trimmed clear of the binding line, then cropped to the art's own box. Every crop was reviewed on contact sheets. A few keep the hairline of the painted ground's lower edge, which is part of the print.

These scans are about 265 ppi, and BHL's masters are lossy: the lowest resolution of Gould's folios here. For the sheet as it is, follow the row's `scan_url` to BHL's original.
