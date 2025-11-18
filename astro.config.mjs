import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwind from '@tailwindcss/vite'; // <--- Import from @tailwindcss/vite

export default defineConfig({
  site: 'https://huajie06.github.io',
  output: 'static',

  integrations: [
    mdx(),
    sitemap(),
    // Remove "tailwind()" from here!
  ],

  // Add this new section:
  vite: {
    plugins: [tailwind()],
  },
});