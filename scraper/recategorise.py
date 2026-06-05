"""
recategorise.py — Fix restaurant town assignments

The corridor/waypoint searches stamped many restaurants with the nearest
*waypoint label* (e.g. "Glentana", "Victoria Bay") instead of the real town in
their address. This re-derives each restaurant's town from its actual address,
with postal-code and GPS fallbacks.

Usage:
    python recategorise.py            # DRY RUN — shows proposed changes only
    python recategorise.py --apply    # write the changes to the JSON files

Resolution order per restaurant:
    1. Locality token immediately before the postal code in the address
    2. Alias match across the whole address (specific towns prioritised)
    3. Postal-code map
    4. Nearest town centroid by GPS coordinates
"""

import re
import json
import glob
import math
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "restaurants"

# Canonical town -> alias substrings (lowercase). Order matters: more specific
# towns are listed first so they win over broad names like "george".
ALIASES = [
    ("Klein Brak River", ["klein brak", "kleinbrak", "little brak", "klipheuwel",
                            "fraai uitsig", "fraaiuitsig", "reebok", "tergniet"]),
    ("Great Brak River",  ["great brak", "groot brak", "grootbrak", "glentana"]),
    ("Hartenbos",         ["hartenbos"]),
    ("Wilderness",        ["wilderness", "hoekwil", "kleinkrantz", "kleinkrans"]),
    ("Sedgefield",        ["sedgefield", "swartvlei", "myoli"]),
    ("Victoria Bay",      ["victoria bay", "vic bay"]),
    ("Herolds Bay",       ["herolds bay", "herold's bay"]),
    ("Nature's Valley",   ["nature's valley", "natures valley", "natureʼs valley"]),
    ("Storms River",      ["storms river", "stormsrivier", "tsitsikamma",
                            "coldstream", "covie"]),
    ("Plettenberg Bay",   ["plettenberg", "plett", "keurbooms", "the crags",
                            "harkerville", "kranshoek", "kwanokuthula",
                            "new horizons", "bossiesgif"]),
    ("Knysna",            ["knysna", "thesen", "brenton", "belvidere", "rheenendal",
                            "leisure isle", "leisure island", "the heads",
                            "hunters home", "noetzie", "buffels bay", "buffalo bay"]),
    ("George",            ["george", "blanco", "pacaltsdorp", "heatherlands",
                            "kraaibosch", "loerie park", "denneoord", "rosemoor",
                            "thembalethu", "conville", "borchards", "bo-dorp"]),
    ("Mossel Bay",        ["mossel bay", "mosselbaai", "dana bay", "danabaai",
                            "santos", "diaz", "the point", "kwanonqaba",
                            "heiderand", "voorbaai", "asla", "riverside"]),
]

POSTAL = {
    "6529": "George", "6530": "George", "6531": "George",
    "6500": "Mossel Bay", "6506": "Mossel Bay",
    "6520": "Hartenbos",
    "6503": "Klein Brak River", "6505": "Klein Brak River",
    "6525": "Great Brak River",
    "6560": "Wilderness",
    "6573": "Sedgefield",
    "6570": "Knysna", "6571": "Knysna",
    "6600": "Plettenberg Bay",
    "6308": "Storms River",
}

# Town centroids for GPS fallback (approximate)
CENTROIDS = {
    "George":           (-33.9630, 22.4617),
    "Mossel Bay":       (-34.1830, 22.1460),
    "Hartenbos":        (-34.1130, 22.1010),
    "Klein Brak River": (-34.0840, 22.0640),
    "Great Brak River": (-34.0470, 22.2330),
    "Wilderness":       (-33.9990, 22.5790),
    "Sedgefield":       (-34.0180, 22.7900),
    "Knysna":           (-34.0360, 23.0480),
    "Plettenberg Bay":  (-34.0530, 23.3730),
    "Storms River":     (-33.9790, 23.8870),
    "Nature's Valley":  (-33.9810, 23.5620),
    "Victoria Bay":     (-34.0010, 22.5520),
    "Herolds Bay":      (-34.0840, 22.4030),
}


def _match_aliases(text: str):
    t = text.lower()
    for town, subs in ALIASES:
        if any(s in t for s in subs):
            return town
    return None


# Tokens that mark a segment as a street/venue line rather than a locality name.
STREET = re.compile(
    r"\b(rd|road|st|street|str|ave|avenue|dr|drive|way|lane|laan|weg|straat|"
    r"n\d|r\d{2,3}|shop|mall|centre|center|cnr|plot|portion|farm|unit|suite|"
    r"blvd|hwy|complex|building|sentrum)\b", re.I)


def locality_segments(address: str):
    """Comma-segments before the postal code that look like place names
    (not street/venue lines, not 'South Africa', not pure numbers)."""
    parts = [p.strip() for p in address.split(",")]
    pidx = None
    for i, seg in enumerate(parts):
        if re.search(r"\b\d{4}\b", seg):
            pidx = i
            break
    region = parts[:pidx] if pidx is not None else parts
    cands = []
    for s in region:
        if not s:
            continue
        if "south africa" in s.lower():
            continue
        if re.fullmatch(r"[\d\s]+", s):
            continue
        if STREET.search(s):
            continue
        cands.append(s)
    return cands


def match_locality(address: str):
    """Most-specific town match among the locality-like segments."""
    cands = locality_segments(address)
    if not cands:
        return None
    joined = " | ".join(cands).lower()
    for town, subs in ALIASES:        # ALIASES is ordered specific -> generic
        if any(s in joined for s in subs):
            return town
    return None


def postal_code(address: str):
    m = re.search(r"\b(\d{4})\b", address)
    return m.group(1) if m else None


def nearest_centroid(lat, lng):
    if not lat or not lng:
        return None
    best, bestd = None, 1e9
    for town, (clat, clng) in CENTROIDS.items():
        d = (lat - clat) ** 2 + (lng - clng) ** 2
        if d < bestd:
            best, bestd = town, d
    return best


def derive_town(rec: dict):
    addr = rec.get("address", "") or ""
    # 1. most-specific locality name (ignoring street/venue lines)
    m = match_locality(addr)
    if m:
        return m, "locality"
    # 2. whole-address alias match (specific towns prioritised by ALIASES order)
    m = _match_aliases(addr)
    if m:
        return m, "address"
    # 3. postal code map
    pc = postal_code(addr)
    if pc and pc in POSTAL:
        return POSTAL[pc], "postal"
    # 4. nearest centroid
    coords = rec.get("coordinates") or {}
    nc = nearest_centroid(coords.get("lat"), coords.get("lng"))
    if nc:
        return nc, "gps"
    return rec.get("town"), "unchanged"


def main(apply: bool):
    files = sorted(glob.glob(str(DATA_DIR / "*.json")))
    changes = []
    method_counts = {}
    new_dist = {}
    for f in files:
        if Path(f).name.startswith("_"):
            continue
        rec = json.load(open(f))
        old = rec.get("town")
        new, method = derive_town(rec)
        method_counts[method] = method_counts.get(method, 0) + 1
        new_dist[new] = new_dist.get(new, 0) + 1
        if new and new != old:
            changes.append((old, new, rec.get("name", ""), rec.get("address", "")[:55], f))
            if apply:
                rec["town"] = new
                json.dump(rec, open(f, "w"), indent=2, ensure_ascii=False)

    changes.sort(key=lambda c: (c[0] or "", c[1] or ""))
    print(f"{'APPLIED' if apply else 'DRY RUN'} — {len(changes)} town changes\n")
    cur = None
    for old, new, name, addr, _ in changes:
        key = f"{old}  ->  {new}"
        if key != cur:
            print(f"\n  {key}")
            cur = key
        print(f"      • {name}  [{addr}]")

    print("\n=== resolution method ===")
    for m, n in sorted(method_counts.items(), key=lambda x: -x[1]):
        print(f"  {m:10} {n}")
    print("\n=== NEW town distribution ===")
    for t, n in sorted(new_dist.items(), key=lambda x: -x[1]):
        print(f"  {t:18} {n}")
    if not apply:
        print("\n(Dry run — nothing written. Re-run with --apply to save.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes to JSON files")
    args = ap.parse_args()
    main(apply=args.apply)
