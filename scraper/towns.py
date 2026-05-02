"""
Garden Route towns and Google Places search queries.
Add or adjust queries here to expand coverage.
"""

TOWNS = [
    {
        "name": "Mossel Bay",
        "queries": [
            "restaurants Mossel Bay South Africa",
            "cafe Mossel Bay South Africa",
        ],
    },
    {
        "name": "George",
        "queries": [
            "restaurants George South Africa",
            "cafe George South Africa",
        ],
    },
    {
        "name": "Wilderness",
        "queries": [
            "restaurants Wilderness Garden Route South Africa",
        ],
    },
    {
        "name": "Sedgefield",
        "queries": [
            "restaurants Sedgefield South Africa",
        ],
    },
    {
        "name": "Knysna",
        "queries": [
            "restaurants Knysna South Africa",
            "cafe Knysna South Africa",
        ],
    },
    {
        "name": "Plettenberg Bay",
        "queries": [
            "restaurants Plettenberg Bay South Africa",
            "cafe Plettenberg Bay South Africa",
        ],
    },
    {
        "name": "Storms River",
        "queries": [
            "restaurants Storms River South Africa",
        ],
    },
]

# Cuisine types Claude may assign
CUISINE_TYPES = [
    "African", "Asian", "Bakery", "Bar", "Breakfast", "Burgers", "Cafe",
    "Fine Dining", "French", "Greek", "Grill", "Indian", "Italian",
    "Mediterranean", "Mexican", "Pizza", "Pub", "Seafood", "South African",
    "Sushi", "Thai", "Vegan", "Vegetarian", "Wine Bar",
]

# Tags Claude may assign
TAGS = [
    "BYO", "Child-friendly", "Dog-friendly", "Family-friendly", "Functions",
    "Garden seating", "Groups", "Late night", "Live music", "Ocean views",
    "Outdoor seating", "Pet-friendly", "Private dining", "Romantic",
    "Sea views", "Sports bar", "Takeaway", "Waterfront",
    "Wheelchair accessible", "Wine list",
]
