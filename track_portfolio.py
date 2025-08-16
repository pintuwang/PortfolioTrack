import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime, timezone, timedelta

# Firms to track
firms = [
    "Polen Capital",
    "Sustainable Growth Advisers",
    "Spyglass Capital Management",
    "Frontier Capital Management",
    "WhiteStar Asset Management"
]

# Function to scrape Google News for portfolio changes
def scrape_news(firm):
    query = f"{firm} buys OR sells portfolio OR holdings site:*.edu | site:*.gov | site:*.org | site:yahoo.com | site:marketwatch.com -inurl:(signup | login)"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "xml")
    items = soup.find_all("item")
    
    changes = []
    for item in items[:5]:  # Limit to 5 recent articles to avoid noise
        title = item.title.text
        pub_date = item.pubDate.text
        link = item.link.text
        if "buy" in title.lower() or "sell" in title.lower():
            changes.append({"title": title, "date": pub_date, "link": link})
    return changes

# Get current timestamp in UTC, convert to +08 for display
now = datetime.now(timezone.utc)
tz_plus_8 = timezone(timedelta(hours=8))
now_plus_8 = now.astimezone(tz_plus_8).strftime("%Y-%m-%d %H:%M:%S %Z")

# Load previous updates
try:
    with open("previous_updates.json", "r") as f:
        previous = json.load(f)
except:
    previous = {firm: [] for firm in firms}

# Fetch new updates
updates = {}
for firm in firms:
    new_changes = scrape_news(firm)
    prev_changes = previous.get(firm, [])
    # Detect new changes by comparing titles
    new_titles = {change["title"] for change in new_changes}
    prev_titles = {change["title"] for change in prev_changes}
    new_entries = [change for change in new_changes if change["title"] not in prev_titles]
    # Include last_updated even if no changes
    updates[firm] = {"last_updated": now_plus_8, "changes": new_entries}
    previous[firm] = new_changes  # Update previous

# Save updates
with open("updates.json", "w") as f:
    json.dump(updates, f)
with open("previous_updates.json", "w") as f:
    json.dump(previous, f)
