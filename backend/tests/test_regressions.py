import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main
import scraper


class AnalyzeEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)

    def test_analyze_success(self) -> None:
        sample_films = [
            {
                "title": "Film A",
                "year": 1999,
                "slug": "film-a",
                "letterboxd_watches": 1_000_000,
                "director": "Dir A",
                "poster_path": "/a.jpg",
                "genres": ["Drama"],
                "production_countries": ["USA"],
                "user_rating": 4.0,
            },
            {
                "title": "Film B",
                "year": 1975,
                "slug": "film-b",
                "letterboxd_watches": 5_000,
                "director": "Dir B",
                "poster_path": "/b.jpg",
                "genres": ["Horror"],
                "production_countries": ["France"],
                "user_rating": 3.5,
            },
            {
                "title": "Film C",
                "year": 2010,
                "slug": "film-c",
                "letterboxd_watches": 200_000,
                "director": "Dir A",
                "poster_path": "/c.jpg",
                "genres": ["Drama", "Mystery"],
                "production_countries": ["USA"],
                "user_rating": 4.5,
            },
        ]

        async def fake_get_user_films(username: str) -> list[dict]:
            return sample_films

        with patch.object(main, "get_user_films", new=fake_get_user_films):
            response = self.client.post("/analyze", json={"username": "testuser"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], "testuser")
        self.assertEqual(payload["total_films"], 3)
        self.assertIn("obscurity_score", payload)
        self.assertIn("films_by_decade", payload)

    def test_analyze_empty_username(self) -> None:
        response = self.client.post("/analyze", json={"username": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Username is required")

    def test_analyze_marks_partial_data_for_rss_fallback(self) -> None:
        sample_films = [
            {
                "title": "Film A",
                "year": 1999,
                "slug": "film-a",
                "letterboxd_watches": 1_000_000,
                "director": "Dir A",
                "poster_path": "/a.jpg",
                "genres": ["Drama"],
                "production_countries": ["USA"],
                "user_rating": 4.0,
                "_obscuriboxd_data_source": "rss_fallback",
            },
            {
                "title": "Film B",
                "year": 1975,
                "slug": "film-b",
                "letterboxd_watches": 5_000,
                "director": "Dir B",
                "poster_path": "/b.jpg",
                "genres": ["Horror"],
                "production_countries": ["France"],
                "user_rating": 3.5,
                "_obscuriboxd_data_source": "rss_fallback",
            },
            {
                "title": "Film C",
                "year": 2010,
                "slug": "film-c",
                "letterboxd_watches": 200_000,
                "director": "Dir A",
                "poster_path": "/c.jpg",
                "genres": ["Drama", "Mystery"],
                "production_countries": ["USA"],
                "user_rating": 4.5,
                "_obscuriboxd_data_source": "rss_fallback",
            },
        ]

        async def fake_get_user_films(username: str) -> list[dict]:
            return sample_films

        with patch.object(main, "get_user_films", new=fake_get_user_films):
            response = self.client.post("/analyze", json={"username": "testuser"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_source"], "rss_fallback")
        self.assertTrue(payload["is_partial_data"])
        self.assertIn("only recent RSS films were analyzed", payload["data_note"])


class ScraperRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_user_films_ignores_404_substring_in_valid_html(self) -> None:
        valid_html = (
            "<html><head><title>Test Profile</title></head>"
            "<body>cacheBustingKey bcd61404 data-target-link=\"/film/test-film/\"</body></html>"
        )

        page_1_films = [
            {
                "title": "Test Film",
                "year": 2024,
                "slug": "test-film",
                "letterboxd_id": "",
                "letterboxd_url": "https://letterboxd.com/film/test-film/",
                "user_rating": None,
            }
        ]

        db_film = {
            "test-film": {
                "title": "Test Film",
                "year": 2024,
                "slug": "test-film",
                "letterboxd_watches": 12_345,
                "director": "A Director",
                "poster_path": "https://a.example/poster.jpg",
                "genres": ["Drama"],
                "production_countries": ["USA"],
            }
        }

        with patch.object(
            scraper,
            "fetch_with_cloudflare_bypass",
            new=AsyncMock(side_effect=[valid_html, valid_html, valid_html]),
        ), patch.object(
            scraper,
            "parse_films_page",
            side_effect=[page_1_films, [], []],
        ), patch.object(
            scraper,
            "get_films_by_slugs",
            return_value=db_film,
        ), patch.object(
            scraper,
            "enrich_with_letterboxd_stats",
            new=AsyncMock(return_value=[]),
        ), patch.object(scraper, "save_films") as save_films_mock:
            films = await scraper.get_user_films("testuser")

        self.assertEqual(len(films), 1)
        self.assertEqual(films[0]["slug"], "test-film")
        self.assertEqual(films[0]["letterboxd_watches"], 12_345)
        save_films_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
