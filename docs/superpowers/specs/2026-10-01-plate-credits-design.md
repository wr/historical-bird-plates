# Plate credits: who drew, lithographed, engraved and printed each plate

2026-10-01 · design approved in conversation · status: spec, awaiting review

## Why

A reader of the r/birding announcement pointed out that many plates published under John Gould's name were drawn by others: Elizabeth Gould was the principal artist of his early works, and Edward Lear, H. C. Richter, Joseph Wolf and William Hart drew and lithographed many more. The dataset credits none of them. Worse, `tools/quickstatements.py` gives every Gould plate `creator (P170): John Gould` and every Havell plate `creator: John James Audubon`, and about 1,700 plate items made from this repo are now on Wikidata saying so (2026-10-01: Europe 392, Australia 558, Supplement 76, Asia 269, Great Britain 7, Havell 399).

Every plate carries its own credit line, engraved below the art: on Gould's, the artist bottom left and the printer bottom right ("Drawn on Stone by E. Lear | Printed by C. Hullmandel"); on Havell's, "Drawn from nature by J.J. Audubon F.R.S. F.L.S." and "Engraved, Printed & Coloured by R. Havell". The credit can be read plate by plate, as the captions were.

## Scope

- All five folios: `havell`, `gould-europe`, `gould-australia`, `gould-asia`, `gould-britain`, about 2,460 plates.
- **Evidence:** the plate's own credit line is the per-plate record. Nothing per plate is claimed beyond its words. What the credit lines don't show (who sketched and who finished a jointly credited plate; Audubon's background and plant artists) goes in each folio's README, cited.
- **Wikidata:** new items get creators from the credit line, and a correction batch fixes the items this repo already made.
- **The commenter** stays anonymous.

Out of scope: per-plate attributions from the literature beyond the credit line, creating Wikidata items for printers that have none, and editing plate items this repo didn't create.

## Data model

### `plates.csv`: new column `imprint`

- The plate's credit lines verbatim, in reading order left to right, joined with ` | ` (the idiom of Havell's `legend`). Example: `Drawn on Stone by E. Lear | Printed by C. Hullmandel`.
- Spelling, abbreviations, capitals and punctuation as engraved; whitespace normalised; superscripts written inline (`Edinr`, `Junr`).
- The caption itself (bird name, Latin, legend) is not part of `imprint`.
- **Empty** only when no credit line can be read on the sheet or the BHL scan. The reason goes in `notes` (`credit line cut off by the binding`, `no credit line engraved`, …).
- Placed after the caption columns: after `legend` in `havell`, after `caption_latin` in the Gould folios.

### `credits.csv`, per folio, generated

One row per plate × name × role.

| Column | |
|---|---|
| `volume` | where the folio numbers per volume (*Australia*, *Great Britain*, *Asia*), as in `plates.csv` |
| `plate` | as in `plates.csv` |
| `name` | the person or firm, a key into `artists.csv` |
| `role` | `drew`, `lithographed`, `engraved`, `retouched`, `printed` or `coloured` |
| `as_printed` | the name as the plate gives it; both rows from "J. & E. Gould" carry `J. & E. Gould` |

- Written by `tools/credits.py` from `imprint`, never edited by hand.
- **Phrase table:** `credits.py` holds an explicit table of the credit-line wordings that occur and the roles each gives: `del.` → drew; `lith.` or `on Stone` → lithographed; `Drawn from Nature & on Stone by` → drew + lithographed; `Drawn on Stone by` → lithographed; `Imp.` or `Printed by` → printed; `Engraved by` → engraved; `Retouched by` → retouched; `Engraved, Printed & Coloured by` → engraved + printed + coloured. It also holds a table of name forms (`J. & E. Gould` → John Gould, Elizabeth Gould; `H.C. Richter`, `H. C. Richter` → Henry Constantine Richter; …).
- A wording or name form not in the tables is an error naming the plate. Every variant is mapped deliberately, never guessed.
- The tables are built from the wordings actually found in the reading pass.
- **Joint credits stay joint:** "J. Gould & H.C. Richter del. et lith." gives both people both `drew` and `lithographed`, because that is all the plate says. The README explains the usual division of labour.

### `artists.csv`, at the root

| Column | |
|---|---|
| `name` | full name as used in `credits.csv` (`Elizabeth Gould`, `Henry Constantine Richter`, `Hullmandel & Walton`) |
| `kind` | `person` or `firm` |
| `wikidata` | QID, or blank if Wikidata has no item |
| `note` | one line: who they were, in this dataset's terms |

Known items, checked 2026-10-01: John Gould Q313787, Elizabeth Gould Q253875, Edward Lear Q309759, Henry Constantine Richter Q1567083, Joseph Wolf Q1708274, William Matthew Hart Q8015234, Charles Joseph Hullmandel Q376691, Hullmandel & Walton Q23872817, Mintern Brothers Q47008735, John James Audubon Q182882, Robert Havell Jr. Q2157495, William Home Lizars Q1616131. "Walter" and "Walter & Cohn" have none. Others are added as the reading finds them, each QID checked by label and description before it goes in.

### `datapackage.json`

- Each `plates` resource gains the `imprint` field.
- New resources: `<folio>-credits` for each folio and `artists`, with `role` and `kind` as enums, and foreign keys `credits.name` → `artists.name` and `credits.(volume, plate)` → `plates`.

## Reading the credit lines

1. **Locate and crop.** Script: for each sheet in `historical-bird-plates-assets/<release>/`, find the lowest lines of text below the art, and crop the left and right credit lines (and any centred one) at full resolution. Lines are found by ink rows, not a fixed band: Europe 52's sits outside a fixed bottom 14%.
2. **Draft.** macOS Vision OCR on each crop, matched to the nearest wording in the growing phrase table. A draft only.
3. **Read by eye, every plate.** Contact sheets of ~16 crops, grouped by drafted wording, so an odd one stands out. Each `imprint` is the text read off the crop. Every crop where the reading differs from the draft is looked at again.
4. **Hard cases.** Faint, cut or misplaced lines are re-read from the unaltered BHL JPEG 2000 (`scan_url`; for Havell, `image_url`) at full resolution with contrast raised. Still unreadable: `imprint` empty, reason in `notes`.
5. **Asia.** Its 530 sheets (3.5 GB) are downloaded from the `gould-asia-v1` release into `historical-bird-plates-assets/gould-asia-v1/` first. Great Britain is read from `gould-britain-v2`.
6. **Working record.** Each folio's `sources/imprints.csv` keeps one row per plate: `volume`, `plate`, `leaf`, crop boxes, `ocr` draft, `read` (`eye` or `scan`), `note`. Like `plate-leaves.csv`, it is the record of how the column was made.
7. **Sanity check.** Per-folio totals by name and role are compared with the literature: Lear's plates in *Europe* (about 68 are usually cited); Elizabeth Gould's in *Australia* and where Richter takes over after her death in 1841; the split of *Asia* and *Great Britain* between Gould, Wolf, Richter and Hart. A total that differs from the literature is explained in the folio README, never adjusted.

## Wikidata

### How a credit is stated

For each plate item:

- **Creator:** each name with a role of `drew`, `lithographed`, `engraved` or `retouched` gets `P170 creator`, with qualifier `P3831 object of statement has role`, one per role: drew → draftsperson Q15296811; lithographed → lithographer Q16947657; engraved → engraver Q329439. The `retouched` and `coloured` role items are chosen and checked during implementation; if Wikidata has no fitting item, that role is left off rather than approximated.
- **Printer:** a `printed` name with a QID gets `P872 printed by`. A firm with no item gets no statement.
- **References:** every creator and printer statement is referenced with `S854` (the plate's scan: BHL `page_url`, or Havell's `image_url`) and `S1683` quotation, `en:` + the `imprint` text.

### New items

`quickstatements.py` reads `credits.csv` and `artists.csv` and writes these statements in place of the fixed `LAST P170 {artist}`. A plate with an empty `imprint` gets no creator statement.

### Correction batch: `quickstatements.py FOLIO --fix-creators`

- **Targets:** plate items this repo created, found as items `part of` the work whose `depicts` statements are referenced to this repository's URL. Items made by others are not touched.
- **Per item:**
  - Every credited creator is added with its roles and references. Where the item already has `P170` with that value, QuickStatements merges the qualifiers and reference onto the existing statement.
  - Where the credit line does not name John Gould (or John James Audubon), the old `P170` statement is removed, but only if it carries no reference (this repo never referenced its `P170` statements). A referenced one is someone else's claim and stays; the script reports it.
  - The printer's `P872` is added.
  - A plate with an empty `imprint` is skipped and reported.
- **Output:** a QuickStatements V1 batch, split by `--chunk` as today. Expected size about 5,000–7,000 edits.
- Wells reviews and runs it. Nothing is sent to Wikidata from the tools.
- Reads use the Wikidata API (as `existing()` does), because the query service can lag.

## READMEs

- **Each folio README** gets a section "Who made the plates":
  - what the credit lines say, with counts by name and role;
  - what they don't show, cited to the standard sources (Sauer's Gould bibliography; Tree, *The Ruling Passion of John Gould*; McEvey on Elizabeth Gould; Hyman, *Edward Lear's Birds*; for Havell, Audubon's *Ornithological Biography* and the Audubon literature).
  - Gould folios: John's sketches and Elizabeth's finished drawings and lithographs; Lear in *Europe*; Richter after 1841; Wolf and Hart later; Sharpe completing *Asia* after Gould's death.
  - Havell: Lizars engraving the first plates, the Havells; Joseph Mason, George Lehman and Maria Martin (backgrounds and plants) and John Woodhouse Audubon, none of whom the plates name.
- **Root README:**
  - the Tables section adds `credits.csv` and `artists.csv` and the `imprint` column;
  - the folio list and the opening say who drew the plates;
  - the Acknowledgements thank a reader of the r/birding announcement, unnamed, for pointing out that Gould's plates need their artists credited.
- **`CITATION.cff` and `.zenodo.json`:** abstract mentions plate credits.

## Validation and tests

- **`tools/validate.py`:**
  - `credits.csv` equals what `credits.py` would write from `imprint`;
  - every `credits.name` is in `artists.csv`;
  - every `artists.wikidata` is a well-formed QID;
  - `role` and `kind` are in their enums;
  - every plate with a non-empty `imprint` has at least one credit;
  - every plate with an empty `imprint` has a note.
- **`tools/test_credits.py`** (in CI next to `test_identify.py`):
  - phrase parsing for each wording found;
  - joint credits;
  - unknown wording and unknown names raising;
  - the correction batch on a fixture item: adds roles to an existing `P170`, removes an unreferenced `P170`, keeps a referenced one, skips an empty `imprint`.

## Order of work

1. `artists.csv`, `credits.py` with its tables, `test_credits.py`, schema and validator, against a handful of hand-read plates.
2. Reading pass, folio by folio: Europe, Australia, Great Britain, Asia, Havell. `imprint` filled, `sources/imprints.csv` written, `credits.csv` generated, sanity check.
3. `quickstatements.py`: creators for new items, then `--fix-creators`; dry-run output reviewed.
4. READMEs, citation metadata.
