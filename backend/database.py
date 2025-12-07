"""
Database module for storing film metadata.
Uses SQLite for simplicity (can be upgraded to PostgreSQL for production).
"""

import sqlite3
import json
from typing import Optional, List, Dict
from contextlib import contextmanager
import os
from pathlib import Path

# Database file paths
# Primary database for new scrapes
_default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "films.db")
DB_PATH = os.getenv("DB_PATH", _default_db_path)

# Complete database with all films (read-only, checked first)
_complete_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "films_complete.db")
COMPLETE_DB_PATH = os.getenv("COMPLETE_DB_PATH", _complete_db_path)


def get_db_path() -> str:
    """Get the primary database file path."""
    return DB_PATH


def get_complete_db_path() -> str:
    """Get the complete database file path."""
    return COMPLETE_DB_PATH


def complete_db_exists() -> bool:
    """Check if the complete database exists."""
    return os.path.exists(COMPLETE_DB_PATH)


@contextmanager
def get_db_connection(db_path: str = None):
    """Context manager for database connections."""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_complete_db_connection():
    """Context manager for complete database connections (read-only)."""
    if not complete_db_exists():
        yield None
        return
    conn = sqlite3.connect(COMPLETE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize the database with required tables."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Films table - stores all film metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS films (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                letterboxd_slug TEXT UNIQUE NOT NULL,
                letterboxd_id TEXT,
                title TEXT NOT NULL,
                year INTEGER,
                tmdb_id INTEGER,
                
                -- Letterboxd data
                letterboxd_watches INTEGER,
                letterboxd_likes INTEGER,
                letterboxd_lists INTEGER,
                letterboxd_rating REAL,
                
                -- TMDb data
                popularity REAL,
                vote_count INTEGER,
                vote_average REAL,
                poster_path TEXT,
                original_language TEXT,
                runtime INTEGER,
                budget INTEGER,
                revenue INTEGER,
                
                -- Metadata
                director TEXT,
                genres TEXT,  -- JSON array of genre names
                production_countries TEXT,  -- JSON array of country names
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Indexes for fast lookups
                UNIQUE(letterboxd_slug)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_letterboxd_slug ON films(letterboxd_slug)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tmdb_id ON films(tmdb_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_year ON films(title, year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_letterboxd_watches ON films(letterboxd_watches)")
        
        conn.commit()


def film_to_dict(row: sqlite3.Row) -> Dict:
    """Convert a database row to a film dictionary."""
    film = {
        'title': row['title'],
        'year': row['year'],
        'slug': row['letterboxd_slug'],
        'letterboxd_id': row['letterboxd_id'],
        'letterboxd_url': f"https://letterboxd.com/film/{row['letterboxd_slug']}/" if row['letterboxd_slug'] else None,
    }
    
    # Letterboxd data
    if row['letterboxd_watches'] is not None:
        film['letterboxd_watches'] = row['letterboxd_watches']
    if row['letterboxd_likes'] is not None:
        film['letterboxd_likes'] = row['letterboxd_likes']
    if row['letterboxd_lists'] is not None:
        film['letterboxd_lists'] = row['letterboxd_lists']
    if row['letterboxd_rating'] is not None:
        film['letterboxd_rating'] = row['letterboxd_rating']
    
    # TMDb data
    if row['tmdb_id'] is not None:
        film['tmdb_id'] = row['tmdb_id']
    if row['popularity'] is not None:
        film['popularity'] = row['popularity']
    if row['vote_count'] is not None:
        film['vote_count'] = row['vote_count']
    if row['vote_average'] is not None:
        film['vote_average'] = row['vote_average']
    if row['poster_path']:
        film['poster_path'] = row['poster_path']
    if row['original_language']:
        film['original_language'] = row['original_language']
    if row['runtime'] is not None:
        film['runtime'] = row['runtime']
    if row['budget'] is not None:
        film['budget'] = row['budget']
    if row['revenue'] is not None:
        film['revenue'] = row['revenue']
    
    # Metadata
    if row['director']:
        film['director'] = row['director']
    if row['genres']:
        try:
            film['genres'] = json.loads(row['genres'])
        except json.JSONDecodeError:
            film['genres'] = []
    else:
        film['genres'] = []
    
    if row['production_countries']:
        try:
            film['production_countries'] = json.loads(row['production_countries'])
        except json.JSONDecodeError:
            film['production_countries'] = []
    else:
        film['production_countries'] = []
    
    return film


def get_film_by_slug(slug: str) -> Optional[Dict]:
    """
    Get a film by its Letterboxd slug.
    Checks films_complete.db first, then films.db.
    """
    # First check complete database
    if complete_db_exists():
        with get_complete_db_connection() as conn:
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM films WHERE letterboxd_slug = ?", (slug,))
                row = cursor.fetchone()
                if row:
                    return film_to_dict(row)
    
    # Then check primary database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM films WHERE letterboxd_slug = ?", (slug,))
        row = cursor.fetchone()
        if row:
            return film_to_dict(row)
    
    return None


def get_films_by_slugs(slugs: List[str]) -> Dict[str, Dict]:
    """
    Get multiple films by their Letterboxd slugs. 
    Checks films_complete.db first, then films.db.
    Returns a dict mapping slug to film.
    """
    if not slugs:
        return {}
    
    result = {}
    remaining_slugs = set(slugs)
    
    # First, check the complete database (if it exists)
    if complete_db_exists():
        with get_complete_db_connection() as conn:
            if conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(remaining_slugs))
                cursor.execute(f"SELECT * FROM films WHERE letterboxd_slug IN ({placeholders})", list(remaining_slugs))
                rows = cursor.fetchall()
                for row in rows:
                    slug = row['letterboxd_slug']
                    result[slug] = film_to_dict(row)
                    remaining_slugs.discard(slug)
    
    # Then, check the primary database for any remaining films
    if remaining_slugs:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(remaining_slugs))
            cursor.execute(f"SELECT * FROM films WHERE letterboxd_slug IN ({placeholders})", list(remaining_slugs))
            rows = cursor.fetchall()
            for row in rows:
                slug = row['letterboxd_slug']
                result[slug] = film_to_dict(row)
    
    return result


def save_film(film: Dict) -> None:
    """Save or update a film in the database."""
    slug = film.get('slug') or film.get('letterboxd_slug')
    if not slug:
        return  # Can't save without a slug
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Prepare data
        genres_json = json.dumps(film.get('genres', []))
        countries_json = json.dumps(film.get('production_countries', []))
        
        # Check if film exists
        cursor.execute("SELECT id FROM films WHERE letterboxd_slug = ?", (slug,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing film - only update fields that are provided (not None)
            update_fields = []
            update_values = []
            
            if 'letterboxd_id' in film:
                update_fields.append('letterboxd_id = ?')
                update_values.append(film.get('letterboxd_id'))
            if 'title' in film and film.get('title'):
                update_fields.append('title = ?')
                update_values.append(film.get('title'))
            if 'year' in film and film.get('year') is not None:
                update_fields.append('year = ?')
                update_values.append(film.get('year'))
            if 'tmdb_id' in film:
                update_fields.append('tmdb_id = ?')
                update_values.append(film.get('tmdb_id'))
            if 'letterboxd_watches' in film and film.get('letterboxd_watches') is not None:
                update_fields.append('letterboxd_watches = ?')
                update_values.append(film.get('letterboxd_watches'))
            if 'letterboxd_likes' in film and film.get('letterboxd_likes') is not None:
                update_fields.append('letterboxd_likes = ?')
                update_values.append(film.get('letterboxd_likes'))
            if 'letterboxd_lists' in film and film.get('letterboxd_lists') is not None:
                update_fields.append('letterboxd_lists = ?')
                update_values.append(film.get('letterboxd_lists'))
            if 'letterboxd_rating' in film and film.get('letterboxd_rating') is not None:
                update_fields.append('letterboxd_rating = ?')
                update_values.append(film.get('letterboxd_rating'))
            if 'popularity' in film:
                update_fields.append('popularity = ?')
                update_values.append(film.get('popularity'))
            if 'vote_count' in film:
                update_fields.append('vote_count = ?')
                update_values.append(film.get('vote_count'))
            if 'vote_average' in film:
                update_fields.append('vote_average = ?')
                update_values.append(film.get('vote_average'))
            if 'poster_path' in film:
                update_fields.append('poster_path = ?')
                update_values.append(film.get('poster_path'))
            if 'original_language' in film:
                update_fields.append('original_language = ?')
                update_values.append(film.get('original_language'))
            if 'runtime' in film:
                update_fields.append('runtime = ?')
                update_values.append(film.get('runtime'))
            if 'budget' in film:
                update_fields.append('budget = ?')
                update_values.append(film.get('budget'))
            if 'revenue' in film:
                update_fields.append('revenue = ?')
                update_values.append(film.get('revenue'))
            if 'director' in film and film.get('director'):
                update_fields.append('director = ?')
                update_values.append(film.get('director'))
            if 'genres' in film:
                update_fields.append('genres = ?')
                update_values.append(genres_json)
            if 'production_countries' in film:
                update_fields.append('production_countries = ?')
                update_values.append(countries_json)
            
            # Always update the updated_at timestamp
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(slug)
            
            if update_fields:
                update_sql = f"UPDATE films SET {', '.join(update_fields)} WHERE letterboxd_slug = ?"
                cursor.execute(update_sql, update_values)
        else:
            # Insert new film
            cursor.execute("""
                INSERT INTO films (
                    letterboxd_slug, letterboxd_id, title, year, tmdb_id,
                    letterboxd_watches, letterboxd_likes, letterboxd_lists, letterboxd_rating,
                    popularity, vote_count, vote_average, poster_path, original_language,
                    runtime, budget, revenue, director, genres, production_countries
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                slug,
                film.get('letterboxd_id'),
                film.get('title'),
                film.get('year'),
                film.get('tmdb_id'),
                film.get('letterboxd_watches'),
                film.get('letterboxd_likes'),
                film.get('letterboxd_lists'),
                film.get('letterboxd_rating'),
                film.get('popularity'),
                film.get('vote_count'),
                film.get('vote_average'),
                film.get('poster_path'),
                film.get('original_language'),
                film.get('runtime'),
                film.get('budget'),
                film.get('revenue'),
                film.get('director'),
                genres_json,
                countries_json
            ))


def save_films(films: List[Dict]) -> None:
    """Save multiple films to the database."""
    for film in films:
        save_film(film)


def get_stats() -> Dict:
    """Get database statistics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM films")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as with_watches FROM films WHERE letterboxd_watches IS NOT NULL")
        with_watches = cursor.fetchone()['with_watches']
        
        cursor.execute("SELECT COUNT(*) as with_tmdb FROM films WHERE tmdb_id IS NOT NULL")
        with_tmdb = cursor.fetchone()['with_tmdb']
        
        return {
            'total_films': total,
            'films_with_watches': with_watches,
            'films_with_tmdb': with_tmdb
        }
