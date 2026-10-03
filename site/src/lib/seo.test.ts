import { test } from "node:test";
import assert from "node:assert/strict";
import { altText, artistDescription, artistJsonLd, clip, plateDescription, plateJsonLd, plateTitle, sheetAlt, shown, tally } from "./seo.ts";
import type { Artist, Folio, Plate } from "./types.ts";

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
  multi: false, taxon: null, image: null, imprint: "", credits: [], imprint_note: "", credit: "", scan: "", original: "",
  ...over,
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
  const ld = plateJsonLd(plate(), europe, "https://x/", "https://x/i.webp", new Map()) as Record<string, any>;
  assert.equal(ld["@type"], "VisualArtwork");
  assert.equal(ld.dateCreated, "1832/1837");
  assert.equal(ld.image, "https://x/i.webp");
  assert.deepEqual(ld.about[0].sameAs, ["https://www.wikidata.org/wiki/Q27064", "https://ebird.org/species/medgul1"]);
  assert.equal(ld.license, "https://creativecommons.org/publicdomain/mark/1.0/");
  assert.equal(ld.creditText, europe.credit);
});

const artist = (name: string, kind: string, wikidata = "") =>
  ({ name, slug: name.toLowerCase().replace(/[^a-z]+/g, "-"), kind, wikidata, note: "", plates: [], folios: [], roles: {} }) as Artist;
const artists = new Map([
  artist("Edward Lear", "person", "Q309759"), artist("Charles Joseph Hullmandel", "person", "Q376691"),
  artist("Robert Havell & Son", "firm"),
].map((a) => [a.slug, a]));
const credit = (a: string, roles: string[]) => ({ name: a, slug: a.toLowerCase().replace(/[^a-z]+/g, "-"), roles });

test("JSON-LD names who made the plate as creators, and the printer as a contributor", () => {
  const p = plate({ credits: [credit("Edward Lear", ["drew", "lithographed"]), credit("Charles Joseph Hullmandel", ["printed"])] });
  const ld = plateJsonLd(p, europe, "https://x/", undefined, artists) as Record<string, any>;
  assert.deepEqual(ld.creator, [{ "@type": "Person", name: "Edward Lear", sameAs: "https://www.wikidata.org/wiki/Q309759" }]);
  assert.deepEqual(ld.contributor, [{ "@type": "Person", name: "Charles Joseph Hullmandel", sameAs: "https://www.wikidata.org/wiki/Q376691" }]);
});

test("a firm that engraved and printed is an Organization, and a creator", () => {
  const p = plate({ credits: [credit("Robert Havell & Son", ["engraved", "printed", "coloured"])] });
  const ld = plateJsonLd(p, europe, "https://x/", undefined, artists) as Record<string, any>;
  assert.deepEqual(ld.creator, [{ "@type": "Organization", name: "Robert Havell & Son" }]);
  assert.equal(ld.contributor, undefined);
});

test("a plate with no credit line read names no creator, not the folio's author", () => {
  const ld = plateJsonLd(plate({ credits: [] }), europe, "https://x/", undefined, artists) as Record<string, any>;
  assert.equal(ld.creator, undefined);
  assert.equal(ld.isPartOf.author.name, "John Gould");
});

test("a plate's own scan credit replaces the folio's in JSON-LD", () => {
  const credit = "University of Pittsburgh, via Wikimedia Commons.";
  const ld = plateJsonLd(plate({ credit }), europe, "https://x/", undefined, new Map()) as Record<string, any>;
  assert.equal(ld.creditText, credit);
});

test("an artist's description says what they did, and where", () => {
  const lear = { ...artists.get("edward-lear")!, note: "Artist and lithographer", roles: { drew: 54, lithographed: 52 } };
  const australia = { ...europe, id: "gould-australia", title: "The Birds of Australia" } as Folio;
  assert.equal(artistDescription(lear, [europe, australia]),
    "Edward Lear drew 54 plates and lithographed 52 of Gould's The Birds of Europe and Gould's The Birds of Australia, by their credit lines.");
});

test("an artist's JSON-LD is a Person or an Organization, the same as Wikidata's", () => {
  const ld = artistJsonLd(artists.get("edward-lear")!, "https://x/") as Record<string, any>;
  assert.deepEqual([ld["@type"], ld.name, ld.url, ld.sameAs], ["Person", "Edward Lear", "https://x/", "https://www.wikidata.org/wiki/Q309759"]);
  const firm = artistJsonLd(artists.get("robert-havell-son")!, "https://x/") as Record<string, any>;
  assert.equal(firm["@type"], "Organization");
  assert.equal(firm.sameAs, undefined);
});

test("plates per role, the first with its noun", () => {
  assert.equal(tally({ printed: 411 }), "Printed 411 plates");
  assert.equal(tally({ drew: 1, lithographed: 1 }), "Drew 1 plate and lithographed 1");
  assert.equal(tally({ engraved: 411, retouched: 4, printed: 1393, coloured: 393 }),
    "Engraved 411 plates, retouched 4, printed 1,393 and coloured 393");
});
