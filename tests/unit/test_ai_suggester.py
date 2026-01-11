"""
Unit tests for AI suggester service.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.ai_suggester.prompts import PromptBuilder
from services.ai_suggester.service import AISuggesterService
from shared.models import AIAnalysisResult, AISuggestion, Market, MarketOutcome, RiskLevel


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.ai = MagicMock()
    settings.ai.model = "gemini-1.5-pro"
    settings.ai.max_suggestions = 5
    settings.ai.confidence_threshold = 0.7
    settings.ai.temperature = 0.3
    settings.trading = MagicMock()
    settings.trading.max_bet_amount = 50.0
    settings.trading.min_balance_to_trade = 10.0
    return settings


@pytest.fixture
def sample_markets():
    """Create sample markets for testing."""
    return [
        Market(
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
        ),
    ]


@pytest.fixture
def sample_suggestion():
    """Create a sample AI suggestion."""
    return AISuggestion(
        market_id="market-001",
        market_question="Will BTC reach $100k?",
        recommended_outcome="Yes",
        confidence=0.85,
        reasoning="Strong momentum",
        suggested_position_size=0.1,
        risk_level=RiskLevel.MEDIUM,
    )


class TestAISuggesterService:
    """Tests for AISuggesterService."""

    @pytest.mark.asyncio
    async def test_analyze_markets_empty(self, mock_settings):
        """Test analyzing empty markets list."""
        service = AISuggesterService(settings=mock_settings)

        result = await service.analyze_markets([])

        assert len(result.suggestions) == 0
        assert result.markets_analyzed == 0

    @pytest.mark.asyncio
    async def test_analyze_markets_success(self, mock_settings, sample_markets):
        """Test successful market analysis."""
        mock_client = MagicMock()
        mock_client.analyze_markets = AsyncMock(
            return_value=AIAnalysisResult(
                suggestions=[
                    AISuggestion(
                        market_id="market-001",
                        recommended_outcome="Yes",
                        confidence=0.85,
                    )
                ],
                markets_analyzed=1,
                overall_market_sentiment="bullish",
            )
        )

        service = AISuggesterService(
            gemini_client=mock_client,
            settings=mock_settings,
        )

        result = await service.analyze_markets(sample_markets)

        assert len(result.suggestions) == 1
        mock_client.analyze_markets.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_markets_filters_low_confidence(self, mock_settings, sample_markets):
        """Test that low confidence suggestions are filtered."""
        mock_client = MagicMock()
        mock_client.analyze_markets = AsyncMock(
            return_value=AIAnalysisResult(
                suggestions=[
                    AISuggestion(
                        market_id="market-001",
                        recommended_outcome="Yes",
                        confidence=0.5,  # Below threshold
                    )
                ],
                markets_analyzed=1,
            )
        )

        service = AISuggesterService(
            gemini_client=mock_client,
            settings=mock_settings,
        )

        result = await service.analyze_markets(sample_markets, confidence_threshold=0.7)

        assert len(result.suggestions) == 0

    @pytest.mark.asyncio
    async def test_should_trade_approved(self, mock_settings, sample_suggestion):
        """Test trade approval for valid suggestion."""
        service = AISuggesterService(settings=mock_settings)

        should_trade, reason, size = await service.should_trade(
            suggestion=sample_suggestion,
            wallet_balance=1000.0,
        )

        assert should_trade is True
        assert size > 0

    @pytest.mark.asyncio
    async def test_should_trade_low_confidence(self, mock_settings):
        """Test trade rejection for low confidence."""
        low_conf_suggestion = AISuggestion(
            market_id="market-001",
            recommended_outcome="Yes",
            confidence=0.5,  # Below threshold
        )

        service = AISuggesterService(settings=mock_settings)

        should_trade, reason, size = await service.should_trade(
            suggestion=low_conf_suggestion,
            wallet_balance=1000.0,
        )

        assert should_trade is False
        assert "below threshold" in reason

    @pytest.mark.asyncio
    async def test_should_trade_low_balance(self, mock_settings, sample_suggestion):
        """Test trade rejection for low balance."""
        service = AISuggesterService(settings=mock_settings)

        should_trade, reason, size = await service.should_trade(
            suggestion=sample_suggestion,
            wallet_balance=5.0,  # Below minimum
        )

        assert should_trade is False
        assert "below minimum" in reason

    def test_filter_suggestions_by_risk(self, mock_settings):
        """Test filtering suggestions by risk level."""
        suggestions = [
            AISuggestion(
                market_id="low-risk",
                recommended_outcome="Yes",
                confidence=0.9,
                risk_level=RiskLevel.LOW,
            ),
            AISuggestion(
                market_id="high-risk",
                recommended_outcome="Yes",
                confidence=0.8,
                risk_level=RiskLevel.HIGH,
            ),
        ]

        service = AISuggesterService(settings=mock_settings)
        filtered = service.filter_suggestions_by_risk(suggestions, max_risk_level="medium")

        assert len(filtered) == 1
        assert filtered[0].market_id == "low-risk"


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    def test_build_analysis_prompt(self, sample_markets):
        """Test building analysis prompt."""
        prompt = PromptBuilder.build_analysis_prompt(
            markets=sample_markets,
            max_suggestions=3,
            confidence_threshold=0.7,
        )

        assert "market-001" in prompt
        assert "Will BTC reach $100k?" in prompt
        assert "Maximum Suggestions: 3" in prompt
        assert "0.7" in prompt

    def test_build_analysis_prompt_empty(self):
        """Test building prompt with empty markets."""
        prompt = PromptBuilder.build_analysis_prompt(markets=[])

        assert "No markets provided" in prompt

    def test_build_insight_prompt(self, sample_markets):
        """Test building insight prompt."""
        prompt = PromptBuilder.build_insight_prompt(sample_markets[0])

        assert "Will BTC reach $100k?" in prompt
        assert "crypto" in prompt

    def test_build_risk_prompt(self, sample_markets):
        """Test building risk prompt."""
        prompt = PromptBuilder.build_risk_prompt(
            market=sample_markets[0],
            position_size=50.0,
            balance=1000.0,
            outcome="Yes",
        )

        assert "$50.00" in prompt
        assert "$1000.00" in prompt

    def test_format_markets(self, sample_markets):
        """Test market formatting for prompts."""
        formatted = PromptBuilder._format_markets(sample_markets)

        assert "Market 1" in formatted
        assert "market-001" in formatted
        assert "crypto" in formatted
