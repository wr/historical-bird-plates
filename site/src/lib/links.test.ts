import { test } from "node:test";
import assert from "node:assert/strict";
import { scanLabel } from "./links.ts";

test("a scan link is named for the site it is on", () => {
  assert.equal(scanLabel("https://www.audubon.org/sites/default/files/boa_plates/plate_121_snowy_owl.jpg"),
    "The plate at audubon.org");
  assert.equal(scanLabel("https://upload.wikimedia.org/wikipedia/commons/d/dd/165_Bachmans_Finch.jpg"),
    "The scan on Wikimedia Commons");
  assert.equal(scanLabel("https://www.biodiversitylibrary.org/page/42173701"),
    "The scan at the Biodiversity Heritage Library");
});

test("any other site is named by its host, and no URL by nothing more", () => {
  assert.equal(scanLabel("https://example.org/plate.jpg"), "The scan at example.org");
  assert.equal(scanLabel("https://notaudubon.org/plate.jpg"), "The scan at notaudubon.org");
  assert.equal(scanLabel(""), "The scan");
});
