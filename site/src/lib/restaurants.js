import { readFileSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
// site/src/lib → site/src → site → repo root → data/restaurants
const DATA_DIR = join(__dirname, '..', '..', '..', 'data', 'restaurants');

export function loadRestaurants() {
  try {
    const files = readdirSync(DATA_DIR)
      .filter(f => f.endsWith('.json') && !f.startsWith('_'));

    return files
      .map(f => {
        try { return JSON.parse(readFileSync(join(DATA_DIR, f), 'utf-8')); }
        catch { return null; }
      })
      .filter(Boolean)
      .sort((a, b) => (b.google_rating || 0) - (a.google_rating || 0));
  } catch {
    return [];
  }
}

export function priceLabel(level) {
  return ['', 'R', 'RR', 'RRR', 'RRRR'][level] || 'RR';
}

export function priceLong(level) {
  return ['', 'Budget', 'Mid-range', 'Upmarket', 'Fine dining'][level] || 'Mid-range';
}

export function getUniqueTowns(restaurants) {
  return [...new Set(restaurants.map(r => r.town))].sort();
}

export function getUniqueCuisines(restaurants) {
  return [...new Set(restaurants.flatMap(r => r.cuisine_types || []))].sort();
}

export function avgRating(restaurants) {
  const rated = restaurants.filter(r => r.google_rating > 0);
  if (!rated.length) return 0;
  return (rated.reduce((s, r) => s + r.google_rating, 0) / rated.length).toFixed(1);
}

// Town hero images — Unsplash (free to hotlink, no auth required)
// Each photo-ID links to a real coastal/forest/harbour scene matching the town character
const TOWN_IMAGES = {
  // Knysna — lagoon/harbour teal water
  'Knysna':          'https://images.unsplash.com/photo-1580060839134-75a5edca2e99?w=800&q=80',
  // Plettenberg Bay — wide sandy beach
  'Plettenberg Bay': 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
  // Wilderness — forest meets beach
  'Wilderness':      'https://images.unsplash.com/photo-1448375240586-882707db888b?w=800&q=80',
  // George — mountain/green landscape
  'George':          'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=800&q=80',
  // Mossel Bay — harbour/coastal cliffs
  'Mossel Bay':      'https://images.unsplash.com/photo-1519046904884-53103b34b206?w=800&q=80',
  // Sedgefield — calm lagoon/lake
  'Sedgefield':      'https://images.unsplash.com/photo-1501854140801-50d01698950b?w=800&q=80',
  // Storms River — dense forest canopy
  'Storms River':    'https://images.unsplash.com/photo-1516026672322-bc52d61a4e1f?w=800&q=80',
  // Smaller towns
  'Groot Brak River':'https://images.unsplash.com/photo-1519046904884-53103b34b206?w=800&q=80',
  'Hartenbos':       'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
  "Nature's Valley": 'https://images.unsplash.com/photo-1448375240586-882707db888b?w=800&q=80',
  'Herolds Bay':     'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
  'Victoria Bay':    'https://images.unsplash.com/photo-1519046904884-53103b34b206?w=800&q=80',
  'Keurboomstrand':  'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
  'Brenton-on-Sea':  'https://images.unsplash.com/photo-1580060839134-75a5edca2e99?w=800&q=80',
};

export function townImage(town) {
  return TOWN_IMAGES[town] || 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80';
}

/**
 * Returns a usable <img src> for a restaurant photo entry.
 * - Local path  (/images/slug/0.jpg)  → returned as-is
 * - places/...  (not yet downloaded)  → routed through /api/photo proxy
 * - Empty / null                      → null (caller shows placeholder)
 */
export function photoUrl(photo) {
  if (!photo) return null;
  const url = typeof photo === 'string' ? photo : photo.url;
  if (!url) return null;
  if (url.startsWith('/')) return url;                          // local static
  if (url.startsWith('places/')) return `/api/photo?name=${encodeURIComponent(url)}&w=800`;
  if (url.startsWith('http')) return url;                       // external (shouldn't happen)
  return null;
}
