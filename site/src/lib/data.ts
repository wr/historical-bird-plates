import raw from "../data/plates.json";
import type { Data, Folio, Plate } from "./types";
import { entryOf } from "../scripts/wall-core";

const data = raw as unknown as Data;

export const { folios, plates, species } = data;
export const folioById = new Map(folios.map((f) => [f.id, f]));
export const plateById = new Map(plates.map((p) => [p.id, p]));
export const speciesByCode = new Map(species.map((s) => [s.code, s]));
export const entries = plates.map(entryOf);

export const SITE = "https://wr.github.io";
const base = import.meta.env.BASE_URL; // "/historical-bird-plates/"

/** A path inside the site, with the base: href("species/") is "/historical-bird-plates/species/". */
export const href = (path = ""): string => base + path.replace(/^\/+/, "");
export const plateHref = (p: Plate): string => href(`${p.folio}/${p.slug}/`);
export const speciesHref = (s: { slug: string }): string => href(`species/${s.slug}/`);
export const folioHref = (f: { id: string }): string => href(`${f.id}/`);
export const imageSrc = (p: Plate, cut: "thumb" | "crop" | "sheet"): string => href(`img/${p.folio}/${p.slug}-${cut}.webp`);
export const absolute = (path: string): string => new URL(path, SITE).href;
export const folioOf = (p: Plate): Folio => folioById.get(p.folio)!;
