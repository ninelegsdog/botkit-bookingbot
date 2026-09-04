"""Extra tests for metrics health/version to boost coverage to 80%."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from src.core.metrics import health, version, metrics, create_metrics_app


class TestHealthExtra(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        return create_metrics_app()

    async def test_health_text(self) -> None:
        with patch("src.core.metrics._get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.execute.return_value = MagicMock()
            mock_db.session.return_value = mock_session
            mock_get_db.return_value = mock_db
            resp = await self.client.request("GET", "/health")
            assert resp.status == 200
            text = await resp.text()
            assert text == "ok"

    async def test_health_json(self) -> None:
        with patch("src.core.metrics._get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.execute.return_value = MagicMock()
            mock_db.session.return_value = mock_session
            mock_get_db.return_value = mock_db
            resp = await self.client.request("GET", "/health", headers={"Accept": "application/json"})
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert "version" in data

    async def test_version(self) -> None:
        resp = await self.client.request("GET", "/version")
        assert resp.status == 200
        data = await resp.json()
        assert "version" in data
        assert data["service"] == "botkit"

    async def test_metrics(self) -> None:
        resp = await self.client.request("GET", "/metrics")
        assert resp.status == 200
        text = await resp.text()
        assert "botkit_" in text


@pytest.mark.asyncio
async def test_health_db_unavailable() -> None:
    from src.core.metrics import health
    from aiohttp.test_utils import make_mocked_request

    with patch("src.core.metrics._get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.execute.side_effect = Exception("db fail")
        mock_db.session.return_value = mock_session
        mock_get_db.return_value = mock_db

        req = make_mocked_request("GET", "/health", headers={"Accept": "text/plain"})
        resp = await health(req)
        assert resp.status == 500
        assert resp.text == "db unavailable"

        req_json = make_mocked_request("GET", "/health", headers={"Accept": "application/json"})
        resp_json = await health(req_json)
        assert resp_json.status == 500
