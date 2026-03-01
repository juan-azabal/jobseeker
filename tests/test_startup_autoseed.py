"""Tests for staging DB auto-seed on startup.

Verifies:
- ENVIRONMENT=staging + no DB + PROD_API_URL set → download_prod_snapshot called
- ENVIRONMENT=production + no DB → NOT called
- ENVIRONMENT=staging + DB exists → NOT called
- ENVIRONMENT=staging + no PROD_API_URL → NOT called
- download fails → startup completes without crash
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


class TestStartupAutoseed:
    def test_seeds_on_staging_empty_volume(self, tmp_path):
        db_path = str(tmp_path / "missing.db")  # does not exist

        with (
            patch("api.main.config.ENVIRONMENT", "staging"),
            patch("api.main.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.main.config.DB_EXPORT_API_KEY", "secret"),
            patch.dict("os.environ", {"DB_PATH": db_path}),
            patch("api.main.download_prod_snapshot", new_callable=AsyncMock, return_value=True) as mock_dl,
        ):
            with TestClient(app):
                pass

        mock_dl.assert_called_once_with("https://prod.example.com", "secret", db_path)

    def test_does_not_seed_in_production(self, tmp_path):
        db_path = str(tmp_path / "missing.db")

        with (
            patch("api.main.config.ENVIRONMENT", "production"),
            patch("api.main.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.main.config.DB_EXPORT_API_KEY", "secret"),
            patch.dict("os.environ", {"DB_PATH": db_path}),
            patch("api.main.download_prod_snapshot", new_callable=AsyncMock, return_value=True) as mock_dl,
        ):
            with TestClient(app):
                pass

        mock_dl.assert_not_called()

    def test_does_not_seed_when_db_exists(self, tmp_path):
        db_path = str(tmp_path / "existing.db")
        tmp_path.joinpath("existing.db").touch()  # file exists

        with (
            patch("api.main.config.ENVIRONMENT", "staging"),
            patch("api.main.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.main.config.DB_EXPORT_API_KEY", "secret"),
            patch.dict("os.environ", {"DB_PATH": db_path}),
            patch("api.main.download_prod_snapshot", new_callable=AsyncMock, return_value=True) as mock_dl,
        ):
            with TestClient(app):
                pass

        mock_dl.assert_not_called()

    def test_does_not_seed_when_prod_url_missing(self, tmp_path):
        db_path = str(tmp_path / "missing.db")

        with (
            patch("api.main.config.ENVIRONMENT", "staging"),
            patch("api.main.config.PROD_API_URL", ""),
            patch("api.main.config.DB_EXPORT_API_KEY", "secret"),
            patch.dict("os.environ", {"DB_PATH": db_path}),
            patch("api.main.download_prod_snapshot", new_callable=AsyncMock, return_value=True) as mock_dl,
        ):
            with TestClient(app):
                pass

        mock_dl.assert_not_called()

    def test_startup_completes_when_seed_fails(self, tmp_path):
        db_path = str(tmp_path / "missing.db")

        with (
            patch("api.main.config.ENVIRONMENT", "staging"),
            patch("api.main.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.main.config.DB_EXPORT_API_KEY", "secret"),
            patch.dict("os.environ", {"DB_PATH": db_path}),
            patch("api.main.download_prod_snapshot", new_callable=AsyncMock, side_effect=Exception("network error")),
        ):
            # Should not raise despite the download failure
            with TestClient(app) as client:
                resp = client.get("/api/health")
            assert resp.status_code == 200
