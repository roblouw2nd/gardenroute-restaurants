"""
download_town_photos.py — Fetch a real photo for each town tile

Downloads a representative, freely-licensed photo of each Garden Route town
from Wikimedia (Wikipedia lead image, with a Commons category fallback) and
saves it locally so the site serves it as a static file:

    site/public/images/towns/<town-slug>.jpg

It also writes attribution to:

    site/public/images/towns/credits.json

Run locally (network access required — like download_photos.py):

    cd scraper
    python3 download_town_photos.py
    python3 download_town_photos.py --force      # re-download existing

After running, eyeball site/public/images/towns/, then commit the folder.
If any town's auto-picked image looks wrong, either:
  • drop your own <slug>.jpg into that folder, or
  • paste a direct image URL into OVERRIDE_URL below and re-run.
"""

import os
import re
import json
import argparse
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "site" / "public" / "images" / "towns"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = "GardenRouteRestaurants/1.0 (https://www.gardenroute-restaurants.co.za; town tiles)"

def slug(town: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", town.lower().replace("'", "")).strip("-")

# Town -> Wikipedia article title (the lead photo of these is usually scenic)
WIKI_TITLE = {
    "George":            "George, Western Cape",
    "Mossel Bay":        "Mossel Bay",
    "Knysna":            "Knysna",
    "Plettenberg Bay":   "Plettenberg Bay",
    "Sedgefield":        "Sedgefield, Western Cape",
    "Wilderness":        "Wilderness, Western Cape",
    "Great Brak River":  "Great Brak River",
    "Storms River":      "Storms River",
    "Hartenbos":         "Hartenbos",
    "Klein Brak River":  "Little Brak River",
    "Victoria Bay":      "Victoria Bay",
    "Nature's Valley":   "Nature's Valley",
    "Herolds Bay":       "Herolds Bay",
}

# Optional manual overrides: town -> direct image URL (takes priority).
OVERRIDE_URL = {
    # "Knysna": "https://upload.wikimedia.org/...jpg",
}

API = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"


def _get_json(base, params):
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def wiki_lead_image(title):
    """Return (image_url, page_title) for a Wikipedia article's lead image."""
    data = _get_json(API, {
        "action": "query", "format": "json", "prop": "pageimages",
        "piprop": "thumbnail", "pithumbsize": "1200", "titles": title,
        "redirects": "1",
    })
    pages = data.get("query", {}).get("pages", {})
    for _, p in pages.items():
        thumb = p.get("thumbnail", {}).get("source")
        if thumb:
            return thumb, p.get("title", title)
    return None, title


# Filenames that are clearly NOT a town photo (ships, maps, crests, etc.)
JUNK = re.compile(r"\b(imo|ship|vessel|boat|tanker|cargo|mv|ss|ferry|yacht|"
                  r"coat[_ ]?of[_ ]?arms|wapen|map|kaart|flag|vlag|logo|seal|"
                  r"diagram|locator|locationmap)\b", re.I)


def commons_category_image(town):
    """Fallback: best usable image in the town's Commons category.
    Skips ships/maps/crests and prefers files whose name mentions the town."""
    token = town.lower().split()[0]  # e.g. "klein", "great", "victoria"
    for cat in (f"Category:{town}", f"Category:{town}, Western Cape"):
        try:
            data = _get_json(COMMONS, {
                "action": "query", "format": "json",
                "generator": "categorymembers", "gcmtitle": cat,
                "gcmtype": "file", "gcmlimit": "30",
                "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": "1200",
            })
        except Exception:
            continue
        candidates = []
        pages = (data.get("query") or {}).get("pages", {})
        for _, p in pages.items():
            title = p.get("title", "")
            for ii in p.get("imageinfo", []):
                mime = ii.get("mime", "")
                if not mime.startswith("image/") or "svg" in mime:
                    continue
                if JUNK.search(title):
                    continue
                candidates.append((title, ii.get("thumburl") or ii.get("url")))
        if candidates:
            # prefer a file that actually names the town, else first clean image
            for title, url in candidates:
                if token in title.lower():
                    return url
            return candidates[0][1]
    return None


def image_attribution(image_url):
    """Best-effort artist + license for a Wikimedia upload URL."""
    fname = urllib.parse.unquote(image_url.split("/")[-1])
    fname = re.sub(r"^\d+px-", "", fname)  # strip thumb prefix
    try:
        data = _get_json(COMMONS, {
            "action": "query", "format": "json", "titles": f"File:{fname}",
            "prop": "imageinfo", "iiprop": "extmetadata",
        })
        pages = (data.get("query") or {}).get("pages", {})
        for _, p in pages.items():
            md = (p.get("imageinfo") or [{}])[0].get("extmetadata", {})
            artist = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()
            lic = md.get("LicenseShortName", {}).get("value", "")
            return {"file": fname, "artist": artist, "license": lic}
    except Exception:
        pass
    return {"file": fname, "artist": "", "license": ""}


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())


def run(force=False):
    credits = {}
    cpath = OUT_DIR / "credits.json"
    if cpath.exists():
        credits = json.loads(cpath.read_text())

    for town, title in WIKI_TITLE.items():
        dest = OUT_DIR / f"{slug(town)}.jpg"
        if dest.exists() and not force:
            print(f"  =  {town} (have it)")
            continue

        url = OVERRIDE_URL.get(town)
        src = "override"
        if not url:
            url, _ = wiki_lead_image(title)
            src = "wikipedia"
        if not url:
            url = commons_category_image(town)
            src = "commons-category"
        if not url:
            print(f"  x  {town}: no image found — add one to OVERRIDE_URL")
            continue

        try:
            download(url, dest)
            credits[slug(town)] = {"town": town, "source": src, **image_attribution(url)}
            cpath.write_text(json.dumps(credits, indent=2, ensure_ascii=False))
            print(f"  +  {town}  <-  {src}")
        except Exception as e:
            print(f"  x  {town}: {e}")

    print(f"\nDone. Images in {OUT_DIR}")
    print("Review them, then commit site/public/images/towns/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download existing")
    args = ap.parse_args()
    run(force=args.force)
