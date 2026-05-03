"""
places.py — Google Places API client
Searches for restaurants in each Garden Route town and returns structured records.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.regularOpeningHours",
    "places.types",
    "places.photos",
])


def search_restaurants(query: str, max_results: int = 20) -> list:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": query,
        "maxResultCount": max_results,
        "languageCode": "en",
    }
    response = requests.post(SEARCH_URL, json=body, headers=headers)
    response.raise_for_status()
    return response.json().get("places", [])


def parse_opening_hours(place: dict) -> dict:
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    result = {day: "Hours not available" for day in days}
    descriptions = place.get("regularOpeningHours", {}).get("weekdayDescriptions", [])
    for description in descriptions:
        if ":" in description:
            parts = description.split(":", 1)
            day_name = parts[0].strip().lower()
            hours_str = parts[1].strip()
            if day_name in result:
                result[day_name] = hours_str
    return result


def get_photo_urls(place: dict, max_photos: int = 5) -> list:
    photos = place.get("photos", [])[:max_photos]
    result = []
    for photo in photos:
        name = photo.get("name", "")
        if name:
            url = (
                f"https://places.googleapis.com/v1/{name}/media"
                f"?maxWidthPx=1200&key={API_KEY}"
            )
            result.append({"url": url, "source": "google", "caption": ""})
    return result


def parse_price_level(place: dict) -> int:
    level_map = {
        "PRICE_LEVEL_FREE": 1,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }
    return level_map.get(place.get("priceLevel", ""), 2)


def parse_place(place: dict, town: str) -> dict:
    return {
        "google_place_id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "town": town,
        "region": "Garden Route",
        "address": place.get("formattedAddress", ""),
        "coordinates": {
            "lat": place.get("location", {}).get("latitude", 0),
            "lng": place.get("location", {}).get("longitude", 0),
        },
        "phone": place.get("internationalPhoneNumber", ""),
        "email": "",
        "website": place.get("websiteUri", ""),
        "google_rating": place.get("rating", 0),
        "google_review_count": place.get("userRatingCount", 0),
        "price_level": parse_price_level(place),
        "google_types": place.get("types", []),
        "opening_hours": parse_opening_hours(place),
        "photos": get_photo_urls(place),
    }


def fetch_town(town_name: str, queries: list) -> list:
    seen_ids = set()
    results = []
    for query in queries:
        print(f"  Searching: {query}")
        try:
            places = search_restaurants(query)
            for place in places:
                place_id = place.get("id", "")
                if place_id and place_id not in seen_ids:
                    seen_ids.add(place_id)
                    results.append(parse_place(place, town_name))
        except requests.HTTPError as e:
            print(f"  Warning: API error for query '{query}': {e}")
    return results