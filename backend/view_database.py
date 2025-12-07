"""
Simple script to view database contents.
Usage: python view_database.py [limit]
"""

import sys
from database import get_db_connection, get_stats

def view_films(limit=20):
    """View films in the database."""
    stats = get_stats()
    print(f"📊 Database Statistics:")
    print(f"   Total films: {stats['total_films']}")
    print(f"   Films with watch counts: {stats['films_with_watches']}")
    print(f"\n🎬 Films in database (showing {limit}):\n")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                title, 
                year, 
                letterboxd_watches,
                director,
                genres,
                letterboxd_slug
            FROM films 
            ORDER BY letterboxd_watches DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        if not rows:
            print("   No films in database yet.")
            return
        
        print(f"{'Title':<40} {'Year':<6} {'Watches':<12} {'Director':<25}")
        print("-" * 90)
        
        for row in rows:
            title = (row['title'] or 'Unknown')[:38]
            year = row['year'] or '?'
            watches = f"{row['letterboxd_watches']:,}" if row['letterboxd_watches'] else "N/A"
            director = (row['director'] or 'Unknown')[:23]
            
            print(f"{title:<40} {str(year):<6} {watches:<12} {director:<25}")

if __name__ == "__main__":
    limit = 20
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("⚠️  Invalid limit, using default of 20")
    
    view_films(limit)
