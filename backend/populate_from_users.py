"""
Populate database by scraping films from popular Letterboxd users.
This works because user profile pages are scrapable (unlike /films/ directory).
"""

import asyncio
from scraper import get_user_films
from database import get_stats

# Popular Letterboxd users with large film collections
POPULAR_USERS = [
    "davidehrlich",      # Film critic
    "kermode",           # Mark Kermode
    "filmspotting",      # Film podcast
    "criterion",         # Criterion Collection
    "letterboxd",        # Official account
    "cinephile",         # Generic popular account
    "film",              # Generic
    "movies",            # Generic
    # Add more popular users here
]

async def populate_from_users(usernames: list[str] = None):
    """Populate database by scraping films from user profiles."""
    if usernames is None:
        usernames = POPULAR_USERS
    
    print("🎬 Populating database from popular Letterboxd users...\n")
    print(f"📊 Will scrape from {len(usernames)} users\n")
    
    total_films = 0
    successful = 0
    failed = 0
    
    for username in usernames:
        print(f"👤 Scraping {username}...", end=" ")
        try:
            films = await get_user_films(username)
            if films:
                total_films += len(films)
                successful += 1
                print(f"✅ Found {len(films)} films")
            else:
                failed += 1
                print("❌ No films found (private profile or doesn't exist)")
        except Exception as e:
            failed += 1
            print(f"❌ Error: {str(e)[:50]}")
        
        # Rate limiting between users
        await asyncio.sleep(1)
    
    stats = get_stats()
    print(f"\n✅ Complete!")
    print(f"   - Successfully scraped: {successful} users")
    print(f"   - Failed: {failed} users")
    print(f"   - Total films added: {total_films}")
    print(f"   - Total films in database: {stats['total_films']}")
    print(f"   - Films with watch counts: {stats['films_with_watches']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Custom usernames provided
        usernames = sys.argv[1:]
        asyncio.run(populate_from_users(usernames))
    else:
        # Use default popular users
        asyncio.run(populate_from_users())
