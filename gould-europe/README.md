# John Gould, *The Birds of Europe* (1832–37)

Five volumes and 449 plates: 448 in this copy, as one was never found. Drawn and lithographed by John and Elizabeth Gould and Edward Lear, hand-coloured, published in parts in London.

**Copy:** Smithsonian Libraries, scanned for the Biodiversity Heritage Library (BHL): [title 65989](https://www.biodiversitylibrary.org/bibliography/65989), items 132863, 132861, 133913, 132862 and 133915, i.e. volumes I–V, BHL barcodes `birdsEurope{I..V}Goul`. Public domain. Credit: *Smithsonian Libraries and Archives, via the Biodiversity Heritage Library.*

## Files

- **`plates.csv`**: one row per plate. It holds:
  - the General List's name for the plate, and the name engraved on the plate itself;
  - where the plate is: volume, BHL item, leaf, BHL PageID, and a link to the page;
  - `scan_url`, the unaltered JPEG 2000 on BHL's open-data bucket;
  - the two release images.
- **`species.csv`**: one row per plate and bird on the General List, including every row that isn't identified.
- **`ku-disagreements.csv`**: every caption-checked plate where the Kansas catalogue names a different species, and what the disagreement is (see below).
- **`sources/`**: the working record.
  - `general-list.csv`: the General List of Plates, transcribed from volume I.
  - `plate-leaves.csv`: every plate leaf in the five volumes, with its pencilled number, engraved caption and orientation.
  - `crosswalk.csv`: each List row mapped to a modern name, with confidence and reason.
  - `ku-catalogue.csv`: the Kansas record for each plate.

## How the plates were identified

1. **Numbering.** The plates were issued unnumbered. The book's own order is the *General List of Plates* in volume I (leaves 23–26): 449 numbers, some with two or three species. The List was transcribed by reading the page images, and its numbers are the plate numbers here. The Smithsonian copy carries each List number in pencil on its plate.
2. **Leaves.** Every leaf of all five volumes was walked. Each plate leaf's pencilled number, its engraved caption and whether it is bound sideways were written down (`sources/plate-leaves.csv`).
3. **Names.** Each List row was mapped to a modern species through its Latin name, its English name and the literature. Each mapping got a confidence and a written reason (`sources/crosswalk.csv`).
4. **Checking.** An identification is `caption_checked: yes` only when its leaf's engraved caption names that bird, by Latin epithet or the whole English name, never a shared family word. It was checked by eye on the scan. 411 identifications on 392 plates meet that bar.
   - **High but unchecked:** 35 more `high` rows are secondary plates of species checked elsewhere, and are not caption-checked.
   - **Open:** 20 plates are `low`: the open questions.
5. **Modern names.** Each identification was first made to BirdNET V2.4's labels (Featherframe's use), then carried to eBird/Clements 2025. Where the two taxonomies differ, `reason` says so. The Wikidata, GBIF and Avibase ids come from the species' Wikidata item, found by its eBird code.

## Traps

These are the plates a careful reader would still get wrong.

- **The gulls:** Gould's "Black-headed Gull" (*Xema melanocephala*, 427) is today's Mediterranean Gull. The modern Black-headed Gull is his "Laughing Gull" (*Xema ridibunda*, 425), and today's American Laughing Gull is his "Black-winged Gull" (*Xema atricilla*, 426). Match on the modern binomial, never the common name.
- **Pencil numbers:** this copy's pencil moves Bulwer's Petrel to 448 and puts both storm-petrels on 447's sheet. It also swaps the pencil numbers of 132 and 133. Where the pencil and the caption disagree, the caption decides.
- **The Dalmatian Regulus** (149) is Pallas's Leaf Warbler.
- **The Imperial Eagle** (5) is the eastern bird.
- **A plate drawn before a split** stands for the species as it was then understood (`form: pre-split`).
- **133** is listed as both Icterine and Melodious Warbler (`judged`; `reason` says why).
- **Sabine's Snipe** (321) is the Common Snipe's dark morph (`form: variant`), not a species.
- **Chough and grebe:** on 219 and 391, Gould's Latin names have since moved to the other species. The plates decide:
  - 219 has the Red-billed Chough's long, curved red bill;
  - 391 has the Eared Grebe's black neck and fanned ear plumes.
- **Red-rumped Swallow** (55): eBird 2025 splits it, and *Cecropis daurica* now names the eastern bird. Gould's European bird is *Cecropis rufula*, European Red-rumped Swallow.
- **Goshawk** (17): BirdNET's Northern Goshawk is split in eBird. Gould's is the Eurasian Goshawk, *Astur gentilis*.
- **Redpoll** (194): eBird 2025 lumps the redpolls. Gould's plate is the Lesser Redpoll form.

## The Kansas catalogue

The University of Kansas Spencer Library's Ellis Collection copy (volume I: [ku-gould:11233](https://digital.lib.ku.edu/ku-gould/11233)) gives each plate a modern scientific name. It is the one other public identification of this folio. Its names were matched from the printed Latin, not from the birds.

Of the 410 caption-checked species, 409 match a KU plate. `ku-disagreements.csv` lists the 27 plates where KU names something else, by kind:

| kind | plates | what it is |
|---|---|---|
| error | 14, 50, 63, 65, 67, 75, 86, 108, 130, 137, 149, 205, 360, 442 | KU names another species. Some are unrelated: 360, the Shoveler, is labelled a warbler; 63 is labelled an Australian monarch. Others are Latin look-alikes. |
| crossed | 219, 391 | Gould's Latin has since moved to the other species (see Traps) |
| typo | 247, 273, 274, 276, 371 | same species, KU's spelling (*Aquila* for *Ardea*, a space in a name) |
| old name | 194, 259, 321 | an older binomial for the same bird |
| pre-split | 217, 287 | KU gives the parent species before the split |
| composite | 151 | KU's English and Latin name different figures on the same sheet |

That is 16 misidentified plates out of about 410, roughly one in 26. On the brace plates, KU's record names only one figure.

## The images: release `gould-europe-v1`

Two images per plate leaf, 448 leaves. `manifest.json` and `SHA256SUMS` give each file's sha256.

- **`sheet-<barcode>-<leaf>.jpg`, the cleaned full sheet:**
  - The JPEG 2000 master, stood upright: 90° clockwise for a landscape plate, so its caption runs along the bottom.
  - The paper is evened. A quadratic surface is fitted to the paper pixels and divided out, removing foxing and the lighting gradient. Anything within 6 % of the paper's own tone becomes pure white.
  - The ink keeps its tone. Caption and imprint are kept.
  - JPEG quality 95.
- **`crop-<barcode>-<leaf>.jpg`, the art crop:**
  - The engraved caption and the pencilled number are cut away. The art is cropped to its own box, and a band of fresh white paper is added.
  - A plate with several birds keeps every one.
  - This is Featherframe's cut for e-paper, and more opinionated than the sheet.
  - The Ivory Gull (436) is white on white paper, so its crop is cut from the whole sheet instead.

Clearing the paper is a choice. For the sheet as it is, with its paper and its age, follow the row's `scan_url` to BHL's original.

**Plates found by pencil alone:** 56 plates (`notes`: *leaf found by its pencilled number*) were located by their pencil number and cleaned the same way. Their captions were not checked against an identification. A landscape one was stood up in the same direction as every checked landscape plate.
