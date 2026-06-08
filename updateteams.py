import requests
import json
import os
from datetime import datetime

API_KEY = "5a5ad2b7-dc79-4187-af30-418b7bd28cae"
BASE_URL = "https://basketball.highlightly.net"
HEADERS = {"x-rapidapi-key": API_KEY}
OUTPUT_FILE = "teams_database.json"


def download_teams_database():
    all_teams = []
    offset = 0
    limit = 500

    # First call to get total count
    response = requests.get(f"{BASE_URL}/teams", headers=HEADERS, params={"limit": limit, "offset": 0})
    data = response.json()
    total = data.get("pagination", {}).get("totalCount", 0)
    all_teams.extend(data.get("data", []))
    print(f"Total teams to download: {total}")
    print(f"Downloaded {len(all_teams)} / {total}...")

    offset += limit

    while len(all_teams) < total:
        response = requests.get(f"{BASE_URL}/teams", headers=HEADERS, params={"limit": limit, "offset": offset})
        data = response.json()
        batch = data.get("data", [])
        if not batch:
            break
        all_teams.extend(batch)
        offset += limit
        print(f"Downloaded {len(all_teams)} / {total}...")

    output = {
        "downloaded_at": datetime.now().isoformat(),
        "total": len(all_teams),
        "teams": all_teams
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone! Saved {len(all_teams)} teams to {OUTPUT_FILE}")



def should_refresh(max_age_days=30):
    if not os.path.exists(OUTPUT_FILE):
        return True
    with open(OUTPUT_FILE) as f:
        data = json.load(f)
    downloaded_at = datetime.fromisoformat(data.get("downloaded_at", "2000-01-01"))
    age = (datetime.now() - downloaded_at).days
    return age > max_age_days


if __name__ == "__main__":
    if should_refresh():
        download_teams_database()
    else:
        with open(OUTPUT_FILE) as f:
            data = json.load(f)
        print(f"Database is up to date. {data['total']} teams loaded from {OUTPUT_FILE}")
        print(f"Downloaded at: {data['downloaded_at']}")