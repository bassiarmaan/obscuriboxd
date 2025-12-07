"""
Script to add TMDb posters to films that don't have them.
Run this to populate posters for existing films in database.
"""

import asyncio
import aiohttp
from database import get_db_connection, save_film, get_stats
from scraper import get_tmdb_poster, get_headers
from aiohttp import ClientTimeout

async def add_posters_to_films():
    """Add TMDb posters to films missing them."""
    print("🎬 Adding TMDb posters to films...\n")
    
    # Get films without posters
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT letterboxd_slug, title, year 
            FROM films 
            WHERE (poster_path IS NULL OR poster_path = '') 
            AND title IS NOT NULL 
            AND year IS NOT NULL
        """)
        films_to_update = cursor.fetchall()
    
    if not films_to_update:
        print("✅ All films already have posters!")
        return
    
    print(f"📊 Found {len(films_to_update)} films without posters\n")
    
    # Process in batches for faster scraping
    batch_size = 30
    timeout = ClientTimeout(total=10, connect=5)
    
    updated = 0
    failed = 0
    
    async def process_film(film_row):
        nonlocal updated, failed
        slug = film_row['letterboxd_slug']
        title = film_row['title']
        year = film_row['year']
        
        try:
            poster_path = await get_tmdb_poster(title, year)
            if poster_path:
                film = {
                    'slug': slug,
                    'poster_path': poster_path
                }
                save_film(film)
                updated += 1
                return True
            else:
                failed += 1
                return False
        except Exception as e:
            failed += 1
            return False
    
    # Process in batches
    for i in range(0, len(films_to_update), batch_size):
        batch = films_to_update[i:i + batch_size]
        tasks = [process_film(film_row) for film_row in batch]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        if (i + batch_size) % 100 == 0 or i + batch_size >= len(films_to_update):
            print(f"   Progress: {min(i + batch_size, len(films_to_update))}/{len(films_to_update)} (updated: {updated}, failed: {failed})")
        
        # Small delay between batches
        if i + batch_size < len(films_to_update):
            await asyncio.sleep(0.1)  # Reduced from 0.2 per film
    
    print(f"\n✅ Complete!")
    print(f"   Updated: {updated}")
    print(f"   Failed: {failed}")
    
    stats = get_stats()
    print(f"\n📊 Database now has {stats['films_with_posters']} films with posters")

if __name__ == "__main__":
    asyncio.run(add_posters_to_films())
