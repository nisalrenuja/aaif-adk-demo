"""Fake flight inventory.

Everything a demo touches on stage should be deterministic. No network call, no
rate limit, no wifi. This module is the whole data layer for Phase 0.
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
