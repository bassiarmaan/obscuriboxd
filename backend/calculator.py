"""
Obscurity score calculation - OBJECTIVE approach like Obscurify.

Uses a custom curve optimized for real-world Letterboxd data distribution.
Most viewers have medians in the 500K-2M range, so we spread scores there.

Control points (watches -> score):
- 5M+  watches -> 5   (mega blockbuster only)
- 3M   watches -> 15  (major blockbusters)
- 2M   watches -> 25  (blockbusters)
- 1.5M watches -> 33  (mainstream hits)
- 1M   watches -> 42  (popular mainstream)
- 700K watches -> 50  (average)
- 500K watches -> 57  (slightly adventurous)
- 300K watches -> 65  (adventurous)
- 150K watches -> 73  (film enthusiast)
- 75K  watches -> 80  (cinephile)
- 30K  watches -> 87  (deep cuts)
- 10K  watches -> 93  (very obscure)
- 3K   watches -> 98  (extremely obscure)
"""

from collections import Counter
import math


# Control points: (watches, score) - carefully tuned for score diversity
# More granular in the 500K-2M range where most viewers fall
SCORE_CURVE = [
    (5_000_000, 5),
    (3_500_000, 10),
    (2_500_000, 18),
    (2_000_000, 25),
    (1_500_000, 33),
    (1_200_000, 39),
    (1_000_000, 45),
    (800_000, 51),
    (600_000, 56),
    (450_000, 61),
    (300_000, 67),
    (200_000, 72),
    (100_000, 78),
    (50_000, 84),
    (25_000, 89),
    (10_000, 94),
    (5_000, 97),
    (1_000, 99),
]


def calculate_obscurity_from_watches(watches: int) -> float:
    """
    Calculate obscurity score using piecewise linear interpolation.
    This gives us precise control over score distribution.
    """
    if watches <= 0:
        return 50.0
    
    # Handle edge cases
    if watches >= SCORE_CURVE[0][0]:
        return SCORE_CURVE[0][1]
    if watches <= SCORE_CURVE[-1][0]:
        return SCORE_CURVE[-1][1]
    
    # Find the two control points to interpolate between
    for i in range(len(SCORE_CURVE) - 1):
        upper_watches, upper_score = SCORE_CURVE[i]
        lower_watches, lower_score = SCORE_CURVE[i + 1]
        
        if lower_watches <= watches <= upper_watches:
            # Linear interpolation
            ratio = (upper_watches - watches) / (upper_watches - lower_watches)
            score = upper_score + ratio * (lower_score - upper_score)
            return score
    
    return 50.0


def get_film_obscurity(film: dict) -> tuple[float, str]:
    """Get obscurity score for a single film."""
    lb_watches = film.get('letterboxd_watches')
    if lb_watches and lb_watches > 0:
        score = calculate_obscurity_from_watches(lb_watches)
        return score, 'letterboxd'
    
    # Fallback to TMDb - estimate watches from popularity
    tmdb_pop = film.get('popularity')
    if tmdb_pop and tmdb_pop > 0:
        # Rough conversion: TMDb popularity to estimated watches
        # Pop 1 ≈ 30K, Pop 10 ≈ 150K, Pop 50 ≈ 500K, Pop 100 ≈ 1M
        estimated_watches = int(30_000 * (tmdb_pop ** 0.85))
        score = calculate_obscurity_from_watches(estimated_watches)
        return score, 'tmdb'
    
    return 50, 'none'


def calculate_obscurity_stats(films: list[dict], username: str) -> dict:
    """Calculate the obscurity score and generate detailed statistics."""
    
    if not films:
        return {
            "username": username,
            "obscurity_score": 0,
            "total_films": 0,
            "average_rating": None,
            "median_watches": None,
            "top_genres": {},
            "decade_breakdown": {},
            "country_breakdown": {},
            "most_obscure_films": [],
            "most_mainstream_films": [],
            "director_counts": {},
            "rating_distribution": {},
            "mood_analysis": {},
        }
    
    obscurity_score, median_watches = calculate_obscurity_score(films)
    
    # Genre breakdown
    genre_counts = Counter()
    for film in films:
        genre_counts.update(film.get('genres', []))
    top_genres = dict(genre_counts.most_common(10))
    
    # Decade breakdown - include ALL films with years
    decade_counts = Counter()
    films_with_years = 0
    films_without_years = 0
    for film in films:
        year = film.get('year')
        if year:
            decade_counts[f"{(year // 10) * 10}s"] += 1
            films_with_years += 1
        else:
            films_without_years += 1
    
    # Debug: print decade distribution
    print(f"Total films: {len(films)}, With years: {films_with_years}, Without years: {films_without_years}")
    print(f"Decade breakdown: {dict(sorted(decade_counts.items()))}")
    
    decade_breakdown = dict(sorted(decade_counts.items()))
    
    # Country breakdown
    country_counts = Counter()
    for film in films:
        country_counts.update(film.get('production_countries', []))
    country_breakdown = dict(country_counts.most_common(10))
    
    # Director breakdown
    director_counts = Counter()
    for film in films:
        director = film.get('director')
        if director:
            director_counts[director] += 1
    top_directors = dict(director_counts.most_common(10))
    
    # Rating distribution
    rating_counts = Counter()
    ratings = []
    for film in films:
        user_rating = film.get('user_rating')
        if user_rating is not None:
            ratings.append(user_rating)
            rating_counts[str(user_rating)] += 1
    
    average_rating = sum(ratings) / len(ratings) if ratings else None
    
    # Sort films by their individual obscurity score
    films_with_scores = []
    for f in films:
        score, source = get_film_obscurity(f)
        films_with_scores.append((f, score, source))
    
    # Sort by obscurity score (highest = most obscure)
    films_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    most_obscure = [
        {
            "title": f.get('title'),
            "year": f.get('year'),
            "watches": f.get('letterboxd_watches'),
            "popularity": round(f.get('popularity', 0), 1) if f.get('popularity') else None,
            "director": f.get('director'),
            "poster_path": f.get('poster_path'),
        }
        for f, score, source in films_with_scores[:5]
    ]
    
    most_mainstream = [
        {
            "title": f.get('title'),
            "year": f.get('year'),
            "watches": f.get('letterboxd_watches'),
            "popularity": round(f.get('popularity', 0), 1) if f.get('popularity') else None,
            "director": f.get('director'),
            "poster_path": f.get('poster_path'),
        }
        for f, score, source in films_with_scores[-5:][::-1]
    ]
    
    mood_analysis = calculate_mood_analysis(films)
    
    # Films by decade - top 5 MOST OBSCURE per decade (lowest watches = most obscure)
    films_by_decade = {}
    for film in films:
        year = film.get('year')
        if year:
            decade = f"{(year // 10) * 10}s"
            if decade not in films_by_decade:
                films_by_decade[decade] = []
            
            # Calculate obscurity score for ranking
            score, _ = get_film_obscurity(film)
            films_by_decade[decade].append({
                "title": film.get('title'),
                "year": film.get('year'),
                "watches": film.get('letterboxd_watches'),
                "popularity": round(film.get('popularity', 0), 1) if film.get('popularity') else None,
                "director": film.get('director'),
                "poster_path": film.get('poster_path'),
                "obscurity_score": round(score, 1),
            })
    
    # Sort each decade by obscurity score (highest = most obscure) and limit to 5
    for decade in films_by_decade:
        films_by_decade[decade] = sorted(
            films_by_decade[decade],
            key=lambda x: x.get('obscurity_score', 0),
            reverse=True
        )[:5]
    
    return {
        "username": username,
        "obscurity_score": round(obscurity_score, 1),
        "total_films": len(films),
        "average_rating": round(average_rating, 2) if average_rating else None,
        "median_watches": median_watches,
        "top_genres": top_genres,
        "decade_breakdown": decade_breakdown,
        "country_breakdown": country_breakdown,
        "most_obscure_films": most_obscure,
        "most_mainstream_films": most_mainstream,
        "director_counts": top_directors,
        "rating_distribution": dict(sorted(rating_counts.items())),
        "mood_analysis": mood_analysis,
        "films_by_decade": films_by_decade,
    }


def calculate_obscurity_score(films: list[dict]) -> tuple[float, int]:
    """
    Calculate overall obscurity score using MEDIAN watch count.
    """
    if not films:
        return 50, 0
    
    # Get all Letterboxd watch counts
    lb_watches = [f.get('letterboxd_watches') for f in films if f.get('letterboxd_watches')]
    
    if lb_watches and len(lb_watches) >= 3:
        # Calculate median
        lb_watches.sort()
        n = len(lb_watches)
        if n % 2 == 0:
            median_watches = (lb_watches[n//2 - 1] + lb_watches[n//2]) // 2
        else:
            median_watches = lb_watches[n//2]
        
        # Calculate score from median
        base_score = calculate_obscurity_from_watches(median_watches)
        
        # Small diversity bonus (max +3) for international/classic films
        bonus = calculate_diversity_bonus(films)
        
        final_score = max(0, min(100, base_score + bonus))
        return final_score, median_watches
    
    # Fallback: use individual film scores
    film_scores = [get_film_obscurity(f)[0] for f in films]
    if film_scores:
        film_scores.sort()
        median_score = film_scores[len(film_scores)//2]
        bonus = calculate_diversity_bonus(films)
        return max(0, min(100, median_score + bonus)), 0
    
    return 50, 0


def calculate_diversity_bonus(films: list[dict]) -> float:
    """Small bonus for diverse taste. Max +3 points."""
    if not films:
        return 0
    
    bonus = 0
    n = len(films)
    
    # Non-US/UK films (max +1.5)
    non_anglophone = sum(
        1 for f in films 
        if f.get('production_countries') and 
        not any(c in f.get('production_countries', []) 
                for c in ['United States of America', 'USA', 'United Kingdom', 'UK'])
    )
    bonus += min(1.5, (non_anglophone / n) * 3) if n > 0 else 0
    
    # Pre-1980 films (max +1.5)
    classic_films = sum(1 for f in films if f.get('year') and f.get('year') < 1980)
    bonus += min(1.5, (classic_films / n) * 3) if n > 0 else 0
    
    return min(3, bonus)


def calculate_mood_analysis(films: list[dict]) -> dict[str, float]:
    """Analyze mood based on genres."""
    mood_mapping = {
        "Dark & Intense": ["Horror", "Thriller", "Crime", "War", "Mystery"],
        "Fun & Light": ["Comedy", "Animation", "Family", "Music"],
        "Emotional & Deep": ["Drama", "Romance", "History"],
        "Adventurous": ["Action", "Adventure", "Science Fiction", "Fantasy", "Western"],
        "Thought-Provoking": ["Documentary", "Mystery", "Science Fiction"]
    }
    
    mood_counts = {mood: 0 for mood in mood_mapping}
    total = 0
    
    for film in films:
        for genre in film.get('genres', []):
            for mood, genres in mood_mapping.items():
                if genre in genres:
                    mood_counts[mood] += 1
                    total += 1
    
    if total > 0:
        return {mood: round((count / total) * 100, 1) for mood, count in mood_counts.items()}
    return {mood: 0 for mood in mood_mapping}
