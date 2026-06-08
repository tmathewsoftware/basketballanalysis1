import requests
import json

API_KEY = "5a5ad2b7-dc79-4187-af30-418b7bd28cae"

response = requests.get(
    "https://basketball.highlightly.net/teams",
    headers={"x-rapidapi-key": API_KEY},
    params={"limit": 5, "offset": 0}
)

data = response.json()
print(type(data))
print(str(data)[:200])

print(data.get("pagination"))