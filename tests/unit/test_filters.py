"""
Unit tests for market filtering logic.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services.scraper.filters import FilterResult, MarketFilter
from shared.models import Market, MarketOutcome


@pytest.fixture
def mock_settings():
    """Create mock settings for filter tests."""
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
def market_filter(mock_settings):
    """Create a MarketFilter instance."""
    return MarketFilter(settings=mock_settings)


@pytest.fixture
def valid_market():
    """Create a market that passes all filters."""
    return Market(
        id="valid-market",
        question="Will BTC reach $100k?",
        category="crypto",
        end_date=datetime.utcnow() + timedelta(minutes=30),
        volume=5000,
        liquidity=2500,
        outcomes=[
            MarketOutcome(name="Yes", price=0.40),
            MarketOutcome(name="No", price=0.60),
        ],
    )


class TestMarketFilter:
    """Tests for MarketFilter class."""

    def test_filter_valid_market(self, market_filter, valid_market):
        """Test that valid market passes all filters."""
        result = market_filter.filter_market(valid_market)

        assert result.passed is True
        assert result.market.passes_filter is True

    def test_filter_market_already_ended(self, market_filter):
        """Test market that has already ended."""
        market = Market(
            id="ended-market",
            question="Past event",
            end_date=datetime.utcnow() - timedelta(hours=1),
            volume=5000,
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "already ended" in result.reason

    def test_filter_market_too_far_future(self, market_filter):
        """Test market that resolves too far in future."""
        market = Market(
            id="future-market",
            question="Far future event",
            end_date=datetime.utcnow() + timedelta(hours=5),
            volume=5000,
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "exceeds maximum" in result.reason

    def test_filter_market_resolves_too_soon(self, market_filter):
        """Test market that resolves too soon (< 5 minutes)."""
        market = Market(
            id="soon-market",
            question="Imminent event",
            end_date=datetime.utcnow() + timedelta(minutes=2),
            volume=5000,
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "too soon" in result.reason

    def test_filter_market_low_volume(self, market_filter):
        """Test market with insufficient volume."""
        market = Market(
            id="low-volume-market",
            question="Low volume event",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=500,  # Below 1000 minimum
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "Volume" in result.reason

    def test_filter_market_low_liquidity(self, market_filter):
        """Test market with insufficient liquidity."""
        market = Market(
            id="low-liquidity-market",
            question="Low liquidity event",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=5000,
            liquidity=200,  # Below 500 minimum
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "Liquidity" in result.reason

    def test_filter_market_excluded_category(self, market_filter):
        """Test market with excluded category."""
        market = Market(
            id="sports-market",
            question="Sports event",
            category="sports",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=5000,
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "excluded" in result.reason

    def test_filter_market_extreme_prices(self, market_filter):
        """Test market with extreme outcome prices."""
        market = Market(
            id="extreme-price-market",
            question="Almost certain event",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=5000,
            liquidity=2500,
            outcomes=[
                MarketOutcome(name="Yes", price=0.99),  # Too extreme
                MarketOutcome(name="No", price=0.01),  # Too extreme
            ],
        )

        result = market_filter.filter_market(market)

        assert result.passed is False
        assert "extreme" in result.reason

    def test_filter_markets_multiple(self, market_filter, valid_market):
        """Test filtering multiple markets."""
        invalid_market = Market(
            id="invalid-market",
            question="Invalid",
            category="sports",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=5000,
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        markets = [valid_market, invalid_market]
        passing, results = market_filter.filter_markets(markets)

        assert len(passing) == 1
        assert passing[0].id == "valid-market"
        assert len(results) == 2

    def test_get_filter_summary(self, market_filter, valid_market):
        """Test filter summary generation."""
        invalid_market = Market(
            id="invalid-market",
            question="Invalid",
            category="sports",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=5000,
            liquidity=2500,
            outcomes=[MarketOutcome(name="Yes", price=0.50)],
        )

        _, results = market_filter.filter_markets([valid_market, invalid_market])
        summary = market_filter.get_filter_summary(results)

        assert summary["total_markets"] == 2
        assert summary["passed"] == 1
        assert summary["filtered_out"] == 1
        assert summary["pass_rate"] == 50.0


class TestFilterResult:
    """Tests for FilterResult dataclass."""

    def test_str_passed(self, valid_market):
        """Test string representation for passed result."""
        result = FilterResult(passed=True, market=valid_market)

        assert "PASS" in str(result)
        assert valid_market.id in str(result)

    def test_str_failed(self, valid_market):
        """Test string representation for failed result."""
        result = FilterResult(
            passed=False,
            market=valid_market,
            reason="Test reason",
        )

        assert "FAIL" in str(result)
        assert "Test reason" in str(result)
