"""
main.py — Pipeline orchestrator
Runs the full scrape → enrich → save pipeline for all Garden Route towns.

Usage:
    python main.py              # Full run, all towns
    python main.py --town Knysna   # Single town (for testing)
"""

import os
import json
import argparse
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
from slugify import slugify

from towns import TOWNS, CORRIDOR
from places import fetch_town, fetch_corridor
from enricher import enrich

DATA_DIR = Path(__file__).parent.parent / "data" / "restaurants"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_existing() -> dict[str, dict]:
    """Load all existing restaurant JSON files, keyed by google_place_id."""
    existing = {}
    for path in DATA_DIR.glob("*.json"):
        if path.name.startswith("_"):
            continue  # skip _example.json
        try:
            with open(path) as f:
                data = json.load(f)
                place_id = data.get("google_place_id")
                if place_id:
                    existing[place_id] = data
        except (json.JSONDecodeError, KeyError):
            pass
    return existing


def save_restaurant(record: dict):
    """Save a restaurant record to its JSON file."""
    path = DATA_DIR / f"{record['slug']}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


def make_slug(name: str, town: str) -> str:
    """Generate a URL-safe slug from name and town."""
    return slugify(f"{name} {town}")


def build_new_record(raw: dict, enriched: dict) -> dict:
    """Combine raw Google data and Claude enrichment into a full record."""
    slug = make_slug(raw["name"], raw["town"])
    now = datetime.now(timezone.utc).isoformat()

    return {
        "id": slug,
        "name": raw["name"],
        "slug": slug,
        "town": raw["town"],
        "region": raw["region"],
        "address": raw["address"],
        "coordinates": raw["coordinates"],
        "phone": raw["phone"],
        "email": raw.get("email", ""),
        "website": raw.get("website", ""),
        "menu_url": raw.get("menu_url", ""),
        "google_place_id": raw["google_place_id"],
        "google_rating": raw["google_rating"],
        "google_review_count": raw["google_review_count"],
        "price_level": enriched.get("price_level", raw["price_level"]),
        "cuisine_types": enriched.get("cuisine_types", []),
        "tags": enriched.get("tags", []),
        "opening_hours": raw["opening_hours"],
        "description_short": enriched.get("description_short", ""),
        "description_long": enriched.get("description_long", ""),
        "photos": raw["photos"],
        "featured": False,
        "last_updated": now,
        "data_sources": ["google_places"],
    }


def update_existing_record(existing: dict, raw: dict) -> dict:
    """Update only the fields that change week-to-week. No Claude call needed."""
    existing["google_rating"] = raw["google_rating"]
    existing["google_review_count"] = raw["google_review_count"]
    existing["opening_hours"] = raw["opening_hours"]
    existing["phone"] = raw["phone"]
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    return existing


def process_places(raw_places: list, existing: dict, stats: dict):
    """Enrich new places and update existing ones. Mutates existing and stats."""
    for raw in raw_places:
        place_id = raw["google_place_id"]
        name = raw["name"]
        try:
            if place_id in existing:
                record = update_existing_record(existing[place_id], raw)
                save_restaurant(record)
                print(f"  ↻  Updated:  {name}")
                stats["updated"] += 1
            else:
                print(f"  +  Enriching: {name}")
                enriched = enrich(raw)
                record = build_new_record(raw, enriched)
                save_restaurant(record)
                existing[place_id] = record
                print(f"     Saved:    {record['slug']}.json")
                stats["new"] += 1
        except Exception as e:
            print(f"  ✗  Error on {name}: {e}")
            stats["errors"] += 1


def run(town_filter: Optional[str] = None, corridor_only: bool = False):
    existing = load_existing()
    print(f"Loaded {len(existing)} existing restaurants from disk.\n")

    stats = {"new": 0, "updated": 0, "errors": 0}

    # ── Named towns ──────────────────────────────────────────────────────────
    if not corridor_only:
        towns = TOWNS
        if town_filter:
            towns = [t for t in TOWNS if t["name"].lower() == town_filter.lower()]
            if not towns:
                print(f"Town '{town_filter}' not found in TOWNS. Check towns.py.")
                print(f"Also checking CORRIDOR areas...")
                corridor = [c for c in CORRIDOR if c["name"].lower() == town_filter.lower()]
                if corridor:
                    for area in corridor:
                        print(f"\n── {area['name']} (corridor) ──")
                        raw_places = fetch_corridor(area["name"], area["waypoints"], area.get("radius_m", 8000))
                        print(f"  Found {len(raw_places)} restaurants")
                        process_places(raw_places, existing, stats)
                else:
                    print(f"'{town_filter}' not found in CORRIDOR either.")
                    return

        for town in towns:
            print(f"\n── {town['name']} ──")
            raw_places = fetch_town(town["name"], town["queries"])
            print(f"  Found {len(raw_places)} restaurants from Google Places")
            process_places(raw_places, existing, stats)

    # ── N2 corridor waypoints ─────────────────────────────────────────────
    if not town_filter or corridor_only:
        print(f"\n{'─'*40}")
        print("── N2 Corridor (between-town areas) ──")
        for area in CORRIDOR:
            print(f"\n── {area['name']} ──")
            raw_places = fetch_corridor(area["name"], area["waypoints"], area.get("radius_m", 8000))
            print(f"  Found {len(raw_places)} restaurants")
            process_places(raw_places, existing, stats)

    print(f"\n── Done ──")
    print(f"  New:     {stats['new']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Errors:  {stats['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Garden Route restaurant scraper")
    parser.add_argument("--town", type=str, help="Scrape a single town or corridor area (for testing)")
    parser.add_argument("--corridor", action="store_true", help="Run only the N2 corridor waypoint searches")
    args = parser.parse_args()
    run(town_filter=args.town, corridor_only=args.corridor)