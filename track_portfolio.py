import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta
from fake_useragent import UserAgent
import time
import os
try:
    from gnews import GNews
except ImportError:
    GNews = None

# Initialize debug file
debug_file = "debug_output.txt"
def log_debug(message):
    try:
        with open(debug_file, "a") as f:
            f.write(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}: {message}\n")
        print(message)
    except Exception as e:
        print(f"Error writing to {debug_file}: {e}")

# Create debug file
try:
    with open(debug_file, "w") as f:
        f.write(f"Script started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
    os.chmod(debug_file, 0o666)  # Ensure file is writable
    log_debug(f"Initialized {debug_file}")
except Exception as e:
    print(f"Fatal error initializing {debug_file}: {e}")
    exit(1)

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

# Clear previous_updates.json
try:
    os.remove("previous_updates.json")
    log_debug("Cleared previous_updates.json")
except FileNotFoundError:
    log_debug("No previous_updates.json to clear")

# Function to scrape Google News for portfolio changes
def scrape_news(firm):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
    if firm == "Berkshire Hathaway":
        query = f'"{firm}" (stake OR investment) after:{yesterday} site:wsj.com -inurl:(signup | login)'
    else:
        query = f'"{firm}" (buys OR sells OR acquires OR divests OR sold OR bought OR portfolio OR holdings OR investments OR stake) after:{yesterday} site:*.com | site:*.gov | site:*.org | site:yahoo.com | site:marketwatch.com | site:wsj.com -inurl:(signup | login)'
    base_url = "https://news.google.com/rss/search"
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }
    headers = {"User-Agent": ua.random}
    
    log_debug(f"\n=== Debug: RSS Query for {firm} ===")
    log_debug(f"Query URL: {base_url}?q={params['q']}")
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        log_debug(f"Response Status: {response.status_code}")
        log_debug(f"RSS Content (first 2000 chars):\n{response.content.decode()[:2000]}...")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")[:20]
        log_debug(f"Found {len(items)} articles in RSS feed for {firm}")
    except Exception as e:
        log_debug(f"Error fetching/parsing RSS for {firm}: {e}")
        items = []
    
    changes = []
    if not items and GNews:
        log_debug(f"No RSS results for {firm}, trying GNews")
        try:
            google_news = GNews(max_results=20)
            articles = google_news.get_news(f'"{firm}" stake site:wsj.com')
            items = [
                type('obj', (), {
                    'title': type('obj', (), {'text': a['title']}),
                    'pubDate': type('obj', (), {'text': a['published date']}),
                    'link': type('obj', (), {'text': a['url']})
                })() for a in articles
            ]
            log_debug(f"Found {len(items)} articles in GNews for {firm}")
        except Exception as e:
            log_debug(f"GNews error for {firm}: {e}")
            items = []
    
    last_72h = datetime.now(timezone.utc) - timedelta(days=3)
    
    for item in items:
        title = item.title.text
        pub_date_str = item.pubDate.text
        link = item.link.text
        
        log_debug(f"\nArticle: {title}")
        log_debug(f"Date: {pub_date_str}")
        log_debug(f"Link: {link}")
        
        try:
            if ',' in pub_date_str:
                pub_date_str = pub_date_str.split(',', 1)[1].strip()
            pub_date = datetime.strptime(pub_date_str, "%d %b %Y %H:%M:%S %Z")
            pub_date = pub_date.replace(tzinfo=timezone.utc)
            log_debug(f"Parsed Date: {pub_date}")
        except ValueError as e:
            log_debug(f"Date parsing error for article '{title}': {e}")
            pub_date = None
        
        date_passes = pub_date and pub_date > last_72h
        log_debug(f"Date Filter Pass: {date_passes} (pub_date: {pub_date}, last_72h: {last_72h})")
        
        if date_passes:
            changes.append({"title": title, "date": pub_date_str, "link": link})
            log_debug(f"Article Included: {title}")
        else:
            log_debug(f"Article Excluded: {title} (due to date filter)")
    
    log_debug(f"\nSummary for {firm}: {len(changes)} articles included out of {len(items)} fetched")
    return changes

# Fetch new updates
updates = {}
all_articles = {}
for firm in firms:
    log_debug(f"\n=== Processing Firm: {firm} ===")
    new_changes = scrape_news(firm)
    
    now = datetime.now(timezone.utc)
    tz_plus_8 = timezone(timedelta(hours=8))
    now_plus_8 = now.astimezone(tz_plus_8).strftime("%Y-%m-%d %H:%M:%S %Z")
    
    try:
        with open("all_articles.json", "r") as f:
            all_articles = json.load(f)
        log_debug("Loaded all_articles.json")
    except (FileNotFoundError, json.JSONDecodeError):
        log_debug("Error loading all_articles.json; initializing empty.")
        all_articles = {firm: [] for firm in firms}
    
    new_titles = {change["title"] for change in new_changes}
    existing_titles = {article["title"] for article in all_articles.get(firm, [])}
    new_entries = [change for change in new_changes if change["title"] not in existing_titles]
    
    updates[firm] = {"last_updated": now_plus_8, "changes": new_entries}
    all_articles[firm] = all_articles.get(firm, []) + [
        change for change in new_changes if change["title"] not in existing_titles
    ]
    
    log_debug(f"\nDuplicate Check for {firm}:")
    log_debug(f"New Titles: {new_titles}")
    log_debug(f"Included New Entries: {len(new_entries)}")
    
    log_debug(f"\n{firm}:")
    if new_entries:
        log_debug(f"New updates found ({len(new_entries)}):")
        for entry in new_entries:
            log_debug(f"- {entry['title']} ({entry['date']}): {entry['link']}")
    else:
        log_debug("No new updates today.")
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
                    log_debug(f"Latest article: {latest_article['title']} ({latest_article['date']}): {latest_article['link']}")
                else:
                    log_debug("No valid articles with parsable dates found.")
            except Exception as e:
                log_debug(f"Error finding latest article: {e}")
        else:
            log_debug("No previous articles found.")
    
    time.sleep(1)

# Save files
try:
    with open("updates.json", "w") as f:
        json.dump(updates, f, indent=4)
    os.chmod("updates.json", 0o666)
    log_debug("Saved updates.json")
except Exception as e:
    log_debug(f"Error saving updates.json: {e}")

try:
    with open("all_articles.json", "w") as f:
        json.dump(all_articles, f, indent=4)
    os.chmod("all_articles.json", 0o666)
    log_debug("Saved all_articles.json")
except Exception as e:
    log_debug(f"Error saving all_articles.json: {e}")

log_debug("\n=== Debug: Final Output ===")
log_debug(f"Updates saved to updates.json: {json.dumps(updates, indent=2)}")

if os.path.exists(debug_file):
    log_debug(f"{debug_file} successfully created")
else:
    log_debug(f"Error: {debug_file} was not created")
