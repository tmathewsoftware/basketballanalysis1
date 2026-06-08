import json
import os
from rapidfuzz import fuzz, process

DATABASE_FILE = "teams_database.json"
CACHE_FILE = "team_id_cache.json"
MATCH_THRESHOLD = 80  # Minimum similarity score to accept a match


def load_teams_database():
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(f"{DATABASE_FILE} not found. Run updateteams.py first.")
    with open(DATABASE_FILE) as f:
        data = json.load(f)
    return data.get("teams", [])


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE) as f:
        return json.load(f)


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def find_team_id(team_name):
    """
    Find the Highlightly team ID for a given team name.
    First checks the cache, then fuzzy matches against the local database.
    Returns (team_id, matched_name, score) or (None, None, 0) if no match found.
    """
    # Check cache first
    cache = load_cache()
    if team_name in cache:
        cached = cache[team_name]
        print(f"[Cache] '{team_name}' → '{cached['matched_name']}' (ID: {cached['team_id']})")
        return cached["team_id"], cached["matched_name"], 100

    # Load database and extract names
    teams = load_teams_database()
    team_names = [t["name"] for t in teams]

    # Fuzzy match
    result = process.extractOne(
        team_name,
        team_names,
        scorer=fuzz.token_sort_ratio
    )

    if result is None:
        print(f"[No Match] '{team_name}' — no match found in database.")
        return None, None, 0

    matched_name, score, index = result

    if score < MATCH_THRESHOLD:
        print(f"[Low Confidence] '{team_name}' → '{matched_name}' (score: {score}) — below threshold.")
        return None, None, score

    team_id = teams[index]["id"]
    print(f"[Matched] '{team_name}' → '{matched_name}' (ID: {team_id}, score: {score})")

    # Save to cache
    cache[team_name] = {
        "team_id": team_id,
        "matched_name": matched_name,
        "score": score
    }
    save_cache(cache)

    return team_id, matched_name, score


if __name__ == "__main__":
    # Test with some example team names
    test_teams = [
    "LA Lakers",
    "Real Madrid",
]

    print("=== Team Matcher Test ===\n")
    for name in test_teams:
        team_id, matched_name, score = find_team_id(name)
        print()