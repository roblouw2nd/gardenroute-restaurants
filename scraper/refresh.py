"""
refresh.py — Refresh the facts on existing listings from Google Places.

Looks up every listing by its google_place_id and updates rating, review count,
opening hours and phone number. It never adds or removes a listing and never
touches descriptions, tags or anything else a curator has written.

  - A field is only overwritten when Google returns a value for it, so a gap in
    Google's data can't blank out something we already have.
  - Listings claimed by their owner keep the owner's hours, phone and website.
  - Places Google reports as closed are flagged (business_status) and listed in
    the run summary for a person to review — they are not removed.
  - If more than 20% of lookups fail, nothing is written.

Usage:
    python refresh.py               # refresh every listing
    python refresh.py --limit 10    # first 10 only (for testing)
    python refresh.py --dry-run     # report what would change, write nothing
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from places import API_KEY, parse_opening_hours

DATA_DIR = Path(__file__).parent.parent / "data" / "restaurants"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
FIELD_MASK = ",".join([
    "id", "internationalPhoneNumber", "websiteUri", "rating",
    "userRatingCount", "regularOpeningHours", "businessStatus",
])
MAX_ERROR_RATE = 0.20


def fetch_details(place_id: str) -> dict:
    response = requests.get(
        DETAILS_URL.format(place_id=place_id),
        headers={"X-Goog-Api-Key": API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        params={"languageCode": "en"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def google_error_message(error: requests.RequestException) -> str:
    """Google's own explanation of a failed request (e.g. a disabled API or a restricted key)."""
    try:
        return error.response.json()["error"]["message"]
    except Exception:  # noqa: BLE001 — no response, or not Google's JSON error shape
        return str(error)


def apply_details(record: dict, place: dict) -> list[str]:
    """Copy fresh facts from a Place Details response onto a listing.
    Returns the names of the fields that changed."""
    updates = {}
    if "rating" in place:
        updates["google_rating"] = place["rating"]
    if "userRatingCount" in place:
        updates["google_review_count"] = place["userRatingCount"]
    if place.get("businessStatus"):
        updates["business_status"] = place["businessStatus"]

    if not record.get("claimed"):
        if place.get("regularOpeningHours", {}).get("weekdayDescriptions"):
            updates["opening_hours"] = parse_opening_hours(place)
        if place.get("internationalPhoneNumber"):
            updates["phone"] = place["internationalPhoneNumber"]
        if place.get("websiteUri") and not record.get("website"):
            updates["website"] = place["websiteUri"]

    changed = [k for k, v in updates.items() if record.get(k) != v]
    # First run: recording that a place is open isn't a change worth a new "updated" date.
    visible = [k for k in changed if not (k == "business_status" and updates[k] == "OPERATIONAL" and not record.get(k))]
    record.update(updates)
    return visible


def write_summary(lines: list[str]):
    text = "\n".join(lines)
    print(text)
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(text + "\n")


def main():
    ap = argparse.ArgumentParser(description="Refresh listing facts from Google Places")
    ap.add_argument("--limit", type=int, default=0, help="only refresh the first N listings")
    ap.add_argument("--dry-run", action="store_true", help="report changes without writing files")
    args = ap.parse_args()

    if not API_KEY:
        sys.exit("GOOGLE_PLACES_API_KEY is not set.")

    paths = sorted(p for p in DATA_DIR.glob("*.json") if not p.name.startswith("_"))
    if args.limit:
        paths = paths[: args.limit]

    now = datetime.now(timezone.utc).isoformat()
    to_write, errors, closed = [], [], []
    first_error = None
    field_counts: dict[str, int] = {}

    for path in paths:
        record = json.loads(path.read_text())
        try:
            place = fetch_details(record["google_place_id"])
        except requests.RequestException as e:
            status = getattr(e.response, "status_code", None)
            errors.append(f"{record['slug']} ({status or type(e).__name__})")
            if first_error is None:
                first_error = google_error_message(e)
            continue

        before = json.dumps(record, sort_keys=True)
        changed = apply_details(record, place)
        for field in changed:
            field_counts[field] = field_counts.get(field, 0) + 1
        if changed:
            record["last_updated"] = now
        if record.get("business_status", "OPERATIONAL") != "OPERATIONAL":
            closed.append(f"{record['name']} — {record['town']} ({record['business_status']})")
        if json.dumps(record, sort_keys=True) != before:
            to_write.append((path, record))
        time.sleep(0.05)

    error_rate = len(errors) / len(paths) if paths else 0
    aborted = error_rate > MAX_ERROR_RATE

    lines = [
        "## Listing refresh",
        f"- Checked: {len(paths)}",
        f"- Listings with changes: {len(to_write)}",
        f"- Lookups failed: {len(errors)}",
    ]
    lines += [f"- Changed `{field}`: {n}" for field, n in sorted(field_counts.items())]
    if closed:
        lines += ["", "### Reported closed by Google — review these"] + [f"- {c}" for c in closed]
    if errors:
        lines += ["", "### Failed lookups", f"First error: {first_error}"] + [f"- {e}" for e in errors[:50]]
    if aborted:
        lines += ["", f"**Nothing written: {error_rate:.0%} of lookups failed (limit {MAX_ERROR_RATE:.0%}).**"]
    elif args.dry_run:
        lines += ["", "Dry run — nothing written."]
    write_summary(lines)

    if aborted:
        sys.exit(1)
    if not args.dry_run:
        for path, record in to_write:
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
