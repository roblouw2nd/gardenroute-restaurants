"""
towns.py — Garden Route towns, suburbs, N2 corridor coverage, and shared taxonomy.

Two types of entries:
  TOWNS    — named towns, searched by text query (paginated, up to 60 results each)
  CORRIDOR — GPS waypoints along the N2 for areas between towns, searched by radius

CUISINE_TYPES and TAGS are used by enricher.py to constrain Claude's output.
"""

CUISINE_TYPES = [
    "South African", "Seafood", "Steakhouse", "Italian", "Mediterranean",
    "Pizza", "Burgers", "Breakfast & Brunch", "Cafe", "Coffee Shop",
    "Bakery", "Deli", "Tapas", "Sushi", "Asian", "Indian", "Mexican",
    "Middle Eastern", "Vegetarian", "Vegan", "Farm-to-table", "Fine Dining",
    "Pub & Grill", "Bar", "Wine Bar", "Cocktail Bar", "Desserts & Ice Cream",
    "Sandwiches & Wraps", "Fast Food", "Food Truck", "Buffet",
]

TAGS = [
    "Ocean views", "Lagoon views", "Mountain views", "Garden setting",
    "Beachfront", "Waterfront", "Outdoor seating", "Dog friendly",
    "Family friendly", "Child friendly", "Good for groups", "Date night",
    "Romantic", "Casual", "Upmarket", "Live music", "Sports bar",
    "Pet friendly", "Wheelchair accessible", "Takeaway", "Delivery",
    "Reservation recommended", "Walk-ins welcome", "Open late",
    "Open Sundays", "Breakfast all day", "BYO wine", "Full bar",
    "Local produce", "Wood-fired", "Farm stall", "Market", "Deli counter",
]


# ---------------------------------------------------------------------------
# Named towns — text-query based
# More queries per town = better coverage of suburbs and specific cuisines
# ---------------------------------------------------------------------------

TOWNS = [
    {
        "name": "Knysna",
        "queries": [
            "restaurants in Knysna South Africa",
            "cafes in Knysna South Africa",
            "restaurants Thesen Island Knysna",
            "restaurants Knysna Waterfront",
            "restaurants Leisure Island Knysna",
            "restaurants Knysna Heads South Africa",
            "bars and pubs Knysna South Africa",
            "breakfast restaurants Knysna South Africa",
        ],
    },
    {
        "name": "Plettenberg Bay",
        "queries": [
            "restaurants in Plettenberg Bay South Africa",
            "cafes in Plettenberg Bay South Africa",
            "restaurants Plett South Africa",
            "restaurants Beacon Isle Plettenberg Bay",
            "restaurants Central Beach Plettenberg Bay",
            "restaurants Keurbooms Plettenberg Bay",
            "bars Plettenberg Bay South Africa",
            "breakfast Plettenberg Bay South Africa",
        ],
    },
    {
        "name": "Wilderness",
        "queries": [
            "restaurants in Wilderness Garden Route South Africa",
            "cafes in Wilderness Western Cape",
            "restaurants Wilderness beach South Africa",
            "breakfast Wilderness Garden Route",
        ],
    },
    {
        "name": "George",
        "queries": [
            "restaurants in George Western Cape South Africa",
            "cafes in George South Africa",
            "restaurants George CBD South Africa",
            "restaurants Pacaltsdorp George South Africa",
            "restaurants Heatherlands George South Africa",
            "restaurants Garden Route Mall George",
            "restaurants Loerie Park George South Africa",
            "restaurants Kraaibosch George South Africa",
            "restaurants Thembalethu George South Africa",
            "restaurants Rosemoor George South Africa",
            "breakfast restaurants George South Africa",
            "fine dining George South Africa",
            "steakhouses George Western Cape",
            "pizza restaurants George South Africa",
            "sushi George South Africa",
        ],
    },
    {
        "name": "Mossel Bay",
        "queries": [
            "restaurants in Mossel Bay South Africa",
            "cafes in Mossel Bay South Africa",
            "restaurants Mossel Bay harbour",
            "restaurants Dana Bay Mossel Bay",
            "restaurants Hartenbos Mossel Bay",
            "restaurants Groot Brak River",
            "restaurants Santos Beach Mossel Bay",
            "seafood restaurants Mossel Bay",
            "breakfast Mossel Bay South Africa",
        ],
    },
    {
        "name": "Sedgefield",
        "queries": [
            "restaurants in Sedgefield Garden Route South Africa",
            "cafes in Sedgefield South Africa",
            "restaurants Swartvlei Sedgefield",
            "breakfast Sedgefield South Africa",
        ],
    },
    {
        "name": "Storms River",
        "queries": [
            "restaurants in Storms River South Africa",
            "cafes Storms River Tsitsikamma South Africa",
            "restaurants Tsitsikamma South Africa",
            "restaurants Nature's Valley South Africa",
        ],
    },
    {
        "name": "Groot Brak River",
        "queries": [
            "restaurants in Groot Brak River South Africa",
            "cafes Grootbrakrivier South Africa",
        ],
    },
    {
        "name": "Hartenbos",
        "queries": [
            "restaurants in Hartenbos South Africa",
            "cafes in Hartenbos South Africa",
        ],
    },
]


# ---------------------------------------------------------------------------
# N2 corridor — GPS waypoints for areas between towns
# Each entry covers a ~8km radius; waypoints overlap slightly to avoid gaps.
# Coordinates mapped along the N2 Garden Route from Mossel Bay → Storms River.
# ---------------------------------------------------------------------------

CORRIDOR = [
    {
        "name": "Glentana",          # Between George and Mossel Bay coast
        "waypoints": [
            (-34.0450, 22.1200),
        ],
        "radius_m": 6000,
    },
    {
        "name": "Herolds Bay",       # West of George on the coast
        "waypoints": [
            (-34.0835, 22.1580),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Victoria Bay",      # Small bay between George and Wilderness
        "waypoints": [
            (-34.0200, 22.5200),
        ],
        "radius_m": 4000,
    },
    {
        "name": "Hoekwil",           # Between Wilderness and Sedgefield
        "waypoints": [
            (-33.9800, 22.6100),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Rondevlei",         # Near Sedgefield
        "waypoints": [
            (-34.0050, 22.7200),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Buffels Bay",       # Between Sedgefield and Knysna
        "waypoints": [
            (-34.0500, 22.8500),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Brenton-on-Sea",    # West side of Knysna, coastal
        "waypoints": [
            (-34.0850, 23.0000),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Belvidere",         # South of Knysna — Belvidere Estate & Brenton
        "waypoints": [
            (-34.0600, 23.0300),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Rheenendal",        # Inland between Knysna and George
        "waypoints": [
            (-33.9200, 23.0600),
        ],
        "radius_m": 6000,
    },
    {
        "name": "Harkerville",       # Between Knysna and Plett
        "waypoints": [
            (-33.9700, 23.2500),
        ],
        "radius_m": 6000,
    },
    {
        "name": "Kranshoek",         # Between Knysna and Plett, coastal
        "waypoints": [
            (-34.0300, 23.2800),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Keurboomstrand",    # East of Plett
        "waypoints": [
            (-34.0100, 23.4700),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Nature's Valley",   # Between Plett and Storms River
        "waypoints": [
            (-33.9750, 23.5500),
        ],
        "radius_m": 5000,
    },
    {
        "name": "Coldstream",        # Near Storms River pass
        "waypoints": [
            (-33.9200, 23.6200),
        ],
        "radius_m": 5000,
    },
]
