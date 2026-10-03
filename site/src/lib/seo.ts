import { ebird, wikidata } from "./links.ts";
import { plural } from "../scripts/wall-core.ts";
import type { Artist, Credit, Folio, Identification, Plate, Species } from "./types";

const DESCRIPTION = 158;
/** The roles that make the picture; printing and colouring make a contribution. */
const MAKING = new Set(["drew", "lithographed", "engraved", "retouched"]);
const PDM = "https://creativecommons.org/publicdomain/mark/1.0/";

/** Letters only, lower case, grey as gray: how misnamed.py compares a printed name with eBird's. */
export function norm(s: string): string {
  return s.toLowerCase().replace(/grey/g, "gray").replace(/parrakeet/g, "parakeet").replace(/[^a-z]/g, "");
}

/** "A", "A and B", "A, B and C". */
export function joinNames(names: string[]): string {
  return names.length <= 2 ? names.join(" and ") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** "Drew 54 plates and lithographed 52": plates per role, in the order given. */
export function tally(roles: Record<string, number>): string {
  return joinNames(Object.entries(roles).map(([role, n], i) =>
    i ? `${role} ${n.toLocaleString("en")}` : `${role.charAt(0).toUpperCase()}${role.slice(1)} ${plural(n, "plate")}`));
}

/** The plate's identified species, once each, in figure order. */
export function identified(p: Plate): Identification[] {
  const seen = new Set<string>();
  return p.species.filter((s) => s.code && !seen.has(s.code) && seen.add(s.code));
}

/** "Snowy Owl"; "Mallard and Northern Pintail"; "An unidentified bird". */
export function shown(p: Plate): string {
  const names = identified(p).map((s) => s.common);
  return names.length ? joinNames(names) : "An unidentified bird";
}

/** "Gould's The Birds of Europe". */
export function possessive(f: Folio): string {
  return `${f.author.split(" ").pop()}'s ${f.title}`;
}

const lowerFirst = (s: string): string => s.charAt(0).toLowerCase() + s.slice(1);
const named = (ids: Identification[]): string => joinNames(ids.map((s) => `${s.common} (${s.scientific})`));

/** "Plate 427 of Gould's The Birds of Europe: Mediterranean Gull (Ichthyaetus melanocephalus)". */
export function altText(p: Plate, f: Folio): string {
  const ids = identified(p);
  return `${p.label} of ${possessive(f)}: ${ids.length ? named(ids) : `“${p.printed.name}”, not identified`}`;
}

/** "The whole sheet of volume I, plate 1, with its engraved caption". */
export function sheetAlt(p: Plate): string {
  return `The whole sheet of ${lowerFirst(p.label)}, with its engraved caption`;
}

/** The modern name, or the printed name quoted first when it differs. */
export function plateTitle(p: Plate, f: Folio): string {
  const modern = shown(p);
  const printed = p.printed.name;
  const lead = !identified(p).length ? `“${printed}”`
    : printed && norm(printed) !== norm(modern) ? `“${printed}” (${modern})` : modern;
  return `${lead} · ${f.cite}, ${lowerFirst(p.label)}`;
}

/** At most max characters, cut at a word, with an ellipsis when cut. */
export function clip(text: string, max = DESCRIPTION): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max - 1);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:.–-]+$/, "")}…`;
}

export function plateDescription(p: Plate, f: Folio): string {
  const ids = identified(p);
  const why = p.species.map((s) => s.reason).find(Boolean) ?? "";
  return clip(`${ids.length ? named(ids) : "An unidentified bird"} on ${lowerFirst(p.label)} of ${possessive(f)}, ${f.years}. ${why}`);
}

function taxon(s: { scientific: string; common: string; code: string; wikidata: string }): object {
  return {
    "@type": "Taxon", name: s.scientific, alternateName: s.common, taxonRank: "species",
    sameAs: [s.wikidata ? wikidata(s.wikidata) : "", ebird(s.code)].filter(Boolean),
  };
}

function agent(c: Credit, artists: Map<string, Artist>): object {
  const a = artists.get(c.slug);
  return { "@type": a?.kind === "firm" ? "Organization" : "Person", name: c.name, ...(a?.wikidata ? { sameAs: wikidata(a.wikidata) } : {}) };
}

/** Who made the plate, from its credit line, by slug in artists; none when no line was read. */
export function plateJsonLd(p: Plate, f: Folio, url: string, image: string | undefined, artists: Map<string, Artist>): object {
  const making = (c: Credit): boolean => c.roles.some((r) => MAKING.has(r));
  const creator = p.credits.filter(making).map((c) => agent(c, artists));
  const contributor = p.credits.filter((c) => !making(c)).map((c) => agent(c, artists));
  return {
    "@context": "https://schema.org",
    "@type": "VisualArtwork",
    name: p.printed.name || shown(p),
    url,
    ...(image ? { image } : {}),
    artform: "Print",
    artMedium: f.medium,
    ...(creator.length ? { creator } : {}),
    ...(contributor.length ? { contributor } : {}),
    dateCreated: `${f.start}/${f.end}`,
    isPartOf: { "@type": "Book", name: f.title, author: { "@type": "Person", name: f.author } },
    position: p.key,
    about: identified(p).map(taxon),
    license: PDM,
    creditText: p.credit || f.credit,
  };
}

export function speciesTitle(s: Species): string {
  return `${s.common} in nineteenth-century bird plates`;
}

export function speciesDescription(s: Species, folios: Folio[]): string {
  const n = s.plates.length;
  return clip(`${s.common} (${s.scientific}, ${s.family}) on ${n} ${n === 1 ? "plate" : "plates"} of ${joinNames(folios.map(possessive))}, each with its printed name and how it was identified.`);
}

export function speciesJsonLd(s: Species, url: string, image?: string): object {
  return {
    "@context": "https://schema.org",
    ...taxon(s),
    url,
    ...(image ? { image } : {}),
    parentTaxon: { "@type": "Taxon", name: s.family, taxonRank: "family" },
  };
}

export function artistTitle(a: Artist): string {
  return `Plates credited to ${a.name} · Historical bird plates`;
}

export function artistDescription(a: Artist, folios: Folio[]): string {
  return clip(`${a.name} ${lowerFirst(tally(a.roles))} of ${joinNames(folios.map(possessive))}, by their credit lines.`);
}

export function artistJsonLd(a: Artist, url: string): object {
  return {
    "@context": "https://schema.org",
    "@type": a.kind === "firm" ? "Organization" : "Person",
    name: a.name,
    description: a.note,
    url,
    ...(a.wikidata ? { sameAs: wikidata(a.wikidata) } : {}),
  };
}
