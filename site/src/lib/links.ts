export const REPO = "https://github.com/wr/historical-bird-plates";

export const ebird = (code: string): string => `https://ebird.org/species/${code}`;
export const wikidata = (q: string): string => `https://www.wikidata.org/wiki/${q}`;
export const gbif = (id: string): string => `https://www.gbif.org/species/${id}`;
export const avibase = (id: string): string => `https://avibase.bsc-eoc.org/species.jsp?avibaseid=${id}`;

/** The outside pages for a species, in a fixed order, skipping IDs it doesn't have. */
export function outlinks(x: { code: string; wikidata: string; gbif: string; avibase: string }): { label: string; href: string }[] {
  const links: { label: string; href: string }[] = [];
  if (x.code) links.push({ label: "eBird", href: ebird(x.code) });
  if (x.wikidata) links.push({ label: "Wikidata", href: wikidata(x.wikidata) });
  if (x.gbif) links.push({ label: "GBIF", href: gbif(x.gbif) });
  if (x.avibase) links.push({ label: "Avibase", href: avibase(x.avibase) });
  return links;
}
