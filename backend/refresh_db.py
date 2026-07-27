#!/usr/bin/env python3
"""
Weekly database refresh for Obscuriboxd (run locally, on a residential IP).

What it does:
  1. Re-fetches watch counts for recent releases (their numbers change fastest).
  2. Pulls the top pages of Letterboxd's popular list to catch newly-popular films.
  3. Enriches any new films and saves everything to films_complete.db.
  4. Re-compresses the DB to films_complete.db.gz (what production downloads).

After running, commit and push films_complete.db.gz so Render redeploys with fresh data:
    python refresh_db.py && git add films_complete.db.gz && git commit -m "chore: weekly DB refresh" && git push

Usage:
    python refresh_db.py                     # refresh last 1 year + top 30 popular pages
    python refresh_db.py --recent-years 2    # refresh films from the last 2 years
    python refresh_db.py --popular-pages 50  # also scan more popular pages for new films
    python refresh_db.py --no-gzip           # skip producing the .gz (build only)
"""

import argparse
import asyncio
import datetime
import gzip
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_database,
    get_stats,
    save_films,
    get_films_by_slugs,
    get_recent_film_slugs,
    get_db_path,
)
from scraper import enrich_with_letterboxd_stats, get_popular_film_slugs


async def refresh_recent_films(recent_years: int) -> int:
    """Re-fetch watch counts for films released within the last `recent_years` years."""
    current_year = datetime.date.today().year
    min_year = current_year - recent_years
    slugs = get_recent_film_slugs(min_year)

    if not slugs:
        print(f"ℹ️  No films with year >= {min_year} in the DB yet - nothing to refresh.")
        return 0

    print(f"\n🔄 Refreshing watch counts for {len(slugs)} films released since {min_year}...")
    films = [{'slug': s, 'letterboxd_url': f"https://letterboxd.com/film/{s}/"} for s in slugs]

    updated = 0
    batch_size = 200
    for i in range(0, len(films), batch_size):
        batch = films[i:i + batch_size]
        enriched = await enrich_with_letterboxd_stats(batch)
        save_films(enriched)
        updated += len(enriched)
        print(f"   ...refreshed {updated}/{len(films)}")

    return updated


async def add_new_popular_films(pages: int) -> int:
    """Scan the top popular pages and enrich any films not already in the DB."""
    if pages <= 0:
        return 0

    print(f"\n🌟 Scanning top {pages} popular pages for new films...")
    slugs = await get_popular_film_slugs(pages)
    if not slugs:
        print("   ⚠️ Could not fetch popular films (blocked or empty).")
        return 0

    existing = get_films_by_slugs(slugs)
    new_slugs = [s for s in slugs if s not in existing]
    print(f"   {len(new_slugs)} new films not yet in the DB.")

    if not new_slugs:
        return 0

    films = [{'slug': s, 'letterboxd_url': f"https://letterboxd.com/film/{s}/"} for s in new_slugs]
    enriched = await enrich_with_letterboxd_stats(films)
    save_films(enriched)
    return len(enriched)


def compress_db() -> None:
    """Compress films_complete.db -> films_complete.db.gz for production download."""
    db_path = get_db_path()
    gz_path = db_path + ".gz"
    print(f"\n🗜️  Compressing {db_path} -> {gz_path}...")
    with open(db_path, 'rb') as f_in:
        with gzip.open(gz_path, 'wb', compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    size_mb = os.path.getsize(gz_path) / (1024 * 1024)
    print(f"✅ Wrote {gz_path} ({size_mb:.1f} MB). Commit & push it to deploy the refresh.")


async def main():
    parser = argparse.ArgumentParser(description="Weekly Obscuriboxd DB refresh")
    parser.add_argument('--recent-years', type=int, default=1,
                        help='Re-fetch watch counts for films released within this many years (default 1)')
    parser.add_argument('--popular-pages', type=int, default=30,
                        help='Also scan this many popular pages for new films (default 30, 0 to skip)')
    parser.add_argument('--no-gzip', action='store_true', help='Skip producing films_complete.db.gz')
    args = parser.parse_args()

    print("🔧 Initializing database...")
    init_database()
    before = get_stats()
    print(f"   Starting with {before['total_films']:,} films ({before['films_with_watches']:,} with watch counts)")

    new_count = await add_new_popular_films(args.popular_pages)
    refreshed = await refresh_recent_films(args.recent_years)

    after = get_stats()
    print(f"\n📊 Done. {new_count} new films added, {refreshed} recent films refreshed.")
    print(f"   DB now has {after['total_films']:,} films ({after['films_with_watches']:,} with watch counts).")

    if not args.no_gzip:
        compress_db()


if __name__ == "__main__":
    asyncio.run(main())
