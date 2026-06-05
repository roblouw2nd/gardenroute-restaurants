import {
  loadRestaurants, getUniqueTowns, townSlug,
  restaurantsInCategory, toSlug,
} from '../lib/restaurants.js';
import { CATEGORIES, MIN_COUNT } from '../lib/categories.js';

export async function GET() {
  const restaurants = loadRestaurants();
  const towns = getUniqueTowns(restaurants);
  const siteUrl = 'https://www.gardenroute-restaurants.co.za';
  const now = new Date().toISOString().split('T')[0];

  const staticPages = [
    { url: '/',        priority: '1.0', changefreq: 'weekly'  },
    { url: '/browse',  priority: '0.9', changefreq: 'weekly'  },
    { url: '/eat',     priority: '0.8', changefreq: 'weekly'  },
    { url: '/towns',   priority: '0.8', changefreq: 'monthly' },
    { url: '/map',     priority: '0.6', changefreq: 'monthly' },
    { url: '/about',   priority: '0.5', changefreq: 'monthly' },
    { url: '/submit',  priority: '0.4', changefreq: 'monthly' },
  ];

  // Real, indexable town landing pages (replaces old /browse?town= query URLs)
  const townPages = towns.map(t => ({
    url: `/town/${townSlug(t)}`,
    priority: '0.8',
    changefreq: 'weekly',
  }));

  // Cuisine / feature landing pages (only those with enough restaurants)
  const categoryPages = CATEGORIES
    .filter(c => restaurantsInCategory(restaurants, c.label).length >= MIN_COUNT)
    .map(c => ({
      url: `/eat/${c.slug || toSlug(c.label)}`,
      priority: '0.7',
      changefreq: 'weekly',
    }));

  const restaurantPages = restaurants.map(r => ({
    url: `/${r.slug}`,
    priority: '0.7',
    changefreq: 'weekly',
    lastmod: r.last_updated ? r.last_updated.split('T')[0] : now,
  }));

  const allPages = [...staticPages, ...townPages, ...categoryPages, ...restaurantPages];

  // Normalise to a trailing slash so sitemap URLs match the canonical tags.
  const withSlash = (u) => (u === '/' ? '/' : (u.endsWith('/') ? u : `${u}/`));

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allPages.map(p => `  <url>
    <loc>${siteUrl}${withSlash(p.url)}</loc>
    <lastmod>${p.lastmod || now}</lastmod>
    <changefreq>${p.changefreq}</changefreq>
    <priority>${p.priority}</priority>
  </url>`).join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
