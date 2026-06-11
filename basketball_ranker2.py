import requests
from datetime import datetime, timedelta
import zoneinfo

HIGHLIGHTLY_API_KEY = "5a5ad2b7-dc79-4187-af30-418b7bd28cae"
BASE_URL = "https://basketball.highlightly.net"
HEADERS = {"x-rapidapi-key": HIGHLIGHTLY_API_KEY}

BET365_ID = 2


def get_tomorrow_date():
    melbourne_tz = zoneinfo.ZoneInfo("Australia/Melbourne")
    tomorrow = (datetime.now(melbourne_tz) + timedelta(days=1)).date()
    return str(tomorrow)


def fetch_match_details(match_id):
    url = f"{BASE_URL}/matches/{match_id}"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    if isinstance(data, list) and len(data) > 0:
        match = data[0]
        return {
            "home": match.get("homeTeam", {}).get("name", "Unknown"),
            "away": match.get("awayTeam", {}).get("name", "Unknown"),
            "league": match.get("league", {}).get("name", "Unknown League"),
            "date": match.get("date", "")
        }
    return None


def parse_spread(market):
    """Parse spread value from market string like 'Spread -7/+7'."""
    try:
        parts = market.replace("Spread ", "").split("/")
        values = [abs(float(p)) for p in parts]
        return min(values)
    except:
        return None


def parse_total(market):
    """Parse total value from market string like 'Total Points 216.5'."""
    try:
        return float(market.replace("Total Points ", ""))
    except:
        return None


def fetch_all_odds(date):
    """Fetch all Bet365 odds for a given date, return dict of matchId -> {spread, total}."""
    url = f"{BASE_URL}/odds"
    all_odds = {}
    offset = 0
    limit = 5

    while True:
        response = requests.get(url, headers=HEADERS, params={
            "date": date,
            "bookmakerId": BET365_ID,
            
            "limit": limit,
            "offset": offset
        })
        data = response.json()
        odds_list = data.get("data", [])

        for entry in odds_list:
            match_id = entry.get("matchId")
            best_spread = None
            best_total = None

            for odd in entry.get("odds", []):
                market = odd.get("market", "")
                values = odd.get("values", [])

                if len(values) != 2:
                    continue

                diff = abs(values[0]["odd"] - values[1]["odd"])

                if market.startswith("Spread "):
                    parsed = parse_spread(market)
                    if parsed is not None:
                        if best_spread is None or diff < best_spread["diff"]:
                            best_spread = {"value": parsed, "diff": diff}

                if market.startswith("Total Points "):
                    parsed = parse_total(market)
                    if parsed is not None:
                        if best_total is None or diff < best_total["diff"]:
                            best_total = {"value": parsed, "diff": diff}

            if best_spread is not None and best_total is not None:
                all_odds[match_id] = {
                    "spread": best_spread["value"],
                    "total": best_total["value"]
                }

        pagination = data.get("pagination", {})
        total_count = pagination.get("totalCount", 0)
        offset += limit

        if offset >= total_count:
            break

    print(f"Found {len(all_odds)} games with Bet365 spread and total odds")
    return all_odds


def build_ranked_list(odds):
    """Fetch match details for each game and rank by spread then total."""
    games = []

    for match_id, odds_data in odds.items():
        match = fetch_match_details(match_id)
        if not match:
            continue

        games.append({
            "event_id": match_id,
            "home": match["home"],
            "away": match["away"],
            "league": match["league"],
            "spread": odds_data["spread"],
            "total": odds_data["total"]
        })

    # Sort: spread ASC, total ASC as tiebreaker
    ranked = sorted(games, key=lambda x: (x["spread"], x["total"]))

    for i, game in enumerate(ranked, 1):
        game["rank"] = i

    return ranked


def fetch_upcoming_games():
    melbourne_tz = zoneinfo.ZoneInfo("Australia/Melbourne")
    now = datetime.now(melbourne_tz)
    cutoff = now + timedelta(hours=48)

    print(f"\nFetching upcoming games...")

    # Fetch today and tomorrow to cover all timezone cases
    today = now.date()
    tomorrow = today + timedelta(days=1)

    odds_today = fetch_all_odds(str(today))
    odds_tomorrow = fetch_all_odds(str(tomorrow))
    odds = {**odds_today, **odds_tomorrow}

    # Filter to only games within next 48 hours
    games = []
    for match_id, odds_data in odds.items():
        match = fetch_match_details(match_id)
        if not match:
            continue
        match_time = match.get("date", "")
        if match_time:
            try:
                match_dt = datetime.fromisoformat(match_time.replace("Z", "+00:00"))
                match_dt_melb = match_dt.astimezone(melbourne_tz)
                if now <= match_dt_melb <= cutoff:
                    games.append({
                        "event_id": match_id,
                        "home": match["home"],
                        "away": match["away"],
                        "league": match["league"],
                        "spread": odds_data["spread"],
                        "total": odds_data["total"]
                    })
            except:
                pass

    ranked = sorted(games, key=lambda x: (x["spread"], x["total"]))
    for i, game in enumerate(ranked, 1):
        game["rank"] = i

    print(f"\n{len(ranked)} games ranked\n")
    return ranked


if __name__ == "__main__":
    games = fetch_upcoming_games()
    for g in games:
        print(f"#{g['rank']}  {g['home']} vs {g['away']}  |  Spread: {g['spread']}  |  Total: {g['total']}  |  {g['league']}")
