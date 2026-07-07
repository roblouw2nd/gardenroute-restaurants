import {
  loadRestaurants, getUniqueTowns, townSlug,
  restaurantsInCategory, restaurantsInTown, toSlug, openInTownOn,
  translatedLangs,
} from '../lib/restaurants.js';
import { CATEGORIES, MIN_COUNT, TOWN_MIN_COUNT, OPEN_DAYS, OPEN_MIN_COUNT } from '../lib/categories.js';
import { LOCALES, DEFAULT_LOCALE } from '../i18n/utils.js';

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

  // Town-scoped programmatic pages (town×category + open-on-day), same gates
  // as site/src/pages/town/[town]/[category].astro
  const inCategory = (r, c) => (r.cuisine_types || []).includes(c.label) || (r.tags || []).includes(c.label);
  const townCategoryPages = [];
  for (const t of towns) {
    const inTown = restaurantsInTown(restaurants, t);
    for (const c of CATEGORIES) {
      if (inTown.filter(r => inCategory(r, c)).length >= TOWN_MIN_COUNT) {
        townCategoryPages.push({ url: `/town/${townSlug(t)}/${c.slug || toSlug(c.label)}`, priority: '0.7', changefreq: 'weekly' });
      }
    }
    for (const d of OPEN_DAYS) {
      if (openInTownOn(restaurants, t, d).length >= OPEN_MIN_COUNT) {
        townCategoryPages.push({ url: `/town/${townSlug(t)}/open-on-${d}`, priority: '0.6', changefreq: 'weekly' });
      }
    }
  }

  // Blog / guides
  const postModules = import.meta.glob('./blog/*.md', { eager: true });
  const blogPages = [
    { url: '/blog', priority: '0.7', changefreq: 'weekly' },
    ...Object.values(postModules).map(m => ({
      url: m.url,
      priority: '0.7',
      changefreq: 'monthly',
      lastmod: String(m.frontmatter.updatedDate || m.frontmatter.pubDate).slice(0, 10),
    })),
  ];

  const restaurantPages = restaurants.map(r => ({
    url: `/${r.slug}`,
    priority: '0.7',
    changefreq: 'weekly',
    lastmod: r.last_updated ? r.last_updated.split('T')[0] : now,
  }));

  // Localized pages (mirror the gates in src/pages/[lang]/…)
  const nonDefault = LOCALES.filter(l => l !== DEFAULT_LOCALE);
  const localizedPages = [
    // Town hubs exist for every locale
    ...nonDefault.flatMap(l => towns.map(t => ({
      url: `/${l}/town/${townSlug(t)}`, priority: '0.6', changefreq: 'weekly',
    }))),
    // Restaurant pages only where a translation exists
    ...restaurants.flatMap(r => translatedLangs(r.slug).map(l => ({
      url: `/${l}/${r.slug}`, priority: '0.5', changefreq: 'weekly',
      lastmod: r.last_updated ? r.last_updated.split('T')[0] : now,
    }))),
  ];

  const allPages = [...staticPages, ...townPages, ...categoryPages, ...townCategoryPages, ...blogPages, ...restaurantPages, ...localizedPages];

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
