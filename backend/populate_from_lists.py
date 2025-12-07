"""
Script to populate database by scraping from Letterboxd popular lists and other sources.
This is more effective than scraping /films/ directory.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from database import init_database, save_film, get_film_by_slug, get_stats
from scraper import get_headers, parse_film_page, parse_stats_html
from populate_database import scrape_single_film


async def scrape_list_page(session: aiohttp.ClientSession, url: str) -> list[str]:
    """Scrape film slugs from a Letterboxd list page."""
    try:
        async with session.get(url, headers=get_headers()) as response:
            if response.status != 200:
                return []
            
            html = await response.text()
            soup = BeautifulSoup(html, 'lxml')
            slugs = []
            
            # Find film components
            film_components = soup.select('div.react-component[data-component-class="LazyPoster"]')
            for component in film_components:
                slug = component.get('data-item-slug', '')
                if slug and slug not in slugs:
                    slugs.append(slug)
            
            # Also try film links
            if not slugs:
                film_links = soup.select('a[href*="/film/"]')
                for link in film_links:
                    href = link.get('href', '')
                    match = re.search(r'/film/([^/]+)/', href)
                    if match:
                        slug = match.group(1)
                        if slug not in ['page', 'popular', 'year', 'country', 'genre'] and slug not in slugs:
                            slugs.append(slug)
            
            return slugs
    except Exception as e:
        print(f"   ❌ Error scraping {url}: {e}")
        return []


async def scrape_popular_films(session: aiohttp.ClientSession, max_pages: int = 50):
    """Scrape from /films/popular/ directory."""
    print("📊 Scraping from /films/popular/...")
    all_slugs = []
    
    for page in range(1, max_pages + 1):
        url = f"https://letterboxd.com/films/popular/page/{page}/"
        print(f"   Page {page}...", end=" ")
        
        slugs = await scrape_list_page(session, url)
        if not slugs:
            print("(empty)")
            break
        
        all_slugs.extend(slugs)
        print(f"Found {len(slugs)} films")
        
        await asyncio.sleep(0.3)
    
    return all_slugs


async def scrape_by_year(session: aiohttp.ClientSession, years: list[int], max_pages_per_year: int = 10):
    """Scrape popular films by year."""
    print(f"\n📅 Scraping popular films by year ({years[0]}-{years[-1]})...")
    all_slugs = []
    
    for year in years:
        print(f"   Year {year}...", end=" ")
        year_slugs = []
        
        for page in range(1, max_pages_per_year + 1):
            url = f"https://letterboxd.com/films/popular/year/{year}/page/{page}/"
            slugs = await scrape_list_page(session, url)
            if not slugs:
                break
            year_slugs.extend(slugs)
            await asyncio.sleep(0.2)
        
        all_slugs.extend(year_slugs)
        print(f"Found {len(year_slugs)} films")
    
    return all_slugs


async def scrape_from_list_url(session: aiohttp.ClientSession, list_url: str, max_pages: int = 20):
    """Scrape films from a specific list URL."""
    print(f"\n📋 Scraping from list: {list_url}")
    all_slugs = []
    
    for page in range(1, max_pages + 1):
        if page == 1:
            url = list_url.rstrip('/')
        else:
            url = f"{list_url.rstrip('/')}/page/{page}/"
        
        slugs = await scrape_list_page(session, url)
        if not slugs:
            break
        
        all_slugs.extend(slugs)
        await asyncio.sleep(0.3)
    
    return all_slugs


async def process_films(session: aiohttp.ClientSession, slugs: list[str], batch_size: int = 20):
    """Process and save films to database."""
    films_scraped = 0
    films_saved = 0
    films_skipped = 0
    
    print(f"\n💾 Processing {len(slugs)} films...\n")
    
    for i in range(0, len(slugs), batch_size):
        batch = slugs[i:i + batch_size]
        batch_films = []
        
        for slug in batch:
            # Check if film already exists
            existing = get_film_by_slug(slug)
            if existing and existing.get('letterboxd_watches') is not None:
                films_skipped += 1
                continue
            
            # Scrape film data
            film_data = await scrape_single_film(session, slug)
            if film_data:
                batch_films.append(film_data)
                films_scraped += 1
            
            await asyncio.sleep(0.2)
        
        # Save batch
        if batch_films:
            for film in batch_films:
                save_film(film)
            films_saved += len(batch_films)
            print(f"   💾 Saved {len(batch_films)} films (Total: {films_saved} saved, {films_skipped} skipped)")
    
    return films_scraped, films_saved, films_skipped


async def main():
    """Main entry point."""
    import sys
    
    print("🎬 Starting database population from Letterboxd lists...\n")
    init_database()
    
    async with aiohttp.ClientSession() as session:
        all_slugs = []
        
        # 1. Scrape popular films
        print("=" * 60)
        popular_slugs = await scrape_popular_films(session, max_pages=50)
        all_slugs.extend(popular_slugs)
        print(f"✅ Found {len(popular_slugs)} films from popular list")
        
        # 2. Scrape popular films by recent years
        print("\n" + "=" * 60)
        current_year = 2025
        years = list(range(current_year - 4, current_year + 1))  # Last 5 years
        year_slugs = await scrape_by_year(session, years, max_pages_per_year=10)
        all_slugs.extend(year_slugs)
        print(f"✅ Found {len(year_slugs)} films from year lists")
        
        # 3. Scrape from specific popular lists (optional)
        popular_lists = [
            "https://letterboxd.com/films/popular/this/year/",
            "https://letterboxd.com/films/popular/this/month/",
            "https://letterboxd.com/films/popular/this/week/",
        ]
        
        print("\n" + "=" * 60)
        for list_url in popular_lists:
            list_slugs = await scrape_from_list_url(session, list_url, max_pages=5)
            all_slugs.extend(list_slugs)
            print(f"✅ Found {len(list_slugs)} films from {list_url.split('/')[-2]}")
        
        # Remove duplicates
        unique_slugs = list(set(all_slugs))
        print(f"\n📊 Total unique films found: {len(unique_slugs)}")
        
        # Process all films
        print("\n" + "=" * 60)
        films_scraped, films_saved, films_skipped = await process_films(session, unique_slugs)
        
        # Final stats
        stats = get_stats()
        print("\n" + "=" * 60)
        print("✅ Database population complete!")
        print(f"📊 Final stats:")
        print(f"   - Total films in database: {stats['total_films']}")
        print(f"   - Films with watch counts: {stats['films_with_watches']}")
        print(f"   - Films scraped this run: {films_scraped}")
        print(f"   - Films saved this run: {films_saved}")
        print(f"   - Films skipped (already in DB): {films_skipped}")


if __name__ == "__main__":
    asyncio.run(main())
