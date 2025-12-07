# Deploying films_complete.db to Render

Since the database file is in `.gitignore`, it won't be deployed automatically. Here are your options:

## Option 1: Upload via Render Shell (Recommended for initial setup)

1. **Compress the database** (to make upload faster):
   ```bash
   cd backend
   gzip films_complete.db
   # Creates films_complete.db.gz
   ```

2. **Upload to Render**:
   - Go to your Render dashboard
   - Open your service → **Shell** tab
   - Or use SSH if you have it configured
   
3. **In Render Shell**, download the compressed file:
   ```bash
   # Option A: Use curl to download from a temporary URL
   # (Upload films_complete.db.gz to a temporary file sharing service first)
   curl -O https://your-temp-url.com/films_complete.db.gz
   
   # Option B: Use scp from your local machine
   # scp backend/films_complete.db.gz render@your-service.onrender.com:/opt/render/project/src/backend/
   ```

4. **Decompress in Render Shell**:
   ```bash
   cd /opt/render/project/src/backend
   gunzip films_complete.db.gz
   ```

5. **Verify it's there**:
   ```bash
   ls -lh films_complete.db
   ```

## Option 2: Use Render Disk (Persistent Storage) - Best for Production

1. **Add a Disk to your Render service**:
   - Go to Render dashboard → Your service → **Settings**
   - Scroll to **Disks** section
   - Click **Add Disk**
   - Name: `database-disk`
   - Size: 10GB (or more if needed)
   - Mount path: `/data`

2. **Update environment variable**:
   - Go to **Environment** tab
   - Add: `DB_PATH=/data/films_complete.db`

3. **Upload database to the disk**:
   - Use Render Shell to copy your database:
   ```bash
   # In Render Shell
   mkdir -p /data
   # Then upload your database file to /data/films_complete.db
   ```

4. **The database will persist** across deployments!

## Option 3: Use External Database (PostgreSQL) - Most Reliable

For production, consider switching to PostgreSQL:

1. **Create PostgreSQL database on Render**
2. **Update database.py** to use PostgreSQL instead of SQLite
3. **Migrate data** from SQLite to PostgreSQL
4. **No file upload needed** - database is managed by Render

## Option 4: Let it Build Gradually

If you don't upload the database:
- The app will start with an empty database
- As users make requests, films will be scraped and saved
- Database grows over time (up to 100 films per request)
- Slower initially, but works automatically

## Quick Upload Script

Create a script to help upload:

```bash
#!/bin/bash
# upload_db.sh

# Compress
cd backend
gzip -k films_complete.db

# Upload to temporary storage (you'll need to set this up)
# Or use Render's file upload feature
echo "Upload films_complete.db.gz to Render Shell, then run:"
echo "gunzip films_complete.db.gz"
```

## Verify Database is Working

After uploading, check the logs:
```bash
# In Render logs, you should see:
# Database initialized. Total films: [number]
```

Or test the API:
```bash
curl https://your-api.onrender.com/stats
```
