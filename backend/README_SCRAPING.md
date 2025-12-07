# Database Scraping Guide

## Problem
Scraping thousands of films during user requests causes the server to crash on Render.

## Solution
Run scrapers locally to populate the database, then upload it to Render.

## Local Scraping Commands

### 1. Scrape from popular users
```bash
cd backend
source venv/bin/activate
python populate_from_users.py username1 username2 username3
```

### 2. Scrape from /films/ directory (limited pages)
```bash
python populate_database.py 50  # Scrapes 50 pages
```

### 3. Update existing films with missing data
```bash
python update_films.py  # Updates films missing titles/years/watch counts
```

## Upload Database to Render

### Option 1: Using Render Shell (Recommended)
1. Go to your Render dashboard
2. Open the Shell/Console for your service
3. Upload the database file:
```bash
# In Render shell, the database will be at the working directory
# You can use scp or Render's file upload feature
```

### Option 2: Using Render Disk (Persistent Storage)
1. Add a Disk to your Render service
2. Mount it to `/data` or similar
3. Update `DB_PATH` environment variable to point to the disk
4. The database will persist across deployments

### Option 3: Use External Database
Switch to PostgreSQL or another managed database that persists automatically.

## Current Behavior

- **On Render**: Only scrapes max 20 films per request (prevents crashes)
- **Locally**: Can scrape unlimited films using the populate scripts
- **Database**: Grows gradually as users use the app (20 films at a time)

## Environment Variable

Set `MAX_FILMS_TO_SCRAPE` environment variable on Render to control scraping limit:
- Default: 20 films per request
- Set to 0 to disable scraping entirely (database-only mode)
