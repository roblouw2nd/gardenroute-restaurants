"""
enricher.py — Local AI enrichment agent (Ollama)

Takes raw Google Places data and returns an enriched restaurant record
(description_short, description_long, cuisine_types, tags, price_level).

This runs entirely against a LOCAL Ollama model — no paid API keys, no
per-request cost. Start Ollama first:

    ollama serve            # if not already running as a service
    ollama pull llama3.1    # or any instruct model you prefer

Configure via environment variables (optional — sensible defaults below):

    OLLAMA_HOST    default http://localhost:11434
    OLLAMA_MODEL   default llama3.1
    OLLAMA_TIMEOUT default 180   (seconds; local generation can be slow)

The public interface — enrich(raw) -> dict — is unchanged, so main.py
needs no edits.
"""

import os
import json
import time

import requests
from dotenv import load_dotenv
from towns import CUISINE_TYPES, TAGS

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

SYSTEM_PROMPT = f"""You are a copywriter for a South African restaurant directory website covering the Garden Route.
Given raw data about a restaurant, return a valid JSON object with EXACTLY these fields and nothing else:

- description_short: One compelling sentence (max 20 words) for the listing card. Warm, specific, no hype.
- description_long: 2-3 paragraphs (separated by blank lines) describing atmosphere, must-try dishes, location highlights, and what makes it special. Honest South African voice. No hype or empty superlatives. Do not invent specific facts (prices, dishes, awards) you cannot infer from the data.
- cuisine_types: Array of strings. Choose ONLY from this exact list: {json.dumps(CUISINE_TYPES)}
- tags: Array of strings. Choose ONLY from this exact list: {json.dumps(TAGS)}
- price_level: Integer 1-4. 1=budget under R150, 2=mid-range R150-R350, 3=upmarket R350-R600, 4=fine dining R600+

Return ONLY the JSON object. No preamble, no markdown fences, no explanation."""


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


def _call_ollama(prompt: str) -> str:
    """Call the local Ollama chat endpoint and return the raw text content."""
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "format": "json",          # ask Ollama to emit strict JSON
            "stream": False,
            "options": {
                "temperature": 0.4,    # low — we want consistent, factual copy
                "num_ctx": 4096,
            },
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _parse_json(text: str) -> dict:
    """Parse model output into a dict, tolerating stray markdown fences."""
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    return json.loads(text)


def _clean(enriched: dict, raw: dict) -> dict:
    """Validate / coerce model output against the allowed taxonomy."""
    cuisine_set = {c.lower(): c for c in CUISINE_TYPES}
    tag_set = {t.lower(): t for t in TAGS}

    cuisines = [
        cuisine_set[c.lower()]
        for c in enriched.get("cuisine_types", [])
        if isinstance(c, str) and c.lower() in cuisine_set
    ]
    tags = [
        tag_set[t.lower()]
        for t in enriched.get("tags", [])
        if isinstance(t, str) and t.lower() in tag_set
    ]

    try:
        price = int(enriched.get("price_level", raw.get("price_level") or 2))
    except (TypeError, ValueError):
        price = raw.get("price_level") or 2
    price = min(4, max(1, price))

    return {
        "description_short": str(enriched.get("description_short", "")).strip(),
        "description_long": str(enriched.get("description_long", "")).strip(),
        "cuisine_types": cuisines,
        "tags": tags,
        "price_level": price,
    }


def enrich(raw: dict, retries: int = 2) -> dict:
    """Call the local model to enrich a raw restaurant record.

    Returns a dict with: description_short, description_long,
    cuisine_types, tags, price_level. Retries on transient failures or
    malformed JSON before giving up.
    """
    prompt = build_prompt(raw)
    last_err = None

    for attempt in range(retries + 1):
        try:
            text = _call_ollama(prompt)
            enriched = _parse_json(text)
            return _clean(enriched, raw)
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))  # simple backoff
            continue

    raise RuntimeError(
        f"Ollama enrichment failed for '{raw.get('name')}' after "
        f"{retries + 1} attempts: {last_err}"
    )
