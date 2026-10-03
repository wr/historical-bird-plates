import { test } from "node:test";
import assert from "node:assert/strict";
import { lines, sentence } from "./credits.ts";

test("a credit line splits at its bars", () => {
  assert.deepEqual(lines("E. Lear del et lithog. | Printed by C. Hullmandel."), ["E. Lear del et lithog.", "Printed by C. Hullmandel."]);
  assert.deepEqual(lines(""), []);
});

test("a note becomes a sentence", () => {
  assert.equal(sentence("credit lines cut off: the sheet ends in the caption"), "Credit lines cut off: the sheet ends in the caption.");
  assert.equal(sentence("No line."), "No line.");
});
