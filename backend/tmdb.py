"""
TMDb API integration for enriching film data with popularity scores and metadata.
"""

import os
import asyncio
import aiohttp
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"


async def enrich_films_with_tmdb(films: list[dict]) -> list[dict]:
    """
    Enrich film list with TMDb data including popularity, genres, etc.
    """
    if not TMDB_API_KEY:
        print("Warning: TMDB_API_KEY not set. Using basic data only.")
        return films
    
    async with aiohttp.ClientSession() as session:
        # Process films in larger batches for speed
        batch_size = 20  # Increased batch size
        enriched = []
        
        for i in range(0, len(films), batch_size):
            batch = films[i:i + batch_size]
            tasks = [enrich_single_film(session, film) for film in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for film, result in zip(batch, results):
                if isinstance(result, Exception):
                    enriched.append(film)
                else:
                    enriched.append(result)
            
            # Reduced rate limiting for speed
            if i + batch_size < len(films):  # Don't sleep after last batch
                await asyncio.sleep(0.1)
        
        return enriched


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
            if letterboxd_director:
                best_match = None
                best_score = 0
                
                # First, score results based on title and year without API calls
                scored_results = []
                for result in results[:10]:  # Check top 10 results
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
                
                # Now check directors for top 2 candidates only (to reduce API calls)
                director_matched = False
                for result, initial_score in scored_results[:2]:
                    score = initial_score
                    
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
                            
                            # Check if director matches - this is REQUIRED when we have director info
                            if directors:
                                # Normalize director names for comparison
                                letterboxd_dir_normalized = letterboxd_director.lower().strip()
                                for tmdb_dir in directors:
                                    tmdb_dir_normalized = tmdb_dir.lower().strip()
                                    # Exact match - REQUIRED
                                    if letterboxd_dir_normalized == tmdb_dir_normalized:
                                        score += 50  # High weight for director match
                                        director_matched = True
                                        break
                                    # Partial match (handles name variations like "Lee Chang Dong" vs "Lee Chang-dong")
                                    # Only accept if names are very similar (one contains the other and length is close)
                                    if (letterboxd_dir_normalized in tmdb_dir_normalized or 
                                        tmdb_dir_normalized in letterboxd_dir_normalized):
                                        # Check if lengths are similar (within 30% difference)
                                        len_diff = abs(len(letterboxd_dir_normalized) - len(tmdb_dir_normalized))
                                        max_len = max(len(letterboxd_dir_normalized), len(tmdb_dir_normalized))
                                        if max_len > 0 and (len_diff / max_len) < 0.3:
                                            score += 30
                                            director_matched = True
                                            break
                            
                            # Also require exact year match when we have year info
                            if year:
                                release_date = details.get('release_date', '')
                                if release_date:
                                    try:
                                        result_year = int(release_date.split('-')[0])
                                        if result_year != year:
                                            # Year mismatch - heavily penalize
                                            score -= 30
                                    except (ValueError, IndexError):
                                        pass
                        
                        # Small delay to avoid rate limiting (reduced for speed)
                        await asyncio.sleep(0.05)
                    
                    if score > best_score:
                        best_score = score
                        best_match = result
                
                # Only return if director matched AND we have a good overall score
                # This prevents matching to wrong films with same title/year
                if best_match and director_matched and best_score >= 30:
                    return best_match
                # If no director match found, return None to avoid wrong matches
                return None
            
            # No director info - require exact year match and exact title match
            if year:
                best_match = None
                best_score = 0
                
                for result in results[:10]:  # Check top 10 results
                    score = 0
                    result_title = result.get('title', '').lower().strip()
                    search_title = title.lower().strip()
                    
                    # Require exact title match (or very close)
                    if result_title == search_title:
                        score += 30
                    elif search_title in result_title or result_title in search_title:
                        # Only accept if the difference is small (e.g., "The Funeral" vs "Funeral")
                        title_diff = abs(len(result_title) - len(search_title))
                        if title_diff <= 5:  # Allow small differences like "The" prefix
                            score += 15
                        else:
                            continue  # Skip if titles are too different
                    else:
                        continue  # Skip if title doesn't match
                    
                    # Require exact year match (no tolerance)
                    release_date = result.get('release_date', '')
                    if release_date:
                        try:
                            result_year = int(release_date.split('-')[0])
                            if result_year == year:
                                score += 30
                            else:
                                continue  # Skip if year doesn't match exactly
                        except (ValueError, IndexError):
                            continue  # Skip if we can't parse year
                    else:
                        continue  # Skip if no release date
                    
                    if score > best_score:
                        best_score = score
                        best_match = result
                
                # Only return if we have exact title + exact year match
                if best_match and best_score >= 30:
                    return best_match
                # Return None if no exact match - better than wrong match
                return None
            
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





