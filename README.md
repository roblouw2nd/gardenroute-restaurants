# Garden Route Restaurants

> **gardenroute-restaurants.co.za** — A human-curated directory of restaurants across the Garden Route, South Africa.

## How it works

1. A Python scraper pulls restaurant data from the Google Places API
2. Each new entry gets a draft description, tags and cuisine classification, which a person reviews and edits in the admin dashboard (`admin/`) before it is published
3. Data is stored as JSON files in `data/restaurants/`; places a curator has removed are recorded in `data/excluded_places.json` and are never re-added
4. An Astro static site builds from the JSON files and deploys to Vercel automatically

## Stack

| Layer | Technology |
|---|---|
| Scraper | Python 3.11, Google Places API |
| Curation | Local admin dashboard (`admin/`) |
| Frontend | Astro + Tailwind CSS |
| Hosting | Vercel |

## Running the scraper locally

```bash
cd scraper
cp .env.example .env        # Fill in your API keys
pip install -r requirements.txt
python main.py
```

## Running the site locally

```bash
cd site
npm install
npm run dev
```

## Environment variables

| Variable | Where to get it |
|---|---|
| `GOOGLE_PLACES_API_KEY` | console.cloud.google.com |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

Set these as GitHub Actions secrets for the automated pipeline.
