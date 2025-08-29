import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta
from fake_useragent import UserAgent  # For user-agent rotation

# Firms to track
firms = [
    "Polen Capital",
    "Sustainable Growth Advisers",
    "Spyglass Capital Management",
    "Frontier Capital Management",
    "Strategy",
    "Berkshire Hathaway"
]

# Initialize user-agent rotation
ua = UserAgent()

# Function to scrape Google News for portfolio changes
def scrape_news(firm):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    query = f'"{firm}" (buys OR sells OR acquires OR divests OR sold OR bought OR portfolio OR holdings OR investments OR stake) after:{yesterday} site:*.com | site:*.gov | site:*.org | site:yahoo.com | site:marketwatch.com | site:wsj.com -inurl:(signup | login)'
    base_url = "https://news.google.com/rss/search"
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }
    headers = {"User-Agent": ua.random}
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        print(f"\n=== Debug: RSS Query for {firm} ===")
        print(f"Query URL: {response.url}")
        print(f"Response Status: {response.status_code}")
        print(f"RSS Content (first 2000 chars):\n{response.content.decode()[:2000]}...")
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching news for {firm}: {e}, Status Code: {response.status_code if response else 'No response'}")
        return []
    
    try:
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        print(f"Found {len(items)} articles in RSS feed for {firm}")
    except Exception as e:
        print(f"Error parsing RSS for {firm}: {e}")
        return []
    
    changes = []
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    
    for item in items:
        title = item.title.text
        pub_date_str = item.pubDate.text
        link = item.link.text
        
        print(f"\nArticle: {title}")
        print(f"Date: {pub_date_str}")
        print(f"Link: {link}")
        
        try:
            if ',' in pub_date_str:
                pub_date_str = pub_date_str.split(',', 1)[1].strip()
            pub_date = datetime.strptime(pub_date_str, "%d %b %Y %H:%M:%S %Z")
            pub_date = pub_date.replace(tzinfo=timezone.utc)
            print(f"Parsed Date: {pub_date}")
        except ValueError as e:
            print(f"Date parsing error for article '{title}': {e}")
            pub_date = None
        
        date_passes = pub_date and pub_date > last_24h
        print(f"Date Filter Pass: {date_passes} (pub_date: {pub_date}, last_24h: {last_24h})")
        
        if date_passes:
            changes.append({"title": title, "date": pub_date_str, "link": link})
            print(f"Article Included: {title}")
        else:
            print(f"Article Excluded: {title} (due to date filter)")
    
    print(f"\nSummary for {firm}: {len(changes)} articles included out of {len(items)} fetched")
    return changes

# Get current timestamp in UTC, convert to +08 for display
now = datetime.now(timezone.utc)
tz_plus_8 = timezone(timedelta(hours=8))
now_plus_8 = now.astimezone(tz_plus_8).strftime("%Y-%m-%d %H:%M:%S %Z")

# Load previous updates and all_articles
try:
    with open("previous_updates.json", "r") as f:
        previous = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("Error loading previous_updates.json; initializing empty.")
    previous = {firm: [] for firm in firms}

try:
    with open("all_articles.json", "r") as f:
        all_articles = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("Error loading all_articles.json; initializing empty.")
    all_articles = {firm: [] for firm in firms}

# Fetch new updates and print results
updates = {}
for firm in firms:
    print(f"\n=== Processing Firm: {firm} ===")
    new_changes = scrape_news(firm)
    prev_changes = previous.get(firm, [])
    new_titles = {change["title"] for change in new_changes}
    prev_titles = {change["title"] for change in prev_changes}
    new_entries = [change for change in new_changes if change["title"] not in prev_titles]
    updates[firm] = {"last_updated": now_plus_8, "changes": new_entries}
    previous[firm] = new_changes
    
    existing_titles = {article["title"] for article in all_articles.get(firm, [])}
    all_articles[firm] = all_articles.get(firm, []) + [
        change for change in new_changes if change["title"] not in existing_titles
    ]
    
    print(f"\nDuplicate Check for {firm}:")
    print(f"New Titles: {new_titles}")
    print(f"Previous Titles: {prev_titles}")
    print(f"Included New Entries: {len(new_entries)}")
    
    print(f"\n{firm}:")
    if new_entries:
        print(f"New updates found ({len(new_entries)}):")
        for entry in new_entries:
            print(f"- {entry['title']} ({entry['date']}): {entry['link']}")
    else:
        print("No new updates today.")
        firm_articles = all_articles.get(firm, [])
        if firm_articles:
            try:
                valid_articles = []
                for article in firm_articles:
                    try:
                        date_str = article['date']
                        if ',' in date_str:
                            date_str = date_str.split(',', 1)[1].strip()
                        date = datetime.strptime(date_str, "%d %b %Y %H:%M:%S %Z")
                        valid_articles.append((date, article))
                    except ValueError:
                        continue
                if valid_articles:
                    latest_article = max(valid_articles, key=lambda x: x[0])[1]
                    print(f"Latest article: {latest_article['title']} ({latest_article['date']}): {latest_article['link']}")
                else:
                    print("No valid articles with parsable dates found.")
            except Exception as e:
                print(f"Error finding latest article: {e}")
        else:
            print("No previous articles found.")

# Save updates
with open("updates.json", "w") as f:
    json.dump(upates, f, indent=4)
with open("previous_updates.json", "w") as f:
    json.dump(previous, f, indent=4)
with open("all_articles.json", "w") as f:
    json.dump(all_articles, f, indent=4)
