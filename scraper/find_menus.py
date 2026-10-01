"""
find_menus.py — Find each restaurant's own menu page and store it as menu_url.

Two steps, with a person in between:

  1. python find_menus.py
     For every listing that has a website but no menu_url, fetch the homepage,
     look for a link to a menu on the restaurant's own site (or a PDF it links
     to), confirm the link loads, and write menu_candidates.csv. The "apply"
     column is pre-filled with "yes" for confident matches.

  2. Review menu_candidates.csv — change "apply" to yes/no, or correct a
     menu_url by hand — then:
     python find_menus.py --apply
     Writes menu_url into the listing JSON for every row marked "yes".

    python find_menus.py --limit 20      # first 20 listings only (for testing)

Standard library only — no API keys needed.
"""

import argparse
import csv
import json
import re
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DATA_DIR = Path(__file__).parent.parent / "data" / "restaurants"
REPORT = Path(__file__).parent / "menu_candidates.csv"

USER_AGENT = "Mozilla/5.0 (compatible; gardenroute-restaurants.co.za menu-link check; +https://www.gardenroute-restaurants.co.za/about/)"
TIMEOUT = 15

# Websites that are profiles rather than the restaurant's own site — no menu to find.
SKIP_HOSTS = ("facebook.com", "instagram.com", "linktr.ee", "google.com", "goo.gl",
              "tripadvisor.", "wa.me", "whatsapp.com", "booking.com", "airbnb.", "lekkeslaap.")

MENU_WORDS = re.compile(r"\b(menus?|spyskaart|food\s*menu|our\s*food)\b", re.I)
# Partial or unrelated menus — a "View menu" button should open the main food menu.
NOT_MENU = re.compile(r"(wine|drinks?|cocktail|kids|wedding|function|conference|spa|room|accommodation|breakfast|takeaway|take-away|specials)", re.I)


class LinkParser(HTMLParser):
    """Collects (href, visible text) for every <a> on a page."""

    def __init__(self):
        super().__init__()
        self.links, self._href, self._text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._text = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def fetch(url: str, max_bytes: int = 600_000):
    """GET a URL. Returns (final_url, content_type, body_bytes) or raises."""
    ctx = ssl.create_default_context()
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"})
    with urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        return resp.geturl(), resp.headers.get("Content-Type", ""), resp.read(max_bytes)


def site_key(host: str) -> str:
    """'www.example.co.za' → 'example.co.za' (good enough to compare a site with itself)."""
    return host.lower().removeprefix("www.")


def score(href: str, text: str, home: str) -> int:
    """Higher = more likely to be the main food menu. 0 = not a candidate."""
    path = urlparse(href).path.lower()
    is_pdf = path.endswith(".pdf")
    same_site = site_key(urlparse(href).netloc) == site_key(urlparse(home).netloc)
    if not (same_site or is_pdf):
        return 0
    if href.rstrip("/") == home.rstrip("/"):
        return 0
    text_hit, path_hit = bool(MENU_WORDS.search(text)), "menu" in path or "spyskaart" in path
    if not (text_hit or path_hit):
        return 0
    points = 0
    if text.strip().lower() in ("menu", "menus", "our menu", "the menu", "food menu", "view menu", "spyskaart"):
        points += 6
    elif text_hit:
        points += 3
    if path_hit:
        points += 3
    if is_pdf:
        points += 1
    if NOT_MENU.search(text) or NOT_MENU.search(path):
        points -= 4
    return max(points, 0)


def find_menu(record: dict) -> dict:
    """Returns a report row for one listing."""
    row = {"slug": record["slug"], "name": record["name"], "website": record.get("website", ""),
           "menu_url": "", "link_text": "", "score": 0, "status": ""}
    site = record.get("website", "")
    host = urlparse(site).netloc.lower()
    if not site or any(s in host for s in SKIP_HOSTS):
        row["status"] = "skipped: no own website"
        return row
    try:
        home, ctype, body = fetch(site)
    except Exception as e:  # noqa: BLE001 — any network/SSL/HTTP failure just means "not found"
        row["status"] = f"site unreachable: {type(e).__name__}"
        return row
    if "html" not in ctype.lower():
        row["status"] = "homepage is not HTML"
        return row

    parser = LinkParser()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 — malformed HTML
        pass

    best = None
    for href, text in parser.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(home, href).split("#")[0]
        if not absolute.startswith("http"):
            continue
        s = score(absolute, text, home)
        if s and (best is None or s > best[0]):
            best = (s, absolute, text)

    if not best:
        row["status"] = "no menu link on homepage"
        return row

    row["score"], row["menu_url"], row["link_text"] = best[0], best[1], best[2][:60]
    try:
        final, ctype, _ = fetch(best[1], max_bytes=2048)
        if site_key(urlparse(final).netloc) != site_key(urlparse(best[1]).netloc) and not final.lower().endswith(".pdf"):
            row["status"] = "menu link redirects off-site"
        else:
            row["menu_url"], row["status"] = final, "found"
    except Exception as e:  # noqa: BLE001
        row["status"] = f"menu link broken: {type(e).__name__}"
    return row


def main():
    ap = argparse.ArgumentParser(description="Find restaurant menu links")
    ap.add_argument("--apply", action="store_true", help="write the reviewed menu_candidates.csv into the listing JSON files")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N listings")
    ap.add_argument("--min-score", type=int, default=6, help="score at which 'apply' is pre-filled with yes (default 6)")
    args = ap.parse_args()

    if args.apply:
        return apply_report()

    records = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        rec = json.loads(path.read_text())
        if not rec.get("menu_url"):
            records.append((path, rec))
    if args.limit:
        records = records[: args.limit]

    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(lambda pr: find_menu(pr[1]), records))

    for r in rows:
        r["apply"] = "yes" if r["status"] == "found" and r["score"] >= args.min_score else "no"

    with open(REPORT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["status"] != "found", -r["score"], r["slug"])))

    found = [r for r in rows if r["status"] == "found"]
    print(f"Checked {len(rows)} listings: {len(found)} menu links found, "
          f"{sum(r['apply'] == 'yes' for r in rows)} pre-marked to apply.")
    print(f"Review {REPORT}, then run: python find_menus.py --apply")


def apply_report():
    """Write menu_url for every row a reviewer has marked apply=yes."""
    with open(REPORT, newline="") as f:
        approved = [r for r in csv.DictReader(f) if r["apply"].strip().lower() == "yes" and r["menu_url"]]
    now = datetime.now(timezone.utc).isoformat()
    for row in approved:
        path = DATA_DIR / f"{row['slug']}.json"
        rec = json.loads(path.read_text())
        rec["menu_url"] = row["menu_url"]
        rec["last_updated"] = now
        path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    print(f"Applied {len(approved)} menu links.")


if __name__ == "__main__":
    sys.exit(main())
