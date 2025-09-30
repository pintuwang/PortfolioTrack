import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta
from fake_useragent import UserAgent
import time
import os
import random
import re

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
    os.chmod(debug_file, 0o666)
    log_debug(f"Initialized {debug_file}")
except Exception as e:
    print(f"Fatal error initializing {debug_file}: {e}")
    exit(1)

# Firms to track with alternative search terms
firms_config = {
    "Polen Capital": ["Polen Capital", "Polen Capital Management"],
    "Fairfax Financial Holdings": ["Fairfax Financial Holdings", "FFH.TO"],
    "Markel Group": ["Markel Group", "MKL"],
    "Pershing Square Holdings": ["Bill Ackman", "Pershing Square Capital Management"],
    "Strategy": ["Strategy","Saylor"],  # Fixed potential typo
    "Berkshire Hathaway": ["Berkshire Hathaway", "Warren Buffett"]
}

# Initialize user-agent rotation
ua = UserAgent()

def get_search_terms():
    """Portfolio-related search terms"""
    return [
        "buys", "sells", "acquires", "divests", "sold", "bought", 
        "portfolio", "holdings", "investments", "stake", "position",
        "increases", "reduces", "adds", "trims", "13F", "filing"
    ]

def build_search_query(firm_names, days_back=3):
    """Build more effective search query"""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    # Use primary firm name
    firm_query = f'"{firm_names[0]}"'
    
    # Add search terms
    search_terms = " OR ".join(get_search_terms())
    
    # Build query with better site targeting
    if "Berkshire" in firm_names[0]:
        query = f'{firm_query} (stake OR investment OR filing OR 13F) after:{yesterday}'
    else:
        query = f'{firm_query} ({search_terms}) after:{yesterday}'
    
    return query

def scrape_google_news_rss(firm_names):
    """Scrape Google News RSS with improved error handling"""
    query = build_search_query(firm_names)
    base_url = "https://news.google.com/rss/search"
    
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }
    
    headers = {
        "User-Agent": ua.random,
        "Accept": "application/rss+xml, application/xml, text/xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    log_debug(f"\n=== RSS Query for {firm_names[0]} ===")
    log_debug(f"Query: {query}")
    log_debug(f"Full URL: {base_url}?q={params['q']}")
    
    try:
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        log_debug(f"Response Status: {response.status_code}")
        log_debug(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 429:
            log_debug("Rate limited by Google News, waiting...")
            time.sleep(random.uniform(10, 20))
            return []
            
        response.raise_for_status()
        
        # Log response content for debugging
        content = response.content.decode('utf-8', errors='ignore')
        log_debug(f"RSS Content length: {len(content)}")
        log_debug(f"RSS Content preview:\n{content[:1000]}...")
        
        soup = BeautifulSoup(content, "xml")
        items = soup.find_all("item")
        
        log_debug(f"Found {len(items)} items in RSS feed")
        
        # If no items found, try alternative parsing
        if not items:
            # Try with html parser as fallback
            soup_html = BeautifulSoup(content, "html.parser")
            items = soup_html.find_all("item")
            log_debug(f"HTML parser found {len(items)} items")
        
        return items[:20]  # Limit to 20 items
        
    except requests.RequestException as e:
        log_debug(f"Request error for {firm_names[0]}: {e}")
        return []
    except Exception as e:
        log_debug(f"Parsing error for {firm_names[0]}: {e}")
        return []

def parse_date(date_str):
    """Improved date parsing with multiple formats"""
    if not date_str:
        return None
        
    # Clean up the date string
    date_str = date_str.strip()
    
    # Remove day of week if present
    if ',' in date_str:
        parts = date_str.split(',')
        if len(parts) >= 2:
            date_str = ','.join(parts[1:]).strip()
    
    # Try multiple date formats
    formats = [
        "%d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S GMT",
        "%d %b %Y %H:%M:%S UTC",
        "%d %b %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y"
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    
    log_debug(f"Could not parse date: {date_str}")
    return None

def is_relevant_article(title, firm_names):
    """Check if article is relevant to portfolio changes"""
    title_lower = title.lower()
    
    # Check if firm name is mentioned
    firm_mentioned = any(name.lower() in title_lower for name in firm_names)
    if not firm_mentioned:
        return False
    
    # Check for portfolio-related keywords
    portfolio_keywords = [
        'buy', 'sell', 'acquire', 'divest', 'stake', 'holding', 'investment',
        'portfolio', 'position', 'share', 'stock', 'equity', '13f', 'filing',
        'increase', 'reduce', 'add', 'trim', 'exit', 'enter'
    ]
    
    has_portfolio_keyword = any(keyword in title_lower for keyword in portfolio_keywords)
    return has_portfolio_keyword

def scrape_news(firm_names):
    """Main scraping function with improved logic"""
    log_debug(f"\n=== Processing Firm: {firm_names[0]} ===")
    
    items = scrape_google_news_rss(firm_names)
    
    if not items:
        log_debug(f"No RSS items found for {firm_names[0]}")
        return []
    
    changes = []
    last_72h = datetime.now(timezone.utc) - timedelta(days=3)
    
    for item in items:
        try:
            title_elem = item.find("title")
            pub_date_elem = item.find("pubDate")
            link_elem = item.find("link")
            
            if not all([title_elem, pub_date_elem, link_elem]):
                log_debug("Missing required elements in RSS item")
                continue
                
            title = title_elem.get_text(strip=True)
            pub_date_str = pub_date_elem.get_text(strip=True)
            link = link_elem.get_text(strip=True)
            
            log_debug(f"\nArticle: {title}")
            log_debug(f"Date: {pub_date_str}")
            log_debug(f"Link: {link}")
            
            # Check relevance first
            if not is_relevant_article(title, firm_names):
                log_debug(f"Article not relevant: {title}")
                continue
            
            # Parse date
            pub_date = parse_date(pub_date_str)
            if not pub_date:
                log_debug(f"Could not parse date for: {title}")
                continue
                
            log_debug(f"Parsed Date: {pub_date}")
            
            # Check if within time window
            if pub_date > last_72h:
                changes.append({
                    "title": title,
                    "date": pub_date_str,
                    "link": link
                })
                log_debug(f"Article Included: {title}")
            else:
                log_debug(f"Article too old: {title}")
                
        except Exception as e:
            log_debug(f"Error processing RSS item: {e}")
            continue
    
    log_debug(f"\nSummary for {firm_names[0]}: {len(changes)} relevant articles found")
    return changes

def load_existing_data(filename, default_factory):
    """Load existing JSON data with error handling"""
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
        else:
            log_debug(f"{filename} does not exist, creating new")
            return default_factory()
    except (json.JSONDecodeError, IOError) as e:
        log_debug(f"Error loading {filename}: {e}, creating new")
        return default_factory()

def save_json_file(filename, data):
    """Save JSON file with error handling"""
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        os.chmod(filename, 0o666)
        log_debug(f"Successfully saved {filename}")
        return True
    except Exception as e:
        log_debug(f"Error saving {filename}: {e}")
        return False

# Main execution
def main():
    # Load existing data
    all_articles = load_existing_data("all_articles.json", lambda: {firm: [] for firm in firms_config.keys()})
    
    updates = {}
    
    for firm, firm_variants in firms_config.items():
        log_debug(f"\n{'='*50}")
        log_debug(f"Processing: {firm}")
        log_debug(f"Search variants: {firm_variants}")
        
        new_changes = scrape_news(firm_variants)
        
        # Get current time in UTC+8
        now = datetime.now(timezone.utc)
        tz_plus_8 = timezone(timedelta(hours=8))
        now_plus_8 = now.astimezone(tz_plus_8).strftime("%Y-%m-%d %H:%M:%S %Z")
        
        # Check for duplicates
        existing_titles = {article["title"] for article in all_articles.get(firm, [])}
        new_entries = [change for change in new_changes if change["title"] not in existing_titles]
        
        # Update data structures
        updates[firm] = {
            "last_updated": now_plus_8,
            "changes": new_entries
        }
        
        # Add new articles to all_articles
        if firm not in all_articles:
            all_articles[firm] = []
        
        all_articles[firm].extend(new_entries)
        
        # Log results
        log_debug(f"\nResults for {firm}:")
        log_debug(f"New articles found: {len(new_changes)}")
        log_debug(f"After duplicate removal: {len(new_entries)}")
        
        if new_entries:
            log_debug("New updates:")
            for entry in new_entries:
                log_debug(f"- {entry['title']}")
                log_debug(f"  Date: {entry['date']}")
                log_debug(f"  Link: {entry['link']}")
        else:
            log_debug("No new updates for this firm")
        
        # Add delay between requests
        time.sleep(random.uniform(2, 5))
    
    # Save results
    success_updates = save_json_file("updates.json", updates)
    success_all = save_json_file("all_articles.json", all_articles)
    
    if success_updates and success_all:
        log_debug("\n=== SUCCESS: All files saved successfully ===")
    else:
        log_debug("\n=== ERROR: Some files failed to save ===")
    
    # Summary
    total_new = sum(len(info["changes"]) for info in updates.values())
    log_debug(f"\n=== FINAL SUMMARY ===")
    log_debug(f"Total new articles across all firms: {total_new}")
    log_debug(f"Firms with updates: {[firm for firm, info in updates.items() if info['changes']]}")

if __name__ == "__main__":
    main()
