import { test } from "node:test";
import assert from "node:assert/strict";
import { arrange, entryOf, fold, matches, readState, writeState, type Entry, type State } from "./wall-core.ts";
import type { Plate } from "../lib/types.ts";

const plate = (over: Record<string, unknown> = {}) => ({
  id: "havell/121", folio: "havell", slug: "121", key: "121", volume: "", plate: "121", group: "", label: "Plate 121",
  printed: { name: "Snowy Owl", latin: "", caption: "", legend: "" },
  species: [{ figure: "", printed_name: "Snowy Owl", printed_latin: "", scientific: "Bubo scandiacus", common: "Snowy Owl",
    code: "snoowl1", slug: "snowy-owl", confidence: "high", form: "", caption_checked: "", reason: "", sources: "",
    wikidata: "", gbif: "", avibase: "", birdnet: "" }],
  misnamed: [], extinct: false, open: false, multi: false,
  taxon: { order: 9000, family: "Strigidae", family_common: "Owls", bird_order: "Strigiformes" },
  image: { thumb: [360, 480], crop: [1198, 1600], sheet: [666, 1000], colour: "#dfdedf", hue: null, light: 0.87 },
  scan: "", original: "", ...over,
}) as unknown as Plate;

const entry = (over: Partial<Entry>): Entry => ({ id: "a", i: 0, f: "havell", v: "", t: " ", fl: "", ord: null, fam: "", hue: null, light: 1, ...over });
const none: State = { q: "", folios: [], flags: [], arrange: "folio" };

test("fold drops accents, apostrophes and case, and spells grey gray", () => {
  assert.equal(fold("Rüppell’s  Grey Warbler!"), "ruppells gray warbler");
});

test("entryOf indexes printed and modern names, Latin and the eBird code", () => {
  const e = entryOf(plate({ printed: { name: "Black-headed Gull", latin: "Larus melanocephalus", caption: "", legend: "" } }), 7);
  assert.equal(e.i, 7);
  for (const words of ["black headed gull", "larus", "snowy owl", "bubo scandiacus", "snoowl1"]) assert.ok(e.t.includes(` ${words}`), words);
  assert.equal(e.fam, "Owls · Strigidae");
  assert.equal(e.hue, null);
});

test("entryOf writes its flags as letters", () => {
  assert.equal(entryOf(plate({ misnamed: [{ name: "x", code: "y" }], extinct: true, open: true, multi: true }), 0).fl, "mxos");
  assert.equal(entryOf(plate(), 0).fl, "");
});

test("every query word must match the start of a word", () => {
  const e = entry({ t: " snowy owl bubo scandiacus " });
  assert.ok(matches(e, { ...none, q: "snow ow" }));
  assert.ok(matches(e, { ...none, q: "  SCANDIACUS " }));
  assert.ok(!matches(e, { ...none, q: "nowy" }));
  assert.ok(!matches(e, { ...none, q: "snowy gull" }));
});

test("folios are alternatives; flags must all hold", () => {
  const e = entry({ f: "gould-asia", fl: "mo" });
  assert.ok(matches(e, { ...none, folios: ["havell", "gould-asia"] }));
  assert.ok(!matches(e, { ...none, folios: ["havell"] }));
  assert.ok(matches(e, { ...none, flags: ["m", "o"] }));
  assert.ok(!matches(e, { ...none, flags: ["m", "x"] }));
});

test("folio order groups by folio, and by volume within one folio", () => {
  const es = [entry({ id: "b", i: 1, f: "gould-asia", v: "Volume I" }), entry({ id: "a", i: 0 }), entry({ id: "c", i: 2, f: "gould-asia", v: "Volume II" })];
  const titles = { havell: "Audubon", "gould-asia": "Asia" };
  assert.deepEqual(arrange(es, "folio", titles), [{ title: "Audubon", ids: ["a"] }, { title: "Asia", ids: ["b", "c"] }]);
  assert.deepEqual(arrange([es[0], es[2]], "folio", titles, "gould-asia").map((g) => g.title), ["Volume I", "Volume II"]);
  assert.deepEqual(arrange([es[1]], "folio", titles, "havell").map((g) => g.title), ["Plates"]);
});

test("taxonomy follows eBird order and puts unidentified plates last", () => {
  const es = [entry({ id: "none", i: 0 }), entry({ id: "owl", i: 1, ord: 9000, fam: "Owls · Strigidae" }),
    entry({ id: "duck", i: 2, ord: 300, fam: "Ducks · Anatidae" }), entry({ id: "owl2", i: 3, ord: 9001, fam: "Owls · Strigidae" })];
  assert.deepEqual(arrange(es, "taxonomy", {}), [
    { title: "Ducks · Anatidae", ids: ["duck"] },
    { title: "Owls · Strigidae", ids: ["owl", "owl2"] },
    { title: "Not identified", ids: ["none"] },
  ]);
});

test("colour sorts by hue, then the colourless from light to dark", () => {
  const es = [entry({ id: "grey", light: 0.4 }), entry({ id: "green", hue: 90 }), entry({ id: "white", light: 0.9 }), entry({ id: "red", hue: 5 })];
  assert.deepEqual(arrange(es, "colour", {})[0].ids, ["red", "green", "white", "grey"]);
});

test("colour treats hue as a circle: reds either side of 0° sort together, first", () => {
  const es = [entry({ id: "orange", hue: 30 }), entry({ id: "red-hi", hue: 356 }), entry({ id: "blue", hue: 220 }), entry({ id: "red-lo", hue: 4 })];
  assert.deepEqual(arrange(es, "colour", {})[0].ids, ["red-hi", "red-lo", "orange", "blue"]);
});

test("state survives the query string", () => {
  const s: State = { q: "owl", folios: ["havell"], flags: ["m"], arrange: "taxonomy" };
  assert.equal(writeState(s), "?q=owl&folio=havell&flag=m&arrange=taxonomy");
  assert.deepEqual(readState(writeState(s)), s);
  assert.equal(writeState(none), "");
  assert.deepEqual(readState("?arrange=nonsense&flag=z"), none);
});
