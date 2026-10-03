import type { Plate } from "../lib/types";

/** One plate as the wall's script sees it: what to search, filter and sort it by. */
export interface Entry {
  id: string;
  i: number; // place in folio order, across all folios
  f: string; // folio id
  v: string; // "Volume I", "Supplement", or "" for folios numbered straight through
  t: string; // folded search text, padded with spaces so a query word can match a word's start
  fl: string; // flags: m misnamed, x extinct, o open question, s several species
  ord: number | null; // eBird taxonomic order of the first species
  fam: string; // "Owls · Strigidae"
  hue: number | null;
  light: number;
}

export type Arrangement = "folio" | "taxonomy" | "colour";

export interface State {
  q: string;
  folios: string[];
  flags: string[];
  arrange: Arrangement;
}

export interface Group {
  title: string;
  ids: string[];
}

export const FLAGS: Record<string, string> = { m: "Misnamed", x: "Extinct", o: "Open question", s: "Several species" };
const ARRANGEMENTS: Arrangement[] = ["folio", "taxonomy", "colour"];

/** Letters that NFKD leaves whole, in the ASCII spelling a person would type. */
const SPELT: Record<string, string> = { æ: "ae", œ: "oe", ø: "o", ł: "l", ß: "ss" };

/** Lower case, accents and apostrophes gone, æ and œ spelt out, grey spelled gray, anything else a single space. */
export function fold(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[æœøłß]/g, (c) => SPELT[c])
    .replace(/grey/g, "gray").replace(/['’]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

export function entryOf(p: Plate, i: number): Entry {
  const words = [p.printed.name, p.printed.latin, p.printed.caption,
    ...p.species.flatMap((s) => [s.printed_name, s.printed_latin, s.common, s.scientific, s.code])];
  return {
    id: p.id,
    i,
    f: p.folio,
    v: p.group,
    t: ` ${fold([...new Set(words.filter(Boolean))].join(" "))} `,
    fl: (p.misnamed.length ? "m" : "") + (p.extinct ? "x" : "") + (p.open ? "o" : "") + (p.multi ? "s" : ""),
    ord: p.taxon ? p.taxon.order : null,
    fam: p.taxon ? `${p.taxon.family_common} · ${p.taxon.family}` : "",
    hue: p.image ? p.image.hue : null,
    light: p.image ? p.image.light : 1,
  };
}

export function matches(e: Entry, s: State): boolean {
  if (s.folios.length > 0 && !s.folios.includes(e.f)) return false;
  if (!s.flags.every((flag) => e.fl.includes(flag))) return false;
  return fold(s.q).split(" ").filter(Boolean).every((word) => e.t.includes(` ${word}`));
}

/** By hue, which is a circle: reds just below 360° sort with those just above 0°, and open the arrangement. The colourless after, from light to dark. */
export function byColour(a: Entry, b: Entry): number {
  if ((a.hue === null) !== (b.hue === null)) return a.hue === null ? 1 : -1;
  if (a.hue !== null && b.hue !== null) {
    const apart = ((a.hue + 20) % 360) - ((b.hue + 20) % 360);
    if (apart !== 0) return apart;
  }
  return b.light - a.light || a.i - b.i;
}

function runs(sorted: Entry[], title: (e: Entry) => string): Group[] {
  const groups: Group[] = [];
  for (const e of sorted) {
    const t = title(e);
    const last = groups[groups.length - 1];
    if (last && last.title === t) last.ids.push(e.id);
    else groups.push({ title: t, ids: [e.id] });
  }
  return groups;
}

/** Sort the entries and cut them into titled groups. Within one folio, folio order groups by volume. */
export function arrange(entries: Entry[], how: Arrangement, titles: Record<string, string>, within: string | null = null): Group[] {
  if (how === "colour") return [{ title: "By colour", ids: [...entries].sort(byColour).map((e) => e.id) }];
  if (how === "taxonomy") {
    const sorted = [...entries].sort((a, b) => (a.ord ?? Infinity) - (b.ord ?? Infinity) || a.i - b.i);
    return runs(sorted, (e) => e.fam || "Not identified");
  }
  return runs([...entries].sort((a, b) => a.i - b.i), (e) => (within ? e.v || "Plates" : titles[e.f]));
}

export function readState(search: string): State {
  const p = new URLSearchParams(search);
  const how = p.get("arrange") as Arrangement;
  return {
    q: p.get("q") ?? "",
    folios: p.getAll("folio"),
    flags: p.getAll("flag").filter((f) => f in FLAGS),
    arrange: ARRANGEMENTS.includes(how) ? how : "folio",
  };
}

export function writeState(s: State): string {
  const p = new URLSearchParams();
  if (s.q.trim()) p.set("q", s.q.trim());
  for (const f of s.folios) p.append("folio", f);
  for (const f of s.flags) p.append("flag", f);
  if (s.arrange !== "folio") p.set("arrange", s.arrange);
  const query = p.toString();
  return query ? `?${query}` : "";
}

export const isDefault = (s: State): boolean => writeState(s) === "";

export const plural = (n: number, word: string): string => `${n.toLocaleString("en")} ${n === 1 ? word : `${word}s`}`;
