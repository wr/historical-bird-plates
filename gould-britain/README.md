# John Gould, *The Birds of Great Britain* (1862–73)

Five volumes and 367 plates. Drawn by John Gould with H. C. Richter, W. Hart and J. Wolf, lithographed and hand-coloured, published in parts in London.

**Copy:** Smithsonian Libraries, scanned for the Biodiversity Heritage Library (BHL): [title 127814](https://www.biodiversitylibrary.org/bibliography/127814), BHL barcodes `birdsgreatbrita{1..5}goul`. Public domain. Credit: *Smithsonian Libraries and Archives, via the Biodiversity Heritage Library.*

**This folio is a first pass.** Only seven plates have been read against their engraved captions. Every other identification is a draft, and every one is marked open (`confidence` `medium` or `low`, `caption_checked` `no`). The easiest way to contribute to this dataset is to check one.

## The plates

Every plate as its art crop, by volume and number. The full-size images are in the [`gould-britain-v1`](https://github.com/wr/historical-bird-plates/releases/tag/gould-britain-v1) release.

<!-- contact sheets -->

## Files

- **`plates.csv`**: one row per plate. It holds:
  - `volume` and `plate`: Gould numbers his plates per volume, as each volume's List of Plates does ("Gt. Brit. iii. pl. 10"). The sheets carry no number. Together the two are the plate's key.
  - the List's English and Latin names, and, for the seven checked plates, the Latin name engraved on the plate;
  - where the plate is: BHL item, leaf, BHL PageID, and a link to the page;
  - `scan_url`, the unaltered JPEG 2000 on BHL's open-data bucket;
  - the two release images.
- **`species.csv`**: one row per plate.
- **`sources/survey.csv`**: the survey the drafts come from. For every plate it gives its leaf, the name as printed, a draft modern name, whether BirdNET V2.4 has it, and the matching plate of *The Birds of Europe* where there is one.

## How the plates were identified

1. **Numbering.** Each volume prints its own List of Plates: 37, 78, 76, 90 and 86 plates. The Smithsonian copy is bound in List order.
2. **Leaves.** Each plate was paired with its leaf by the binding's order, and the pairing checked by thumbnail and OCR, not caption by caption.
3. **Names.** Each List name was carried to a modern species in one pass. 336 drafts agree with the caption-checked identification of the same bird's plate in *The Birds of Europe*. The row's `reason` says so.
4. **Checking.** Seven plates were read against their engraved captions, and those are the only `high` rows. They are the species *The Birds of Europe* lacks: Yellow-browed Warbler, Rock Pipit, Water Pipit, Little Bunting, Pallas's Sandgrouse, Pink-footed Goose and Ross's Gull.
5. **Modern names.** `scientific` and `common` are eBird/Clements 2025's. `birdnet_label` is BirdNET V2.4's label, where it has the bird.

## Traps

- **Garden and Orphean Warblers:** II.62, printed *Curruca hortensis*, is BirdNET's exact label for the Western Orphean Warbler. The bird is the Garden Warbler (*Sylvia borin*). II.61, *Curruca orphea*, is the Orphean.
- **Terns:** Gould's *Sterna paradisea* (V.71) is the Roseate Tern. His *S. macrura* (V.72) is the Arctic Tern, today's *Sterna paradisaea*.
- **Spotted Eagle** (I.3) and **Bean-Goose** (V.2): today's splits leave the species uncertain, so both are `low`.
- **Rock and Water Pipits** (III.10, III.11): *The Birds of Europe* has the two on one plate, as one species. This folio, thirty years later, gives each its own plate.

## The images: release `gould-britain-v1`

Two images per plate, 367 plates, made as for *The Birds of Europe*. `manifest.json` and `SHA256SUMS` give each file's sha256.

- **`sheet-<barcode>-<leaf>.jpg`, the cleaned full sheet:**
  - The JPEG 2000 master, stood upright. Half the plates are bound sideways, and they are turned so the caption runs along the bottom.
  - The paper is evened, and anything within 6 % of its tone becomes pure white.
  - The later volumes' painted backgrounds are kept.
- **`crop-<barcode>-<leaf>.jpg`, the art crop:** cut above the caption and cropped to the art's own box. Only the seven checked plates' crops have been reviewed.

These scans are about 265 ppi, and BHL's masters are lossy: the lowest resolution of Gould's folios here. For the sheet as it is, follow the row's `scan_url` to BHL's original.
