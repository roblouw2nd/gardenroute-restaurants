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

// Town hero images — actual Garden Route locations (Wikimedia Commons, CC licensed)
const TOWN_IMAGES = {
  // Knysna Heads / lagoon
  'Knysna':          'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Knysna_Heads_2.jpg/1280px-Knysna_Heads_2.jpg',
  // Plettenberg Bay beach
  'Plettenberg Bay': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Plettenberg_Bay_from_Keurbooms_River_mouth.jpg/1280px-Plettenberg_Bay_from_Keurbooms_River_mouth.jpg',
  // Wilderness beach & lagoon
  'Wilderness':      'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Wilderness_Beach%2C_Garden_Route%2C_Western_Cape%2C_South_Africa_%2814415699143%29.jpg/1280px-Wilderness_Beach%2C_Garden_Route%2C_Western_Cape%2C_South_Africa_%2814415699143%29.jpg',
  // George town / Outeniqua mountains
  'George':          'https://upload.wikimedia.org/wikipedia/commons/thumb/9/94/George_Western_Cape.jpg/1280px-George_Western_Cape.jpg',
  // Mossel Bay harbour / Cape St Blaize
  'Mossel Bay':      'https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Mossel_Bay_Harbour_from_the_lighthouse.jpg/1280px-Mossel_Bay_Harbour_from_the_lighthouse.jpg',
  // Sedgefield lagoon
  'Sedgefield':      'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Swartvlei_Sedgefield.jpg/1280px-Swartvlei_Sedgefield.jpg',
  // Storms River / Tsitsikamma suspension bridge
  'Storms River':    'https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Storms_River_Mouth_suspension_bridge.jpg/1280px-Storms_River_Mouth_suspension_bridge.jpg',
  // Smaller towns — fall back to closest scenic match
  'Groot Brak River':'https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Mossel_Bay_Harbour_from_the_lighthouse.jpg/1280px-Mossel_Bay_Harbour_from_the_lighthouse.jpg',
  'Hartenbos':       'https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Mossel_Bay_Harbour_from_the_lighthouse.jpg/1280px-Mossel_Bay_Harbour_from_the_lighthouse.jpg',
  "Nature's Valley": 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Storms_River_Mouth_suspension_bridge.jpg/1280px-Storms_River_Mouth_suspension_bridge.jpg',
  'Herolds Bay':     'https://upload.wikimedia.org/wikipedia/commons/thumb/9/94/George_Western_Cape.jpg/1280px-George_Western_Cape.jpg',
  'Victoria Bay':    'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Wilderness_Beach%2C_Garden_Route%2C_Western_Cape%2C_South_Africa_%2814415699143%29.jpg/1280px-Wilderness_Beach%2C_Garden_Route%2C_Western_Cape%2C_South_Africa_%2814415699143%29.jpg',
};

export function townImage(town) {
  return TOWN_IMAGES[town] || 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80';
}
