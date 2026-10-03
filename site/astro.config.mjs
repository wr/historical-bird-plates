import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { copyFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

/** /sitemap.xml, the address crawlers try first: the list of URLs itself while it fits in one file, else the index. */
const sitemapXml = {
  name: "sitemap-xml",
  hooks: {
    "astro:build:done": async ({ dir }) => {
      const out = fileURLToPath(dir);
      const parts = (await readdir(out)).filter((f) => /^sitemap-\d+\.xml$/.test(f));
      await copyFile(out + (parts.length === 1 ? parts[0] : "sitemap-index.xml"), out + "sitemap.xml");
    },
  },
};

export default defineConfig({
  site: "https://historical-bird-plates.wells.ee",
  trailingSlash: "always",
  integrations: [sitemap({ filter: (page) => page !== "https://historical-bird-plates.wells.ee/404/" }), sitemapXml],
});
