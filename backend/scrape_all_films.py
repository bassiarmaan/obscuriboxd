"""
Simple script to scrape ALL Letterboxd films and store in database.
Run this locally to build your complete film database.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from database import init_database, save_film, get_film_by_slug, get_stats
from scraper import get_headers, parse_film_page, parse_stats_html

async def scrape_film(session: aiohttp.ClientSession, slug: str):
    """Scrape a single film and save to database."""
    from scraper import get_film_stats
    
    # Check if already exists
    existing = get_film_by_slug(slug)
    if existing and existing.get('letterboxd_watches') is not None and existing.get('poster_path'):
        return False  # Already have it with poster
    
    film = {'slug': slug}
    
    # Use the main scraper function which gets everything including TMDb poster
    stats = await get_film_stats(session, film)
    film.update(stats)
    
    if film.get('title') or film.get('letterboxd_watches'):
        save_film(film)
        return True
    return False

async def get_film_slugs_from_page(session: aiohttp.ClientSession, url: str):
    """Extract film slugs from any Letterboxd page."""
    try:
        async with session.get(url, headers=get_headers()) as r:
            if r.status != 200:
                return []
            html = await r.text()
            soup = BeautifulSoup(html, 'lxml')
            slugs = []
            
            # Find all film components
            components = soup.select('div.react-component[data-component-class="LazyPoster"]')
            for comp in components:
                slug = comp.get('data-item-slug', '')
                if slug:
                    slugs.append(slug)
            
            # Also find film links
            links = soup.select('a[href*="/film/"]')
            for link in links:
                href = link.get('href', '')
                match = re.search(r'/film/([^/]+)/', href)
                if match:
                    slug = match.group(1)
                    if slug not in ['page', 'popular', 'year', 'country', 'genre'] and slug not in slugs:
                        slugs.append(slug)
            
            return slugs
    except:
        return []

async def scrape_from_user(session: aiohttp.ClientSession, username: str):
    """Get all film slugs from a user's profile."""
    print(f"📋 Getting films from user: {username}")
    slugs = []
    page = 1
    
    while True:
        url = f"https://letterboxd.com/{username}/films/page/{page}/"
        page_slugs = await get_film_slugs_from_page(session, url)
        if not page_slugs:
            break
        slugs.extend(page_slugs)
        print(f"   Page {page}: {len(page_slugs)} films")
        page += 1
        await asyncio.sleep(0.3)
    
    return list(set(slugs))  # Remove duplicates

async def main():
    """Main scraper - gets films from multiple sources."""
    print("🎬 Starting comprehensive Letterboxd film scraper...\n")
    init_database()
    
    # Popular users with large collections
    users = [
        "davidehrlich", "kermode", "filmspotting", "criterion",
        "cinephile", "film", "movies", "cinema", "movie"
    ]
    
    all_slugs = set()
    
    async with aiohttp.ClientSession() as session:
        # Get films from users
        for user in users:
            try:
                user_slugs = await scrape_from_user(session, user)
                all_slugs.update(user_slugs)
                print(f"✅ {user}: {len(user_slugs)} films\n")
            except Exception as e:
                print(f"❌ {user}: {e}\n")
            await asyncio.sleep(1)
        
        print(f"📊 Total unique films found: {len(all_slugs)}\n")
        print("💾 Scraping film data...\n")
        
        # Scrape all films
        saved = 0
        skipped = 0
        failed = 0
        
        for i, slug in enumerate(all_slugs, 1):
            if i % 100 == 0:
                print(f"   Progress: {i}/{len(all_slugs)} (saved: {saved}, skipped: {skipped}, failed: {failed})")
            
            try:
                if await scrape_film(session, slug):
                    saved += 1
                else:
                    skipped += 1
            except:
                failed += 1
            
            await asyncio.sleep(0.2)
        
        print(f"\n✅ Complete!")
        print(f"   Saved: {saved}")
        print(f"   Skipped: {skipped}")
        print(f"   Failed: {failed}")
        
        stats = get_stats()
        print(f"\n📊 Database now has {stats['total_films']} films")

if __name__ == "__main__":
    asyncio.run(main())
