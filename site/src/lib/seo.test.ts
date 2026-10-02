import { test } from "node:test";
import assert from "node:assert/strict";
import { altText, clip, plateDescription, plateJsonLd, plateTitle, sheetAlt, shown } from "./seo.ts";
import type { Folio, Plate } from "./types.ts";

const europe = {
  id: "gould-europe", author: "John Gould", title: "The Birds of Europe", years: "1832–37", start: 1832, end: 1837,
  cite: "Gould, The Birds of Europe", short: "Europe", medium: "Hand-coloured lithograph", release: "gould-europe-v1",
  intro: "", credit: "Smithsonian Libraries and Archives, via the Biodiversity Heritage Library.", plates: 449,
  readme: "", images: "",
} as Folio;

const ident = (over: Record<string, unknown> = {}) => ({
  figure: "", printed_name: "", printed_latin: "", scientific: "Ichthyaetus melanocephalus",
  common: "Mediterranean Gull", code: "medgul1", slug: "mediterranean-gull", confidence: "high", form: "",
  caption_checked: "yes", reason: "Gould's Black-headed Gull is the Mediterranean Gull: black hood, white primaries.",
  sources: "", wikidata: "Q27064", gbif: "", avibase: "", birdnet: "", ...over,
});

const plate = (over: Record<string, unknown> = {}) => ({
  id: "gould-europe/427", folio: "gould-europe", slug: "427", key: "427", volume: "V", plate: "427", group: "",
  label: "Plate 427", printed: { name: "Black-headed Gull", latin: "Larus melanocephalus", caption: "", legend: "" },
  species: [ident()], misnamed: [{ name: "Black-headed Gull", code: "bkhgul" }], extinct: false, open: false,
  multi: false, taxon: null, image: null, credit: "", scan: "", original: "", ...over,
}) as unknown as Plate;

test("a printed name that differs leads, quoted, with the modern name after", () => {
  assert.equal(plateTitle(plate(), europe), "“Black-headed Gull” (Mediterranean Gull) · Gould, The Birds of Europe, plate 427");
});

test("a printed name that agrees, grey and gray alike, is not repeated", () => {
  const p = plate({ printed: { name: "Grey Heron", latin: "", caption: "", legend: "" }, species: [ident({ common: "Gray Heron", code: "graher1" })] });
  assert.equal(plateTitle(p, europe), "Gray Heron · Gould, The Birds of Europe, plate 427");
});

test("several species are named once each, joined with and", () => {
  const p = plate({ species: ["A", "B", "C", "A"].map((n) => ident({ common: n, code: n })) });
  assert.equal(shown(p), "A, B and C");
});

test("an unidentified plate is named by its printed name", () => {
  const p = plate({ printed: { name: "Bird of Washington", latin: "", caption: "", legend: "" }, species: [ident({ common: "", scientific: "", code: "" })] });
  assert.equal(plateTitle(p, europe), "“Bird of Washington” · Gould, The Birds of Europe, plate 427");
});

test("a description stops at a word, under 160 characters", () => {
  const d = plateDescription(plate({ species: [ident({ reason: "word ".repeat(80) })] }), europe);
  assert.ok(d.length <= 158, String(d.length));
  assert.ok(d.startsWith("Mediterranean Gull (Ichthyaetus melanocephalus) on plate 427 of Gould's The Birds of Europe, 1832–37. "), d);
  assert.ok(d.endsWith("word…"), d);
  assert.equal(clip("short"), "short");
});

test("alt text names the plate, the folio and the bird", () => {
  assert.equal(altText(plate(), europe), "Plate 427 of Gould's The Birds of Europe: Mediterranean Gull (Ichthyaetus melanocephalus)");
});

test("the full sheet's alt text keeps a volume's roman numeral", () => {
  assert.equal(sheetAlt(plate({ label: "Volume I, plate 1" })), "The whole sheet of volume I, plate 1, with its engraved caption");
  assert.equal(sheetAlt(plate()), "The whole sheet of plate 427, with its engraved caption");
});

test("JSON-LD is a VisualArtwork about a Taxon", () => {
  const ld = plateJsonLd(plate(), europe, "https://x/", "https://x/i.webp") as Record<string, any>;
  assert.equal(ld["@type"], "VisualArtwork");
  assert.equal(ld.dateCreated, "1832/1837");
  assert.equal(ld.image, "https://x/i.webp");
  assert.deepEqual(ld.about[0].sameAs, ["https://www.wikidata.org/wiki/Q27064", "https://ebird.org/species/medgul1"]);
  assert.equal(ld.license, "https://creativecommons.org/publicdomain/mark/1.0/");
  assert.equal(ld.creditText, europe.credit);
});

test("a plate's own scan credit replaces the folio's in JSON-LD", () => {
  const credit = "University of Pittsburgh, via Wikimedia Commons.";
  const ld = plateJsonLd(plate({ credit }), europe, "https://x/") as Record<string, any>;
  assert.equal(ld.creditText, credit);
});
