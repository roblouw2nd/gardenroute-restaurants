# Garden Route Restaurants

> **gardenroute-restaurants.co.za** — An AI-maintained directory of restaurants across the Garden Route, South Africa.

## How it works

1. A Python scraper pulls restaurant data from Google Places API weekly
2. Claude enriches each entry with descriptions, tags, and cuisine classification
3. Data is stored as JSON files in `data/restaurants/`
4. An Astro static site builds from the JSON files and deploys to Vercel automatically

## Stack

| Layer | Technology |
|---|---|
| Scraper | Python 3.11, Google Places API, Anthropic Claude |
| Automation | GitHub Actions (weekly cron) |
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
