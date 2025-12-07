"""
Script to pre-populate the database with all Letterboxd films.
This scrapes the /films/ directory to get all films and their metadata.
Run this once to build a complete database of all films.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from database import init_database, save_film, get_film_by_slug, get_stats
from scraper import get_headers, parse_film_page
import time


async def scrape_all_letterboxd_films(max_pages: int = None, batch_size: int = 50):
    """
    Scrape all films from Letterboxd's /films/ directory.
    
    Args:
        max_pages: Maximum number of pages to scrape (None = all pages)
        batch_size: Number of films to process before saving to database
    """
    print("🎬 Starting Letterboxd film database population...")
    print("📊 This will scrape all films from letterboxd.com/films/")
    print("⏳ This may take a while...\n")
    
    init_database()
    
    films_scraped = 0
    films_saved = 0
    films_skipped = 0
    page = 1
    consecutive_empty = 0
    
    async with aiohttp.ClientSession() as session:
        while True:
            if max_pages and page > max_pages:
                break
                
            url = f"https://letterboxd.com/films/page/{page}/"
            print(f"📄 Scraping page {page}... ({url})")
            
            try:
                async with session.get(url, headers=get_headers()) as response:
                    if response.status == 404:
                        print(f"✅ Reached end at page {page}")
                        break
                    
                    if response.status != 200:
                        print(f"⚠️  Got status {response.status}, stopping")
                        break
                    
                    html = await response.text()
                    slugs = extract_film_slugs(html)
                    
                    if not slugs:
                        consecutive_empty += 1
                        if consecutive_empty >= 2:  # Reduced from 3 to 2 for faster detection
                            print(f"✅ No more films found after {consecutive_empty} empty pages")
                            print(f"   (Letterboxd's /films/ directory may only show limited pages)")
                            break
                        print(f"   ⚠️  No films found on page {page}, trying next page...")
                        page += 1
                        continue
                    
                    consecutive_empty = 0
                    print(f"   Found {len(slugs)} films on this page")
                    
                    # Process films in batches
                    for i in range(0, len(slugs), batch_size):
                        batch = slugs[i:i + batch_size]
                        batch_films = []
                        
                        for slug in batch:
                            # Check if film already exists in database
                            existing = get_film_by_slug(slug)
                            if existing and existing.get('letterboxd_watches') is not None:
                                films_skipped += 1
                                continue
                            
                            # Scrape film data
                            film_data = await scrape_single_film(session, slug)
                            if film_data:
                                batch_films.append(film_data)
                                films_scraped += 1
                            
                            # Rate limiting
                            await asyncio.sleep(0.2)
                        
                        # Save batch to database
                        if batch_films:
                            for film in batch_films:
                                save_film(film)
                            films_saved += len(batch_films)
                            print(f"   💾 Saved {len(batch_films)} films (Total: {films_saved} saved, {films_skipped} skipped)")
                    
                    page += 1
                    
                    # Rate limiting between pages
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"❌ Error on page {page}: {e}")
                page += 1
                continue
    
    # Final stats
    stats = get_stats()
    print(f"\n✅ Database population complete!")
    print(f"📊 Final stats:")
    print(f"   - Total films in database: {stats['total_films']}")
    print(f"   - Films with watch counts: {stats['films_with_watches']}")
    print(f"   - Films scraped this run: {films_scraped}")
    print(f"   - Films saved this run: {films_saved}")
    print(f"   - Films skipped (already in DB): {films_skipped}")


def extract_film_slugs(html: str) -> list[str]:
    """Extract film slugs from a Letterboxd films listing page."""
    soup = BeautifulSoup(html, 'lxml')
    slugs = []
    
    # Primary method: react-component with LazyPoster (most reliable)
    film_components = soup.select('div.react-component[data-component-class="LazyPoster"]')
    for component in film_components:
        slug = component.get('data-item-slug', '')
        if slug and slug not in slugs:
            slugs.append(slug)
    
    # Fallback: Find all film links
    if not slugs:
        film_links = soup.select('a[href*="/film/"]')
        for link in film_links:
            href = link.get('href', '')
            # Extract slug from href like "/film/slug-name/"
            match = re.search(r'/film/([^/]+)/', href)
            if match:
                slug = match.group(1)
                # Filter out non-film links
                if slug not in ['page', 'popular', 'year', 'country', 'genre'] and slug not in slugs:
                    slugs.append(slug)
    
    # Also check for data attributes in other structures
    if not slugs:
        # Try finding slugs in data attributes
        for elem in soup.select('[data-film-slug], [data-slug]'):
            slug = elem.get('data-film-slug') or elem.get('data-slug')
            if slug and slug not in slugs:
                slugs.append(slug)
    
    return slugs


async def scrape_single_film(session: aiohttp.ClientSession, slug: str) -> dict:
    """Scrape complete data for a single film."""
    film = {
        'slug': slug,
        'letterboxd_url': f"https://letterboxd.com/film/{slug}/"
    }
    
    # Get stats (watch counts)
    stats_url = f"https://letterboxd.com/csi/film/{slug}/stats/"
    try:
        async with session.get(stats_url, headers=get_headers()) as response:
            if response.status == 200:
                html = await response.text()
                stats = parse_stats_html(html)
                film.update(stats)
    except Exception as e:
        pass
    
    # Get main page data (title, year, director, genres, countries)
    main_url = f"https://letterboxd.com/film/{slug}/"
    try:
        async with session.get(main_url, headers=get_headers()) as response:
            if response.status == 200:
                html = await response.text()
                main_data = parse_film_page(html)
                film.update(main_data)
                
                # Also extract title and year from the page if not in main_data
                if not film.get('title'):
                    title_year = extract_title_year(html)
                    if title_year:
                        film.update(title_year)
    except Exception as e:
        pass
    
    return film if film.get('title') or film.get('letterboxd_watches') else None


def parse_stats_html(html: str) -> dict:
    """Parse watch counts from the stats endpoint."""
    soup = BeautifulSoup(html, 'lxml')
    stats = {}
    
    # Get watch count
    watches_div = soup.select_one('.production-statistic.-watches')
    if watches_div:
        aria_label = watches_div.get('aria-label', '')
        match = re.search(r'Watched by ([\d,]+)', aria_label.replace('&nbsp;', ' '))
        if match:
            watches_str = match.group(1).replace(',', '')
            stats['letterboxd_watches'] = int(watches_str)
    
    # Get likes count
    likes_div = soup.select_one('.production-statistic.-likes')
    if likes_div:
        aria_label = likes_div.get('aria-label', '')
        match = re.search(r'Liked by ([\d,]+)', aria_label.replace('&nbsp;', ' '))
        if match:
            likes_str = match.group(1).replace(',', '')
            stats['letterboxd_likes'] = int(likes_str)
    
    # Get list appearances
    lists_div = soup.select_one('.production-statistic.-lists')
    if lists_div:
        aria_label = lists_div.get('aria-label', '')
        match = re.search(r'Appears in ([\d,]+)', aria_label.replace('&nbsp;', ' '))
        if match:
            lists_str = match.group(1).replace(',', '')
            stats['letterboxd_lists'] = int(lists_str)
    
    return stats


def extract_title_year(html: str) -> dict:
    """Extract title and year from film page HTML."""
    soup = BeautifulSoup(html, 'lxml')
    result = {}
    
    # Try to get title from various places
    title_elem = soup.select_one('h1.headline-1, h1.film-title, meta[property="og:title"]')
    if title_elem:
        title_text = title_elem.get_text(strip=True) if hasattr(title_elem, 'get_text') else title_elem.get('content', '')
        # Extract year from title like "Film Name (2024)"
        year_match = re.search(r'\((\d{4})\)', title_text)
        if year_match:
            result['year'] = int(year_match.group(1))
            result['title'] = re.sub(r'\s*\(\d{4}\)\s*$', '', title_text).strip()
        else:
            result['title'] = title_text
    
    return result


async def main():
    """Main entry point."""
    import sys
    
    max_pages = None
    if len(sys.argv) > 1:
        try:
            max_pages = int(sys.argv[1])
            print(f"📌 Limiting to {max_pages} pages")
        except ValueError:
            print("⚠️  Invalid page limit, scraping all pages")
    
    await scrape_all_letterboxd_films(max_pages=max_pages)


if __name__ == "__main__":
    asyncio.run(main())
