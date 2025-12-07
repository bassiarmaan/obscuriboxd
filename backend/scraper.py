"""
Letterboxd scraper using web scraping techniques.
Now fetches watch counts from the CSI stats endpoint.
Saves films to database for future use.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import os
from database import save_films, get_films_by_slugs
from aiohttp import ClientTimeout

# Import TMDb functions for poster fetching
try:
    from tmdb import search_film, TMDB_API_KEY
    TMDB_AVAILABLE = True
except:
    TMDB_AVAILABLE = False
    TMDB_API_KEY = None


async def get_user_films(username: str) -> list[dict]:
    """
    Scrape all films from a Letterboxd user's profile.
    Returns a list of films with title, year, rating, and letterboxd URL.
    NO PAGE LIMITS - scrapes all pages to get complete film list.
    """
    films = []
    page = 1
    consecutive_empty_pages = 0
    max_empty_pages = 2  # Stop after 2 consecutive empty pages
    
    # Create session with timeout to prevent hanging
    timeout = ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
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
                        consecutive_empty_pages += 1
                        if consecutive_empty_pages >= max_empty_pages:
                            break
                        page += 1
                        continue
                    
                    consecutive_empty_pages = 0  # Reset counter
                    films.extend(page_films)
                    page += 1
                    
                    # Rate limiting - be nice to Letterboxd
                    await asyncio.sleep(0.1)  # Reduced delay
                    
            except aiohttp.ClientError as e:
                raise Exception(f"Error fetching data: {str(e)}")
    
    # Check database first for existing films
    slugs = [f.get('slug') for f in films if f.get('slug')]
    db_films = get_films_by_slugs(slugs)
    
    # Merge database data with user's film list
    enriched_films = []
    films_to_scrape = []
    
    for film in films:
        slug = film.get('slug')
        if slug and slug in db_films:
            # Film exists in database - use DB data but keep user rating
            db_film = db_films[slug]
            film.update({k: v for k, v in db_film.items() if k != 'user_rating'})
            
            # If film doesn't have a poster, add it to scrape list to get poster
            if not film.get('poster_path'):
                films_to_scrape.append(film)
            else:
                enriched_films.append(film)
        else:
            # Film not in DB - need to scrape
            films_to_scrape.append(film)
    
    # Scrape only films not in database, but limit to prevent server overload
    # On production (Render), disable scraping entirely (set MAX_FILMS_TO_SCRAPE=0)
    # Run populate scripts locally instead
    MAX_FILMS_TO_SCRAPE_PER_REQUEST = int(os.getenv("MAX_FILMS_TO_SCRAPE", "20"))
    
    if films_to_scrape:
        # If scraping is disabled, just use films as-is (without watch counts)
        if MAX_FILMS_TO_SCRAPE_PER_REQUEST == 0:
            print(f"📊 Found {len(films_to_scrape)} films not in database (scraping disabled on server)")
            enriched_films.extend(films_to_scrape)
        elif len(films_to_scrape) > MAX_FILMS_TO_SCRAPE_PER_REQUEST:
            # Too many films - only scrape a sample and use defaults for the rest
            print(f"📊 Found {len(films_to_scrape)} films not in database, scraping {MAX_FILMS_TO_SCRAPE_PER_REQUEST} (limited to prevent overload)...")
            films_to_scrape_now = films_to_scrape[:MAX_FILMS_TO_SCRAPE_PER_REQUEST]
            films_to_skip = films_to_scrape[MAX_FILMS_TO_SCRAPE_PER_REQUEST:]
            
            # Scrape the limited batch
            scraped_films = await enrich_with_letterboxd_stats(films_to_scrape_now)
            enriched_films.extend(scraped_films)
            save_films(scraped_films)
            
            # For the rest, use them as-is (without watch counts) - they'll be scraped later
            enriched_films.extend(films_to_skip)
        else:
            # Small number of films - safe to scrape all
            print(f"📊 Found {len(films_to_scrape)} films not in database, scraping...")
            scraped_films = await enrich_with_letterboxd_stats(films_to_scrape)
            enriched_films.extend(scraped_films)
            save_films(scraped_films)
    else:
        print(f"✅ All {len(films)} films found in database!")
    
    return enriched_films


async def enrich_with_letterboxd_stats(films: list[dict]) -> list[dict]:
    """
    Fetch Letterboxd watch counts from the stats CSI endpoint.
    Fetches for ALL films to ensure complete data.
    Uses smaller batches and better error handling for large collections.
    """
    if not films:
        return films
    
    # Adjust batch size based on total films to avoid overwhelming
    # Increased batch sizes and reduced delays for faster scraping
    if len(films) > 1000:
        batch_size = 20  # Increased from 5
        delay = 0.1  # Reduced from 0.5
    elif len(films) > 500:
        batch_size = 25  # Increased from 8
        delay = 0.1  # Reduced from 0.4
    else:
        batch_size = 30  # Increased from 10
        delay = 0.1  # Reduced from 0.3
    
    # Create session with timeout settings
    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for i in range(0, len(films), batch_size):
            batch = films[i:i + batch_size]
            tasks = [get_film_stats(session, film) for film in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for film, result in zip(batch, results):
                if isinstance(result, dict):
                    film.update(result)
                # Silently skip exceptions - they're handled in get_film_stats
            
            # Rate limiting - be respectful to Letterboxd
            if i + batch_size < len(films):  # Don't sleep after last batch
                await asyncio.sleep(delay)
    
    return films


async def get_film_stats(session: aiohttp.ClientSession, film: dict, retries: int = 3) -> dict:
    """
    Get Letterboxd watch count from the CSI stats endpoint.
    This is the REAL source of watch counts.
    Includes retry logic for connection errors.
    Also fetches TMDb poster image.
    """
    slug = film.get('slug', '')
    if not slug:
        return {}
    
    # The stats endpoint has the watch count
    stats_url = f"https://letterboxd.com/csi/film/{slug}/stats/"
    
    for attempt in range(retries):
        try:
            # Add timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            async with session.get(stats_url, headers=get_headers(), timeout=timeout) as response:
                if response.status != 200:
                    return {}
                
                html = await response.text()
                stats = parse_stats_html(html)
                
                # Always get additional details from main page (director, genres, countries)
                main_url = f"https://letterboxd.com/film/{slug}/"
                async with session.get(main_url, headers=get_headers(), timeout=timeout) as main_response:
                    if main_response.status == 200:
                        main_html = await main_response.text()
                        main_stats = parse_film_page(main_html)
                        stats.update({k: v for k, v in main_stats.items() if v})
                
                # Get TMDb poster if we don't have one from Letterboxd
                if stats.get('title') and stats.get('year') and not stats.get('poster_path'):
                    tmdb_poster = await get_tmdb_poster(stats.get('title'), stats.get('year'))
                    if tmdb_poster:
                        stats['poster_path'] = tmdb_poster
                
                return stats
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as e:
            # Retry on connection errors
            if attempt < retries - 1:
                await asyncio.sleep(0.2 * (attempt + 1))  # Reduced exponential backoff
                continue
            # Don't print error on last attempt - too noisy
            return {}
        except Exception as e:
            # Don't retry on other errors
            return {}
    
    return {}


async def get_tmdb_poster(title: str, year: int) -> str | None:
    """Get TMDb poster path for a film. Returns just the path (e.g., '/abc123.jpg')."""
    if not TMDB_AVAILABLE or not TMDB_API_KEY:
        return None
    
    try:
        timeout = ClientTimeout(total=5, connect=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            tmdb_data = await search_film(session, title, year, None)
            if tmdb_data and tmdb_data.get('poster_path'):
                return tmdb_data.get('poster_path')
    except:
        pass
    
    return None


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
    """Parse title, year, director, genres, and countries from the main film page."""
    soup = BeautifulSoup(html, 'lxml')
    stats = {}
    
    # Get title and year from og:title meta tag (e.g., "Film Name (2024)")
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title_content = og_title.get('content', '')
        # Extract year from title like "Film Name (2024)"
        year_match = re.search(r'\((\d{4})\)', title_content)
        if year_match:
            stats['year'] = int(year_match.group(1))
            stats['title'] = re.sub(r'\s*\(\d{4}\)\s*$', '', title_content).strip()
        else:
            stats['title'] = title_content.strip()
    
    # Also try h1.headline-1 as fallback
    if not stats.get('title'):
        h1 = soup.select_one('h1.headline-1 .name, h1.headline-1')
        if h1:
            title_text = h1.get_text(strip=True)
            year_match = re.search(r'\((\d{4})\)', title_text)
            if year_match:
                stats['year'] = int(year_match.group(1))
                stats['title'] = re.sub(r'\s*\(\d{4}\)\s*$', '', title_text).strip()
            else:
                stats['title'] = title_text
    
    # Get year from release date if not found in title
    if not stats.get('year'):
        # Try to find year in various places
        year_elem = soup.select_one('a[href*="/films/year/"]')
        if year_elem:
            year_text = year_elem.get_text(strip=True)
            year_match = re.search(r'(\d{4})', year_text)
            if year_match:
                stats['year'] = int(year_match.group(1))
    
    # Get poster image from og:image (Letterboxd poster)
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image:
        image_url = og_image.get('content', '')
        if image_url:
            stats['poster_path'] = image_url
    
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
