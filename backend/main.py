from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import get_user_films
from calculator import calculate_obscurity_stats
from database import init_database, get_stats
import os

app = FastAPI(title="Obscuriboxd API", version="1.0.0")

# CORS for frontend
# In production, set FRONTEND_URL environment variable to your Vercel domain
frontend_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://www.obscuriboxd.com",
    "https://obscuriboxd.com",
]

# Add production frontend URL if set
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    frontend_origins.append(frontend_url)
    # Also allow the base domain without path
    frontend_origins.append(frontend_url.rstrip("/"))

# Allow all Vercel preview URLs
frontend_origins.append("https://*.vercel.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_database()
    stats = get_stats()
    print(f"Database initialized. Total films: {stats['total_films']}")


class AnalyzeRequest(BaseModel):
    username: str


class FilmStats(BaseModel):
    title: str
    year: int | None
    rating: float | None
    popularity: float | None
    genres: list[str]


class AnalyzeResponse(BaseModel):
    username: str
    obscurity_score: float
    total_films: int
    average_rating: float | None
    top_genres: dict[str, int]
    decade_breakdown: dict[str, int]
    country_breakdown: dict[str, int]
    most_obscure_films: list[dict]
    most_mainstream_films: list[dict]
    director_counts: dict[str, int]
    rating_distribution: dict[str, int]
    mood_analysis: dict[str, float]
    films_by_decade: dict[str, list[dict]]


@app.get("/")
async def root():
    return {"message": "Obscuriboxd API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/stats")
async def database_stats():
    """Get database statistics."""
    return get_stats()


@app.get("/films")
async def list_films(limit: int = 50, offset: int = 0):
    """List films in the database."""
    from database import get_db_connection
    import json
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM films")
        total = cursor.fetchone()['total']
        
        # Get films
        cursor.execute("""
            SELECT 
                title, year, letterboxd_slug, letterboxd_watches,
                director, genres, production_countries
            FROM films 
            ORDER BY letterboxd_watches DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        films = []
        for row in rows:
            film = {
                'title': row['title'],
                'year': row['year'],
                'slug': row['letterboxd_slug'],
                'watches': row['letterboxd_watches'],
                'director': row['director'],
            }
            if row['genres']:
                try:
                    film['genres'] = json.loads(row['genres'])
                except:
                    film['genres'] = []
            if row['production_countries']:
                try:
                    film['countries'] = json.loads(row['production_countries'])
                except:
                    film['countries'] = []
            films.append(film)
        
        return {
            'total': total,
            'limit': limit,
            'offset': offset,
            'films': films
        }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_user(request: AnalyzeRequest):
    """
    Analyze a Letterboxd user's film taste and calculate obscurity score.
    """
    username = request.username.strip().lower()
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    try:
        # Step 1: Scrape user's films from Letterboxd (includes watch counts, genres, director, countries)
        films = await get_user_films(username)
        
        if not films:
            raise HTTPException(
                status_code=404, 
                detail=f"No films found for user '{username}'. Make sure the profile is public."
            )
        
        # Step 2: Calculate obscurity score and stats (all data comes from Letterboxd)
        stats = calculate_obscurity_stats(films, username)
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        # Log the error but don't expose internal details
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        # For other errors, return generic message
        print(f"Error analyzing user {username}: {error_msg}")
        raise HTTPException(
            status_code=500, 
            detail="Error analyzing user. Please try again later."
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


