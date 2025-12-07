"""
Download films_complete.db from GitHub if it doesn't exist locally.
This runs on startup to ensure the database is available on Render.
"""

import os
import gzip
import shutil
import requests
from pathlib import Path

def download_database_from_github():
    """Download and decompress database from GitHub if it doesn't exist."""
    db_path = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "films_complete.db"))
    db_gz_path = db_path + ".gz"
    
    # If database already exists, skip
    if os.path.exists(db_path):
        print(f"✅ Database already exists at {db_path}")
        return
    
    # GitHub raw URL - update this to your actual repo and path
    # Option 1: From main branch
    github_url = "https://raw.githubusercontent.com/bassiarmaan/obscuriboxd/main/backend/films_complete.db.gz"
    
    # Option 2: From GitHub Releases (better for large files)
    # github_url = "https://github.com/bassiarmaan/obscuriboxd/releases/download/v1.0/films_complete.db.gz"
    
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
