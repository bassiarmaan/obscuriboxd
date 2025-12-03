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
        # Process films in batches to avoid rate limiting
        batch_size = 10
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
            
            # Rate limiting
            await asyncio.sleep(0.25)
        
        return enriched


async def enrich_single_film(session: aiohttp.ClientSession, film: dict) -> dict:
    """
    Enrich a single film with TMDb data.
    """
    title = film.get('title', '')
    year = film.get('year')
    
    # Search for the film on TMDb
    tmdb_data = await search_film(session, title, year)
    
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
    year: Optional[int] = None
) -> Optional[dict]:
    """
    Search for a film on TMDb.
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
            
            if not results:
                # Try without year if no results
                if year:
                    params.pop('year', None)
                    async with session.get(url, params=params) as retry_response:
                        if retry_response.status == 200:
                            retry_data = await retry_response.json()
                            results = retry_data.get('results', [])
            
            if results:
                # Return the best match (first result)
                return results[0]
            
            return None
            
    except Exception:
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


