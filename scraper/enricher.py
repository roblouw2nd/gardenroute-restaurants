"""
enricher.py — Claude AI enrichment agent
Takes raw Google Places data and returns an enriched restaurant record.
"""

import os
import json
import anthropic
from dotenv import load_dotenv
from towns import CUISINE_TYPES, TAGS

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = f"""You are a copywriter for a South African restaurant directory website covering the Garden Route.
Given raw data about a restaurant, return a valid JSON object with exactly these fields:

- description_short: One compelling sentence (max 20 words) for the listing card. Warm, specific, no hype.
- description_long: 2-3 paragraphs describing atmosphere, must-try dishes, location highlights, and what makes it special. Honest South African voice. No hype or superlatives.
- cuisine_types: Array of strings — choose only from this list: {json.dumps(CUISINE_TYPES)}
- tags: Array of strings — choose only from this list: {json.dumps(TAGS)}
- price_level: Integer 1–4. 1=budget under R150, 2=mid-range R150-R350, 3=upmarket R350-R600, 4=fine dining R600+

Return ONLY valid JSON. No preamble, no markdown fences, no explanation."""


def build_prompt(raw: dict) -> str:
    """Build the user prompt from raw place data."""
    lines = [
        f"Restaurant name: {raw['name']}",
        f"Town: {raw['town']}",
        f"Address: {raw['address']}",
        f"Google rating: {raw['google_rating']} ({raw['google_review_count']} reviews)",
        f"Price level (Google 1-4): {raw['price_level']}",
        f"Google types: {', '.join(raw.get('google_types', []))}",
        f"Website: {raw.get('website', 'none')}",
        f"Phone: {raw.get('phone', 'none')}",
    ]
    return "\n".join(lines)


def enrich(raw: dict) -> dict:
    """Call Claude to enrich a raw restaurant record. Returns enriched fields."""
    prompt = build_prompt(raw)

    message = client.messages.create(
        model="claude-sonnet-4-5",  
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()

    # Strip markdown fences if Claude adds them despite instructions
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    enriched = json.loads(text)
    return enriched