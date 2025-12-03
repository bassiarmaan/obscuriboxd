from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import get_user_films
from tmdb import enrich_films_with_tmdb
from calculator import calculate_obscurity_stats
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


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_user(request: AnalyzeRequest):
    """
    Analyze a Letterboxd user's film taste and calculate obscurity score.
    """
    username = request.username.strip().lower()
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    try:
        # Step 1: Scrape user's films from Letterboxd
        films = await get_user_films(username)
        
        if not films:
            raise HTTPException(
                status_code=404, 
                detail=f"No films found for user '{username}'. Make sure the profile is public."
            )
        
        # Step 2: Enrich films with TMDb data (popularity, genres, etc.)
        enriched_films = await enrich_films_with_tmdb(films)
        
        # Step 3: Calculate obscurity score and stats
        stats = calculate_obscurity_stats(enriched_films, username)
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing user: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


