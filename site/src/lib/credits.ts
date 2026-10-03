/** A credit line's lines, left to right. */
export const lines = (imprint: string): string[] => (imprint ? imprint.split(" | ") : []);

/** "credit lines cut off: …" as a sentence: a capital and a stop. */
export function sentence(note: string): string {
  const s = note.charAt(0).toUpperCase() + note.slice(1);
  return /[.!?]$/.test(s) ? s : `${s}.`;
}
