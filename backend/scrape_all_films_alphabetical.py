"""
Scrape ALL films from Letterboxd using the alphabetical listing.
Uses: https://letterboxd.com/films/by/name/
This is the most comprehensive way to get all films.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from database import init_database, save_film, get_film_by_slug, get_stats
from scraper import get_headers, get_film_stats

async def get_film_slugs_from_page(session: aiohttp.ClientSession, url: str):
    """Extract film slugs from any Letterboxd page."""
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
                        if slug not in ['page', 'popular', 'year', 'country', 'genre', 'decade', 'list', 'by', 'name'] and slug not in slugs:
                            slugs.append(slug)
            
            # Method 3: Check for data attributes
            if not slugs:
                for elem in soup.select('[data-film-slug], [data-slug], [data-item-slug]'):
                    slug = elem.get('data-film-slug') or elem.get('data-slug') or elem.get('data-item-slug')
                    if slug and slug not in slugs and slug not in ['page', 'popular', 'year', 'country', 'genre', 'decade', 'by', 'name']:
                        slugs.append(slug)
            
            return slugs
    except Exception as e:
        return []

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

async def scrape_all_films_alphabetical():
    """Scrape ALL films from Letterboxd using the alphabetical listing."""
    print("🎬 Starting comprehensive Letterboxd film scraper...")
    print("📊 Using alphabetical listing: /films/by/name/\n")
    
    init_database()
    all_slugs = set()
    
    # Optimized session
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        # Step 1: Collect all film slugs from alphabetical listing
        print("📋 Step 1: Collecting film slugs from alphabetical listing...")
        page = 1
        consecutive_empty = 0
        max_consecutive_empty = 3
        
        while True:
            url = f"https://letterboxd.com/films/by/name/page/{page}/"
            slugs = await get_film_slugs_from_page(session, url)
            
            if not slugs:
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    print(f"   ✅ Reached end at page {page} (after {consecutive_empty} empty pages)")
                    break
            else:
                consecutive_empty = 0
                all_slugs.update(slugs)
                
                if page % 50 == 0:
                    print(f"   Page {page}: {len(slugs)} films (total: {len(all_slugs)} unique)")
            
            page += 1
            await asyncio.sleep(0.05)  # Minimal delay
        
        print(f"\n✅ Collected {len(all_slugs)} unique film slugs\n")
        
        # Step 2: Scrape all the film data
        print("💾 Step 2: Scraping film data in parallel batches...\n")
        
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
        print(f"   With TMDb data: {stats['films_with_tmdb']}")

if __name__ == "__main__":
    asyncio.run(scrape_all_films_alphabetical())
