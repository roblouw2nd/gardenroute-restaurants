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

// Town tile images — real local photos downloaded by
// scraper/download_town_photos.py into site/public/images/towns/<slug>.jpg.
// Until those exist, the <img> onerror falls back to TOWN_IMAGE_FALLBACK so a
// tile never renders broken.
export const TOWN_IMAGE_FALLBACK = '/images/towns/_default.svg';

export function townImage(town) {
  return `/images/towns/${townSlug(town)}.jpg`;
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

// ── Slugs & lookups ────────────────────────────────────────────────────────

/** URL-safe slug for a town name. "Nature's Valley" → "natures-valley" */
export function townSlug(town) {
  return String(town)
    .toLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Same slug rule, reusable for cuisines/tags ("Pub & Grill" → "pub-grill") */
export function toSlug(str) {
  return townSlug(str);
}

export function restaurantsInTown(restaurants, town) {
  return restaurants.filter(r => r.town === town);
}

/** Restaurants whose cuisine_types OR tags match a category label. */
export function restaurantsInCategory(restaurants, label) {
  return restaurants.filter(r =>
    (r.cuisine_types || []).includes(label) || (r.tags || []).includes(label)
  );
}

/** Top N cuisines by frequency within a set of restaurants. */
export function topCuisines(restaurants, n = 3) {
  const counts = {};
  for (const r of restaurants) {
    for (const c of r.cuisine_types || []) counts[c] = (counts[c] || 0) + 1;
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([c]) => c);
}

/** True if a restaurant is open on a given day ('monday'…'sunday'). */
export function isOpenOn(r, day) {
  const h = r.opening_hours?.[day];
  return Boolean(h) && h !== 'Hours not available' && h.toLowerCase() !== 'closed';
}

/** Restaurants in a town open on a given day, best-rated first. */
export function openInTownOn(restaurants, town, day) {
  return restaurants
    .filter(r => r.town === town && isOpenOn(r, day))
    .sort((a, b) => (b.google_rating || 0) - (a.google_rating || 0));
}

/**
 * Nearby & similar restaurants for a detail page: same town first (ranked by
 * cuisine overlap, then rating), topped up with the closest well-rated spots
 * from other towns (by coordinates when available).
 */
export function similarRestaurants(restaurants, r, n = 6) {
  const overlap = (a, b) => {
    const set = new Set(a.cuisine_types || []);
    return (b.cuisine_types || []).filter(c => set.has(c)).length;
  };
  const dist = (a, b) => {
    if (!a.coordinates?.lat || !b.coordinates?.lat) return Infinity;
    const dLat = a.coordinates.lat - b.coordinates.lat;
    const dLng = a.coordinates.lng - b.coordinates.lng;
    return dLat * dLat + dLng * dLng;
  };

  const others = restaurants.filter(x => x.slug !== r.slug);
  const sameTown = others
    .filter(x => x.town === r.town)
    .sort((a, b) => overlap(r, b) - overlap(r, a) || (b.google_rating || 0) - (a.google_rating || 0));
  const elsewhere = others
    .filter(x => x.town !== r.town && (x.google_rating || 0) >= 4)
    .sort((a, b) => dist(r, a) - dist(r, b));

  return [...sameTown, ...elsewhere].slice(0, n);
}

// ── Optional AI-generated copy (from scraper/generate_content.py) ───────────
// If data/content/<file>.json exists, pages use the richer Ollama-written copy;
// otherwise they fall back to data-driven templated copy. Build stays static.

function loadJsonFromData(relPath) {
  try {
    const p = join(DATA_DIR, '..', relPath);
    return JSON.parse(readFileSync(p, 'utf-8'));
  } catch {
    return {};
  }
}

export function loadTownContent() {
  return loadJsonFromData(join('content', 'towns.json'));
}

export function loadCuisineContent() {
  return loadJsonFromData(join('content', 'cuisines.json'));
}

/** Optional AI copy for town×category pages, keyed "<town-slug>/<category-slug>". */
export function loadTownCategoryContent() {
  return loadJsonFromData(join('content', 'town_categories.json'));
}

// ── Translations (from scraper/translate.py → data/i18n/) ───────────────────

const I18N_DIR = join(DATA_DIR, '..', 'i18n');
let _i18nRestaurants = null;

/** Map of slug → {de: {description_short, description_long}, fr: …}. Cached. */
export function loadRestaurantTranslations() {
  if (_i18nRestaurants) return _i18nRestaurants;
  _i18nRestaurants = {};
  try {
    const dir = join(I18N_DIR, 'restaurants');
    for (const f of readdirSync(dir).filter(f => f.endsWith('.json'))) {
      try {
        _i18nRestaurants[f.replace(/\.json$/, '')] = JSON.parse(readFileSync(join(dir, f), 'utf-8'));
      } catch { /* skip corrupt file */ }
    }
  } catch { /* no translations yet */ }
  return _i18nRestaurants;
}

/** Translation for one restaurant+lang, or null. */
export function restaurantTranslation(slug, lang) {
  const tr = loadRestaurantTranslations()[slug];
  return tr?.[lang]?.description_short ? tr[lang] : null;
}

/** Locale codes (excl. 'en') that have a translation for this slug. */
export function translatedLangs(slug) {
  const tr = loadRestaurantTranslations()[slug] || {};
  return Object.keys(tr).filter(k => k !== '_hash' && tr[k]?.description_short);
}

/** Translated town/cuisine content: data/i18n/content/towns.json → {town: {de: {...}}} */
export function loadTownContentI18n() {
  try {
    return JSON.parse(readFileSync(join(I18N_DIR, 'content', 'towns.json'), 'utf-8'));
  } catch {
    return {};
  }
}
