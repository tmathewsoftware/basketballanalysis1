import json
import os
import base64
import requests
from rapidfuzz import fuzz, process
from league_mapping import get_league_info

DATABASE_FILE = "teams_database.json"
CACHE_FILE = "team_id_cache.json"
MATCH_THRESHOLD = 80
TOP_N = 5

HIGHLIGHTLY_API_KEY = "5a5ad2b7-dc79-4187-af30-418b7bd28cae"
BASE_URL = "https://basketball.highlightly.net"
HEADERS = {"x-rapidapi-key": HIGHLIGHTLY_API_KEY}

GITHUB_API_BASE = "https://api.github.com"


def _get_github_config():
    """Read GitHub token and repo from Streamlit secrets, if available."""
    try:
        import streamlit as st
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        if token and repo:
            return token, repo
    except Exception:
        pass
    return None, None


def _github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }


def github_load_cache():
    """Load team_id_cache.json from GitHub repo. Returns dict or None if unavailable."""
    token, repo = _get_github_config()
    if not token or not repo:
        return None

    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{CACHE_FILE}"
    try:
        response = requests.get(url, headers=_github_headers(token))
        if response.status_code != 200:
            return None
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content)
    except Exception:
        return None


def github_save_cache(cache):
    """Push updated team_id_cache.json to GitHub repo."""
    token, repo = _get_github_config()
    if not token or not repo:
        return False

    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{CACHE_FILE}"

    # Get current file SHA (required for update)
    sha = None
    try:
        get_resp = requests.get(url, headers=_github_headers(token))
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
    except Exception:
        pass

    content_str = json.dumps(cache, indent=2)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": "Update team_id_cache.json via app",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha

    try:
        put_resp = requests.put(url, headers=_github_headers(token), json=payload)
        return put_resp.status_code in (200, 201)
    except Exception:
        return False


def load_teams_database():
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(f"{DATABASE_FILE} not found. Run updateteams.py first.")
    with open(DATABASE_FILE) as f:
        data = json.load(f)
    return data.get("teams", [])


def load_cache():
    """
    Load cache, preferring GitHub (persistent) over local file (ephemeral on cloud).
    Falls back to local file if GitHub isn't configured or fails.
    """
    github_cache = github_load_cache()
    if github_cache is not None:
        return github_cache

    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE) as f:
        return json.load(f)


def save_cache(cache):
    """
    Save cache both locally and to GitHub (if configured) for persistence
    across Streamlit Cloud restarts.
    """
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

    github_save_cache(cache)


def get_team_league(team_id):
    """Look up which league a team belongs to via the teams statistics endpoint."""
    try:
        url = f"{BASE_URL}/teams/statistics/{team_id}"
        response = requests.get(url, headers=HEADERS, params={"fromDate": "2023-08-06"})
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("leagueName")
        elif isinstance(data, dict):
            return data.get("leagueName")
    except:
        pass
    return None


def get_top_candidates(team_name, n=TOP_N):
    """Return top N fuzzy matches for a team name from the full database."""
    teams = load_teams_database()
    team_names = [t["name"] for t in teams]

    results = process.extract(
        team_name,
        team_names,
        scorer=fuzz.token_sort_ratio,
        limit=n
    )

    candidates = []
    for matched_name, score, index in results:
        candidates.append({
            "name": matched_name,
            "id": teams[index]["id"],
            "score": score
        })

    return candidates


def get_league_teams(league_name):
    """
    Fetch all teams in a league via the standings endpoint.
    Returns a list of candidate dicts, or None if league not mapped.
    """
    league_info = get_league_info(league_name)
    if not league_info:
        return None

    url = f"{BASE_URL}/standings"
    response = requests.get(url, headers=HEADERS, params={
        "leagueId": league_info["league_id"],
        "season": league_info["season"]
    })

    try:
        data = response.json()
    except:
        return None

    standings = data if isinstance(data, list) else data.get("data", [])

    candidates = []
    for entry in standings:
        # Standings structure may vary - try common patterns
        team = entry.get("team", entry)
        team_id = team.get("id")
        team_name = team.get("name")
        if team_id and team_name:
            candidates.append({
                "name": team_name,
                "id": team_id,
                "score": None  # No fuzzy score since this is league-based
            })

    return candidates if candidates else None


def resolve_team(team_name, league_name=None):
    """
    Try to resolve a team name to a Highlightly ID.
    Returns:
        - (team_id, matched_name, "auto") if confident match found
        - (None, candidates, "manual") if manual selection needed
          candidates may come from league standings (preferred) or fuzzy search (fallback)
    """
    # Check cache first
    cache = load_cache()
    if team_name in cache:
        cached = cache[team_name]
        return cached["team_id"], cached["matched_name"], "auto"

    # Try fuzzy match against full database
    teams = load_teams_database()
    team_names = [t["name"] for t in teams]

    result = process.extractOne(
        team_name,
        team_names,
        scorer=fuzz.token_sort_ratio
    )

    if result:
        matched_name, score, index = result
        if score >= MATCH_THRESHOLD:
            team_id = teams[index]["id"]
            cache[team_name] = {
                "team_id": team_id,
                "matched_name": matched_name,
                "score": score
            }
            save_cache(cache)
            return team_id, matched_name, "auto"

    # Manual selection needed — prefer league-based candidates if available
    if league_name:
        league_candidates = get_league_teams(league_name)
        if league_candidates:
            return None, league_candidates, "manual"

    # Fallback to generic fuzzy candidates
    candidates = get_top_candidates(team_name)
    return None, candidates, "manual"


def confirm_team_selection(team_name, selected_name, selected_id):
    """Save a manually selected team mapping to cache."""
    cache = load_cache()
    cache[team_name] = {
        "team_id": selected_id,
        "matched_name": selected_name,
        "score": 100
    }
    save_cache(cache)