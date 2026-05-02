import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://gardenroute-restaurants.co.za',
  integrations: [
    tailwind(),
  ],
});
