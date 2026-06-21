"""
Maps BetsAPI league names to Highlightly league IDs.
Used to fetch standings for a specific league when team name matching fails,
so the user can pick the correct team from a relevant shortlist.
"""

LEAGUE_MAP = {
    # USA
    "WNBA": {"league_id": 11847, "season": 2025},
    "NBA": {"league_id": 10996, "season": 2025},
    "NCAA": {"league_id": 99500, "season": 2025},

    # Europe
    "Turkiye BSL": {"league_id": 87586, "season": 2025},
    "Poland PLK": {"league_id": 62056, "season": 2025},
    "France Ligue B": {"league_id": 7592, "season": 2025},
    "Czechia NBL": {"league_id": 28016, "season": 2025},
    "Germany BBL": {"league_id": 34824, "season": 2025},
    "Israel Super League": {"league_id": 44185, "season": 2025},

    # Americas
    "Argentina Liga A": {"league_id": 16102, "season": 2025},
    "Puerto Rico Superior Nacional": {"league_id": 65460, "season": 2025},
    "Venezuela Superliga": {"league_id": 234809, "season": 2025},
    "Dominican Republic LNB": {"league_id": 324164, "season": 2025},
    "Paraguay Primera": {"league_id": 220342, "season": 2025},
    "Uruguay Liga Uruguaya": {"league_id": 94394, "season": 2025},

    # Asia
    "Chinese Taipei P League": {"league_id": 343737, "season": 2025},
    "Vietnam VBA": {"league_id": 235660, "season": 2025},
}


def get_league_info(betsapi_league_name):
    """
    Try to find a Highlightly league match for a BetsAPI league name.
    Returns dict with league_id and season, or None if not mapped.
    """
    # Exact match first
    if betsapi_league_name in LEAGUE_MAP:
        return LEAGUE_MAP[betsapi_league_name]

    # Try partial/fuzzy match on keywords
    name_lower = betsapi_league_name.lower()
    for key, value in LEAGUE_MAP.items():
        if key.lower() in name_lower or name_lower in key.lower():
            return value

    return None