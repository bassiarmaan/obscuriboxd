"""
Download films_complete.db from GitHub if it doesn't exist or is incomplete.
This runs on startup to ensure the database is available on Render.
"""

import os
import gzip
import shutil
import sqlite3
import requests
from pathlib import Path

MIN_FILMS_WITH_WATCHES = 100  # Minimum expected films with watch counts

def check_database_valid(db_path: str) -> bool:
    """Check if the database has sufficient data."""
    if not os.path.exists(db_path):
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for films table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='films'")
        if not cursor.fetchone():
            print(f"   ⚠️ Database missing 'films' table")
            conn.close()
            return False
        
        # Check for films with watch counts
        cursor.execute("SELECT COUNT(*) FROM films WHERE letterboxd_watches IS NOT NULL AND letterboxd_watches > 0")
        films_with_watches = cursor.fetchone()[0]
        conn.close()
        
        print(f"   📊 Database has {films_with_watches} films with watch counts")
        
        if films_with_watches < MIN_FILMS_WITH_WATCHES:
            print(f"   ⚠️ Database has insufficient data (need at least {MIN_FILMS_WITH_WATCHES})")
            return False
        
        return True
    except Exception as e:
        print(f"   ⚠️ Error checking database: {e}")
        return False

def download_database_from_github():
    """Download and decompress database from GitHub if it doesn't exist or is incomplete."""
    db_path = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "films_complete.db"))
    db_gz_path = db_path + ".gz"
    
    # Check if database exists AND has sufficient data
    print(f"🔍 Checking database at {db_path}...")
    if os.path.exists(db_path):
        if check_database_valid(db_path):
            print(f"✅ Database is valid and ready")
            return
        else:
            print(f"🔄 Database exists but is incomplete - will re-download")
            # Remove the incomplete database
            os.remove(db_path)
    
    # GitHub raw URL
    github_url = "https://raw.githubusercontent.com/bassiarmaan/obscuriboxd/main/backend/films_complete.db.gz"
    
    print(f"📥 Downloading database from GitHub...")
    
    try:
        # Download the compressed file
        response = requests.get(github_url, stream=True, timeout=60)
        response.raise_for_status()
        
        # Save to temporary location
        with open(db_gz_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Downloaded {os.path.getsize(db_gz_path) / (1024*1024):.1f} MB")
        
        # Decompress
        print(f"🗜️  Decompressing database...")
        with gzip.open(db_gz_path, 'rb') as f_in:
            with open(db_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove compressed file
        os.remove(db_gz_path)
        
        print(f"✅ Database ready at {db_path} ({os.path.getsize(db_path) / (1024*1024):.1f} MB)")
        
        # Verify the downloaded database
        if check_database_valid(db_path):
            print(f"✅ Downloaded database verified successfully!")
        else:
            print(f"⚠️ Downloaded database may be incomplete")
        
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Could not download database from GitHub: {e}")
        print(f"   The app will start with an empty database and build it over time.")
    except Exception as e:
        print(f"⚠️  Error setting up database: {e}")
        # Clean up partial files
        if os.path.exists(db_gz_path):
            os.remove(db_gz_path)
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    download_database_from_github()
