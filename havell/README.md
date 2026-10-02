# John James Audubon, *The Birds of America*, Havell edition (1827–38)

435 plates, engraved, printed and hand-coloured by Robert Havell Jr. in London from Audubon's watercolours. Numbered 1–435 on the plates themselves.

## Images

Release [`havell-v1`](https://github.com/wr/historical-bird-plates/releases/tag/havell-v1) has two images of every plate. `manifest.json` and `SHA256SUMS` give each file's sha256.

- **`sheet-NNN.jpg`**: the full plate, as audubon.org publishes it, unaltered. About 2.7 GB.
- **`crop-NNN.jpg`**: the same plate with its lettering trimmed away: the plate number along the top and the engraved caption along the bottom. It is the whole engraving, never one bird of a sheet. About 250 MB.

Credit the scans: *Courtesy of the John James Audubon Center at Mill Grove, Montgomery County Audubon Collection, and Zebra Publishing.*

- **Rights:** the plates are public domain, and a faithful photograph of a public-domain plate carries no copyright of its own in the US. The images are marked with the [Public Domain Mark](https://creativecommons.org/publicdomain/mark/1.0/). audubon.org offers them under its [terms of use](https://www.audubon.org/terms-use); please follow its credit line.
- **Other mirrors:** Nathan Buchar's [audubon-bird-plates](https://github.com/nathanbuchar/audubon-bird-plates) holds the same files. Public-domain scans of other copies are on [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:The_Birds_of_America) and at the University of Pittsburgh's [Darlington Library](https://digital.library.pitt.edu/collection/audubon-birds-america).

## The plates

Every plate with its lettering trimmed, by Havell number.

**Plates 1–50**

![Plates 1–50](img/plates-001-050.jpg)

**Plates 51–100**

![Plates 51–100](img/plates-051-100.jpg)

**Plates 101–150**

![Plates 101–150](img/plates-101-150.jpg)

**Plates 151–200**

![Plates 151–200](img/plates-151-200.jpg)

**Plates 201–250**

![Plates 201–250](img/plates-201-250.jpg)

**Plates 251–300**

![Plates 251–300](img/plates-251-300.jpg)

**Plates 301–350**

![Plates 301–350](img/plates-301-350.jpg)

**Plates 351–400**

![Plates 351–400](img/plates-351-400.jpg)

**Plates 401–435**

![Plates 401–435](img/plates-401-435.jpg)

## Files

- **`plates.csv`**: plate, title and legend. The titles and image links come from Nathan Buchar's [`data.json`](https://github.com/nathanbuchar/audubon-bird-plates/blob/master/data.json). Its titles run one plate late from 361 to 399, though its file names and images are right, so those titles are corrected here.
  - `title` is Audubon's title as audubon.org gives it. That is usually the plate's *first-state* lettering, which some plates later changed. Plate 50 is the exception: audubon.org titles it "Black & Yellow Warbler", the later lettering, while its scan carries the 1828 first state, "Swainson's Warbler".
  - `legend` is the lines engraved under the title and Latin name: the figure key and the plant or setting, in Audubon's spelling, transcribed from the scans' caption bands.
- **`species.csv`**: one row per plate and modern species. On a sheet with several species, `figure` is that species' own key.
  - `printed_name` is the English title engraved on this release's scan, read off all 435 sheets on 1 Oct 2026, in the engraver's spelling: "Ruffed Grous", "Belted Kingsfisher", "Great Red brested Rail or Fresh-water Marsh hen". Case and hyphens are not compared. On a sheet with several species it is that bird's own title; a bird named only in the legend (284 fig. 3, 285 fig. 2) or a plate with no English title (245) carries its Latin. Where the scan and audubon.org's `title` differ, as on plates 48, 153, 198 and 263, the row's `reason` gives both.

## How the plates were identified

- **Sources:** each plate was mapped from two independent sources, joined and read against the titles by hand:
  - Wikimedia Commons' per-plate species categories;
  - the Havell titles (the Commons gallery and the mirror's file names).
- **Hard cases:** the 76 plates whose modern name shares no word with Audubon's title were verified one by one against audubon.org, the University of Pittsburgh's Havell catalogue and the New-York Historical Society.
- **Second plates:** the 29 plates that repeat a species shown on another plate were matched later, against audubon.org, Wikimedia Commons, the Boston Public Library's prints on Digital Commonwealth and Pitt's catalogue. Each row's `sources` names the ones that agree.
- **Modern names:** made first to BirdNET V2.4's labels, then carried to eBird/Clements 2025 (see *Splits* below).
- **Extinct species:** extinct and far out-of-range species are included, so the map is complete. BirdNET has no class for 22 of them, including the Carolina Parakeet, Passenger Pigeon, Labrador Duck, Great Auk, Eskimo Curlew and Ivory-billed Woodpecker. Their `birdnet_label` is empty.
- **Caption checks:** `caption_checked` is left empty here. These identifications were checked against catalogues, not recorded caption by caption as Gould's were.

## Traps

- **Plate 50 is a young Magnolia Warbler.** These scans carry its 1828 lettering, "Swainson's Warbler, *Sylvicola swainsonia*". Audubon wrote in 1831 that one drawing had been engraved in place of another while he was away from London, and the plate was re-lettered "Black and yellow warbler, *Sylvia maculosa*, young male". It is not the Swainson's Warbler of plate 198, which Audubon described in 1834. The adult Magnolia pair is plate 123.
- **Plate 165's scan is not the Havell plate.** audubon.org's file, and so `sheet-165.jpg`, is the octavo edition's small lithograph (J. T. Bowen, Philadelphia), lettered "Bachman's Pinewood-Finch", at 1082 × 1314 pixels. The row keeps the Havell title, "Bachman's Finch".
- **Plate 132's "Three-toed Woodpecker" is the Black-backed.** Every back on the plate is solid black, and Audubon himself called it Swainson's *Apternus arcticus* (1839). The American Three-toed is 417, figs. 3–4.
- **Plate 229's "Scaup Duck" is the Lesser Scaup.** Audubon wrote in 1844 that the bird "figured in my large plates" was the smaller species.
- **Plate 247's "Velvet Duck" is the White-winged Scoter**, the American daughter of the split; BirdNET still lumps the two, so its label is the Velvet Scoter's.
- **Plate 45, Traill's Flycatcher, can't be split.** Halley (2025) shows the type, this bird, can't be told as Alder or Willow; both rows are `pre-split`, `judged`.
- **Plate 407, the "Dusky Albatros", is the Light-mantled** (`judged`): Audubon describes the skin's pale body against a dark head and a long wedge tail, which the colourist's all-brown plate hides.
- **Plate 394 fig. 2, the "Black-headed Siskin", is the Hooded Siskin** (`judged`), by Audubon's own measurements.
- **Plate 399's "Mourning Warbler" (figs. 4–5) is MacGillivray's Warbler.** Audubon wrote in 1839 that these Columbia River birds were misnamed on the plate, and named them *Sylvia macgillivrayi*. He has no plate of the true Mourning Warbler.
- **Nelson's Sparrow is not on 149.** Wilson's "Sharp-tailed Finch" there is the Saltmarsh Sparrow.
- **Black-throated Diver (346)** is the Pacific Loon on audubon.org and at NYHS. Pitt still says Arctic Loon.
- **Splits since BirdNET's taxonomy:** the old binomial stays with the Old World bird, so Audubon's plates go to the American daughter:
  - Goshawk (141): American Goshawk, *Astur atricapillus*.
  - Yellow Warbler (95): Northern Yellow Warbler, *Setophaga aestiva*.
  - Barn Owl (171): American Barn Owl, *Tyto furcata*.
  - Hudsonian Curlew (237): Hudsonian Whimbrel, *Numenius hudsonicus*.
  - Herring Gull (291): American Herring Gull, *Larus smithsonianus*.
- **Trudeau's Tern (409, fig. 2)** is the Snowy-crowned Tern, *Sterna trudeaui*: the plate is its type. Audubon's New Jersey locality is doubted, not the bird. Figure 1, Havell's Tern, is Forster's.
- **Redpoll (375):** eBird 2025 lumps the redpolls; the plate's Common Redpoll is now "Redpoll".

## Not identified

6 plates have no species here. Each row's `reason` says what is known and what would settle it.

**Disputed birds, left out on purpose rather than guessed:**
- 11, Bird of Washington;
- 55, Cuvier's Kinglet;
- 60, Carbonated Warbler;
- 164, Tawny Thrush: traditionally the Veery, disputed (Halley 2018);
- 184, Mangrove Humming Bird;
- 338, Bemaculated Duck: a hybrid.

Some figures on composite plates are left out for the same reason:
- 400 fig. 4, Townsend's Bunting;
- 434 fig. 2, Small-headed Flycatcher, fig. 3, Blue Mountain Warbler, and fig. 4, Bartram's Vireo (yellow-throated and brown-eyed, so not plainly the Red-eyed Vireo that NYHS and the Boston Public Library give);

**Composite plates** carry one row per species, with its figure key from the legend. Until 1 Oct only the species Featherframe needed had rows; 21 plates gained 32 birds, and 402 now has all five, Kittlitz's Murrelet included (fig. 2, Audubon's "young" Black-throated Guillemot). Prey, such as the ducks under the Great-footed Hawk (16), has no row.
