"""
test_api.py — Quick test to debug Google Places API connection
Run from the scraper directory: python3 test_api.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
print(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-4:] if API_KEY else 'NOT FOUND'}")

url = "https://places.googleapis.com/v1/places:searchText"
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "places.id,places.displayName",
}
body = {
    "textQuery": "restaurants Knysna South Africa",
    "maxResultCount": 3,
}

print(f"\nCalling: {url}")
print(f"Headers: {headers}")
print(f"Body: {body}\n")

response = requests.post(url, json=body, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
