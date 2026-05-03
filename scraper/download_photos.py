"""
download_photos.py — One-time photo downloader
================================================
Fetches every Google Places photo referenced in data/restaurants/*.json,
saves them to site/public/images/<slug>/<index>.jpg, then rewrites the
JSON `photos[].url` to the local path (e.g. /images/emily-moon/0.jpg).

Run once:
    cd scraper
    python3 download_photos.py

After this you can turn off / restrict the API key — images are served
as static files from Netlify and never need the API again.
"""

import os
import json
import glob
import time
import hashlib
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("GOOGLE_PLACES_API_KEY")
REPO_ROOT  = Path(__file__).resolve().parent.parent
DATA_DIR   = REPO_ROOT / "data" / "restaurants"
IMG_DIR    = REPO_ROOT / "site" / "public" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"X-Goog-Api-Key": API_KEY}

def google_photo_url(name: str, width: int = 800) -> str:
    return (
        f"https://places.googleapis.com/v1/{name}/media"
        f"?maxWidthPx={width}&skipHttpRedirect=true&key={API_KEY}"
    )

def download_photo(name: str, dest: Path) -> bool:
    """Fetch a Google Places photo name → save as JPEG. Returns True on success."""
    try:
        # Step 1: get the redirect URI from Places API
        r = requests.get(google_photo_url(name), timeout=15)
        if r.status_code != 200:
            print(f"    ✗ API error {r.status_code} for {name[:40]}…")
            return False

        data = r.json()
        photo_uri = data.get("photoUri")
        if not photo_uri:
            print(f"    ✗ No photoUri in response for {name[:40]}…")
            return False

        # Step 2: fetch the actual image
        img = requests.get(photo_uri, timeout=20)
        if img.status_code != 200:
            print(f"    ✗ Image fetch failed {img.status_code}")
            return False

        content_type = img.headers.get("content-type", "image/jpeg")
        ext = ".jpg" if "jpeg" in content_type or "jpg" in content_type else ".webp" if "webp" in content_type else ".jpg"
        dest = dest.with_suffix(ext)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(img.content)
        return str(dest)  # return actual path with extension

    except Exception as e:
        print(f"    ✗ Exception: {e}")
        return False


def run():
    files = sorted(glob.glob(str(DATA_DIR / "*.json")))
    total_files  = len(files)
    total_photos = 0
    downloaded   = 0
    skipped      = 0
    errors       = 0

    print(f"Processing {total_files} restaurant files…\n")

    for i, fpath in enumerate(files, 1):
        try:
            data = json.loads(Path(fpath).read_text())
        except Exception:
            continue

        slug   = data.get("slug", Path(fpath).stem)
        photos = data.get("photos", [])
        if not photos:
            continue

        slug_dir = IMG_DIR / slug
        updated  = False

        for idx, photo in enumerate(photos):
            url = photo.get("url", "")

            # Already a local path — skip
            if url.startswith("/images/"):
                skipped += 1
                continue

            # Extract the "places/..." name from stored path or old full URL
            if url.startswith("places/"):
                name = url
            elif "places.googleapis.com" in url:
                import re
                m = re.search(r"(places/[^?&\s]+/photos/[^?&\s]+)", url)
                name = m.group(1) if m else None
            else:
                name = None

            if not name:
                print(f"  [{i}/{total_files}] {slug}: photo {idx} — unrecognised URL, skipping")
                continue

            dest_base = slug_dir / str(idx)
            # Check if already downloaded (any extension)
            existing = list(slug_dir.glob(f"{idx}.*"))
            if existing:
                # Already downloaded — just update the path
                rel = "/" + existing[0].relative_to(REPO_ROOT / "site" / "public").as_posix()
                photo["url"] = rel
                updated = True
                skipped += 1
                continue

            total_photos += 1
            print(f"  [{i}/{total_files}] {slug}: downloading photo {idx}…", end=" ", flush=True)
            result = download_photo(name, dest_base)

            if result:
                rel_path = "/" + Path(result).relative_to(REPO_ROOT / "site" / "public").as_posix()
                photo["url"] = rel_path
                updated = True
                downloaded += 1
                print(f"✓  →  {rel_path}")
            else:
                errors += 1
                # Keep original name so we can retry later
                photo["url"] = name

            time.sleep(0.15)  # be polite — ~6 req/s

        if updated:
            Path(fpath).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Done.")
    print(f"  Downloaded : {downloaded}")
    print(f"  Skipped    : {skipped}  (already local)")
    print(f"  Errors     : {errors}")
    print(f"\nImages saved to: site/public/images/")
    print(f"You can now turn off / restrict your Google Places API key.")


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in scraper/.env")
        exit(1)
    run()
