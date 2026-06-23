import requests
from tabulate import tabulate

API_TOKEN = "254448-7egKxs8eGrHjXY"
BASE_URL = "https://api.b365api.com"

#finding games

def fetch_upcoming_games():
    url = f"{BASE_URL}/v1/events/upcoming"
    params = {
        "sport_id": 18,       # 18 = Basketball
        "token": API_TOKEN,
        "page": 1
    }

    all_events = []
    while True:
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("success") != 1:
            print("Error fetching games:", data)
            break

        events = data.get("results", [])
        if not events:
            break

        all_events.extend(events)

        # Handle pagination
        pager = data.get("pager", {})
        total = pager.get("total", 0)
        per_page = pager.get("per_page", 50)
        current_page = pager.get("page", 1)

        if current_page * per_page >= total:
            break

        params["page"] += 1

    return all_events


# ─────────────────────────────────────────────
# STEP 2: Fetch odds (spread + totals) for a game
# ─────────────────────────────────────────────
def fetch_odds(event_id):
    url = f"{BASE_URL}/v2/event/odds"
    params = {
        "token": API_TOKEN,
        "event_id": event_id,
        "source": "bet365",
        "since": ""
    }

    response = requests.get(url, params=params)
    data = response.json()

    spread = None
    total = None

    if data.get("success") != 1:
        return spread, total

    odds = data.get("results", {}).get("odds", {})

    # 18_2 = Spread/Handicap
    spread_odds = odds.get("18_2", [])
    if spread_odds:
        try:
            spread = abs(float(spread_odds[0].get("handicap", 0)))
        except:
            pass

    # 18_3 = Totals/Over-Under
    total_odds = odds.get("18_3", [])
    if total_odds:
        try:
            total = float(total_odds[0].get("handicap", 0))
        except:
            pass

    return spread, total


# ─────────────────────────────────────────────
# STEP 3: Build ranked game list (ALL available games, no date filter)
# ─────────────────────────────────────────────
def build_ranked_list(events):
    games = []

    from datetime import datetime, timedelta
    import zoneinfo

    melbourne_tz = zoneinfo.ZoneInfo("Australia/Melbourne")
    now = datetime.now(melbourne_tz)
    today_date = now.date()
    cutoff_date = today_date + timedelta(days=3)

    print(f"\nFound {len(events)} total upcoming games. Filtering to next 3 days and fetching odds... please wait.\n")

    # Pre-filter to next 7 days before fetching odds (saves API calls)
    filtered_events = []
    for event in events:
        event_time = event.get("time", "")
        if event_time:
            try:
                event_date = datetime.fromtimestamp(int(event_time), tz=melbourne_tz).date()
                if today_date <= event_date <= cutoff_date:
                    filtered_events.append(event)
            except:
                pass

    print(f"{len(filtered_events)} games within the next 3 days. Fetching odds...\n")

    for event in filtered_events:
        event_id = event.get("id")
        home = event.get("home", {}).get("name", "Unknown")
        away = event.get("away", {}).get("name", "Unknown")
        league = event.get("league", {}).get("name", "Unknown League")
        event_time = event.get("time", "")

        spread, total = fetch_odds(event_id)

        # Only include games that have both spread and total
        if spread is not None and total is not None:
            # Determine date category: today / tomorrow / later
            date_category = "later"
            event_date_str = None
            event_time_str = None
            if event_time:
                try:
                    event_dt = datetime.fromtimestamp(int(event_time), tz=melbourne_tz)
                    event_date = event_dt.date()
                    event_date_str = event_date.strftime("%d %b %Y")
                    event_time_str = event_dt.strftime("%I:%M %p")
                    days_diff = (event_date - today_date).days
                    if days_diff == 0:
                        date_category = "today"
                    elif days_diff == 1:
                        date_category = "tomorrow"
                    else:
                        date_category = "later"
                except:
                    pass

            games.append({
                "event_id": event_id,
                "home": home,
                "away": away,
                "league": league,
                "time": event_time,
                "date_category": date_category,
                "date_str": event_date_str,
                "time_str": event_time_str,
                "spread": spread,
                "total": total
            })

    # Sort: spread ASC first, then total ASC as tiebreaker
    ranked = sorted(games, key=lambda x: (x["spread"], x["total"]))

    # Add rank numbers
    for i, game in enumerate(ranked, 1):
        game["rank"] = i

    return ranked


# ─────────────────────────────────────────────
# STEP 4: Display ranked list
# ─────────────────────────────────────────────
def display_ranked_list(ranked_games):
    if not ranked_games:
        print("No games found with spread and totals data.")
        return

    table_data = []
    for g in ranked_games:
        table_data.append([
            g["rank"],
            g["home"],
            g["away"],
            g["league"],
            g["date_category"],
            g["date_str"],
            g["spread"],
            g["total"],
            g["event_id"]
        ])

    headers = ["Rank", "Home", "Away", "League", "When", "Date", "Spread", "Total", "Event ID"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print(f"\nTotal games ranked: {len(ranked_games)}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  BASKETBALL GAME RANKER — Powered by BetsAPI")
    print("=" * 60)

    if API_TOKEN == "YOUR_API_TOKEN_HERE":
        print("\n⚠️  Please set your API_TOKEN at the top of this script.")
        exit()

    print("\nFetching upcoming basketball games...")
    events = fetch_upcoming_games()
    print(f"Found {len(events)} upcoming games.")

    ranked_games = build_ranked_list(events)
    display_ranked_list(ranked_games)