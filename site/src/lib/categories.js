// categories.js — curated, high-intent landing-page categories.
// Each label MUST match a value in scraper/towns.py CUISINE_TYPES or TAGS so
// restaurantsInCategory() can match on cuisine_types OR tags.
//
// type: 'cuisine'  → "Best <label> restaurants on the Garden Route"
//       'feature'  → "<label> restaurants on the Garden Route" (e.g. Sea-view)
// Only categories meeting MIN_COUNT restaurants get a page (avoids thin pages
// that hurt crawl budget).

export const MIN_COUNT = 4;

export const CATEGORIES = [
  // Cuisines
  { label: 'Seafood',            type: 'cuisine',  h1: 'seafood restaurants' },
  { label: 'Pizza',              type: 'cuisine',  h1: 'pizza places' },
  { label: 'Steakhouse',         type: 'cuisine',  h1: 'steakhouses' },
  { label: 'Italian',            type: 'cuisine',  h1: 'Italian restaurants' },
  { label: 'Sushi',              type: 'cuisine',  h1: 'sushi restaurants' },
  { label: 'Cafe',               type: 'cuisine',  h1: 'cafés' },
  { label: 'Coffee Shop',        type: 'cuisine',  h1: 'coffee shops' },
  { label: 'Bakery',             type: 'cuisine',  h1: 'bakeries' },
  { label: 'Breakfast & Brunch', type: 'cuisine',  h1: 'breakfast & brunch spots' },
  { label: 'Fine Dining',        type: 'cuisine',  h1: 'fine dining restaurants' },
  { label: 'Burgers',            type: 'cuisine',  h1: 'burger joints' },
  { label: 'Vegetarian',         type: 'cuisine',  h1: 'vegetarian restaurants' },
  { label: 'Vegan',              type: 'cuisine',  h1: 'vegan restaurants' },
  { label: 'Pub & Grill',        type: 'cuisine',  h1: 'pubs & grills' },
  { label: 'Asian',              type: 'cuisine',  h1: 'Asian restaurants' },
  { label: 'Indian',             type: 'cuisine',  h1: 'Indian restaurants' },
  { label: 'Mexican',            type: 'cuisine',  h1: 'Mexican restaurants' },
  { label: 'Wine Bar',           type: 'cuisine',  h1: 'wine bars' },

  // Features (from tags)
  { label: 'Ocean views',  type: 'feature', h1: 'restaurants with ocean views',  slug: 'sea-view' },
  { label: 'Waterfront',   type: 'feature', h1: 'waterfront restaurants' },
  { label: 'Dog friendly', type: 'feature', h1: 'dog-friendly restaurants' },
  { label: 'Family friendly', type: 'feature', h1: 'family-friendly restaurants' },
  { label: 'Live music',   type: 'feature', h1: 'restaurants with live music' },
  { label: 'Date night',   type: 'feature', h1: 'date-night restaurants' },
  { label: 'Outdoor seating', type: 'feature', h1: 'restaurants with outdoor seating' },
];
