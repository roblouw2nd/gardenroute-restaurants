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

// Town hero images from Unsplash
const TOWN_IMAGES = {
  'Knysna':          'https://images.unsplash.com/photo-1580060839134-75a5edca2e99?w=800&q=80',
  'Plettenberg Bay': 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
  'Wilderness':      'https://images.unsplash.com/photo-1448375240586-882707db888b?w=800&q=80',
  'George':          'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=800&q=80',
  'Mossel Bay':      'https://images.unsplash.com/photo-1504701954957-2010ec3bcec1?w=800&q=80',
  'Sedgefield':      'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80',
  'Storms River':    'https://images.unsplash.com/photo-1542273917363-3b1817f69a2d?w=800&q=80',
};

export function townImage(town) {
  return TOWN_IMAGES[town] || 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80';
}
