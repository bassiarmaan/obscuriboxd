# Render Environment Variable Setup

## Current Issue
The `MAX_FILMS_TO_SCRAPE` environment variable is not being read correctly on Render, so it's defaulting to 20 films per request.

## Solution: Set Environment Variable in Render Dashboard

1. Go to your Render dashboard: https://dashboard.render.com
2. Navigate to your `obscuriboxd-api` service
3. Go to **Environment** tab
4. Add or update the environment variable:
   - **Key**: `MAX_FILMS_TO_SCRAPE`
   - **Value**: `100` (or higher if you want more)
5. Save and redeploy

## Alternative: Increase the Default

If you want to increase the default value in code (so it works even without the env var), you can change the default in `scraper.py` line 98 from `"20"` to `"100"`.

## Current Behavior

- **With env var set to 100**: Scrapes up to 100 films per request
- **Without env var (current)**: Only scrapes 20 films per request (default)
- **With env var set to 0**: Disables scraping entirely (database-only mode)

## Recommendation

Set `MAX_FILMS_TO_SCRAPE=100` in Render dashboard for better coverage while still preventing server overload.
