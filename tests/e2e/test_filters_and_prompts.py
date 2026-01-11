"""
End-to-end tests for filters and prompts modules.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

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
def valid_market():
    """Create a valid market that passes all filters."""
    return Market(
        id="market-001",
        question="Will BTC reach $100k?",
        category="crypto",
        end_date=datetime.utcnow() + timedelta(minutes=30),
        volume=50000,
        liquidity=25000,
        outcomes=[
            MarketOutcome(name="Yes", price=0.35),
            MarketOutcome(name="No", price=0.65),
        ],
    )


@pytest.fixture
def markets_for_filtering():
    """Create various markets for filter testing."""
    return [
        # Valid market - passes all filters
        Market(
            id="valid-001",
            question="Will BTC reach $100k?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
        # Low volume - should fail volume filter
        Market(
            id="low-volume-001",
            question="Test market?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=500,  # Below min_volume
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
        # Excluded category - should fail category filter
        Market(
            id="sports-001",
            question="Who will win the game?",
            category="sports",  # Excluded
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Team A", price=0.35),
                MarketOutcome(name="Team B", price=0.65),
            ],
        ),
        # Too far in future - should fail time filter
        Market(
            id="far-future-001",
            question="Long term market?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(hours=5),  # > 1 hour
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
        # Low liquidity - should fail liquidity filter
        Market(
            id="low-liquidity-001",
            question="Illiquid market?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=50000,
            liquidity=100,  # Below min_liquidity
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
        # Extreme price - should fail price filter
        Market(
            id="extreme-price-001",
            question="Near certain market?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.98),  # Above max_price
                MarketOutcome(name="No", price=0.02),
            ],
        ),
        # Low price - should fail price filter
        Market(
            id="low-price-001",
            question="Very unlikely market?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.02),  # Below min_price
                MarketOutcome(name="No", price=0.98),
            ],
        ),
        # Past end date - should fail time filter
        Market(
            id="past-001",
            question="Past market?",
            category="crypto",
            end_date=datetime.utcnow() - timedelta(hours=1),  # In past
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
    ]


@pytest.mark.e2e
class TestMarketFilterE2E:
    """End-to-end tests for market filter."""

    def test_filter_passes_valid_market(self, mock_settings, valid_market):
        """Test that valid market passes filters."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        result = filter.filter_market(valid_market)

        assert result.passed is True
        assert result.market.id == "market-001"

    def test_filter_rejects_low_volume(self, mock_settings, markets_for_filtering):
        """Test that low volume market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        low_volume_market = markets_for_filtering[1]
        result = filter.filter_market(low_volume_market)

        assert result.passed is False
        assert "volume" in result.reason.lower()

    def test_filter_rejects_excluded_category(self, mock_settings, markets_for_filtering):
        """Test that excluded category market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        sports_market = markets_for_filtering[2]
        result = filter.filter_market(sports_market)

        assert result.passed is False
        assert "category" in result.reason.lower()

    def test_filter_rejects_far_future(self, mock_settings, markets_for_filtering):
        """Test that far future market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        far_future_market = markets_for_filtering[3]
        result = filter.filter_market(far_future_market)

        assert result.passed is False
        assert "time" in result.reason.lower()

    def test_filter_rejects_low_liquidity(self, mock_settings, markets_for_filtering):
        """Test that low liquidity market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        low_liquidity_market = markets_for_filtering[4]
        result = filter.filter_market(low_liquidity_market)

        assert result.passed is False
        assert "liquidity" in result.reason.lower()

    def test_filter_rejects_extreme_price(self, mock_settings, markets_for_filtering):
        """Test that extreme price market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        extreme_price_market = markets_for_filtering[5]
        result = filter.filter_market(extreme_price_market)

        assert result.passed is False
        assert "price" in result.reason.lower()

    def test_filter_rejects_low_price(self, mock_settings, markets_for_filtering):
        """Test that low price market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        low_price_market = markets_for_filtering[6]
        result = filter.filter_market(low_price_market)

        assert result.passed is False
        assert "price" in result.reason.lower()

    def test_filter_rejects_past_market(self, mock_settings, markets_for_filtering):
        """Test that past market is rejected."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        past_market = markets_for_filtering[7]
        result = filter.filter_market(past_market)

        assert result.passed is False

    def test_filter_markets_batch(self, mock_settings, markets_for_filtering):
        """Test filtering multiple markets."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        passed, results = filter.filter_markets(markets_for_filtering)

        # Only the first market should pass
        assert len(passed) == 1
        assert passed[0].id == "valid-001"
        assert len(results) == len(markets_for_filtering)

    def test_filter_summary(self, mock_settings, markets_for_filtering):
        """Test getting filter summary."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)
        _, results = filter.filter_markets(markets_for_filtering)
        summary = filter.get_filter_summary(results)

        assert "total_markets" in summary
        assert "passed" in summary
        assert "filtered_out" in summary
        assert summary["total_markets"] == len(markets_for_filtering)
        assert summary["passed"] == 1

    def test_individual_filter_checks(self, mock_settings, valid_market):
        """Test individual filter check methods."""
        from services.scraper.filters import MarketFilter

        filter = MarketFilter(mock_settings)

        # Test _check_volume
        result = filter._check_volume(valid_market)
        assert result.passed is True

        # Test _check_category
        result = filter._check_category(valid_market)
        assert result.passed is True

        # Test _check_liquidity
        result = filter._check_liquidity(valid_market)
        assert result.passed is True

        # Test _check_time_to_resolution
        result = filter._check_time_to_resolution(valid_market)
        assert result.passed is True

        # Test _check_price_range
        result = filter._check_price_range(valid_market)
        assert result.passed is True


@pytest.mark.e2e
class TestPromptBuilderE2E:
    """End-to-end tests for prompt builder."""

    def test_build_analysis_prompt(self, valid_market):
        """Test building analysis prompt."""
        from services.ai_suggester.prompts import PromptBuilder

        prompt = PromptBuilder.build_analysis_prompt([valid_market])

        assert valid_market.question in prompt
        assert "market-001" in prompt

    def test_build_insight_prompt(self, valid_market):
        """Test building insight prompt."""
        from services.ai_suggester.prompts import PromptBuilder

        prompt = PromptBuilder.build_insight_prompt(valid_market)

        assert valid_market.question in prompt

    def test_build_risk_prompt(self, valid_market):
        """Test building risk assessment prompt."""
        from services.ai_suggester.prompts import PromptBuilder

        prompt = PromptBuilder.build_risk_prompt(
            market=valid_market,
            position_size=50.0,
            balance=500.0,
            outcome="Yes",
        )

        assert valid_market.question in prompt
        assert "50" in prompt
        assert "500" in prompt

    def test_format_market_for_prompt(self, valid_market):
        """Test formatting single market for prompt."""
        from services.ai_suggester.prompts import PromptBuilder

        # Using the private method _format_markets
        formatted = PromptBuilder._format_markets([valid_market])

        assert valid_market.id in formatted
        assert valid_market.question in formatted
        assert "crypto" in formatted

    def test_format_markets_for_prompt(self, markets_for_filtering):
        """Test formatting multiple markets for prompt."""
        from services.ai_suggester.prompts import PromptBuilder

        formatted = PromptBuilder._format_markets(markets_for_filtering[:3])

        # Should include all three markets
        assert "valid-001" in formatted
        assert "low-volume-001" in formatted
        assert "sports-001" in formatted


@pytest.mark.e2e
class TestModelHelpersE2E:
    """End-to-end tests for model helper methods."""

    def test_market_compute_time_to_resolution(self):
        """Test computing time to resolution."""
        market = Market(
            id="test",
            question="Test?",
            category="test",
            end_date=datetime.utcnow() + timedelta(hours=2),
            volume=1000,
            liquidity=500,
            outcomes=[],
        )

        time_hours = market.compute_time_to_resolution()
        assert 1.9 < time_hours < 2.1  # Allow small variance

    def test_market_compute_time_to_resolution_past(self):
        """Test computing time to resolution for past market."""
        market = Market(
            id="test",
            question="Test?",
            category="test",
            end_date=datetime.utcnow() - timedelta(hours=1),
            volume=1000,
            liquidity=500,
            outcomes=[],
        )

        time_hours = market.compute_time_to_resolution()
        # Past markets return 0 (not negative) per the implementation
        assert time_hours == 0.0

    def test_position_calculate_pnl(self):
        """Test calculating PnL."""
        from shared.models import Position, TradingMode

        position = Position(
            id="test",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.39,
            quantity=100,
            entry_value=30.0,
            current_value=39.0,
            mode=TradingMode.FAKE,
        )

        pnl = position.calculate_pnl()
        # (0.39 - 0.30) / 0.30 * 100 = 30%
        assert abs(pnl - 30.0) < 0.01  # Allow for floating point error

    def test_ai_analysis_result_get_high_confidence(self):
        """Test getting high confidence suggestions."""
        from shared.models import AIAnalysisResult, AISuggestion

        result = AIAnalysisResult(
            suggestions=[
                AISuggestion(
                    market_id="m1",
                    market_question="Test?",
                    recommended_outcome="Yes",
                    confidence=0.9,
                    reasoning="High confidence",
                ),
                AISuggestion(
                    market_id="m2",
                    market_question="Test?",
                    recommended_outcome="Yes",
                    confidence=0.5,
                    reasoning="Low confidence",
                ),
            ],
            markets_analyzed=2,
        )

        high_conf = result.get_high_confidence_suggestions(0.7)
        assert len(high_conf) == 1
        assert high_conf[0].market_id == "m1"

    def test_ai_analysis_result_get_top_suggestions(self):
        """Test getting top suggestions."""
        from shared.models import AIAnalysisResult, AISuggestion

        result = AIAnalysisResult(
            suggestions=[
                AISuggestion(
                    market_id="m1",
                    market_question="Test?",
                    recommended_outcome="Yes",
                    confidence=0.7,
                    reasoning="Medium",
                ),
                AISuggestion(
                    market_id="m2",
                    market_question="Test?",
                    recommended_outcome="Yes",
                    confidence=0.9,
                    reasoning="High",
                ),
                AISuggestion(
                    market_id="m3",
                    market_question="Test?",
                    recommended_outcome="Yes",
                    confidence=0.8,
                    reasoning="Medium-high",
                ),
            ],
            markets_analyzed=3,
        )

        top = result.get_top_suggestions(2)
        assert len(top) == 2
        assert top[0].confidence == 0.9  # Highest first
        assert top[1].confidence == 0.8
