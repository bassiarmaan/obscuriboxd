"""
Script to update existing films in database with missing titles/years.
Re-scrapes only films that are missing title or year data.
"""

import asyncio
import aiohttp
from database import get_db_connection, save_film, get_stats
from scraper import get_headers, parse_film_page

async def update_missing_data():
    """Update films that are missing title or year."""
    print("🔄 Updating films with missing titles/years...\n")
    
    # Get films missing title, year, or watch counts
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT letterboxd_slug, title, year, letterboxd_watches
            FROM films 
            WHERE title IS NULL OR title = '' OR year IS NULL OR letterboxd_watches IS NULL
        """)
        films_to_update = cursor.fetchall()
    
    if not films_to_update:
        print("✅ All films already have titles and years!")
        return
    
    print(f"📊 Found {len(films_to_update)} films to update\n")
    
    updated = 0
    failed = 0
    
    async with aiohttp.ClientSession() as session:
        for film_row in films_to_update:
            slug = film_row['letterboxd_slug']
            print(f"   Updating: {slug}...", end=" ")
            
            try:
                film_dict = {'slug': slug}
                
                # Get stats (watch counts)
                stats_url = f"https://letterboxd.com/csi/film/{slug}/stats/"
                async with session.get(stats_url, headers=get_headers()) as stats_response:
                    if stats_response.status == 200:
                        from scraper import parse_stats_html
                        stats_html = await stats_response.text()
                        stats_data = parse_stats_html(stats_html)
                        film_dict.update(stats_data)
                
                # Get main page data (title, year, director, genres, countries)
                main_url = f"https://letterboxd.com/film/{slug}/"
                async with session.get(main_url, headers=get_headers()) as response:
                    if response.status == 200:
                        html = await response.text()
                        film_data = parse_film_page(html)
                        film_dict.update(film_data)
                
                # Update the film if we got any data
                if film_dict.get('title') or film_dict.get('year') or film_dict.get('letterboxd_watches'):
                    save_film(film_dict)
                    updated += 1
                    title = film_dict.get('title', 'Unknown')[:30]
                    year = film_dict.get('year', '?')
                    watches = film_dict.get('letterboxd_watches', 0)
                    print(f"✅ {title} ({year}) - {watches:,} watches")
                else:
                    failed += 1
                    print("❌ No data found")
                
                # Rate limiting
                await asyncio.sleep(0.3)
                
            except Exception as e:
                failed += 1
                print(f"❌ Error: {e}")
    
    print(f"\n✅ Update complete!")
    print(f"   Updated: {updated}")
    print(f"   Failed: {failed}")
    
    # Show final stats
    stats = get_stats()
    print(f"\n📊 Database now has {stats['total_films']} films")

if __name__ == "__main__":
    asyncio.run(update_missing_data())
