"""
Letterboxd scraper using web scraping techniques.
Now fetches watch counts from the CSI stats endpoint.
Saves films to database for future use.
"""

import asyncio
import aiohttp
import random
from bs4 import BeautifulSoup
import re
import os
from database import save_films, get_films_by_slugs
from aiohttp import ClientTimeout

# Import curl_cffi for browser-fingerprinted requests (defeats Cloudflare TLS/JA3 fingerprinting).
# This replaces cloudscraper, which is effectively obsolete against modern Cloudflare (2026).
try:
    from curl_cffi import requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
    print("✅ curl_cffi is available for browser-fingerprinted requests")
except ImportError:
    CURL_CFFI_AVAILABLE = False
    cffi_requests = None
    print("⚠️  curl_cffi not available - will use aiohttp (likely blocked by Cloudflare)")

# Browser profiles to rotate through on retries. curl_cffi sets a matching TLS + HTTP/2
# fingerprint AND browser headers for each, so we intentionally do NOT override headers.
IMPERSONATE_PROFILES = ["chrome", "chrome131", "safari", "chrome124"]

# Import TMDb functions for poster fetching
try:
    from tmdb import search_film, TMDB_API_KEY
    TMDB_AVAILABLE = True
except:
    TMDB_AVAILABLE = False
    TMDB_API_KEY = None

# Import xml parser for RSS
import xml.etree.ElementTree as ET

DATA_SOURCE_MARKER = "_obscuriboxd_data_source"


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
    blocked_mid_pagination = False  # Track if we got blocked after already collecting some films
    
    # Create session with timeout to prevent hanging
    timeout = ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            url = f"https://letterboxd.com/{username}/films/page/{page}/"
            
            try:
                # Fetch via curl_cffi browser impersonation (falls back to RSS below if blocked)
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
                    print(f"⚠️  Cloudflare challenge on page {page}, returning {len(films)} films collected so far (partial)")
                    blocked_mid_pagination = True
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
                # A 404 on page 1 means the user does not exist - surface it clearly.
                if ("404" in error_msg or "Not Found" in error_msg) and page == 1 and not films:
                    raise Exception(f"User '{username}' not found on Letterboxd.")
                # Check if Cloudflare is blocking
                if "CLOUDFLARE_BLOCKED" in error_msg or "403" in error_msg:
                    if page == 1 and not used_rss_fallback:
                        # Nothing collected yet - try the (unprotected) RSS feed as a fallback.
                        print(f"🔄 Cloudflare blocking detected, trying RSS feed as fallback...")
                        try:
                            rss_films = await get_user_films_from_rss(username)
                            if rss_films:
                                print(f"✅ RSS fallback successful! Found {len(rss_films)} films")
                                films = rss_films
                                used_rss_fallback = True
                                break  # Exit the while loop
                        except Exception as rss_error:
                            rss_msg = str(rss_error)
                            print(f"⚠️  RSS fallback also failed: {rss_msg}")
                            if "not found" in rss_msg.lower():
                                raise Exception(f"User '{username}' not found on Letterboxd.")
                    elif films:
                        # We already have films from earlier pages - return them as partial data
                        # instead of failing the whole request.
                        print(f"⚠️  Blocked on page {page}, returning {len(films)} films collected so far (partial)")
                        blocked_mid_pagination = True
                        break
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
    
    # DB-only enrichment: watch counts and film metadata come entirely from our
    # precomputed local database (built offline via populate_local.py). We do NOT scrape
    # individual film stats live on the server - that is what kept getting Cloudflare-blocked.
    #
    # Films that are NOT in our DB are, by construction (the DB holds the most-watched films),
    # almost certainly obscure. We assign them a low default watch count so they are correctly
    # reflected as obscure in the median-based score instead of being dropped.
    DEFAULT_OBSCURE_WATCHES = int(os.getenv("DEFAULT_OBSCURE_WATCHES", "2000"))

    enriched_films = []
    from_db_count = 0
    missing_count = 0

    for film in films:
        slug = film.get('slug')
        if slug and slug in db_films:
            # Film exists in database - use DB data but keep the user's own rating.
            db_film = db_films[slug]
            film.update({k: v for k, v in db_film.items() if k != 'user_rating'})
            from_db_count += 1
        else:
            # Not in our precomputed DB -> treat as obscure.
            if film.get('letterboxd_watches') is None:
                film['letterboxd_watches'] = DEFAULT_OBSCURE_WATCHES
            missing_count += 1
        enriched_films.append(film)

    print(f"📊 Database lookup: {from_db_count} from DB, {missing_count} not in DB (treated as obscure, default {DEFAULT_OBSCURE_WATCHES} watches)")

    # Tag the data source so the API can tell the frontend whether this was a full analysis,
    # a partial one (some pages blocked), or an RSS-only fallback (recent films only).
    if used_rss_fallback:
        data_source = "rss_fallback"
    elif blocked_mid_pagination:
        data_source = "partial_scrape"
    else:
        data_source = "full_scrape"

    if data_source != "full_scrape":
        for film in enriched_films:
            film[DATA_SOURCE_MARKER] = data_source

    return enriched_films


async def enrich_with_letterboxd_stats(films: list[dict]) -> list[dict]:
    """
    Fetch Letterboxd watch counts from the stats CSI endpoint.
    Fetches for ALL films to ensure complete data.
    Uses smaller batches and better error handling for large collections.
    """
    if not films:
        return films
    
    # Gentle concurrency: each film does 2 requests (stats + main page), so batch_size N
    # means ~2N concurrent curl_cffi requests. Keep this modest to stay under Letterboxd's
    # rate limits during large offline builds (better a slower job than a blocked one).
    batch_size = int(os.getenv("ENRICH_BATCH_SIZE", "15"))
    delay = float(os.getenv("ENRICH_DELAY", "0.3"))
    
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
            
            # Use curl_cffi browser impersonation to defeat Cloudflare fingerprinting.
            if CURL_CFFI_AVAILABLE:
                profile = IMPERSONATE_PROFILES[attempt % len(IMPERSONATE_PROFILES)]

                async def fetch_cffi(u):
                    try:
                        async with cffi_requests.AsyncSession() as s:
                            resp = await s.get(u, impersonate=profile, timeout=15, allow_redirects=True)
                        if resp.status_code == 200:
                            return resp.text
                        return ""
                    except Exception:
                        return ""

                stats_html, main_html = await asyncio.gather(
                    fetch_cffi(stats_url),
                    fetch_cffi(main_url),
                    return_exceptions=True,
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


async def fetch_with_scrapingbee(url: str, headers: dict | None = None) -> str | None:
    """Try fetching with ScrapingBee. Returns HTML on success, None otherwise."""
    api_key = os.getenv("SCRAPINGBEE_API_KEY")
    if not api_key:
        return None

    params = {
        "api_key": api_key,
        "url": url,
        "premium_proxy": "true",
        "country_code": os.getenv("SCRAPINGBEE_COUNTRY", "us"),
        "render_js": os.getenv("SCRAPINGBEE_RENDER_JS", "false"),
    }
    timeout = ClientTimeout(total=45, connect=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://app.scrapingbee.com/api/v1/", params=params, headers=headers) as response:
                if response.status != 200:
                    print(f"   ⚠️ ScrapingBee failed: HTTP {response.status}")
                    return None

                html = await response.text()
                if not html:
                    print("   ⚠️ ScrapingBee returned empty response")
                    return None
                if is_cloudflare_challenge(html):
                    print("   ⚠️ ScrapingBee response still looks like Cloudflare challenge")
                    return None

                print(f"✅ Successfully fetched {url} via ScrapingBee (length: {len(html)})")
                return html
    except Exception as e:
        print(f"   ⚠️ ScrapingBee error: {e}")
        return None


async def fetch_with_zenrows(url: str, headers: dict | None = None) -> str | None:
    """Try fetching with ZenRows. Returns HTML on success, None otherwise."""
    api_key = os.getenv("ZENROWS_API_KEY")
    if not api_key:
        return None

    params = {
        "apikey": api_key,
        "url": url,
        "premium_proxy": "true",
        "js_render": os.getenv("ZENROWS_JS_RENDER", "true"),
    }
    timeout = ClientTimeout(total=45, connect=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://api.zenrows.com/v1/", params=params, headers=headers) as response:
                if response.status != 200:
                    print(f"   ⚠️ ZenRows failed: HTTP {response.status}")
                    return None

                html = await response.text()
                if not html:
                    print("   ⚠️ ZenRows returned empty response")
                    return None
                if is_cloudflare_challenge(html):
                    print("   ⚠️ ZenRows response still looks like Cloudflare challenge")
                    return None

                print(f"✅ Successfully fetched {url} via ZenRows (length: {len(html)})")
                return html
    except Exception as e:
        print(f"   ⚠️ ZenRows error: {e}")
        return None


async def fetch_with_managed_scraper(url: str, headers: dict | None = None) -> str | None:
    """
    Try a managed scraper provider for Cloudflare-blocked requests.
    Supported providers:
    - SCRAPINGBEE_API_KEY (+ optional SCRAPER_PROVIDER=scrapingbee)
    - ZENROWS_API_KEY (+ optional SCRAPER_PROVIDER=zenrows)
    """
    provider = os.getenv("SCRAPER_PROVIDER", "").strip().lower()

    if provider and provider not in {"scrapingbee", "zenrows"}:
        print(f"   ⚠️ Unknown SCRAPER_PROVIDER='{provider}', skipping managed scraper fallback")
        return None

    if provider in {"", "scrapingbee"}:
        html = await fetch_with_scrapingbee(url, headers)
        if html:
            return html

    if provider in {"", "zenrows"}:
        html = await fetch_with_zenrows(url, headers)
        if html:
            return html

    return None


async def _fetch_curl_cffi(url: str, retries: int = 3) -> str:
    """
    Fetch a URL using curl_cffi with browser impersonation.

    Rotates through browser profiles and backs off on Cloudflare 403/challenge.
    Returns HTML text on success.
    Raises Exception('404 Not Found...') for missing users/pages (do not retry).
    Raises Exception('CLOUDFLARE_BLOCKED...') after exhausting retries.
    """
    last_error = "CLOUDFLARE_BLOCKED: 403 Forbidden"

    for attempt in range(retries):
        profile = IMPERSONATE_PROFILES[attempt % len(IMPERSONATE_PROFILES)]
        try:
            # Let the impersonation profile own the headers so the TLS fingerprint and
            # the User-Agent/Sec-* headers stay consistent (mismatches are an instant block).
            async with cffi_requests.AsyncSession() as session:
                resp = await session.get(
                    url,
                    impersonate=profile,
                    timeout=30,
                    allow_redirects=True,
                )
            status = resp.status_code

            if status == 404:
                raise Exception("404 Not Found: User or page does not exist")

            if status == 403:
                last_error = "CLOUDFLARE_BLOCKED: 403 Forbidden"
                print(f"   🛡️ curl_cffi got 403 for {url} (profile={profile}, attempt {attempt + 1}/{retries})")
                await asyncio.sleep(0.5 * (attempt + 1) + random.random() * 0.5)
                continue

            if status != 200:
                last_error = f"HTTP {status} error"
                await asyncio.sleep(0.3 * (attempt + 1))
                continue

            html = resp.text
            if not html:
                last_error = "Empty response received"
                await asyncio.sleep(0.3 * (attempt + 1))
                continue

            if is_cloudflare_challenge(html):
                last_error = "CLOUDFLARE_BLOCKED: challenge page"
                print(f"   🛡️ curl_cffi got a Cloudflare challenge for {url} (profile={profile})")
                await asyncio.sleep(0.5 * (attempt + 1) + random.random() * 0.5)
                continue

            return html
        except Exception as e:
            error_msg = str(e)
            # 404 is definitive - do not retry or fall back.
            if "404" in error_msg or "Not Found" in error_msg:
                raise
            last_error = error_msg
            print(f"   ⚠️ curl_cffi error for {url} (profile={profile}): {error_msg}")
            await asyncio.sleep(0.3 * (attempt + 1))

    raise Exception(last_error)


async def fetch_with_cloudflare_bypass(url: str, headers: dict = None) -> str:
    """
    Fetch a URL, defeating Cloudflare fingerprinting via curl_cffi browser impersonation.

    Order: curl_cffi (primary) -> managed scraper API (if configured) -> plain aiohttp (last resort).
    """
    request_headers = headers or get_headers()

    print(f"🌐 Attempting to fetch: {url}")

    # 1. curl_cffi browser impersonation (primary)
    if CURL_CFFI_AVAILABLE:
        try:
            html = await _fetch_curl_cffi(url)
            print(f"✅ Successfully fetched {url} via curl_cffi (length: {len(html)})")
            return html
        except Exception as e:
            error_msg = str(e)
            # 404 is definitive - propagate so callers can surface "user not found".
            if "404" in error_msg or "Not Found" in error_msg:
                raise
            print(f"⚠️  curl_cffi failed for {url}: {error_msg}")

            # 2. Managed scraper API fallback (env-gated, off by default)
            managed_html = await fetch_with_managed_scraper(url, request_headers)
            if managed_html:
                return managed_html
            print(f"   Falling back to aiohttp...")

    # 3. Plain aiohttp (last resort - usually blocked on datacenter IPs, but free to try)
    timeout = ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=request_headers) as response:
            if response.status == 404:
                raise Exception("404 Not Found: User or page does not exist")
            if response.status != 200:
                error_text = await response.text()
                if response.status == 403:
                    print(f"   🛡️ aiohttp also received 403 for {url}")
                    managed_html = await fetch_with_managed_scraper(url, request_headers)
                    if managed_html:
                        return managed_html
                    raise Exception("CLOUDFLARE_BLOCKED: 403 Forbidden")
                raise Exception(f"HTTP {response.status} error: {response.reason}. Response: {error_text[:200]}")
            html = await response.text()
            if is_cloudflare_challenge(html):
                print(f"   🛡️ aiohttp returned Cloudflare challenge page")
                managed_html = await fetch_with_managed_scraper(url, request_headers)
                if managed_html:
                    return managed_html
                raise Exception("CLOUDFLARE_BLOCKED: challenge page")
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


def parse_popular_slugs(html: str) -> list[str]:
    """
    Parse film slugs from the popular-films CSI list endpoint
    (/csi/films/films-browser-list/popular/page/N/). Returns slugs in popularity order.
    """
    soup = BeautifulSoup(html, 'lxml')
    slugs = []
    seen = set()

    # Poster components expose the slug via data attributes or a /film/<slug>/ target link.
    for el in soup.select('[data-film-slug], [data-item-slug], [data-target-link]'):
        slug = el.get('data-film-slug') or el.get('data-item-slug') or ''
        if not slug:
            target = el.get('data-target-link', '')
            m = re.search(r'/film/([^/]+)/', target)
            if m:
                slug = m.group(1)
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    # Fallback: pull slugs from any /film/<slug>/ links in the markup.
    if not slugs:
        for slug in re.findall(r'/film/([a-z0-9:.-]+)/', html):
            if slug not in seen:
                seen.add(slug)
                slugs.append(slug)

    return slugs


async def get_popular_film_slugs(pages: int, delay: float = 0.3) -> list[str]:
    """
    Fetch slugs of the most-watched films from Letterboxd's popular list.

    Uses the CSI list endpoint (72 films/page) which is what /films/popular/ lazy-loads.
    Intended to be run offline (locally) to build the watch-count database.
    """
    all_slugs = []
    seen = set()

    for page in range(1, pages + 1):
        url = f"https://letterboxd.com/csi/films/films-browser-list/popular/page/{page}/?esiAllowFilters=true"
        try:
            print(f"📡 Fetching popular page {page}/{pages}...")
            html = await fetch_with_cloudflare_bypass(url)
        except Exception as e:
            print(f"   ⚠️ Failed to fetch popular page {page}: {e}")
            break

        page_slugs = parse_popular_slugs(html)
        if not page_slugs:
            print(f"   ⚠️ No slugs on page {page}, stopping (reached the end or blocked).")
            break

        new = [s for s in page_slugs if s not in seen]
        for s in new:
            seen.add(s)
        all_slugs.extend(new)
        print(f"   Found {len(page_slugs)} films ({len(all_slugs)} unique total)")

        await asyncio.sleep(delay)

    return all_slugs


# Keep old function names for compatibility
async def get_film_letterboxd_stats(session: aiohttp.ClientSession, film: dict) -> dict:
    """Alias for get_film_stats for backward compatibility."""
    return await get_film_stats(session, film)


async def get_film_details(slug: str) -> dict:
    """Get detailed information about a specific film."""
    async with aiohttp.ClientSession() as session:
        return await get_film_stats(session, {'slug': slug})
