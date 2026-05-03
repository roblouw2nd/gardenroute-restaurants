"""
places.py — Google Places API client
Searches for restaurants in each Garden Route town/area and returns structured records.

Supports two search modes:
  1. Text queries  — existing behaviour, used for named towns
  2. Nearby search — coordinate + radius, used for N2 corridor gaps between towns
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
SEARCH_TEXT_URL   = "https://places.googleapis.com/v1/places:searchText"
SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.menuUri",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.regularOpeningHours",
    "places.types",
    "places.photos",
])

# Types that indicate a place is food/drink related
FOOD_TYPES = {
    "restaurant", "cafe", "coffee_shop", "bar", "bakery",
    "fast_food_restaurant", "food", "meal_takeaway", "meal_delivery",
    "sandwich_shop", "ice_cream_shop", "juice_shop", "pizza_restaurant",
    "seafood_restaurant", "steak_house", "sushi_restaurant",
    "wine_bar", "pub", "diner", "brunch_restaurant",
}

# Types that indicate a place is NOT a restaurant (filter these out)
EXCLUDE_TYPES = {
    "lodging", "hotel", "motel", "guest_house", "campground",
    "rv_park", "gas_station", "convenience_store", "grocery_store",
    "supermarket", "clothing_store", "hardware_store", "pharmacy",
    "bank", "atm", "car_repair", "car_wash", "parking",
}


def _is_restaurant(place: dict) -> bool:
    """Return True if the place looks like a food/drink venue."""
    types = set(place.get("types", []))
    # Exclude if it's clearly not food
    if types & EXCLUDE_TYPES and not types & FOOD_TYPES:
        return False
    # Must have at least one food type OR the word 'restaurant/cafe/bar' in the name
    if types & FOOD_TYPES:
        return True
    name = place.get("displayName", {}).get("text", "").lower()
    return any(w in name for w in ["restaurant", "cafe", "café", "bar", "grill",
                                    "bistro", "eatery", "kitchen", "diner",
                                    "bakery", "coffee", "pub", "tavern"])


def search_text(query: str, max_results: int = 20) -> list:
    """Text-based search. The new Places API (v1) doesn't support pagination
    for searchText — max is 20 per call. We compensate with more targeted queries."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": query,
        "maxResultCount": min(max_results, 20),
        "languageCode": "en",
    }
    response = requests.post(SEARCH_TEXT_URL, json=body, headers=headers)
    response.raise_for_status()
    return response.json().get("places", [])


def search_nearby(lat: float, lng: float, radius_m: int = 8000) -> list:
    """
    Coordinate + radius search using the Nearby Search (New) endpoint.
    Returns all restaurants/cafes within radius_m metres of the given point.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "includedTypes": ["restaurant", "cafe", "bar", "bakery", "coffee_shop"],
        "maxResultCount": 20,
        "languageCode": "en",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
    }

    all_places = []
    # Nearby search doesn't paginate the same way, but we can request up to 20 at a time.
    # Run once — caller handles deduplication across multiple waypoints.
    response = requests.post(SEARCH_NEARBY_URL, json=body, headers=headers)
    response.raise_for_status()
    all_places.extend(response.json().get("places", []))
    return all_places


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
        "menu_url": place.get("menuUri", ""),
        "google_rating": place.get("rating", 0),
        "google_review_count": place.get("userRatingCount", 0),
        "price_level": parse_price_level(place),
        "google_types": place.get("types", []),
        "opening_hours": parse_opening_hours(place),
        "photos": get_photo_urls(place),
    }


def fetch_town(town_name: str, queries: list) -> list:
    """Text-query based fetch for a named town. Paginates each query."""
    seen_ids = set()
    results = []
    for query in queries:
        print(f"  Searching: {query}")
        try:
            places = search_text(query)
            for place in places:
                place_id = place.get("id", "")
                if place_id and place_id not in seen_ids and _is_restaurant(place):
                    seen_ids.add(place_id)
                    results.append(parse_place(place, town_name))
        except requests.HTTPError as e:
            print(f"  Warning: API error for query '{query}': {e}")
    return results


def fetch_corridor(area_name: str, waypoints: list, radius_m: int = 8000) -> list:
    """
    Coordinate-based fetch for N2 corridor gaps.
    waypoints: list of (lat, lng) tuples — overlapping circles along the route.
    Returns deduplicated list of restaurants, labelled with area_name as town.
    """
    seen_ids = set()
    results = []
    for lat, lng in waypoints:
        print(f"  Nearby search: {area_name} @ ({lat:.4f}, {lng:.4f}) r={radius_m}m")
        try:
            places = search_nearby(lat, lng, radius_m)
            for place in places:
                place_id = place.get("id", "")
                if place_id and place_id not in seen_ids and _is_restaurant(place):
                    seen_ids.add(place_id)
                    results.append(parse_place(place, area_name))
            time.sleep(1)  # be polite to the API
        except requests.HTTPError as e:
            print(f"  Warning: API error near ({lat}, {lng}): {e}")
    return results
