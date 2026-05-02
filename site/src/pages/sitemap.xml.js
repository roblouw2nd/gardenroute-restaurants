import { loadRestaurants, getUniqueTowns } from '../lib/restaurants.js';

export async function GET() {
  const restaurants = loadRestaurants();
  const towns = getUniqueTowns(restaurants);
  const siteUrl = 'https://gardenroute-restaurants.co.za';
  const now = new Date().toISOString().split('T')[0];

  const staticPages = [
    { url: '/',        priority: '1.0', changefreq: 'weekly'  },
    { url: '/browse',  priority: '0.9', changefreq: 'weekly'  },
    { url: '/towns',   priority: '0.8', changefreq: 'monthly' },
    { url: '/about',   priority: '0.5', changefreq: 'monthly' },
  ];

  const townPages = towns.map(t => ({
    url: `/browse?town=${encodeURIComponent(t)}`,
    priority: '0.8',
    changefreq: 'weekly',
  }));

  const restaurantPages = restaurants.map(r => ({
    url: `/${r.slug}`,
    priority: '0.7',
    changefreq: 'weekly',
    lastmod: r.last_updated ? r.last_updated.split('T')[0] : now,
  }));

  const allPages = [...staticPages, ...townPages, ...restaurantPages];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allPages.map(p => `  <url>
    <loc>${siteUrl}${p.url}</loc>
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
