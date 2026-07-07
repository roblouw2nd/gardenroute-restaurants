"""
generate_content.py — Local-AI SEO copy generator (Ollama)

Mass-produces unique landing-page copy for the site using your LOCAL Ollama
model — no API cost. Writes two JSON files the Astro site reads at build time:

    data/content/towns.json      -> {"<Town>": {"intro": "...", "faqs": [{q,a}, ...]}}
    data/content/cuisines.json   -> {"<Label>": {"intro": "...", "faqs": [{q,a}, ...]}}

The town/cuisine pages use this richer copy when present and fall back to
auto-generated templated copy when it isn't — so the site always builds, with
or without this step.

Usage:
    ollama serve                 # ensure Ollama is running
    python generate_content.py               # all towns + categories
    python generate_content.py --towns       # towns only
    python generate_content.py --cuisines    # categories only
    python generate_content.py --force       # regenerate even if already present

Config via env (same as enricher.py): OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT
"""

import os
import json
import argparse
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "restaurants"
OUT_DIR = ROOT / "data" / "content"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_COUNT = 4       # keep in sync with site/src/lib/categories.js
TOWN_MIN_COUNT = 3  # gate for town×category pages (TOWN_MIN_COUNT in categories.js)

# Category labels — must match values in towns.py CUISINE_TYPES / TAGS,
# and the labels in site/src/lib/categories.js
CATEGORY_LABELS = [
    "Seafood", "Pizza", "Steakhouse", "Italian", "Sushi", "Cafe", "Coffee Shop",
    "Bakery", "Breakfast & Brunch", "Fine Dining", "Burgers", "Vegetarian",
    "Vegan", "Pub & Grill", "Asian", "Indian", "Mexican", "Wine Bar",
    "Ocean views", "Waterfront", "Dog friendly", "Family friendly",
    "Live music", "Date night", "Outdoor seating",
]


# Slug overrides — keep in sync with categories.js (slug: 'sea-view')
SLUG_OVERRIDES = {"Ocean views": "sea-view"}


def to_slug(s: str) -> str:
    """Mirror of site/src/lib/restaurants.js toSlug()."""
    import re
    s = SLUG_OVERRIDES.get(s, s)
    s = re.sub(r"['’]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def load_restaurants():
    out = []
    for p in DATA_DIR.glob("*.json"):
        if p.name.startswith("_"):
            continue
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            pass
    return out


def _ollama_json(system: str, user: str) -> dict:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.6, "num_ctx": 4096},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return json.loads(text.strip())


SYSTEM = (
    "You are an editor for a South African restaurant directory covering the "
    "Garden Route. Write warm, honest, locally-flavoured copy with no hype or "
    "empty superlatives. Never invent specific facts (named dishes, prices, "
    "awards) that aren't in the data provided. Return ONLY valid JSON."
)


def top_cuisines(restaurants, n=4):
    c = Counter()
    for r in restaurants:
        c.update(r.get("cuisine_types", []))
    return [k for k, _ in c.most_common(n)]


def gen_town(town, restaurants):
    rated = sorted(restaurants, key=lambda r: r.get("google_rating", 0), reverse=True)
    top = rated[:5]
    avg = round(sum(r.get("google_rating", 0) for r in rated) / max(len(rated), 1), 1)
    facts = {
        "town": town,
        "restaurant_count": len(restaurants),
        "average_rating": avg,
        "top_cuisines": top_cuisines(restaurants),
        "highest_rated": [
            {"name": r["name"], "rating": r.get("google_rating"),
             "reviews": r.get("google_review_count"),
             "cuisine": (r.get("cuisine_types") or [None])[0]}
            for r in top
        ],
    }
    user = (
        "Write JSON for a town restaurant landing page using ONLY these facts:\n"
        f"{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Return an object with:\n"
        '- "intro": 2-3 sentence introduction (60-90 words) about dining in this '
        "town on the Garden Route. Mention the kinds of food available and the "
        "setting. Natural, specific, no hype.\n"
        '- "faqs": array of exactly 4 objects, each {"q": question, "a": answer}. '
        "Cover: how many restaurants, the best-rated options (name real ones from "
        "the facts), the kinds of cuisine, and a practical tip (booking/views/"
        "family). Keep answers 1-3 sentences."
    )
    return _ollama_json(SYSTEM, user)


def gen_category(label, restaurants):
    rated = sorted(restaurants, key=lambda r: r.get("google_rating", 0), reverse=True)
    towns = Counter(r["town"] for r in restaurants)
    facts = {
        "category": label,
        "count": len(restaurants),
        "towns": dict(towns.most_common()),
        "top_examples": [
            {"name": r["name"], "town": r["town"], "rating": r.get("google_rating")}
            for r in rated[:5]
        ],
    }
    user = (
        "Write JSON for a category landing page (restaurants matching a cuisine or "
        "feature) on a Garden Route directory, using ONLY these facts:\n"
        f"{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Return an object with:\n"
        '- "intro": 2-3 sentences (50-80 words) about finding this kind of '
        "restaurant on the Garden Route, mentioning which towns have the most. "
        "Natural, no hype.\n"
        '- "faqs": array of exactly 3 objects {"q":..., "a":...} covering how many '
        "options there are, which towns are best for it, and a practical tip."
    )
    return _ollama_json(SYSTEM, user)


def gen_town_category(town, label, restaurants, town_total):
    rated = sorted(restaurants, key=lambda r: r.get("google_rating", 0), reverse=True)
    facts = {
        "town": town,
        "category": label,
        "count": len(restaurants),
        "town_total_restaurants": town_total,
        "top_examples": [
            {"name": r["name"], "rating": r.get("google_rating"),
             "reviews": r.get("google_review_count"),
             "description": r.get("description_short")}
            for r in rated[:4]
        ],
    }
    user = (
        "Write JSON for a landing page listing a specific kind of restaurant in ONE "
        "Garden Route town (e.g. 'seafood restaurants in Knysna'), using ONLY these "
        f"facts:\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Return an object with:\n"
        '- "intro": 2-3 sentences (50-80 words) about this kind of eating in this '
        "specific town. Name one or two of the top examples naturally. No hype.\n"
        '- "faqs": array of exactly 2 objects {"q":..., "a":...}: how many options '
        "there are in this town, and which is the best-rated (name it)."
    )
    return _ollama_json(SYSTEM, user)


def run(do_towns: bool, do_cuisines: bool, force: bool, do_town_categories: bool = False):
    restaurants = load_restaurants()
    print(f"Loaded {len(restaurants)} restaurants.\n")

    if do_towns:
        path = OUT_DIR / "towns.json"
        existing = json.loads(path.read_text()) if path.exists() else {}
        towns = sorted({r["town"] for r in restaurants})
        for town in towns:
            if town in existing and not force:
                print(f"  =  {town} (cached)")
                continue
            subset = [r for r in restaurants if r["town"] == town]
            try:
                existing[town] = gen_town(town, subset)
                path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
                print(f"  +  {town} ({len(subset)} restaurants)")
            except Exception as e:
                print(f"  x  {town}: {e}")
        print(f"\nWrote {path}\n")

    if do_cuisines:
        path = OUT_DIR / "cuisines.json"
        existing = json.loads(path.read_text()) if path.exists() else {}
        for label in CATEGORY_LABELS:
            subset = [
                r for r in restaurants
                if label in (r.get("cuisine_types") or []) or label in (r.get("tags") or [])
            ]
            if len(subset) < MIN_COUNT:
                continue
            if label in existing and not force:
                print(f"  =  {label} (cached)")
                continue
            try:
                existing[label] = gen_category(label, subset)
                path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
                print(f"  +  {label} ({len(subset)} restaurants)")
            except Exception as e:
                print(f"  x  {label}: {e}")
        print(f"\nWrote {path}\n")

    if do_town_categories:
        # Copy for /town/<town>/<category> pages, keyed "<town-slug>/<cat-slug>"
        # (read by site/src/lib/restaurants.js loadTownCategoryContent()).
        path = OUT_DIR / "town_categories.json"
        existing = json.loads(path.read_text()) if path.exists() else {}
        towns = sorted({r["town"] for r in restaurants})
        for town in towns:
            in_town = [r for r in restaurants if r["town"] == town]
            for label in CATEGORY_LABELS:
                subset = [
                    r for r in in_town
                    if label in (r.get("cuisine_types") or []) or label in (r.get("tags") or [])
                ]
                if len(subset) < TOWN_MIN_COUNT:
                    continue
                key = f"{to_slug(town)}/{to_slug(label)}"
                if key in existing and not force:
                    print(f"  =  {key} (cached)")
                    continue
                try:
                    existing[key] = gen_town_category(town, label, subset, len(in_town))
                    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
                    print(f"  +  {key} ({len(subset)} restaurants)")
                except Exception as e:
                    print(f"  x  {key}: {e}")
        print(f"\nWrote {path}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate SEO landing-page copy with local Ollama")
    ap.add_argument("--towns", action="store_true", help="towns only")
    ap.add_argument("--cuisines", action="store_true", help="categories only")
    ap.add_argument("--town-categories", action="store_true",
                    help="town×category pages only (/town/<town>/<category>)")
    ap.add_argument("--force", action="store_true", help="regenerate even if cached")
    args = ap.parse_args()
    # Default: do all three
    all_ = not (args.towns or args.cuisines or args.town_categories)
    run(
        do_towns=args.towns or all_,
        do_cuisines=args.cuisines or all_,
        force=args.force,
        do_town_categories=args.town_categories or all_,
    )
