import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://historical-bird-plates.wells.ee",
  trailingSlash: "always",
  integrations: [sitemap({ filter: (page) => page !== "https://historical-bird-plates.wells.ee/404/" })],
});
