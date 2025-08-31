import json
from datetime import datetime, timezone, timedelta

def parse_article_date(date_str):
    """Parse article date with multiple format support"""
    if not date_str:
        return None
    
    # Clean up date string
    clean_date = date_str.strip()
    
    # Remove day of week if present (e.g., "Sat, 30 Aug 2025...")
    if clean_date.startswith(('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')):
        parts = clean_date.split(',', 1)
        if len(parts) > 1:
            clean_date = parts[1].strip()
    
    # Try multiple date formats
    formats = [
        "%d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S GMT", 
        "%d %b %Y %H:%M:%S UTC",
        "%d %b %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(clean_date, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    
    print(f"Could not parse date: {date_str}")
    return None

def fix_updates_from_articles():
    """Fix updates.json by properly filtering recent articles"""
    
    # Load all_articles.json
    try:
        with open("all_articles.json", "r") as f:
            all_articles = json.load(f)
        print("Loaded all_articles.json")
    except Exception as e:
        print(f"Error loading all_articles.json: {e}")
        return
    
    # Define "recent" as last 3 days
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=3)
    print(f"Cutoff date for recent articles: {cutoff_date}")
    
    # Get current time for timestamps
    now = datetime.now(timezone.utc)
    tz_plus_8 = timezone(timedelta(hours=8))
    current_time = now.astimezone(tz_plus_8).strftime("%Y-%m-%d %H:%M:%S %Z")
    
    updates = {}
    
    for firm, articles in all_articles.items():
        print(f"\n=== Processing {firm} ===")
        print(f"Total articles: {len(articles)}")
        
        recent_changes = []
        
        for article in articles:
            print(f"\nChecking: {article['title'][:80]}...")
            print(f"Date string: {article['date']}")
            
            # Parse the article date
            article_date = parse_article_date(article['date'])
            
            if article_date:
                print(f"Parsed date: {article_date}")
                print(f"Is recent? {article_date > cutoff_date}")
                
                if article_date > cutoff_date:
                    recent_changes.append(article)
                    print(f"✓ INCLUDED as recent")
                else:
                    print(f"✗ Too old ({article_date.strftime('%Y-%m-%d')})")
            else:
                print(f"✗ Could not parse date")
        
        updates[firm] = {
            "last_updated": current_time,
            "changes": recent_changes
        }
        
        print(f"\nResult for {firm}: {len(recent_changes)} recent articles")
        if recent_changes:
            for change in recent_changes:
                print(f"  - {change['title'][:60]}...")
    
    # Save the corrected updates.json
    try:
        with open("updates.json", "w") as f:
            json.dump(updates, f, indent=4)
        print(f"\n✓ Saved corrected updates.json")
        
        # Print summary
        print(f"\n=== SUMMARY ===")
        total_recent = 0
        for firm, data in updates.items():
            count = len(data["changes"])
            total_recent += count
            status = f"{count} recent" if count > 0 else "no recent"
            print(f"{firm}: {status} articles")
        
        print(f"Total recent articles: {total_recent}")
        
        # Show what will appear on webpage
        print(f"\n=== WEBPAGE PREVIEW ===")
        for firm, data in updates.items():
            if data["changes"]:
                print(f"{firm}: {len(data['changes'])} new updates")
                for change in data["changes"]:
                    print(f"  • {change['title']}")
            else:
                print(f"{firm}: No new updates")
        
    except Exception as e:
        print(f"Error saving updates.json: {e}")

if __name__ == "__main__":
    fix_updates_from_articles()
