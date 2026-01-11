"""
Unit tests for Scraper service FastAPI endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import Market, MarketOutcome


@pytest.fixture
def mock_scraper_service():
    """Create a mocked scraper service."""
    service = MagicMock()
    service.get_markets = AsyncMock(return_value=[])
    service.get_filtered_markets = AsyncMock(return_value=([], {}))
    service.get_tradeable_markets = AsyncMock(return_value=[])
    service.get_market = AsyncMock(return_value=None)
    service.apply_custom_filter = MagicMock(return_value=[])
    return service


@pytest.fixture
def sample_market():
    """Create a sample market."""
    return Market(
        id="market-001",
        question="Will BTC reach $100k?",
        category="crypto",
        end_date=datetime.utcnow() + timedelta(hours=1),
        volume=50000,
        liquidity=25000,
        outcomes=[
            MarketOutcome(name="Yes", price=0.35),
            MarketOutcome(name="No", price=0.65),
        ],
    )


@pytest.fixture
def client(mock_scraper_service):
    """Create test client with mocked service."""
    with patch("services.scraper.main._scraper_service", None):
        with patch(
            "services.scraper.main.get_scraper_service",
            return_value=mock_scraper_service,
        ):
            import services.scraper.main as scraper_main
            from services.scraper.main import app

            # Reset service instance
            scraper_main._scraper_service = None

            with TestClient(app) as test_client:
                yield test_client


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestMarketEndpoints:
    """Tests for market endpoints."""

    def test_get_markets_filtered(self, client, mock_scraper_service, sample_market):
        """Test getting filtered markets."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            return_value=([sample_market], {"total": 1, "filtered": 1})
        )

        response = client.get("/markets?filtered=true&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "market-001"

    def test_get_markets_unfiltered(self, client, mock_scraper_service, sample_market):
        """Test getting unfiltered markets."""
        mock_scraper_service.get_markets = AsyncMock(return_value=[sample_market])

        response = client.get("/markets?filtered=false&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_get_markets_with_pagination(self, client, mock_scraper_service):
        """Test market pagination parameters."""
        mock_scraper_service.get_filtered_markets = AsyncMock(return_value=([], {}))

        response = client.get("/markets?limit=25&offset=10")

        assert response.status_code == 200
        mock_scraper_service.get_filtered_markets.assert_called_once_with(
            limit=25, offset=10
        )

    def test_get_markets_error(self, client, mock_scraper_service):
        """Test market endpoint error handling."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            side_effect=Exception("API Error")
        )

        response = client.get("/markets")

        assert response.status_code == 500
        assert "API Error" in response.json()["detail"]

    def test_get_tradeable_markets(self, client, mock_scraper_service, sample_market):
        """Test getting tradeable markets."""
        mock_scraper_service.get_tradeable_markets = AsyncMock(
            return_value=[sample_market]
        )

        response = client.get("/markets/tradeable?max_markets=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        mock_scraper_service.get_tradeable_markets.assert_called_once_with(
            max_markets=5
        )

    def test_get_tradeable_markets_error(self, client, mock_scraper_service):
        """Test tradeable markets error handling."""
        mock_scraper_service.get_tradeable_markets = AsyncMock(
            side_effect=Exception("Service Error")
        )

        response = client.get("/markets/tradeable")

        assert response.status_code == 500

    def test_get_market_by_id(self, client, mock_scraper_service, sample_market):
        """Test getting a specific market by ID."""
        mock_scraper_service.get_market = AsyncMock(return_value=sample_market)

        response = client.get("/markets/market-001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "market-001"
        assert data["question"] == "Will BTC reach $100k?"

    def test_get_market_not_found(self, client, mock_scraper_service):
        """Test getting a non-existent market."""
        mock_scraper_service.get_market = AsyncMock(return_value=None)

        response = client.get("/markets/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_market_error(self, client, mock_scraper_service):
        """Test market by ID error handling."""
        mock_scraper_service.get_market = AsyncMock(
            side_effect=Exception("Database error")
        )

        response = client.get("/markets/market-001")

        assert response.status_code == 500


class TestFilterEndpoints:
    """Tests for filter endpoints."""

    def test_filter_markets_basic(self, client, mock_scraper_service, sample_market):
        """Test filtering markets with basic parameters."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            return_value=([sample_market], {"total": 10, "filtered": 1})
        )
        mock_scraper_service.apply_custom_filter = MagicMock(
            return_value=[sample_market]
        )

        response = client.post("/markets/filter?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "markets" in data
        assert "count" in data
        assert "filter_summary" in data
        assert "applied_filters" in data

    def test_filter_markets_with_category(
        self, client, mock_scraper_service, sample_market
    ):
        """Test filtering markets by category."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            return_value=([sample_market], {})
        )
        mock_scraper_service.apply_custom_filter = MagicMock(
            return_value=[sample_market]
        )

        response = client.post("/markets/filter?category=crypto&limit=10")

        assert response.status_code == 200
        mock_scraper_service.apply_custom_filter.assert_called_once()

    def test_filter_markets_with_min_volume(
        self, client, mock_scraper_service, sample_market
    ):
        """Test filtering markets by minimum volume."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            return_value=([sample_market], {})
        )
        mock_scraper_service.apply_custom_filter = MagicMock(
            return_value=[sample_market]
        )

        response = client.post("/markets/filter?min_volume=10000&limit=10")

        assert response.status_code == 200

    def test_filter_markets_with_max_time_hours(
        self, client, mock_scraper_service, sample_market
    ):
        """Test filtering markets by max time to resolution."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            return_value=([sample_market], {})
        )
        mock_scraper_service.apply_custom_filter = MagicMock(
            return_value=[sample_market]
        )

        response = client.post("/markets/filter?max_time_hours=2.0&limit=10")

        assert response.status_code == 200

    def test_filter_markets_error(self, client, mock_scraper_service):
        """Test filter endpoint error handling."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            side_effect=Exception("Filter Error")
        )

        response = client.post("/markets/filter")

        assert response.status_code == 500


class TestSummaryEndpoints:
    """Tests for summary endpoints."""

    def test_get_markets_summary(self, client, mock_scraper_service, sample_market):
        """Test getting markets summary."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            return_value=([sample_market], {"total": 100, "filtered": 50})
        )

        response = client.get("/markets/summary")

        assert response.status_code == 200
        data = response.json()
        assert "average_volume" in data
        assert "average_liquidity" in data
        assert "categories" in data

    def test_get_markets_summary_empty(self, client, mock_scraper_service):
        """Test getting summary with no markets."""
        mock_scraper_service.get_filtered_markets = AsyncMock(return_value=([], {}))

        response = client.get("/markets/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["average_volume"] == 0
        assert data["average_liquidity"] == 0
        assert data["categories"] == []

    def test_get_markets_summary_error(self, client, mock_scraper_service):
        """Test summary endpoint error handling."""
        mock_scraper_service.get_filtered_markets = AsyncMock(
            side_effect=Exception("Summary Error")
        )

        response = client.get("/markets/summary")

        assert response.status_code == 500


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_filter_config(self, client):
        """Test getting filter configuration."""
        response = client.get("/filters/config")

        assert response.status_code == 200
        data = response.json()
        assert "min_volume" in data
        assert "max_time_to_resolution_hours" in data
        assert "min_liquidity" in data
        assert "excluded_categories" in data
        assert "min_price" in data
        assert "max_price" in data
