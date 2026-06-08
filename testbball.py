import requests
import json

API_KEY = "5a5ad2b7-dc79-4187-af30-418b7bd28cae"
BASE_URL = "https://basketball.highlightly.net"

HEADERS = {
    "x-rapidapi-key": API_KEY
}

# Step 1: Search for the team to get their teamId
def find_team(name):
    url = f"{BASE_URL}/teams"
    params = {"name": name}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    print("=== TEAM SEARCH RESULTS ===")
    print(json.dumps(data, indent=2))
    return data

# Step 2: Fetch team statistics using teamId
def get_team_stats(team_id):
    url = f"{BASE_URL}/teams/statistics"
    params = {"teamId": team_id}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    print("\n=== TEAM STATISTICS ===")
    print(json.dumps(data, indent=2))
    return data

# Run the test
teams = find_team("spurs")

# If a team was found, grab the first result's ID and fetch stats
if teams and len(teams) > 0:
    team_id = teams[0].get("id")
    print(f"\nFound team ID: {team_id}")
    get_team_stats(team_id)
else:
    print("No team found.")