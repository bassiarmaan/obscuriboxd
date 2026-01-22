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

# Import cloudscraper for Cloudflare bypass
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
    print("✅ Cloudscraper is available for Cloudflare bypass")
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    cloudscraper = None
    print("⚠️  Cloudscraper not available - will use aiohttp (may be blocked by Cloudflare)")

# Import TMDb functions for poster fetching
try:
    from tmdb import search_film, TMDB_API_KEY
    TMDB_AVAILABLE = True
except:
    TMDB_AVAILABLE = False
    TMDB_API_KEY = None

# Import xml parser for RSS
import xml.etree.ElementTree as ET


async def get_user_films_from_rss(username: str) -> list[dict]:
    """
    Get user's films from their RSS feed.
    This is a fallback when HTML scraping is blocked by Cloudflare.
    Note: RSS only contains recent diary entries, not all watched films.
    """
    rss_url = f"https://letterboxd.com/{username}/rss/"
    print(f"📡 Fetching films from RSS feed: {rss_url}")
    
    try:
        timeout = ClientTimeout(total=30, connect=10)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(rss_url, headers=headers) as response:
                print(f"   RSS response status: {response.status}")
                if response.status == 404:
                    raise Exception(f"User '{username}' not found")
                if response.status != 200:
                    raise Exception(f"Failed to fetch RSS feed: HTTP {response.status}")
                
                content = await response.text()
                print(f"   RSS content length: {len(content)}")
                print(f"   RSS content preview: {content[:200]}")
                
                # Check for Cloudflare challenge
                if is_cloudflare_challenge(content):
                    raise Exception("RSS feed is blocked by Cloudflare")
                
                # Check if we got valid XML
                if not content.startswith('<?xml'):
                    print(f"   ⚠️ RSS content doesn't start with <?xml")
                    raise Exception(f"Invalid RSS response - not XML (starts with: {content[:50]})")
    except aiohttp.ClientError as e:
        print(f"   ❌ aiohttp error: {e}")
        raise Exception(f"Network error fetching RSS: {e}")
    except Exception as e:
        print(f"   ❌ RSS fetch error: {e}")
        raise
    
    # Parse RSS XML
    films = []
    seen_slugs = set()
    
    try:
        root = ET.fromstring(content)
        
        # Define namespaces - ElementTree requires explicit namespace handling
        namespaces = {
            'letterboxd': 'https://letterboxd.com',
            'tmdb': 'https://themoviedb.org'
        }
        
        # Find all items in the RSS feed
        for item in root.findall('.//item'):
            film = {}
            
            # Get film link to extract slug
            link_elem = item.find('link')
            if link_elem is not None and link_elem.text:
                link = link_elem.text
                # Extract slug from link like https://letterboxd.com/armbot/film/marty-supreme/
                slug_match = re.search(r'/film/([^/]+)/?$', link)
                if slug_match:
                    film['slug'] = slug_match.group(1)
            
            if not film.get('slug') or film['slug'] in seen_slugs:
                continue
            seen_slugs.add(film['slug'])
            
            # Get letterboxd-specific data using namespaces
            # ElementTree requires {namespace_uri}element_name format
            
            # Get film title
            film_title = item.find('{https://letterboxd.com}filmTitle')
            if film_title is not None and film_title.text:
                film['title'] = film_title.text
            
            # Get film year
            film_year = item.find('{https://letterboxd.com}filmYear')
            if film_year is not None and film_year.text:
                try:
                    film['year'] = int(film_year.text)
                except ValueError:
                    pass
            
            # Get user's rating
            member_rating = item.find('{https://letterboxd.com}memberRating')
            if member_rating is not None and member_rating.text:
                try:
                    film['user_rating'] = float(member_rating.text)
                except ValueError:
                    pass
            
            # Get TMDB movie ID
            tmdb_id = item.find('{https://themoviedb.org}movieId')
            if tmdb_id is not None and tmdb_id.text:
                film['tmdb_id'] = tmdb_id.text
            
            # Extract poster URL from description (it's in an img tag)
            description = item.find('description')
            if description is not None and description.text:
                poster_match = re.search(r'<img src="([^"]+)"', description.text)
                if poster_match:
                    film['poster_path'] = poster_match.group(1)
            
            # Build letterboxd URL
            film['letterboxd_url'] = f"https://letterboxd.com/film/{film['slug']}/"
            
            # Add empty letterboxd_id for compatibility
            film['letterboxd_id'] = ''
            
            films.append(film)
        
        print(f"✅ Found {len(films)} films in RSS feed")
        
    except ET.ParseError as e:
        print(f"⚠️  Failed to parse RSS XML: {e}")
        raise Exception(f"Failed to parse RSS feed: {e}")
    
    return films


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
    used_rss_fallback = False  # Track if we used RSS (can't scrape if Cloudflare is blocking)
    
    # Create session with timeout to prevent hanging
    timeout = ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            url = f"https://letterboxd.com/{username}/films/page/{page}/"
            
            try:
                # Try using cloudscraper first to bypass Cloudflare
                print(f"📡 Fetching page {page} for user '{username}'...")
                html = await fetch_with_cloudflare_bypass(url, get_headers())
                
                # Check if we got a Cloudflare challenge
                if is_cloudflare_challenge(html):
                    print(f"🛡️  Cloudflare challenge detected! HTML preview: {html[:300]}")
                    if page == 1:
                        # Try RSS feed as fallback
                        print(f"🔄 Trying RSS feed as fallback...")
                        try:
                            rss_films = await get_user_films_from_rss(username)
                            if rss_films:
                                print(f"✅ RSS fallback successful! Found {len(rss_films)} films")
                                films = rss_films
                                used_rss_fallback = True  # Mark that we used RSS
                                break  # Exit the while loop and continue with these films
                        except Exception as rss_error:
                            print(f"⚠️  RSS fallback failed: {rss_error}")
                        
                        # If RSS also failed, raise the original error
                        raise Exception(
                            f"Cloudflare protection detected. Letterboxd is blocking automated requests. "
                            f"This may be temporary. Please try again later or check if your IP is blocked."
                        )
                    print(f"⚠️  Cloudflare challenge on page {page}, stopping")
                    break
                
                # Check for 404 by looking for common 404 indicators
                if 'not found' in html.lower() or '404' in html.lower() or 'page not found' in html.lower():
                    if page == 1:
                        raise Exception(f"User '{username}' not found")
                    print(f"⚠️  404 detected on page {page}, stopping")
                    break
                
                # Check if profile is private - look for specific Letterboxd private profile messages
                # Don't match false positives like "private-note-modal.css" in stylesheets
                private_indicators = [
                    "this person's profile is private",
                    "this profile is private",
                    "has a private profile",
                ]
                html_lower = html.lower()
                is_private = any(indicator in html_lower for indicator in private_indicators)
                if is_private:
                    if page == 1:
                        raise Exception(f"User '{username}' profile is private. Make sure the profile is public.")
                    break
                
                # Verify we got valid HTML
                if not html or len(html) < 100:
                    if page == 1:
                        raise Exception(f"Received empty or invalid response from Letterboxd for user '{username}'")
                    break
                
                print(f"📊 Parsing films from page {page} (HTML length: {len(html)})...")
                page_films = parse_films_page(html)
                print(f"   Found {len(page_films)} films on page {page}")
                
                if not page_films:
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_empty_pages:
                        if page == 1:
                            # First page with no films - could be empty profile or parsing issue
                            print(f"⚠️  No films found on first page for user '{username}'")
                            print(f"   HTML length: {len(html)}")
                            print(f"   Contains 'film': {'film' in html.lower()}")
                            print(f"   Contains 'letterboxd': {'letterboxd' in html.lower()}")
                            # Save a sample of HTML for debugging (first 500 chars)
                            print(f"   HTML preview: {html[:500]}")
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
            except Exception as e:
                error_msg = str(e)
                # Check if Cloudflare is blocking - try RSS fallback
                if "CLOUDFLARE_BLOCKED" in error_msg or "403" in error_msg:
                    if page == 1 and not used_rss_fallback:
                        print(f"🔄 Cloudflare blocking detected, trying RSS feed as fallback...")
                        try:
                            rss_films = await get_user_films_from_rss(username)
                            if rss_films:
                                print(f"✅ RSS fallback successful! Found {len(rss_films)} films")
                                films = rss_films
                                used_rss_fallback = True
                                break  # Exit the while loop
                        except Exception as rss_error:
                            print(f"⚠️  RSS fallback also failed: {rss_error}")
                # Re-raise our custom exceptions
                raise
    
    # If no films found at all, raise an error
    if not films:
        raise Exception(f"No films found for user '{username}'. Make sure the profile is public.")
    
    # Check database first for existing films
    slugs = [f.get('slug') for f in films if f.get('slug')]
    print(f"🔍 Looking up {len(slugs)} film slugs in database...")
    db_films = get_films_by_slugs(slugs)
    print(f"   Found {len(db_films)} films in database")
    
    # Merge database data with user's film list
    enriched_films = []
    films_to_scrape = []
    from_db_count = 0
    incomplete_count = 0
    missing_count = 0
    
    for film in films:
        slug = film.get('slug')
        if slug and slug in db_films:
            # Film exists in database - use DB data but keep user rating
            db_film = db_films[slug]
            film.update({k: v for k, v in db_film.items() if k != 'user_rating'})
            
            # Check if film is missing critical information - if so, scrape to complete it
            needs_scraping = False
            missing_fields = []
            
            # Check for missing critical fields
            if not film.get('title') or not film.get('title').strip():
                needs_scraping = True
                missing_fields.append('title')
            if film.get('year') is None:
                needs_scraping = True
                missing_fields.append('year')
            if film.get('letterboxd_watches') is None:
                needs_scraping = True
                missing_fields.append('watches')
            if not film.get('poster_path') or not film.get('poster_path').strip():
                needs_scraping = True
                missing_fields.append('poster')
            
            if needs_scraping:
                # Film exists but missing critical info - scrape to complete it
                incomplete_count += 1
                films_to_scrape.append(film)
            else:
                # Film is complete - use as-is from database
                from_db_count += 1
                enriched_films.append(film)
        else:
            # Film not in DB - need to scrape all information
            missing_count += 1
            films_to_scrape.append(film)
    
    # Log database usage stats
    print(f"📊 Database lookup: {from_db_count} from DB, {incomplete_count} incomplete (needs scraping), {missing_count} not in DB")
    
    # Scrape only films not in database, but limit to prevent server overload
    # On production (Render), disable scraping entirely (set MAX_FILMS_TO_SCRAPE=0)
    # Run populate scripts locally instead
    MAX_FILMS_TO_SCRAPE_PER_REQUEST = int(os.getenv("MAX_FILMS_TO_SCRAPE", "100"))  # Default to 100 instead of 20
    
    if films_to_scrape:
        # If we used RSS fallback, Cloudflare is blocking so we can't scrape stats either
        # Just use what we have (films will have default obscurity score)
        if used_rss_fallback:
            print(f"📊 Skipping scraping for {len(films_to_scrape)} films (using RSS fallback, Cloudflare blocking)")
            print(f"   ⚠️  Films without watch data will use default obscurity scores")
            # Use DB data if available, otherwise use RSS data as-is
            for film in films_to_scrape:
                slug = film.get('slug')
                if slug and slug in db_films:
                    db_film = db_films[slug]
                    film.update({k: v for k, v in db_film.items() if k != 'user_rating'})
                enriched_films.append(film)
        # If scraping is disabled, use what we have from DB (even if incomplete)
        elif MAX_FILMS_TO_SCRAPE_PER_REQUEST == 0:
            print(f"📊 Found {len(films_to_scrape)} films to scrape (scraping disabled on server)")
            # Use DB data if available, even if incomplete
            for film in films_to_scrape:
                slug = film.get('slug')
                if slug and slug in db_films:
                    db_film = db_films[slug]
                    film.update({k: v for k, v in db_film.items() if k != 'user_rating'})
                enriched_films.append(film)
        elif len(films_to_scrape) > MAX_FILMS_TO_SCRAPE_PER_REQUEST:
            # Too many films - prioritize films not in DB, then incomplete films
            print(f"📊 Found {len(films_to_scrape)} films to scrape (limited to {MAX_FILMS_TO_SCRAPE_PER_REQUEST} per request)...")
            
            # Separate: films not in DB vs films missing info
            films_not_in_db = [f for f in films_to_scrape if f.get('slug') not in db_films]
            films_missing_info = [f for f in films_to_scrape if f.get('slug') in db_films]
            
            # Prioritize films not in DB
            films_to_scrape_now = (films_not_in_db + films_missing_info)[:MAX_FILMS_TO_SCRAPE_PER_REQUEST]
            films_to_skip = films_to_scrape[MAX_FILMS_TO_SCRAPE_PER_REQUEST:]
            
            # Scrape the limited batch
            scraped_films = await enrich_with_letterboxd_stats(films_to_scrape_now)
            enriched_films.extend(scraped_films)
            save_films(scraped_films)
            
            # For the rest, use what we have from DB (even if incomplete)
            for film in films_to_skip:
                slug = film.get('slug')
                if slug and slug in db_films:
                    db_film = db_films[slug]
                    film.update({k: v for k, v in db_film.items() if k != 'user_rating'})
                enriched_films.append(film)
        else:
            # Small number of films - safe to scrape all
            films_not_in_db = [f for f in films_to_scrape if f.get('slug') not in db_films]
            films_missing_info = [f for f in films_to_scrape if f.get('slug') in db_films]
            
            if films_not_in_db:
                print(f"📊 Scraping {len(films_not_in_db)} new films and {len(films_missing_info)} incomplete films...")
            else:
                print(f"📊 Completing information for {len(films_missing_info)} films...")
            
            scraped_films = await enrich_with_letterboxd_stats(films_to_scrape)
            enriched_films.extend(scraped_films)
            save_films(scraped_films)
    else:
        print(f"✅ All {len(films)} films found in database with complete information!")
        print(f"   💾 100% from database - no scraping needed!")
    
    return enriched_films


async def enrich_with_letterboxd_stats(films: list[dict]) -> list[dict]:
    """
    Fetch Letterboxd watch counts from the stats CSI endpoint.
    Fetches for ALL films to ensure complete data.
    Uses smaller batches and better error handling for large collections.
    """
    if not films:
        return films
    
    # Optimized batch sizes for maximum speed
    # For large-scale scraping, use much larger batches
    if len(films) > 1000:
        batch_size = 50  # Increased for bulk scraping
        delay = 0.05  # Minimal delay
    elif len(films) > 500:
        batch_size = 50
        delay = 0.05
    else:
        batch_size = 50
        delay = 0.05
    
    # Create session with optimized timeout and connection limits
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)  # Higher connection limits
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for i in range(0, len(films), batch_size):
            batch = films[i:i + batch_size]
            tasks = [get_film_stats(session, film) for film in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for film, result in zip(batch, results):
                if isinstance(result, dict):
                    film.update(result)
                # Silently skip exceptions - they're handled in get_film_stats
            
            # Minimal rate limiting - only for very large batches
            if i + batch_size < len(films) and len(films) > 100:
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
            # Optimized: fetch stats and main page in parallel
            stats_url = f"https://letterboxd.com/csi/film/{slug}/stats/"
            main_url = f"https://letterboxd.com/film/{slug}/"
            
            headers = get_headers()
            stats = {}
            
            # Use cloudscraper to bypass Cloudflare if available
            if CLOUDSCRAPER_AVAILABLE:
                loop = asyncio.get_event_loop()
                scraper = cloudscraper.create_scraper()
                
                def fetch_stats():
                    try:
                        resp = scraper.get(stats_url, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            # Force UTF-8 encoding before accessing .text (cloudscraper encoding detection can fail)
                            resp.encoding = 'utf-8'
                            return resp.text
                        return ""
                    except:
                        return ""
                
                def fetch_main():
                    try:
                        resp = scraper.get(main_url, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            # Force UTF-8 encoding before accessing .text (cloudscraper encoding detection can fail)
                            resp.encoding = 'utf-8'
                            return resp.text
                        return ""
                    except:
                        return ""
                
                stats_html, main_html = await asyncio.gather(
                    loop.run_in_executor(None, fetch_stats),
                    loop.run_in_executor(None, fetch_main),
                    return_exceptions=True
                )
                
                # Parse stats page
                if not isinstance(stats_html, Exception) and stats_html:
                    if not is_cloudflare_challenge(stats_html):
                        stats = parse_stats_html(stats_html)
                
                # Parse main page
                if not isinstance(main_html, Exception) and main_html:
                    if not is_cloudflare_challenge(main_html):
                        main_stats = parse_film_page(main_html)
                        stats.update({k: v for k, v in main_stats.items() if v})
            else:
                # Fallback to aiohttp
                stats_task = session.get(stats_url, headers=headers)
                main_task = session.get(main_url, headers=headers)
                
                stats_response, main_response = await asyncio.gather(
                    stats_task, main_task, return_exceptions=True
                )
                
                # Parse stats page
                if not isinstance(stats_response, Exception) and stats_response.status == 200:
                    html = await stats_response.text()
                    if not is_cloudflare_challenge(html):
                        stats = parse_stats_html(html)
                
                # Parse main page
                if not isinstance(main_response, Exception) and main_response.status == 200:
                    main_html = await main_response.text()
                    if not is_cloudflare_challenge(main_html):
                        main_stats = parse_film_page(main_html)
                        stats.update({k: v for k, v in main_stats.items() if v})
            
            # TMDb poster lookup - skip during bulk scraping for speed
            # Can be added later via add_posters.py script
            # if stats.get('title') and stats.get('year') and not stats.get('poster_path'):
            #     try:
            #         tmdb_poster = await get_tmdb_poster(stats.get('title'), stats.get('year'))
            #         if tmdb_poster:
            #             stats['poster_path'] = tmdb_poster
            #     except Exception:
            #         pass
            
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
        'Accept-Encoding': 'gzip, deflate',  # Note: removed 'br' (brotli) as cloudscraper may not decode it properly
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def is_cloudflare_challenge(html: str) -> bool:
    """Check if the HTML response is a Cloudflare challenge page."""
    if not html:
        return False
    
    # Real Letterboxd pages are large (100KB+), challenge pages are small (<20KB)
    # If the page is large, it's almost certainly not a challenge page
    if len(html) > 50000:
        return False
    
    html_lower = html.lower()
    
    # Strong indicators that ONLY appear on challenge pages (not normal pages)
    strong_indicators = [
        'just a moment',
        'checking your browser',
        'enable javascript and cookies to continue',
        'cf-browser-verification',
        'cf-spinner',
    ]
    
    for indicator in strong_indicators:
        if indicator in html_lower:
            return True
    
    return False


async def fetch_with_cloudflare_bypass(url: str, headers: dict = None) -> str:
    """
    Fetch URL with Cloudflare bypass using cloudscraper.
    Falls back to aiohttp if cloudscraper is not available.
    """
    request_headers = headers or get_headers()
    
    print(f"🌐 Attempting to fetch: {url}")
    print(f"   Cloudscraper available: {CLOUDSCRAPER_AVAILABLE}")
    
    if CLOUDSCRAPER_AVAILABLE:
        # Use cloudscraper in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        # Create scraper with minimal configuration - let cloudscraper auto-detect
        scraper = cloudscraper.create_scraper()
        try:
            def fetch():
                resp = scraper.get(url, timeout=30, allow_redirects=True)
                print(f"   Response status: {resp.status_code}")
                # Verify we got a successful response
                if resp.status_code == 404:
                    raise Exception(f"404 Not Found: User or page does not exist")
                elif resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code} error: {resp.reason}")
                # Force UTF-8 encoding before accessing .text (cloudscraper encoding detection can fail)
                resp.encoding = 'utf-8'
                html_text = resp.text
                if not html_text:
                    raise Exception("Empty response received")
                # Check if we got a Cloudflare challenge even with 200 status
                if is_cloudflare_challenge(html_text):
                    print(f"   ⚠️ Cloudscraper returned Cloudflare challenge page!")
                    print(f"   HTML preview: {html_text[:200]}")
                return html_text
            
            html = await loop.run_in_executor(None, fetch)
            print(f"✅ Successfully fetched {url} via cloudscraper (length: {len(html)})")
            return html
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️  Cloudscraper failed for {url}: {error_msg}")
            # If it's a 404, don't fall back - raise it
            if "404" in error_msg or "Not Found" in error_msg:
                raise
            # If it's a 403 Forbidden, Cloudflare is blocking - raise to trigger RSS fallback
            if "403" in error_msg or "Forbidden" in error_msg:
                print(f"   🛡️ Cloudflare blocking detected (403) - will try RSS fallback")
                raise Exception("CLOUDFLARE_BLOCKED: 403 Forbidden")
            print(f"   Falling back to aiohttp...")
    
    # Fallback to aiohttp
    timeout = ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=request_headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status} error: {response.reason}. Response: {error_text[:200]}")
            html = await response.text()
            print(f"✅ Successfully fetched {url} via aiohttp (length: {len(html)})")
            return html


def parse_films_page(html: str) -> list[dict]:
    """Parse a page of films from Letterboxd's current HTML structure."""
    soup = BeautifulSoup(html, 'lxml')
    films = []
    seen_slugs = set()
    
    # Try multiple selectors as Letterboxd may have changed their structure
    # Method 1: Elements with data-target-link containing film slug (2025+ structure)
    film_components = soup.select('[data-target-link*="/film/"]')
    
    # Method 2: React component with LazyPoster
    if not film_components:
        film_components = soup.select('div.react-component[data-component-class="LazyPoster"]')
    
    # Method 3: Alternative selector for film posters
    if not film_components:
        film_components = soup.select('li[data-film-slug]')
    
    # Method 4: Look for film links in the films list
    if not film_components:
        film_components = soup.select('div.film-poster, li.film-detail')
    
    # Method 5: Try finding any element with data-item-slug
    if not film_components:
        film_components = soup.select('[data-item-slug]')
    
    # Method 6: Look for poster images in list items
    if not film_components:
        film_components = soup.select('li img[alt^="Poster for"]')
    
    for component in film_components:
        item_name = ''
        slug = ''
        film_id = ''
        
        # Method 1: Extract from data-target-link attribute (2025+ structure)
        target_link = component.get('data-target-link', '')
        if target_link and '/film/' in target_link:
            slug_match = re.search(r'/film/([^/]+)/?', target_link)
            if slug_match:
                slug = slug_match.group(1)
                film_id = component.get('data-film-id', '')
        
        # Check if this is a poster img element (Method 6)
        elif component.name == 'img' and component.get('alt', '').startswith('Poster for'):
            # Extract title and year from alt text: "Poster for Film Name (Year)"
            alt_text = component.get('alt', '')
            item_name = alt_text.replace('Poster for ', '')
            
            # Find the parent li and look for the film link
            parent_li = component.find_parent('li')
            if parent_li:
                film_link = parent_li.find('a', href=re.compile(r'/film/[^/]+/?$'))
                if film_link:
                    href = film_link.get('href', '')
                    slug_match = re.search(r'/film/([^/]+)/?$', href)
                    if slug_match:
                        slug = slug_match.group(1)
        else:
            # Original extraction logic for other methods
            item_name = (component.get('data-item-name', '') or 
                        component.get('data-film-name', '') or
                        component.get('title', ''))
            slug = (component.get('data-item-slug', '') or 
                   component.get('data-film-slug', ''))
            film_id = component.get('data-film-id', '')
            
            # If we still don't have a slug, try extracting from href or data-target-link
            if not slug:
                # Try data-target-link first
                target_link = component.get('data-target-link', '')
                if target_link:
                    slug_match = re.search(r'/film/([^/]+)/?', target_link)
                    if slug_match:
                        slug = slug_match.group(1)
                
                # Fall back to href
                if not slug:
                    link = component.find('a', href=re.compile(r'/film/'))
                    if link:
                        href = link.get('href', '')
                        slug_match = re.search(r'/film/([^/]+)/?', href)
                        if slug_match:
                            slug = slug_match.group(1)
                            if not item_name:
                                item_name = link.get_text(strip=True) or link.get('title', '')
        
        if not slug or slug in seen_slugs:
            continue
        
        seen_slugs.add(slug)
        
        # Parse title and year from item_name (e.g., "Wicked: For Good (2025)")
        title = item_name
        year = None
        
        # Extract year from the end of the title
        year_match = re.search(r'\((\d{4})\)$', item_name)
        if year_match:
            year = int(year_match.group(1))
            title = item_name[:year_match.start()].strip()
        
        # If we still don't have a title, use the slug
        if not title:
            title = slug.replace('-', ' ').title()
        
        # Find the rating - look in different places depending on structure
        user_rating = None
        
        # For img-based components, find the parent li and look for rating
        if component.name == 'img':
            parent_li = component.find_parent('li')
            if parent_li:
                # Look for rating in paragraph following the poster
                rating_p = parent_li.find('p')
                if rating_p:
                    # Count star characters (★ = full star, ½ = half star)
                    rating_text = rating_p.get_text()
                    full_stars = rating_text.count('★')
                    half_stars = rating_text.count('½')
                    if full_stars > 0 or half_stars > 0:
                        user_rating = full_stars + (0.5 if half_stars else 0)
        else:
            # Original rating extraction
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
    
    # Debug: Log if no films found but HTML seems valid
    if not films and html and not is_cloudflare_challenge(html):
        # Check if this looks like a valid profile page
        if 'letterboxd' in html.lower() and ('films' in html.lower() or 'watched' in html.lower()):
            print(f"⚠️  Warning: No films found but page appears valid. HTML length: {len(html)}")
            # Try to find any film links as last resort
            all_film_links = soup.select('a[href*="/film/"]')
            if all_film_links:
                print(f"   Found {len(all_film_links)} potential film links, trying to extract...")
                for link in all_film_links[:100]:  # Increased limit
                    href = link.get('href', '')
                    # Only match direct film links, not user film pages
                    slug_match = re.search(r'^/film/([^/]+)/?$', href)
                    if slug_match:
                        slug = slug_match.group(1)
                        if slug not in seen_slugs:
                            seen_slugs.add(slug)
                            title_text = link.get_text(strip=True) or link.get('title', '') or slug.replace('-', ' ').title()
                            year = None
                            year_match = re.search(r'\((\d{4})\)', title_text)
                            if year_match:
                                year = int(year_match.group(1))
                                title_text = re.sub(r'\s*\(\d{4}\)\s*', '', title_text).strip()
                            
                            if not title_text:
                                title_text = slug.replace('-', ' ').title()
                            
                            films.append({
                                'title': title_text,
                                'year': year,
                                'slug': slug,
                                'letterboxd_id': '',
                                'letterboxd_url': f"https://letterboxd.com/film/{slug}/",
                                'user_rating': None
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
