"""
End-to-end tests for the Scraper service FastAPI endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import Market, MarketOutcome


@pytest.fixture
def mock_markets():
    """Create mock markets for testing."""
    return [
        Market(
            id="market-001",
            question="Will BTC reach $100k?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=45),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
        Market(
            id="market-002",
            question="Will ETH flip BTC?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=30000,
            liquidity=15000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.10),
                MarketOutcome(name="No", price=0.90),
            ],
        ),
        Market(
            id="market-003",
            question="Will Fed cut rates?",
            category="politics",
            end_date=datetime.utcnow() + timedelta(minutes=50),
            volume=100000,
            liquidity=50000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.15),
                MarketOutcome(name="No", price=0.85),
            ],
        ),
    ]


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.api = MagicMock()
    settings.api.cors_origins = ["*"]
    settings.market_filters = MagicMock()
    settings.market_filters.min_volume = 1000
    settings.market_filters.max_time_to_resolution_hours = 1.0
    settings.market_filters.min_liquidity = 500
    settings.market_filters.excluded_categories = ["sports"]
    settings.market_filters.min_price = 0.05
    settings.market_filters.max_price = 0.95
    return settings


@pytest.fixture
def mock_scraper_service(mock_markets):
    """Create mock scraper service."""
    service = MagicMock()
    service.get_markets = AsyncMock(return_value=mock_markets)
    service.get_filtered_markets = AsyncMock(
        return_value=(mock_markets, {"total_markets": 3, "passed": 3, "filtered_out": 0})
    )
    service.get_tradeable_markets = AsyncMock(return_value=mock_markets[:2])
    service.get_market = AsyncMock(return_value=mock_markets[0])
    service.apply_custom_filter = MagicMock(return_value=mock_markets[:1])
    return service


@pytest.mark.e2e
class TestScraperEndpointsE2E:
    """End-to-end tests for scraper endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings, mock_scraper_service):
        """Setup test fixtures."""
        with patch("services.scraper.main.get_settings", return_value=mock_settings):
            with patch("services.scraper.main.get_scraper_service", return_value=mock_scraper_service):
                with patch("services.scraper.main._scraper_service", None):
                    # Need to reimport to apply patches
                    from services.scraper import main
                    main._scraper_service = None
                    self.client = TestClient(main.app)
                    self.mock_service = mock_scraper_service
                    yield

    def test_health_check(self):
        """Test health endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_readiness_check(self):
        """Test readiness endpoint."""
        response = self.client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_get_markets_filtered(self):
        """Test getting filtered markets."""
        response = self.client.get("/markets?filtered=true&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["id"] == "market-001"

    def test_get_markets_unfiltered(self):
        """Test getting unfiltered markets."""
        response = self.client.get("/markets?filtered=false&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_tradeable_markets(self):
        """Test getting tradeable markets."""
        response = self.client.get("/markets/tradeable?max_markets=20")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_markets_summary(self, mock_markets):
        """Test getting markets summary."""
        response = self.client.get("/markets/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_markets" in data
        assert "average_volume" in data
        assert "average_liquidity" in data
        assert "categories" in data

    def test_get_market_by_id(self):
        """Test getting a single market by ID."""
        response = self.client.get("/markets/market-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "market-001"
        assert data["question"] == "Will BTC reach $100k?"

    def test_get_market_not_found(self):
        """Test getting a non-existent market."""
        self.mock_service.get_market = AsyncMock(return_value=None)
        response = self.client.get("/markets/non-existent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_filter_markets_with_custom_filters(self, mock_markets):
        """Test filtering markets with custom criteria."""
        response = self.client.post(
            "/markets/filter?category=crypto&min_volume=10000&max_time_hours=2.0&limit=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert "markets" in data
        assert "count" in data
        assert "filter_summary" in data
        assert "applied_filters" in data

    def test_get_filter_config(self, mock_settings):
        """Test getting filter configuration."""
        response = self.client.get("/filters/config")
        assert response.status_code == 200
        data = response.json()
        assert "min_volume" in data
        assert "max_time_to_resolution_hours" in data
        assert "min_liquidity" in data
        assert "excluded_categories" in data
        assert "min_price" in data
        assert "max_price" in data

    def test_get_markets_error_handling(self):
        """Test error handling for markets endpoint."""
        self.mock_service.get_filtered_markets = AsyncMock(side_effect=Exception("API Error"))
        response = self.client.get("/markets")
        assert response.status_code == 500
        assert "API Error" in response.json()["detail"]

    def test_get_tradeable_markets_error_handling(self):
        """Test error handling for tradeable markets endpoint."""
        self.mock_service.get_tradeable_markets = AsyncMock(side_effect=Exception("Connection failed"))
        response = self.client.get("/markets/tradeable")
        assert response.status_code == 500

    def test_filter_markets_error_handling(self):
        """Test error handling for filter markets endpoint."""
        self.mock_service.get_filtered_markets = AsyncMock(side_effect=Exception("Filter error"))
        response = self.client.post("/markets/filter?limit=10")
        assert response.status_code == 500

    def test_get_market_error_handling(self):
        """Test error handling for get market endpoint."""
        self.mock_service.get_market = AsyncMock(side_effect=Exception("Fetch failed"))
        response = self.client.get("/markets/market-001")
        assert response.status_code == 500
