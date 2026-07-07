import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://www.gardenroute-restaurants.co.za',
  // Multilingual: English at the root (existing URLs unchanged), others prefixed.
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'af', 'de', 'fr', 'es', 'pt'],
    routing: {
      prefixDefaultLocale: false,   // /  (en),  /af/…, /de/…, /fr/…, /es/…, /pt/…
    },
  },
  integrations: [
    tailwind(),
  ],
});
