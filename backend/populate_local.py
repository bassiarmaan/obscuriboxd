#!/usr/bin/env python3
"""
Local scraping script to populate the database with film data.
Run this locally where cloudscraper can bypass Cloudflare more effectively.

Usage:
    python populate_local.py armbot              # Scrape a single user's films
    python populate_local.py --popular           # Scrape popular films from Letterboxd
    python populate_local.py --check             # Check database status
"""

import asyncio
import argparse
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_stats, save_films, get_films_by_slugs, get_db_connection
from scraper import get_user_films, enrich_with_letterboxd_stats, get_headers, is_cloudflare_challenge

# For direct scraping
import cloudscraper
import re
from bs4 import BeautifulSoup
import time


def check_database():
    """Check database status and show sample data."""
    print("\n📊 Database Status:")
    print("=" * 50)
    
    stats = get_stats()
    print(f"Total films: {stats['total_films']:,}")
    print(f"Films with watch counts: {stats['films_with_watches']:,}")
    print(f"Films with TMDB data: {stats['films_with_tmdb']:,}")
    
    # Check for films with slugs
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM films WHERE letterboxd_slug IS NOT NULL AND letterboxd_slug != ''")
        with_slugs = cursor.fetchone()['count']
        print(f"Films with slugs: {with_slugs:,}")
        
        # Show sample films
        cursor.execute("""
            SELECT letterboxd_slug, title, year, letterboxd_watches 
            FROM films 
            WHERE letterboxd_slug IS NOT NULL AND letterboxd_slug != ''
            ORDER BY letterboxd_watches DESC NULLS LAST
            LIMIT 5
        """)
        rows = cursor.fetchall()
        
        if rows:
            print("\n📋 Sample films with highest watch counts:")
            for row in rows:
                watches = f"{row['letterboxd_watches']:,}" if row['letterboxd_watches'] else "N/A"
                print(f"   - {row['title']} ({row['year']}) - {watches} watches - slug: {row['letterboxd_slug']}")
        else:
            print("\n⚠️  No films with slugs found!")
            
            # Show what we do have
            cursor.execute("SELECT title, year FROM films LIMIT 5")
            sample = cursor.fetchall()
            if sample:
                print("\n   Sample films in DB (without slugs):")
                for row in sample:
                    print(f"   - {row['title']} ({row['year']})")


async def scrape_user_films(username: str, save_to_db: bool = True):
    """Scrape all films from a user's profile and optionally save to database."""
    print(f"\n🎬 Scraping films for user: {username}")
    print("=" * 50)
    
    try:
        films = await get_user_films(username)
        print(f"\n✅ Found {len(films)} films for {username}")
        
        if films and save_to_db:
            print(f"\n💾 Saving {len(films)} films to database...")
            save_films(films)
            print("✅ Films saved!")
            
            # Show sample
            print("\n📋 Sample saved films:")
            for film in films[:5]:
                watches = film.get('letterboxd_watches', 'N/A')
                if isinstance(watches, int):
                    watches = f"{watches:,}"
                print(f"   - {film.get('title')} ({film.get('year')}) - {watches} watches")
        
        return films
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return []


def scrape_popular_films_sync(pages: int = 10):
    """Scrape popular films from Letterboxd's popular page."""
    print(f"\n🌟 Scraping popular films ({pages} pages)...")
    print("=" * 50)
    
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'desktop': True,
        }
    )
    
    all_films = []
    
    for page in range(1, pages + 1):
        url = f"https://letterboxd.com/films/popular/page/{page}/"
        print(f"📡 Fetching page {page}...")
        
        try:
            response = scraper.get(url, headers=get_headers(), timeout=30)
            
            if response.status_code == 403:
                print(f"   ⚠️  403 Forbidden - Cloudflare blocking")
                break
            
            if response.status_code != 200:
                print(f"   ⚠️  HTTP {response.status_code}")
                continue
            
            html = response.text
            
            if is_cloudflare_challenge(html):
                print(f"   ⚠️  Cloudflare challenge detected")
                break
            
            # Parse films from the page
            soup = BeautifulSoup(html, 'lxml')
            film_elements = soup.select('li.poster-container div.film-poster')
            
            if not film_elements:
                # Try alternative selector
                film_elements = soup.select('div[data-film-slug]')
            
            page_films = []
            for elem in film_elements:
                slug = elem.get('data-film-slug') or elem.get('data-target-link', '').replace('/film/', '').rstrip('/')
                if slug:
                    film = {
                        'slug': slug,
                        'letterboxd_url': f"https://letterboxd.com/film/{slug}/"
                    }
                    page_films.append(film)
            
            if page_films:
                print(f"   Found {len(page_films)} films")
                all_films.extend(page_films)
            else:
                print(f"   No films found on page {page}")
            
            # Rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    print(f"\n📊 Total films collected: {len(all_films)}")
    return all_films


async def enrich_and_save_films(films: list):
    """Enrich films with Letterboxd stats and save to database."""
    if not films:
        return
    
    print(f"\n🔄 Enriching {len(films)} films with Letterboxd data...")
    
    # Enrich in batches
    batch_size = 50
    total_enriched = 0
    
    for i in range(0, len(films), batch_size):
        batch = films[i:i + batch_size]
        print(f"   Processing batch {i//batch_size + 1} ({len(batch)} films)...")
        
        try:
            enriched = await enrich_with_letterboxd_stats(batch)
            save_films(enriched)
            total_enriched += len(enriched)
            print(f"   ✅ Saved {len(enriched)} films")
        except Exception as e:
            print(f"   ⚠️  Batch error: {e}")
        
        # Rate limiting
        await asyncio.sleep(0.2)
    
    print(f"\n✅ Total enriched and saved: {total_enriched}")


async def scrape_multiple_users(usernames: list):
    """Scrape films from multiple users to build up the database."""
    all_slugs = set()
    
    for username in usernames:
        try:
            films = await scrape_user_films(username, save_to_db=True)
            for film in films:
                if film.get('slug'):
                    all_slugs.add(film['slug'])
        except Exception as e:
            print(f"⚠️  Error with {username}: {e}")
        
        # Rate limiting between users
        await asyncio.sleep(1)
    
    print(f"\n📊 Total unique films collected: {len(all_slugs)}")


def fix_database_slugs():
    """Try to add slugs to films that are missing them based on title/year matching."""
    print("\n🔧 Attempting to fix missing slugs...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Count films without slugs
        cursor.execute("SELECT COUNT(*) as count FROM films WHERE letterboxd_slug IS NULL OR letterboxd_slug = ''")
        missing = cursor.fetchone()['count']
        print(f"   Films missing slugs: {missing:,}")
        
        if missing == 0:
            print("   ✅ All films have slugs!")
            return
        
        # Generate slugs from titles
        cursor.execute("""
            SELECT id, title, year 
            FROM films 
            WHERE (letterboxd_slug IS NULL OR letterboxd_slug = '') AND title IS NOT NULL
        """)
        rows = cursor.fetchall()
        
        fixed = 0
        for row in rows:
            title = row['title']
            year = row['year']
            
            # Generate a slug from title
            slug = title.lower()
            slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # Remove special chars
            slug = re.sub(r'\s+', '-', slug)  # Replace spaces with hyphens
            slug = re.sub(r'-+', '-', slug)  # Remove multiple hyphens
            slug = slug.strip('-')
            
            if year:
                # Add year if title is common
                cursor.execute(
                    "SELECT COUNT(*) as count FROM films WHERE title = ?",
                    (title,)
                )
                if cursor.fetchone()['count'] > 1:
                    slug = f"{slug}-{year}"
            
            # Update the film
            cursor.execute(
                "UPDATE films SET letterboxd_slug = ? WHERE id = ?",
                (slug, row['id'])
            )
            fixed += 1
            
            if fixed % 1000 == 0:
                print(f"   Fixed {fixed:,} films...")
        
        conn.commit()
        print(f"   ✅ Generated slugs for {fixed:,} films")
        print("   ⚠️  Note: Generated slugs may not match actual Letterboxd slugs exactly")


async def main():
    parser = argparse.ArgumentParser(description='Populate the Obscuriboxd database locally')
    parser.add_argument('username', nargs='?', help='Letterboxd username to scrape')
    parser.add_argument('--popular', action='store_true', help='Scrape popular films')
    parser.add_argument('--popular-pages', type=int, default=10, help='Number of popular pages to scrape')
    parser.add_argument('--check', action='store_true', help='Check database status')
    parser.add_argument('--fix-slugs', action='store_true', help='Try to fix missing slugs')
    parser.add_argument('--users', nargs='+', help='Multiple usernames to scrape')
    
    args = parser.parse_args()
    
    # Initialize database
    print("🔧 Initializing database...")
    init_database()
    
    if args.check:
        check_database()
        return
    
    if args.fix_slugs:
        fix_database_slugs()
        check_database()
        return
    
    if args.popular:
        films = scrape_popular_films_sync(args.popular_pages)
        if films:
            await enrich_and_save_films(films)
        check_database()
        return
    
    if args.users:
        await scrape_multiple_users(args.users)
        check_database()
        return
    
    if args.username:
        await scrape_user_films(args.username)
        check_database()
        return
    
    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
