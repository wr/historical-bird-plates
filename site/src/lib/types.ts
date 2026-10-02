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

export interface Data {
  folios: Folio[];
  plates: Plate[];
  species: Species[];
}
