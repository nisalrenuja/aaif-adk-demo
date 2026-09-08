"""Fake travel inventory: flights, hotels and activities.

Everything a demo touches on stage should be deterministic. No network call, no
rate limit, no wifi. This module is the whole data layer for the demo.
"""

from __future__ import annotations

# Keyed by (origin, destination), both uppercase IATA codes.
FLIGHTS: dict[tuple[str, str], list[dict]] = {
    ("CMB", "SIN"): [
        {"carrier": "SriLankan", "number": "UL 306", "depart": "01:05", "arrive": "07:45", "price_usd": 288, "stops": 0},
        {"carrier": "Singapore Airlines", "number": "SQ 469", "depart": "09:20", "arrive": "16:05", "price_usd": 412, "stops": 0},
        {"carrier": "Malaysia Airlines", "number": "MH 178", "depart": "13:40", "arrive": "23:30", "price_usd": 231, "stops": 1},
    ],
    ("CMB", "DXB"): [
        {"carrier": "Emirates", "number": "EK 651", "depart": "03:40", "arrive": "06:55", "price_usd": 355, "stops": 0},
        {"carrier": "FlyDubai", "number": "FZ 558", "depart": "20:15", "arrive": "23:35", "price_usd": 249, "stops": 0},
    ],
    ("LHR", "CMB"): [
        {"carrier": "SriLankan", "number": "UL 504", "depart": "21:20", "arrive": "13:35", "price_usd": 640, "stops": 0},
        {"carrier": "Qatar Airways", "number": "QR 004", "depart": "14:05", "arrive": "09:40", "price_usd": 587, "stops": 1},
    ],
    ("SIN", "CMB"): [
        {"carrier": "SriLankan", "number": "UL 307", "depart": "08:55", "arrive": "10:20", "price_usd": 295, "stops": 0},
        {"carrier": "Scoot", "number": "TR 466", "depart": "17:30", "arrive": "19:05", "price_usd": 178, "stops": 0},
    ],
}

# Anything not in the table falls back to this, so the tool never dead ends.
GENERIC_FLIGHTS: list[dict] = [
    {"carrier": "Demo Air", "number": "DA 100", "depart": "08:00", "arrive": "12:30", "price_usd": 310, "stops": 0},
    {"carrier": "Demo Air", "number": "DA 240", "depart": "18:45", "arrive": "23:55", "price_usd": 205, "stops": 1},
]


# Keyed by lowercase city name.
HOTELS: dict[str, list[dict]] = {
    "kandy": [
        {"name": "Kandy Hills Rest", "area": "Hantana", "price_usd_per_night": 42, "rating": 4.1, "style": "budget guesthouse"},
        {"name": "Lakeside Boutique", "area": "Kandy Lake", "price_usd_per_night": 95, "rating": 4.5, "style": "boutique"},
        {"name": "Temple View Grand", "area": "City centre", "price_usd_per_night": 168, "rating": 4.7, "style": "colonial luxury"},
        {"name": "Mahaweli Eco Lodge", "area": "Katugastota", "price_usd_per_night": 61, "rating": 4.3, "style": "eco lodge"},
    ],
    "colombo": [
        {"name": "Fort Backpackers", "area": "Fort", "price_usd_per_night": 25, "rating": 3.9, "style": "hostel"},
        {"name": "Galle Face Residences", "area": "Galle Face", "price_usd_per_night": 140, "rating": 4.6, "style": "seafront"},
        {"name": "Cinnamon Gardens Villa", "area": "Colombo 7", "price_usd_per_night": 88, "rating": 4.4, "style": "villa"},
    ],
    "ella": [
        {"name": "Nine Arch Cabins", "area": "Ella town", "price_usd_per_night": 55, "rating": 4.4, "style": "cabin"},
        {"name": "Little Adam Retreat", "area": "Ella Rock road", "price_usd_per_night": 110, "rating": 4.6, "style": "retreat"},
    ],
    "galle": [
        {"name": "Rampart Walk Inn", "area": "Galle Fort", "price_usd_per_night": 70, "rating": 4.2, "style": "heritage"},
        {"name": "Unawatuna Beach House", "area": "Unawatuna", "price_usd_per_night": 120, "rating": 4.5, "style": "beachfront"},
    ],
}

GENERIC_HOTELS: list[dict] = [
    {"name": "Demo Central Hotel", "area": "City centre", "price_usd_per_night": 75, "rating": 4.0, "style": "mid range"},
    {"name": "Demo Budget Stay", "area": "Outskirts", "price_usd_per_night": 38, "rating": 3.7, "style": "budget"},
]

# Keyed by lowercase city name. duration_hours and price_usd feed the budget maths
# in later phases, so keep both fields on every entry.
ACTIVITIES: dict[str, list[dict]] = {
    "kandy": [
        {"name": "Temple of the Sacred Tooth Relic", "category": "culture", "duration_hours": 2, "price_usd": 12, "best_time": "morning"},
        {"name": "Kandy Lake walk", "category": "outdoors", "duration_hours": 1, "price_usd": 0, "best_time": "evening"},
        {"name": "Royal Botanical Gardens, Peradeniya", "category": "outdoors", "duration_hours": 3, "price_usd": 10, "best_time": "morning"},
        {"name": "Kandyan dance performance", "category": "culture", "duration_hours": 1, "price_usd": 8, "best_time": "evening"},
        {"name": "Ceylon tea factory tour, Hantana", "category": "food", "duration_hours": 3, "price_usd": 18, "best_time": "morning"},
        {"name": "Udawattakele forest hike", "category": "outdoors", "duration_hours": 3, "price_usd": 6, "best_time": "morning"},
        {"name": "Kandy market and street food crawl", "category": "food", "duration_hours": 2, "price_usd": 15, "best_time": "afternoon"},
        {"name": "Bahiravokanda Buddha viewpoint", "category": "culture", "duration_hours": 2, "price_usd": 3, "best_time": "sunset"},
        {"name": "Ambuluwawa Tower day trip", "category": "outdoors", "duration_hours": 5, "price_usd": 25, "best_time": "morning"},
    ],
    "colombo": [
        {"name": "Galle Face Green sunset", "category": "outdoors", "duration_hours": 2, "price_usd": 0, "best_time": "evening"},
        {"name": "Pettah market wander", "category": "culture", "duration_hours": 3, "price_usd": 5, "best_time": "morning"},
        {"name": "National Museum", "category": "culture", "duration_hours": 2, "price_usd": 9, "best_time": "afternoon"},
    ],
    "ella": [
        {"name": "Nine Arch Bridge", "category": "outdoors", "duration_hours": 2, "price_usd": 0, "best_time": "morning"},
        {"name": "Little Adams Peak hike", "category": "outdoors", "duration_hours": 3, "price_usd": 0, "best_time": "sunrise"},
        {"name": "Ravana Falls", "category": "outdoors", "duration_hours": 2, "price_usd": 4, "best_time": "afternoon"},
    ],
    "galle": [
        {"name": "Galle Fort ramparts at sunset", "category": "culture", "duration_hours": 2, "price_usd": 0, "best_time": "evening"},
        {"name": "Stilt fishermen at Koggala", "category": "culture", "duration_hours": 2, "price_usd": 10, "best_time": "morning"},
    ],
}

GENERIC_ACTIVITIES: list[dict] = [
    {"name": "Old town walking tour", "category": "culture", "duration_hours": 2, "price_usd": 15, "best_time": "morning"},
    {"name": "Local food market visit", "category": "food", "duration_hours": 2, "price_usd": 12, "best_time": "afternoon"},
    {"name": "Sunset viewpoint", "category": "outdoors", "duration_hours": 1, "price_usd": 0, "best_time": "evening"},
]
