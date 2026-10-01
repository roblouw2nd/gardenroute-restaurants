"""
refresh_from_web.py — Check listing facts against each restaurant's own website.

No API keys. For every listing with its own website, fetch the homepage (and
its contact page) and read what the restaurant itself publishes:

  - phone numbers, from tel: links and schema.org markup
  - opening hours, from schema.org markup (openingHoursSpecification)
  - whether the website still loads at all

Two steps, with a person in between:

  1. python refresh_from_web.py
     Writes web_refresh.csv: one row per difference between a listing and the
     restaurant's site. "apply" is pre-filled with "yes" only where the listing
     has a gap (no phone, no hours) that the site fills; conflicts are "no"
     until someone decides which side is right.

  2. Review web_refresh.csv, then:
     python refresh_from_web.py --apply

Ratings and review counts are Google's and are not touched here.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from find_menus import SKIP_HOSTS, LinkParser, fetch, site_key

DATA_DIR = Path(__file__).parent.parent / "data" / "restaurants"
REPORT = Path(__file__).parent / "web_refresh.csv"
FIELDS = ["slug", "name", "field", "current", "found", "source", "note", "apply"]

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_ALIASES = {d[:2]: d for d in DAYS} | {d[:3]: d for d in DAYS} | {d: d for d in DAYS}
BUSINESS_TYPES = {"Restaurant", "LocalBusiness", "FoodEstablishment", "CafeOrCoffeeShop", "BarOrPub",
                  "Bakery", "FastFoodRestaurant", "Winery", "Brewery", "Hotel", "LodgingBusiness", "Organization"}


class JsonLdParser(HTMLParser):
    """Collects the contents of <script type="application/ld+json"> blocks."""

    def __init__(self):
        super().__init__()
        self.blocks, self._in = [], False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and (dict(attrs).get("type") or "").lower() == "application/ld+json":
            self._in = True
            self.blocks.append("")

    def handle_data(self, data):
        if self._in:
            self.blocks[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self._in = False


def walk(node):
    """Yield every dict inside a parsed JSON-LD document."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def phone_digits(raw: str) -> str:
    """'+27 (0)44 382 5555' / '044 382 5555' → '27443825555'. '' if not a plausible SA number."""
    digits = re.sub(r"\D", "", re.sub(r"\(0\)", "", raw or ""))
    if digits.startswith("0027"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 10:
        digits = "27" + digits[1:]
    return digits if len(digits) == 11 and digits.startswith("27") else ""


def format_phone(digits: str) -> str:
    """'27443825555' → '+27 44 382 5555' (the format the listings already use)."""
    return f"+{digits[:2]} {digits[2:4]} {digits[4:7]} {digits[7:]}"


def format_time(value: str) -> str:
    """'09:00' / '21:30:00' → '9:00 AM' / '9:30 PM', matching the stored hours."""
    m = re.match(r"^(\d{1,2}):(\d{2})", value or "")
    if not m:
        return ""
    hour, minute = int(m.group(1)), m.group(2)
    return f"{hour % 12 or 12}:{minute} {'AM' if hour < 12 else 'PM'}"


def hours_from_jsonld(node: dict) -> dict:
    """{'monday': '9:00 AM – 5:00 PM', …} from openingHoursSpecification, or {} if unusable."""
    specs = node.get("openingHoursSpecification")
    if isinstance(specs, dict):
        specs = [specs]
    if not isinstance(specs, list):
        return {}
    hours = {}
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        opens, closes = format_time(str(spec.get("opens", ""))), format_time(str(spec.get("closes", "")))
        days = spec.get("dayOfWeek", [])
        for day in days if isinstance(days, list) else [days]:
            key = DAY_ALIASES.get(str(day).rsplit("/", 1)[-1].lower())
            if key and opens and closes and opens != closes:
                hours[key] = f"{opens} – {closes}"
    return hours


def read_page(url: str) -> dict:
    """Fetch one page and pull out phones, hours and outgoing links."""
    final, ctype, body = fetch(url)
    html = body.decode("utf-8", errors="replace") if "html" in ctype.lower() else ""
    links, ld = LinkParser(), JsonLdParser()
    for parser in (links, ld):
        try:
            parser.feed(html)
        except Exception:  # noqa: BLE001 — malformed HTML
            pass

    phones, hours = [], {}
    for href, _ in links.links:
        if (href or "").lower().startswith("tel:"):
            phones.append(phone_digits(href[4:]))
    for block in ld.blocks:
        try:
            doc = json.loads(block)
        except ValueError:
            continue
        for node in walk(doc):
            types = node.get("@type", [])
            types = set(types if isinstance(types, list) else [types])
            if types & BUSINESS_TYPES:
                phones.append(phone_digits(str(node.get("telephone", ""))))
                hours = hours or hours_from_jsonld(node)
    return {"url": final, "phones": [p for p in dict.fromkeys(phones) if p], "hours": hours,
            "digits": re.sub(r"\D", "", html),   # to spot a number written as plain text
            "links": [(urljoin(final, h or ""), t) for h, t in links.links]}


def check(record: dict, shared_hosts: set) -> list[dict]:
    """Compare one listing with its own website. Returns report rows."""
    def row(field, current, found, source, note, apply="no"):
        return {"slug": record["slug"], "name": record["name"], "field": field, "current": current,
                "found": found, "source": source, "note": note, "apply": apply}

    site = record.get("website", "")
    host = urlparse(site).netloc.lower()
    if not site or any(s in host for s in SKIP_HOSTS):
        return []
    try:
        home = read_page(site)
    except Exception as e:  # noqa: BLE001 — any network/SSL/HTTP failure
        return [row("website", site, "", site, f"site did not load ({type(e).__name__}) — check it is still open")]

    pages = [home]
    contact = next((u for u, text in home["links"]
                    if re.search(r"contact|kontak|find us", text or "", re.I)
                    and site_key(urlparse(u).netloc) == site_key(urlparse(home["url"]).netloc)
                    and u.rstrip("/") != home["url"].rstrip("/")), None)
    if contact:
        try:
            pages.append(read_page(contact))
        except Exception:  # noqa: BLE001
            pass

    rows = []
    # A chain's national site lists head-office details, not this branch's.
    chain = site_key(host) in shared_hosts
    phones = list(dict.fromkeys(p for page in pages for p in page["phones"]))
    current = phone_digits(record.get("phone", ""))
    if phones and not chain:
        source = next(page["url"] for page in pages if page["phones"])
        if not current:
            rows.append(row("phone", record.get("phone", ""), format_phone(phones[0]), source,
                            "listing has no phone", "yes" if len(phones) == 1 else "no"))
        elif current not in phones and not any(current[2:] in page["digits"] for page in pages):
            rows.append(row("phone", record.get("phone", ""), " / ".join(format_phone(p) for p in phones[:3]),
                            source, "site shows a different number"))

    hours_page = next((page for page in pages if page["hours"]), None)
    if hours_page and not chain:
        stored = record.get("opening_hours") or {}
        has_hours = any(v and v != "Hours not available" for v in stored.values())
        found = {d: hours_page["hours"].get(d, "Closed") for d in DAYS}
        plain = lambda h: {d: re.sub(r"\s", " ", str(h.get(d, ""))) for d in DAYS}  # noqa: E731
        if plain(found) != plain(stored):
            rows.append(row("opening_hours", json.dumps(stored, ensure_ascii=False), json.dumps(found, ensure_ascii=False),
                            hours_page["url"], "listing has no hours" if not has_hours else "site shows different hours",
                            "no" if has_hours else "yes"))
    return rows


def crawl(limit: int):
    records = [json.loads(p.read_text()) for p in sorted(DATA_DIR.glob("*.json")) if not p.name.startswith("_")]
    hosts = Counter(site_key(urlparse(r.get("website", "")).netloc) for r in records if r.get("website"))
    shared = {h for h, n in hosts.items() if n > 1}
    records = [r for r in records if not r.get("claimed")]   # an owner's own details win
    if limit:
        records = records[:limit]

    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = [r for found in pool.map(lambda rec: check(rec, shared), records) for r in found]

    with open(REPORT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["field"], r["apply"] != "yes", r["slug"])))

    print(f"Checked {len(records)} listings against their own websites.")
    for (field, note), n in sorted(Counter((r["field"], r["note"].split(" (")[0]) for r in rows).items()):
        print(f"  {field}: {note} — {n}")
    print(f"{sum(r['apply'] == 'yes' for r in rows)} rows pre-marked to apply. Review {REPORT}, then run with --apply.")


def apply_report():
    """Write every row a reviewer has marked apply=yes into the listing JSON."""
    with open(REPORT, newline="") as f:
        approved = [r for r in csv.DictReader(f) if r["apply"].strip().lower() == "yes"]
    now = datetime.now(timezone.utc).isoformat()
    for row in approved:
        path = DATA_DIR / f"{row['slug']}.json"
        record = json.loads(path.read_text())
        if row["field"] == "phone":
            record["phone"] = row["found"].split(" / ")[0]
        elif row["field"] == "opening_hours":
            record["opening_hours"] = json.loads(row["found"])
        else:
            continue
        record["last_updated"] = now
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"Applied {len(approved)} changes.")


def main():
    ap = argparse.ArgumentParser(description="Check listings against restaurants' own websites")
    ap.add_argument("--apply", action="store_true", help="write the reviewed web_refresh.csv into the listings")
    ap.add_argument("--limit", type=int, default=0, help="only check the first N listings")
    args = ap.parse_args()
    return apply_report() if args.apply else crawl(args.limit)


if __name__ == "__main__":
    sys.exit(main())
