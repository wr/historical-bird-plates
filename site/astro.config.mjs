import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://wr.github.io",
  base: "/historical-bird-plates",
  trailingSlash: "always",
  integrations: [sitemap({ filter: (page) => page !== "https://wr.github.io/historical-bird-plates/404/" })],
});
