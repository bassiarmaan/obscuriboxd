"""
Comprehensive scraper to get ALL films from Letterboxd.
Uses multiple strategies:
1. Scrape by year (1900-present)
2. Scrape from popular lists
3. Scrape from popular users
4. Scrape from genre pages
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from database import init_database, save_film, get_film_by_slug, get_stats
from scraper import get_headers, get_film_stats

async def get_film_slugs_from_page(session: aiohttp.ClientSession, url: str):
    """Extract film slugs from any Letterboxd page - improved version."""
    try:
        async with session.get(url, headers=get_headers()) as r:
            if r.status != 200:
                return []
            html = await r.text()
            soup = BeautifulSoup(html, 'lxml')
            slugs = []
            
            # Method 1: react-component with LazyPoster (most reliable)
            components = soup.select('div.react-component[data-component-class="LazyPoster"]')
            for comp in components:
                slug = comp.get('data-item-slug', '')
                if slug and slug not in slugs:
                    slugs.append(slug)
            
            # Method 2: Find all film links (fallback)
            if not slugs:
                links = soup.select('a[href*="/film/"]')
                for link in links:
                    href = link.get('href', '')
                    match = re.search(r'/film/([^/]+)/', href)
                    if match:
                        slug = match.group(1)
                        if slug not in ['page', 'popular', 'year', 'country', 'genre', 'decade', 'list'] and slug not in slugs:
                            slugs.append(slug)
            
            # Method 3: Check for data attributes
            if not slugs:
                for elem in soup.select('[data-film-slug], [data-slug], [data-item-slug]'):
                    slug = elem.get('data-film-slug') or elem.get('data-slug') or elem.get('data-item-slug')
                    if slug and slug not in slugs and slug not in ['page', 'popular', 'year', 'country', 'genre', 'decade']:
                        slugs.append(slug)
            
            return slugs
    except Exception as e:
        return []

async def scrape_by_year(session: aiohttp.ClientSession, year: int, max_pages: int = 50):
    """Scrape all films from a specific year."""
    all_slugs = set()
    page = 1
    consecutive_empty = 0
    
    while page <= max_pages:
        # Try both URL formats
        urls = [
            f"https://letterboxd.com/films/popular/year/{year}/page/{page}/",
            f"https://letterboxd.com/films/year/{year}/page/{page}/"
        ]
        
        slugs = []
        for url in urls:
            page_slugs = await get_film_slugs_from_page(session, url)
            if page_slugs:
                slugs = page_slugs
                break
        
        if not slugs:
            consecutive_empty += 1
            if consecutive_empty >= 2:  # Stop after 2 empty pages
                break
        else:
            consecutive_empty = 0
            all_slugs.update(slugs)
        
        page += 1
        await asyncio.sleep(0.05)
    
    return list(all_slugs)

async def scrape_by_decade(session: aiohttp.ClientSession, decade_start: int, max_pages_per_year: int = 20):
    """Scrape all films from a decade by iterating through years."""
    all_slugs = set()
    decade_end = decade_start + 9
    
    print(f"   📅 Decade {decade_start}s ({decade_start}-{decade_end})...")
    
    # Scrape each year in the decade
    for year in range(decade_start, decade_end + 1):
        year_slugs = await scrape_by_year(session, year, max_pages=max_pages_per_year)
        all_slugs.update(year_slugs)
        if year_slugs:
            print(f"      {year}: {len(year_slugs)} films", end=" | ")
        await asyncio.sleep(0.1)  # Small delay between years
    
    if all_slugs:
        print()  # New line after year output
    
    return list(all_slugs)

async def scrape_from_user(session: aiohttp.ClientSession, username: str):
    """Get all film slugs from a user's profile."""
    slugs = []
    page = 1
    
    while True:
        url = f"https://letterboxd.com/{username}/films/page/{page}/"
        page_slugs = await get_film_slugs_from_page(session, url)
        if not page_slugs:
            break
        slugs.extend(page_slugs)
        page += 1
        await asyncio.sleep(0.1)
    
    return list(set(slugs))

async def scrape_from_list(session: aiohttp.ClientSession, list_url: str, max_pages: int = 100):
    """Scrape films from a Letterboxd list."""
    all_slugs = set()
    page = 1
    
    while page <= max_pages:
        url = f"{list_url}page/{page}/" if page > 1 else list_url
        slugs = await get_film_slugs_from_page(session, url)
        
        if not slugs:
            break
        
        all_slugs.update(slugs)
        page += 1
        await asyncio.sleep(0.05)
    
    return list(all_slugs)

async def scrape_film(session: aiohttp.ClientSession, slug: str):
    """Scrape a single film and save to database."""
    # Check if already exists with complete data
    existing = get_film_by_slug(slug)
    if existing and existing.get('letterboxd_watches') is not None:
        return False  # Already have it
    
    film = {'slug': slug}
    
    # Use the main scraper function
    stats = await get_film_stats(session, film)
    film.update(stats)
    
    if film.get('title') or film.get('letterboxd_watches'):
        save_film(film)
        return True
    return False

async def main():
    """Main scraper - comprehensive approach to get ALL films."""
    print("🎬 Starting COMPREHENSIVE Letterboxd film scraper...")
    print("📊 This will scrape from multiple sources to get ALL films\n")
    
    init_database()
    all_slugs = set()
    
    # Optimized session
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        # Strategy 1: Scrape by decade (most comprehensive and efficient)
        print("📅 Strategy 1: Scraping films by decade (1900s-2020s)...")
        
        # Decades: 1900s, 1910s, 1920s, ..., 2020s
        decades = [1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
        
        for i, decade_start in enumerate(decades, 1):
            decade_slugs = await scrape_by_decade(session, decade_start, max_pages_per_year=30)
            all_slugs.update(decade_slugs)
            
            print(f"   ✅ {decade_start}s: {len(decade_slugs)} films (total: {len(all_slugs)} unique)")
            await asyncio.sleep(0.2)  # Small delay between decades
        
        print(f"✅ Decade scraping complete: {len(all_slugs)} unique films\n")
        
        # Strategy 2: Popular users with large collections
        print("👥 Strategy 2: Scraping from popular users...")
        users = [
            "davidehrlich", "kermode", "filmspotting", "criterion",
            "cinephile", "film", "movies", "cinema", "movie",
            "tspdt", "sightandsound", "afi", "imdb"
        ]
        
        for user in users:
            try:
                user_slugs = await scrape_from_user(session, user)
                all_slugs.update(user_slugs)
                print(f"   ✅ {user}: {len(user_slugs)} films (total: {len(all_slugs)})")
            except Exception as e:
                print(f"   ❌ {user}: {e}")
            await asyncio.sleep(0.2)
        
        print(f"✅ User scraping complete: {len(all_slugs)} unique films\n")
        
        # Strategy 3: Popular lists
        print("📋 Strategy 3: Scraping from popular lists...")
        popular_lists = [
            "https://letterboxd.com/list/the-official-top-1000-narrative-feature-films/",
            "https://letterboxd.com/list/the-criterion-collection/",
            "https://letterboxd.com/list/afi-100-years-100-movies/",
            "https://letterboxd.com/list/sight-sound-top-250/",
            "https://letterboxd.com/list/tspdt-1000-greatest-films/",
            "https://letterboxd.com/list/imdb-top-250/",
            "https://letterboxd.com/list/popular-this-week/",
            "https://letterboxd.com/list/popular-this-month/",
            "https://letterboxd.com/list/popular-this-year/",
        ]
        
        for list_url in popular_lists:
            try:
                list_slugs = await scrape_from_list(session, list_url)
                all_slugs.update(list_slugs)
                print(f"   ✅ List: {len(list_slugs)} films (total: {len(all_slugs)})")
            except Exception as e:
                print(f"   ❌ List error: {e}")
            await asyncio.sleep(0.2)
        
        print(f"✅ List scraping complete: {len(all_slugs)} unique films\n")
        
        # Now scrape all the film data
        print(f"📊 Total unique films found: {len(all_slugs)}\n")
        print("💾 Scraping film data in parallel batches...\n")
        
        slugs_list = list(all_slugs)
        batch_size = 50
        saved = 0
        skipped = 0
        failed = 0
        
        for i in range(0, len(slugs_list), batch_size):
            batch = slugs_list[i:i + batch_size]
            tasks = [scrape_film(session, slug) for slug in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, bool):
                    if result:
                        saved += 1
                    else:
                        skipped += 1
                else:
                    failed += 1
            
            if (i + batch_size) % 500 == 0 or i + batch_size >= len(slugs_list):
                print(f"   Progress: {min(i + batch_size, len(slugs_list))}/{len(slugs_list)} (saved: {saved}, skipped: {skipped}, failed: {failed})")
            
            if i + batch_size < len(slugs_list):
                await asyncio.sleep(0.05)
        
        print(f"\n✅ Complete!")
        print(f"   Saved: {saved}")
        print(f"   Skipped: {skipped}")
        print(f"   Failed: {failed}")
        
        stats = get_stats()
        print(f"\n📊 Database now has {stats['total_films']} films")
        print(f"   With watch counts: {stats['films_with_watches']}")
        print(f"   With posters: {stats['films_with_posters']}")

if __name__ == "__main__":
    asyncio.run(main())
