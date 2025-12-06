"""
Letterboxd scraper using web scraping techniques.
Now fetches watch counts from the CSI stats endpoint.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re


async def get_user_films(username: str) -> list[dict]:
    """
    Scrape all films from a Letterboxd user's profile.
    Returns a list of films with title, year, rating, and letterboxd URL.
    """
    films = []
    page = 1
    
    async with aiohttp.ClientSession() as session:
        while True:
            url = f"https://letterboxd.com/{username}/films/page/{page}/"
            
            try:
                async with session.get(url, headers=get_headers()) as response:
                    if response.status == 404:
                        if page == 1:
                            raise Exception(f"User '{username}' not found")
                        break
                    
                    if response.status != 200:
                        break
                    
                    html = await response.text()
                    page_films = parse_films_page(html)
                    
                    if not page_films:
                        break
                    
                    films.extend(page_films)
                    page += 1
                    
                    # Rate limiting - be nice to Letterboxd
                    await asyncio.sleep(0.3)
                    
                    # Increased limit to capture films from all decades (25 pages = ~1800 films)
                    # Letterboxd orders by watch date, so we need more pages to get older films
                    if page > 25:
                        break
                    
            except aiohttp.ClientError as e:
                raise Exception(f"Error fetching data: {str(e)}")
    
    # Fetch Letterboxd watch counts for a sample of films
    films = await enrich_with_letterboxd_stats(films)
    
    return films


async def enrich_with_letterboxd_stats(films: list[dict]) -> list[dict]:
    """
    Fetch Letterboxd watch counts from the stats CSI endpoint.
    Sample films for speed.
    """
    if not films:
        return films
    
    # Determine which films to sample
    if len(films) <= 30:
        sample_indices = list(range(len(films)))
    else:
        # Sample evenly across the list
        sample_size = 30
        step = len(films) / sample_size
        sample_indices = [int(i * step) for i in range(sample_size)]
    
    films_to_fetch = [(i, films[i]) for i in sample_indices]
    
    async with aiohttp.ClientSession() as session:
        # Process in batches
        batch_size = 10
        
        for i in range(0, len(films_to_fetch), batch_size):
            batch = films_to_fetch[i:i + batch_size]
            tasks = [get_film_stats(session, film) for idx, film in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for (idx, film), result in zip(batch, results):
                if isinstance(result, dict):
                    films[idx].update(result)
            
            # Rate limiting
            await asyncio.sleep(0.3)
    
    return films


async def get_film_stats(session: aiohttp.ClientSession, film: dict) -> dict:
    """
    Get Letterboxd watch count from the CSI stats endpoint.
    This is the REAL source of watch counts.
    """
    slug = film.get('slug', '')
    if not slug:
        return {}
    
    # The stats endpoint has the watch count
    stats_url = f"https://letterboxd.com/csi/film/{slug}/stats/"
    
    try:
        async with session.get(stats_url, headers=get_headers()) as response:
            if response.status != 200:
                return {}
            
            html = await response.text()
            stats = parse_stats_html(html)
            
            # Also get additional details from main page if needed
            if not stats.get('director') or not stats.get('genres'):
                main_url = f"https://letterboxd.com/film/{slug}/"
                async with session.get(main_url, headers=get_headers()) as main_response:
                    if main_response.status == 200:
                        main_html = await main_response.text()
                        main_stats = parse_film_page(main_html)
                        stats.update({k: v for k, v in main_stats.items() if v})
            
            return stats
    except Exception as e:
        print(f"Error fetching stats for {slug}: {e}")
        return {}


def parse_stats_html(html: str) -> dict:
    """
    Parse the CSI stats endpoint response.
    Format: <div class="production-statistic -watches" aria-label="Watched by 6,234,540&nbsp;members">
    """
    soup = BeautifulSoup(html, 'lxml')
    stats = {}
    
    # Get watch count
    watches_div = soup.select_one('.production-statistic.-watches')
    if watches_div:
        aria_label = watches_div.get('aria-label', '')
        # Extract number from "Watched by 6,234,540 members"
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


def parse_film_page(html: str) -> dict:
    """Parse director and genres from the main film page."""
    soup = BeautifulSoup(html, 'lxml')
    stats = {}
    
    # Get director
    director_link = soup.select_one('a[href*="/director/"]')
    if director_link:
        stats['director'] = director_link.get_text(strip=True)
    
    # Get genres
    genre_links = soup.select('#tab-genres a.text-slug')
    if genre_links:
        # Filter out the "Show All" and category-type genres
        stats['genres'] = [
            g.get_text(strip=True) for g in genre_links[:5]
            if not g.get_text(strip=True).startswith('Show')
        ]
    
    # Get countries
    country_links = soup.select('a[href*="/films/country/"]')
    if country_links:
        stats['production_countries'] = [c.get_text(strip=True) for c in country_links]
    
    # Get letterboxd rating
    rating_meta = soup.select_one('meta[name="twitter:data2"]')
    if rating_meta:
        rating_text = rating_meta.get('content', '')
        try:
            rating_value = float(rating_text.split()[0])
            stats['letterboxd_rating'] = rating_value
        except (ValueError, IndexError):
            pass
    
    return stats


def get_headers() -> dict:
    """Return headers to mimic a browser request."""
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }


def parse_films_page(html: str) -> list[dict]:
    """Parse a page of films from Letterboxd's current HTML structure."""
    soup = BeautifulSoup(html, 'lxml')
    films = []
    
    # Find all react-component divs with film data
    film_components = soup.select('div.react-component[data-component-class="LazyPoster"]')
    
    for component in film_components:
        # Extract film data from data attributes
        item_name = component.get('data-item-name', '')
        slug = component.get('data-item-slug', '')
        film_id = component.get('data-film-id', '')
        
        if not item_name or not slug:
            continue
        
        # Parse title and year from item_name (e.g., "Wicked: For Good (2025)")
        title = item_name
        year = None
        
        # Extract year from the end of the title
        year_match = re.search(r'\((\d{4})\)$', item_name)
        if year_match:
            year = int(year_match.group(1))
            title = item_name[:year_match.start()].strip()
        
        # Find the rating in the poster-viewingdata element
        user_rating = None
        viewingdata = component.find_next('p', class_='poster-viewingdata')
        if viewingdata:
            rating_span = viewingdata.select_one('span.rating')
            if rating_span:
                rating_class = rating_span.get('class', [])
                for cls in rating_class:
                    if cls.startswith('rated-'):
                        try:
                            # rated-6 means 3 stars (rating * 2)
                            rating_value = int(cls.replace('rated-', ''))
                            user_rating = rating_value / 2.0
                        except ValueError:
                            pass
        
        films.append({
            'title': title,
            'year': year,
            'slug': slug,
            'letterboxd_id': film_id,
            'letterboxd_url': f"https://letterboxd.com/film/{slug}/" if slug else None,
            'user_rating': user_rating
        })
    
    return films


# Keep old function names for compatibility
async def get_film_letterboxd_stats(session: aiohttp.ClientSession, film: dict) -> dict:
    """Alias for get_film_stats for backward compatibility."""
    return await get_film_stats(session, film)


async def get_film_details(slug: str) -> dict:
    """Get detailed information about a specific film."""
    async with aiohttp.ClientSession() as session:
        return await get_film_stats(session, {'slug': slug})
