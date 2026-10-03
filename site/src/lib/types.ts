export interface Folio {
  id: string;
  author: string;
  title: string;
  years: string;
  start: number;
  end: number;
  cite: string;
  short: string;
  medium: string;
  release: string;
  intro: string;
  credit: string;
  plates: number;
  readme: string;
  /** The README's "Who made the plates". */
  makers: string;
  images: string;
}

export interface Identification {
  figure: string;
  printed_name: string;
  printed_latin: string;
  scientific: string;
  common: string;
  code: string;
  slug: string;
  confidence: string;
  form: string;
  caption_checked: string;
  reason: string;
  sources: string;
  wikidata: string;
  gbif: string;
  avibase: string;
  birdnet: string;
}

export interface PlateImage {
  thumb: [number, number];
  crop: [number, number];
  sheet: [number, number];
  colour: string;
  hue: number | null;
  light: number;
}

/** One name in a plate's credit line, with every role the line gives it. */
export interface Credit {
  name: string;
  slug: string;
  roles: string[];
}

export interface Plate {
  id: string;
  folio: string;
  slug: string;
  key: string;
  volume: string;
  plate: string;
  group: string;
  label: string;
  printed: { name: string; latin: string; caption: string; legend: string };
  species: Identification[];
  misnamed: { name: string; code: string }[];
  extinct: boolean;
  open: boolean;
  multi: boolean;
  taxon: { order: number; family: string; family_common: string; bird_order: string } | null;
  image: PlateImage | null;
  /** The credit lines as engraved, joined with " | "; empty when none could be read. */
  imprint: string;
  credits: Credit[];
  /** Why no credit line was read; empty when one was. */
  imprint_note: string;
  /** The scan's credit when it isn't the folio's; empty otherwise. */
  credit: string;
  scan: string;
  original: string;
}

export interface Species {
  code: string;
  slug: string;
  common: string;
  scientific: string;
  family: string;
  family_common: string;
  order: string;
  taxon_order: number;
  extinct: boolean;
  wikidata: string;
  gbif: string;
  avibase: string;
  birdnet: string;
  plates: string[];
  printed_as: string[];
}

/** A person or firm named in the credit lines, from artists.csv. */
export interface Artist {
  name: string;
  slug: string;
  kind: "person" | "firm";
  wikidata: string;
  note: string;
  plates: string[];
  folios: string[];
  /** Plates per role, in credits.py's order of roles. */
  roles: Record<string, number>;
}

export interface Data {
  folios: Folio[];
  plates: Plate[];
  species: Species[];
  artists: Artist[];
}
