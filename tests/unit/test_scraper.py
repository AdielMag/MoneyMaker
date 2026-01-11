"""
Unit tests for scraper service.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.scraper.service import ScraperService, get_scraper_service
from shared.models import Market, MarketOutcome


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.market_filters = MagicMock()
    settings.market_filters.min_volume = 1000
    settings.market_filters.max_time_to_resolution_hours = 1.0
    settings.market_filters.min_liquidity = 500
    settings.market_filters.excluded_categories = ["sports", "entertainment"]
    settings.market_filters.min_price = 0.05
    settings.market_filters.max_price = 0.95
    return settings


@pytest.fixture
def sample_markets():
    """Create sample markets for testing."""
    return [
        Market(
            id="market-001",
            question="Test market 1",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=5000,
            liquidity=2500,
            outcomes=[
                MarketOutcome(name="Yes", price=0.40),
                MarketOutcome(name="No", price=0.60),
            ],
        ),
        Market(
            id="market-002",
            question="Test market 2",
            category="politics",
            end_date=datetime.utcnow() + timedelta(hours=2),
            volume=10000,
            liquidity=5000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.30),
                MarketOutcome(name="No", price=0.70),
            ],
        ),
    ]


class TestScraperService:
    """Tests for ScraperService."""

    @pytest.mark.asyncio
    async def test_get_markets(self, mock_settings, sample_markets):
        """Test fetching markets."""
        mock_client = MagicMock()
        mock_client.get_markets = AsyncMock(return_value=sample_markets)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        service = ScraperService(
            polymarket_client=mock_client,
            settings=mock_settings,
        )

        markets = await service.get_markets(limit=10)

        assert len(markets) == 2
        mock_client.get_markets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_filtered_markets(self, mock_settings, sample_markets):
        """Test fetching and filtering markets."""
        mock_client = MagicMock()
        mock_client.get_markets = AsyncMock(return_value=sample_markets)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        service = ScraperService(
            polymarket_client=mock_client,
            settings=mock_settings,
        )

        filtered, summary = await service.get_filtered_markets(limit=10)

        # market-002 should be filtered (time > 1 hour)
        assert len(filtered) == 1
        assert filtered[0].id == "market-001"

    @pytest.mark.asyncio
    async def test_get_tradeable_markets(self, mock_settings, sample_markets):
        """Test getting tradeable markets sorted by volume."""
        mock_client = MagicMock()
        mock_client.get_markets = AsyncMock(return_value=sample_markets)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        service = ScraperService(
            polymarket_client=mock_client,
            settings=mock_settings,
        )

        tradeable = await service.get_tradeable_markets(max_markets=5)

        # Should return filtered markets
        assert len(tradeable) <= 5

    def test_apply_custom_filter_category(self, mock_settings, sample_markets):
        """Test custom filter by category."""
        service = ScraperService(settings=mock_settings)

        filtered = service.apply_custom_filter(
            sample_markets,
            category="crypto",
        )

        assert len(filtered) == 1
        assert filtered[0].category == "crypto"

    def test_apply_custom_filter_volume(self, mock_settings, sample_markets):
        """Test custom filter by volume."""
        service = ScraperService(settings=mock_settings)

        filtered = service.apply_custom_filter(
            sample_markets,
            min_volume=8000,
        )

        assert len(filtered) == 1
        assert filtered[0].volume >= 8000


class TestGetScraperService:
    """Tests for factory function."""

    def test_get_scraper_service(self):
        """Test factory creates service."""
        with patch("services.scraper.service.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock()

            service = get_scraper_service()

            assert isinstance(service, ScraperService)
