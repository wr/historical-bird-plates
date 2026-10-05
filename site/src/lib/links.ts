export const REPO = "https://github.com/wr/historical-bird-plates";
export const FEATHERFRAME = "https://shop.wells.ee/products/featherframe/";

export const ebird = (code: string): string => `https://ebird.org/species/${code}`;
export const wikidata = (q: string): string => `https://www.wikidata.org/wiki/${q}`;
export const gbif = (id: string): string => `https://www.gbif.org/species/${id}`;
export const avibase = (id: string): string => `https://avibase.bsc-eoc.org/species.jsp?avibaseid=${id}`;

/** The link text for a plate's source scan, named for the site it is on. */
export function scanLabel(url: string): string {
  const host = URL.canParse(url) ? new URL(url).hostname : "";
  const on = (domain: string): boolean => host === domain || host.endsWith(`.${domain}`);
  if (on("audubon.org")) return "The plate at audubon.org";
  if (on("wikimedia.org")) return "The scan on Wikimedia Commons";
  if (on("biodiversitylibrary.org")) return "The scan at the Biodiversity Heritage Library";
  return host ? `The scan at ${host}` : "The scan";
}

/** The outside pages for a species, in a fixed order, skipping IDs it doesn't have. */
export function outlinks(x: { code: string; wikidata: string; gbif: string; avibase: string }): { label: string; href: string }[] {
  const links: { label: string; href: string }[] = [];
  if (x.code) links.push({ label: "eBird", href: ebird(x.code) });
  if (x.wikidata) links.push({ label: "Wikidata", href: wikidata(x.wikidata) });
  if (x.gbif) links.push({ label: "GBIF", href: gbif(x.gbif) });
  if (x.avibase) links.push({ label: "Avibase", href: avibase(x.avibase) });
  return links;
}
