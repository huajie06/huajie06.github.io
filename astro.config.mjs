import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import tailwind from "@tailwindcss/vite";
import expressiveCode from "astro-expressive-code";

import { pluginLineNumbers } from "@expressive-code/plugin-line-numbers";

export default defineConfig({
  site: "https://huajie06.github.io",
  output: "static",

  integrations: [
    expressiveCode({
      themes: ["catppuccin-macchiato"],
      // Settings must be inside 'defaultProps' to apply to every block

      plugins: [pluginLineNumbers()],
      defaultProps: {
        showLineNumbers: true,
        wrap: false,
      },
      styleOverrides: {
        codeFontSize: "0.9rem",
        // This ensures the gutter (where numbers live) has enough width
        gutterPaddingInline: "1rem",
      },
    }),
    mdx(),
    sitemap(),
  ],

  markdown: {
    syntaxHighlight: false,
  },

  vite: {
    plugins: [tailwind()],
  },
});
