# Obscuriboxd 🎬

**Obscurify for Letterboxd** — Discover how unique your film taste really is.

![Obscuriboxd](https://img.shields.io/badge/Status-Development-yellow)

## What is this?

Obscuriboxd analyzes your Letterboxd profile and calculates an "obscurity score" based on how mainstream or niche your film taste is. It also provides insights about your viewing habits including:

- 🎯 **Obscurity Score** — How unique is your taste compared to average viewers?
- 🎭 **Genre Breakdown** — What genres do you gravitate toward?
- 📅 **Decade Analysis** — Are you into classics or modern cinema?
- 🌍 **Country Distribution** — How internationally diverse is your watchlist?
- 🎬 **Director Stats** — Who are your most-watched filmmakers?
- 🎭 **Mood Analysis** — What's the emotional vibe of your film collection?

## Tech Stack

### Backend (Python)
- **FastAPI** — Modern async web framework
- **BeautifulSoup** — Web scraping for Letterboxd data
- **TMDb API** — Film metadata and popularity scores
- **aiohttp** — Async HTTP client

### Frontend (Next.js)
- **Next.js 14** — React framework
- **Tailwind CSS** — Styling
- **Framer Motion** — Animations
- **Recharts** — Data visualization

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- TMDb API key (free at https://www.themoviedb.org/settings/api)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "TMDB_API_KEY=your_api_key_here" > .env

# Run the server
python main.py
```

The API will be available at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The app will be available at `http://localhost:3000`

## Deployment

### Frontend (Vercel)

1. Push your code to GitHub
2. Go to [vercel.com](https://vercel.com) and import your repository
3. Set the **Root Directory** to `frontend`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = Your backend URL (e.g., `https://your-app.railway.app`)
5. Deploy!

### Backend (Railway)

1. Go to [railway.app](https://railway.app) and create a new project
2. Select "Deploy from GitHub repo"
3. Set the **Root Directory** to `backend`
4. Add environment variables:
   - `TMDB_API_KEY` = Your TMDb API key
   - `FRONTEND_URL` = Your Vercel URL (e.g., `https://obscuriboxd.vercel.app`)
5. Deploy!

Alternative backend hosts: [Render](https://render.com), [Fly.io](https://fly.io), [Heroku](https://heroku.com)

## API Endpoints

### `POST /analyze`
Analyze a Letterboxd user's film taste.

**Request:**
```json
{
  "username": "letterboxd_username"
}
```

**Response:**
```json
{
  "username": "letterboxd_username",
  "obscurity_score": 65.4,
  "total_films": 342,
  "average_rating": 3.8,
  "top_genres": {
    "Drama": 89,
    "Comedy": 56,
    ...
  },
  "decade_breakdown": {
    "2020s": 45,
    "2010s": 123,
    ...
  },
  ...
}
```

## How Obscurity is Calculated

The obscurity score (0-100) is based on:

1. **TMDb Popularity** — Films with lower popularity scores contribute to higher obscurity
2. **Vote Count** — Fewer votes = more obscure
3. **Geographic Diversity** — Watching films from many countries adds to obscurity
4. **Temporal Diversity** — Spanning many decades shows broader taste

The formula uses a logarithmic scale since film popularity follows a power-law distribution.

## Disclaimer

This project is not affiliated with Letterboxd. It scrapes publicly available profile data and is intended for personal use. Please be respectful of Letterboxd's servers and don't abuse this tool.

## License

MIT



