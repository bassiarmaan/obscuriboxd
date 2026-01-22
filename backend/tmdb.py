"""
TMDb API integration for enriching film data with popularity scores and metadata.
Now checks database first to avoid redundant API calls.
"""

import os
import asyncio
import aiohttp
from typing import Optional
from dotenv import load_dotenv
from database import get_films_by_slugs, save_film

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"


async def enrich_films_with_tmdb(films: list[dict]) -> list[dict]:
    """
    Enrich film list with TMDb data including popularity, genres, etc.
    Checks database first to avoid redundant API calls.
    """
    if not TMDB_API_KEY:
        print("Warning: TMDB_API_KEY not set. Using basic data only.")
        return films
    
    # First, check database for existing films
    slugs = [f.get('slug') for f in films if f.get('slug')]
    db_films = get_films_by_slugs(slugs)
    
    # Separate films into those we have in DB and those we need to fetch
    films_to_enrich = []
    enriched_from_db = []
    
    for film in films:
        slug = film.get('slug')
        if slug and slug in db_films:
            # Film exists in database - merge DB data with film data
            db_film = db_films[slug]
            # Preserve user-specific data (rating) but use DB data for metadata
            film.update({k: v for k, v in db_film.items() if k not in ['user_rating']})
            enriched_from_db.append(film)
        else:
            # Film not in DB or missing slug - need to fetch
            films_to_enrich.append(film)
    
    if not films_to_enrich:
        # All films found in database!
        return enriched_from_db
    
    # Enrich remaining films via API
    async with aiohttp.ClientSession() as session:
        # Process films in batches - adjust batch size based on total films
        total_films = len(films_to_enrich)
        if total_films > 500:
            batch_size = 15  # Larger batches for big collections
            delay = 0.2  # Shorter delay
        elif total_films > 200:
            batch_size = 10
            delay = 0.3
        else:
            batch_size = 5  # Smaller batches for normal collections
            delay = 0.5
        
        enriched = []
        
        for i in range(0, len(films_to_enrich), batch_size):
            batch = films_to_enrich[i:i + batch_size]
            tasks = [enrich_single_film(session, film) for film in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for film, result in zip(batch, results):
                if isinstance(result, Exception):
                    enriched.append(film)
                else:
                    enriched.append(result)
                    # Save to database for future use
                    save_film(result)
            
            # Rate limiting
            if i + batch_size < len(films_to_enrich):  # Don't sleep after last batch
                await asyncio.sleep(delay)
        
    # Combine films from DB and newly enriched films
    return enriched_from_db + enriched


async def enrich_single_film(session: aiohttp.ClientSession, film: dict) -> dict:
    """
    Enrich a single film with TMDb data.
    """
    title = film.get('title', '')
    year = film.get('year')
    letterboxd_director = film.get('director', '').strip()  # Director from Letterboxd
    
    # Search for the film on TMDb with better matching
    tmdb_data = await search_film(session, title, year, letterboxd_director)
    
    if tmdb_data:
        film['tmdb_id'] = tmdb_data.get('id')
        film['popularity'] = tmdb_data.get('popularity', 0)
        film['vote_count'] = tmdb_data.get('vote_count', 0)
        film['vote_average'] = tmdb_data.get('vote_average', 0)
        film['genre_ids'] = tmdb_data.get('genre_ids', [])
        film['original_language'] = tmdb_data.get('original_language', '')
        film['poster_path'] = tmdb_data.get('poster_path', '')
        
        # Get full film details for more info
        if film['tmdb_id']:
            details = await get_film_details(session, film['tmdb_id'])
            if details:
                film['genres'] = [g['name'] for g in details.get('genres', [])]
                film['production_countries'] = [
                    c['name'] for c in details.get('production_countries', [])
                ]
                film['runtime'] = details.get('runtime')
                film['budget'] = details.get('budget', 0)
                film['revenue'] = details.get('revenue', 0)
                
                # Get director from credits
                credits = details.get('credits', {})
                crew = credits.get('crew', [])
                directors = [c['name'] for c in crew if c.get('job') == 'Director']
                if directors:
                    film['director'] = directors[0]
                    film['directors'] = directors
    else:
        # Set defaults if TMDb lookup fails
        film['popularity'] = None
        film['genres'] = []
        film['production_countries'] = []
    
    return film


async def search_film(
    session: aiohttp.ClientSession, 
    title: str, 
    year: Optional[int] = None,
    letterboxd_director: Optional[str] = None
) -> Optional[dict]:
    """
    Search for a film on TMDb with improved matching.
    Validates matches using year and director when available.
    """
    params = {
        'api_key': TMDB_API_KEY,
        'query': title,
        'include_adult': 'false'
    }
    
    if year:
        params['year'] = str(year)
    
    url = f"{TMDB_BASE_URL}/search/movie"
    
    try:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return None
            
            data = await response.json()
            results = data.get('results', [])
            
            if not results and year:
                # Try without year if no results
                params.pop('year', None)
                async with session.get(url, params=params) as retry_response:
                    if retry_response.status == 200:
                        retry_data = await retry_response.json()
                        results = retry_data.get('results', [])
            
            if not results:
                return None
            
            # If we have director info from Letterboxd, validate matches
            # But only check director for top 1 candidate to reduce API calls
            if letterboxd_director:
                best_match = None
                best_score = 0
                
                # First, score results based on title and year without API calls
                scored_results = []
                for result in results[:5]:  # Check top 5 results (reduced from 10)
                    score = 0
                    result_year = None
                    
                    # Check title similarity (normalize for comparison)
                    result_title = result.get('title', '').lower().strip()
                    search_title = title.lower().strip()
                    if result_title == search_title:
                        score += 20
                    elif search_title in result_title or result_title in search_title:
                        score += 10
                    
                    # Check year match
                    release_date = result.get('release_date', '')
                    if release_date:
                        try:
                            result_year = int(release_date.split('-')[0])
                            if year and result_year == year:
                                score += 20
                            elif year and abs(result_year - year) <= 1:  # Allow 1 year difference
                                score += 10
                        except (ValueError, IndexError):
                            pass
                    
                    scored_results.append((result, score))
                
                # Sort by initial score (title + year)
                scored_results.sort(key=lambda x: x[1], reverse=True)
                
                # Only check director for top 1 candidate to minimize API calls
                best_initial_score = 0
                for result, initial_score in scored_results[:1]:
                    score = initial_score
                    best_initial_score = initial_score  # Track the initial score
                    
                    # Get director from TMDb to validate
                    tmdb_id = result.get('id')
                    if tmdb_id:
                        details = await get_film_details(session, tmdb_id)
                        if details:
                            # Skip if it's a TV show (check media_type or genres)
                            media_type = details.get('media_type')
                            if media_type == 'tv':
                                continue
                            
                            credits = details.get('credits', {})
                            crew = credits.get('crew', [])
                            directors = [c['name'] for c in crew if c.get('job') == 'Director']
                            
                            # Check if director matches
                            if directors:
                                # Normalize director names for comparison
                                letterboxd_dir_normalized = letterboxd_director.lower().strip()
                                for tmdb_dir in directors:
                                    tmdb_dir_normalized = tmdb_dir.lower().strip()
                                    # Exact match
                                    if letterboxd_dir_normalized == tmdb_dir_normalized:
                                        score += 30
                                        break
                                    # Partial match (handles name variations like "Lee Chang Dong" vs "Lee Chang-dong")
                                    if (letterboxd_dir_normalized in tmdb_dir_normalized or 
                                        tmdb_dir_normalized in letterboxd_dir_normalized):
                                        score += 15
                            
                            # If director didn't match but we have good title+year match, check popularity
                            # For popular films, be more lenient - accept title+year match even without director
                            if score == initial_score and initial_score >= 30:  # Good title+year but no director match
                                pop = details.get('popularity', 0)
                                votes = details.get('vote_count', 0)
                                # If film has significant popularity or votes, accept the match
                                # Popular films are less likely to have wrong matches
                                if pop > 10 or votes > 500:
                                    score += 20  # Boost score to accept it
                        
                        # Small delay to avoid rate limiting (reduced for speed)
                        await asyncio.sleep(0.1)
                    
                    if score > best_score:
                        best_score = score
                        best_match = result
                
                # Only return if we found a good match (score >= 20, meaning at least title+year or director match)
                if best_match and best_score >= 20:
                    return best_match
                
                # If no good match found, return None to avoid wrong matches
                return None
            
            # No director info - prioritize exact year matches and title similarity
            if year:
                best_match = None
                best_score = 0
                
                for result in results[:5]:  # Check top 5 results
                    score = 0
                    result_title = result.get('title', '').lower().strip()
                    search_title = title.lower().strip()
                    
                    # Title match
                    if result_title == search_title:
                        score += 20
                    elif search_title in result_title or result_title in search_title:
                        score += 10
                    
                    # Year match
                    release_date = result.get('release_date', '')
                    if release_date:
                        try:
                            result_year = int(release_date.split('-')[0])
                            if result_year == year:
                                score += 20
                            elif abs(result_year - year) <= 1:
                                score += 10
                        except (ValueError, IndexError):
                            pass
                    
                    if score > best_score:
                        best_score = score
                        best_match = result
                
                # Only return if we have a reasonable match (score >= 20)
                if best_match and best_score >= 20:
                    return best_match
                # Fallback to first result if no good match
                return results[0] if results else None
            
            # No year specified - prioritize exact title matches
            for result in results[:5]:
                result_title = result.get('title', '').lower().strip()
                search_title = title.lower().strip()
                if result_title == search_title:
                    return result
            
            # Fallback to first result
            return results[0]
            
    except Exception as e:
        print(f"Error searching TMDb for '{title}': {e}")
        return None


async def get_film_details(session: aiohttp.ClientSession, tmdb_id: int) -> Optional[dict]:
    """
    Get detailed film information from TMDb.
    """
    url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {
        'api_key': TMDB_API_KEY,
        'append_to_response': 'credits'
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return None
            
            return await response.json()
            
    except Exception:
        return None


# TMDb genre mapping
GENRE_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Science Fiction",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western"
}


def get_genre_name(genre_id: int) -> str:
    """Convert TMDb genre ID to name."""
    return GENRE_MAP.get(genre_id, "Unknown")





