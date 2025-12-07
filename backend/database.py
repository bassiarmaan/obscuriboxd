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

# Database file path
# Defaults to backend/films_complete.db, but can be overridden with DB_PATH env variable
_default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "films_complete.db")
DB_PATH = os.getenv("DB_PATH", _default_db_path)


def get_db_path() -> str:
    """Get the database file path."""
    return DB_PATH


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize the database with required tables."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if films table exists and get its schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='films'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Get existing columns
            cursor.execute("PRAGMA table_info(films)")
            existing_columns = {row[1]: row for row in cursor.fetchall()}
        else:
            existing_columns = {}
        
        # Films table - stores all film metadata
        # Only create if it doesn't exist, or add missing columns if it does
        if not table_exists:
            cursor.execute("""
                CREATE TABLE films (
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
        else:
            # Table exists - check and add missing columns if needed
            required_columns = {
                'letterboxd_slug': 'TEXT UNIQUE NOT NULL',
                'letterboxd_id': 'TEXT',
                'title': 'TEXT NOT NULL',
                'year': 'INTEGER',
                'tmdb_id': 'INTEGER',
                'letterboxd_watches': 'INTEGER',
                'letterboxd_likes': 'INTEGER',
                'letterboxd_lists': 'INTEGER',
                'letterboxd_rating': 'REAL',
                'popularity': 'REAL',
                'vote_count': 'INTEGER',
                'vote_average': 'REAL',
                'poster_path': 'TEXT',
                'original_language': 'TEXT',
                'runtime': 'INTEGER',
                'budget': 'INTEGER',
                'revenue': 'INTEGER',
                'director': 'TEXT',
                'genres': 'TEXT',
                'production_countries': 'TEXT',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            }
            
            for col_name, col_def in required_columns.items():
                if col_name not in existing_columns:
                    try:
                        # SQLite doesn't support ALTER TABLE ADD COLUMN with constraints easily
                        # So we'll add without NOT NULL constraint if needed
                        safe_def = col_def.replace(' NOT NULL', '').replace(' UNIQUE', '')
                        cursor.execute(f"ALTER TABLE films ADD COLUMN {col_name} {safe_def}")
                    except sqlite3.OperationalError:
                        # Column might already exist or other issue - skip
                        pass
        
        # Create indexes for common queries (only if column exists)
        cursor.execute("PRAGMA table_info(films)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'letterboxd_slug' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_letterboxd_slug ON films(letterboxd_slug)")
        if 'tmdb_id' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tmdb_id ON films(tmdb_id)")
        if 'title' in columns and 'year' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_year ON films(title, year)")
        if 'letterboxd_watches' in columns:
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
    """Get a film by its Letterboxd slug."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM films WHERE letterboxd_slug = ?", (slug,))
        row = cursor.fetchone()
        if row:
            return film_to_dict(row)
    return None


def get_films_by_slugs(slugs: List[str]) -> Dict[str, Dict]:
    """Get multiple films by their Letterboxd slugs. Returns a dict mapping slug to film."""
    if not slugs:
        return {}
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(slugs))
            cursor.execute(f"SELECT * FROM films WHERE letterboxd_slug IN ({placeholders})", slugs)
            rows = cursor.fetchall()
            result = {row['letterboxd_slug']: film_to_dict(row) for row in rows}
            
            # Debug: show sample of what we found
            if result:
                sample_slug = list(result.keys())[0]
                print(f"   ✅ Sample match: '{sample_slug}' -> {result[sample_slug].get('title', 'N/A')}")
            elif slugs:
                # Show sample of what we're looking for
                print(f"   ⚠️  No matches found. Sample slugs searched: {slugs[:3]}")
                # Check if database has any films at all
                cursor.execute("SELECT COUNT(*) as total FROM films")
                total = cursor.fetchone()['total']
                print(f"   📊 Database has {total} total films")
                if total > 0:
                    # Show sample slugs from database
                    cursor.execute("SELECT letterboxd_slug FROM films LIMIT 3")
                    sample_db_slugs = [row['letterboxd_slug'] for row in cursor.fetchall()]
                    print(f"   📋 Sample slugs in DB: {sample_db_slugs}")
            
            return result
    except Exception as e:
        print(f"   ❌ Error querying database: {e}")
        return {}


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
            
            # Always update the updated_at timestamp (if column exists)
            # Check if column exists before adding it
            cursor.execute("PRAGMA table_info(films)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'updated_at' in columns:
                update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(slug)
            
            if update_fields:
                update_sql = f"UPDATE films SET {', '.join(update_fields)} WHERE letterboxd_slug = ?"
                cursor.execute(update_sql, update_values)
        else:
            # Insert new film - check which columns exist first
            cursor.execute("PRAGMA table_info(films)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Build column list based on what exists
            insert_cols = []
            insert_vals = []
            placeholders = []
            
            # Required columns
            insert_cols.append('letterboxd_slug')
            insert_vals.append(slug)
            placeholders.append('?')
            
            # Optional columns (only if they exist in schema)
            optional_fields = [
                ('letterboxd_id', film.get('letterboxd_id')),
                ('title', film.get('title')),
                ('year', film.get('year')),
                ('tmdb_id', film.get('tmdb_id')),
                ('letterboxd_watches', film.get('letterboxd_watches')),
                ('letterboxd_likes', film.get('letterboxd_likes')),
                ('letterboxd_lists', film.get('letterboxd_lists')),
                ('letterboxd_rating', film.get('letterboxd_rating')),
                ('popularity', film.get('popularity')),
                ('vote_count', film.get('vote_count')),
                ('vote_average', film.get('vote_average')),
                ('poster_path', film.get('poster_path')),
                ('original_language', film.get('original_language')),
                ('runtime', film.get('runtime')),
                ('budget', film.get('budget')),
                ('revenue', film.get('revenue')),
                ('director', film.get('director')),
                ('genres', genres_json),
                ('production_countries', countries_json),
            ]
            
            for col_name, col_value in optional_fields:
                if col_name in columns:
                    insert_cols.append(col_name)
                    insert_vals.append(col_value)
                    placeholders.append('?')
            
            # Insert with dynamic column list
            if len(insert_cols) > 1:  # At least slug + one other column
                insert_sql = f"INSERT INTO films ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(insert_sql, insert_vals)


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
