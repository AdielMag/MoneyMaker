"""
End-to-end tests for the discovery workflow.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.orchestrator.workflows import DiscoveryWorkflow
from shared.models import (
    AIAnalysisResult,
    AISuggestion,
    Market,
    MarketOutcome,
    TradingMode,
    Wallet,
)


@pytest.fixture
def e2e_settings():
    """Create settings for e2e tests."""
    settings = MagicMock()
    settings.real_money_enabled = False
    settings.fake_money_enabled = True
    settings.trading = MagicMock()
    settings.trading.min_balance_to_trade = 10.0
    settings.trading.max_bet_amount = 50.0
    settings.trading.max_positions = 5
    settings.trading.sell_thresholds = MagicMock()
    settings.trading.sell_thresholds.stop_loss_percent = -15.0
    settings.trading.sell_thresholds.take_profit_percent = 30.0
    settings.ai = MagicMock()
    settings.ai.max_suggestions = 3
    settings.ai.confidence_threshold = 0.7
    settings.market_filters = MagicMock()
    settings.market_filters.min_volume = 1000
    settings.market_filters.max_time_to_resolution_hours = 1.0
    settings.market_filters.min_liquidity = 500
    settings.market_filters.excluded_categories = ["sports"]
    settings.market_filters.min_price = 0.05
    settings.market_filters.max_price = 0.95
    settings.get_active_mode = MagicMock(return_value="fake")
    return settings


@pytest.fixture
def mock_markets():
    """Create mock markets for e2e tests."""
    return [
        Market(
            id="btc-100k",
            question="Will BTC reach $100k by end of day?",
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
            id="eth-flip",
            question="Will ETH flip BTC market cap?",
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
            id="fed-rate",
            question="Will Fed cut rates today?",
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
def mock_ai_suggestions():
    """Create mock AI suggestions."""
    return AIAnalysisResult(
        suggestions=[
            AISuggestion(
                market_id="btc-100k",
                market_question="Will BTC reach $100k by end of day?",
                recommended_outcome="Yes",
                confidence=0.82,
                reasoning="Strong bullish momentum",
                suggested_position_size=0.1,
            ),
            AISuggestion(
                market_id="fed-rate",
                market_question="Will Fed cut rates today?",
                recommended_outcome="No",
                confidence=0.90,
                reasoning="No scheduled announcement",
                suggested_position_size=0.15,
            ),
        ],
        markets_analyzed=3,
        overall_market_sentiment="bullish",
    )


@pytest.mark.e2e
class TestDiscoveryWorkflowE2E:
    """End-to-end tests for discovery workflow."""

    @pytest.mark.asyncio
    async def test_complete_discovery_flow_fake_money(
        self, e2e_settings, mock_markets, mock_ai_suggestions
    ):
        """Test complete discovery workflow with fake money."""
        # Create mock services
        mock_polymarket = MagicMock()
        mock_polymarket.get_markets = AsyncMock(return_value=mock_markets)
        mock_polymarket.__aenter__ = AsyncMock(return_value=mock_polymarket)
        mock_polymarket.__aexit__ = AsyncMock(return_value=None)

        mock_gemini = MagicMock()
        mock_gemini.analyze_markets = AsyncMock(return_value=mock_ai_suggestions)

        mock_wallet = Wallet(wallet_id="test", balance=1000.0)
        mock_firestore = MagicMock()
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)
        mock_firestore.get_wallet = AsyncMock(return_value=mock_wallet)
        mock_firestore.update_wallet_balance = AsyncMock(return_value=mock_wallet)
        mock_firestore.create_transaction = AsyncMock()
        mock_firestore.create_position = AsyncMock()
        mock_firestore.get_workflow_state = AsyncMock(return_value=None)
        mock_firestore.update_workflow_state = AsyncMock()

        # Create services with mocks
        from services.ai_suggester.service import AISuggesterService
        from services.scraper.service import ScraperService
        from services.trader.service import TraderService

        scraper = ScraperService(
            polymarket_client=mock_polymarket,
            settings=e2e_settings,
        )

        ai_suggester = AISuggesterService(
            gemini_client=mock_gemini,
            settings=e2e_settings,
        )

        trader = TraderService(
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        # Create workflow
        workflow = DiscoveryWorkflow(
            scraper_service=scraper,
            ai_service=ai_suggester,
            trader_service=trader,
            settings=e2e_settings,
        )

        # Run workflow
        result = await workflow.run(TradingMode.FAKE)

        # Verify results
        assert result.workflow_id == "discovery"
        assert result.mode == TradingMode.FAKE
        assert result.markets_analyzed > 0
        assert result.suggestions_generated > 0
        # Orders may or may not be placed depending on should_trade logic
        assert len(result.errors) == 0 or result.success

    @pytest.mark.asyncio
    async def test_discovery_insufficient_balance(self, e2e_settings):
        """Test discovery workflow with insufficient balance."""
        mock_wallet = Wallet(wallet_id="test", balance=5.0)  # Below minimum
        mock_firestore = MagicMock()
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)
        mock_firestore.get_wallet = AsyncMock(return_value=mock_wallet)

        from services.trader.service import TraderService

        trader = TraderService(
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        workflow = DiscoveryWorkflow(
            scraper_service=MagicMock(),
            ai_service=MagicMock(),
            trader_service=trader,
            settings=e2e_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is False
        assert any("balance" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_discovery_no_tradeable_markets(self, e2e_settings):
        """Test discovery when no markets pass filters."""
        mock_polymarket = MagicMock()
        mock_polymarket.get_markets = AsyncMock(return_value=[])
        mock_polymarket.__aenter__ = AsyncMock(return_value=mock_polymarket)
        mock_polymarket.__aexit__ = AsyncMock(return_value=None)

        mock_wallet = Wallet(wallet_id="test", balance=1000.0)
        mock_firestore = MagicMock()
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)
        mock_firestore.get_wallet = AsyncMock(return_value=mock_wallet)

        from services.scraper.service import ScraperService
        from services.trader.service import TraderService

        scraper = ScraperService(
            polymarket_client=mock_polymarket,
            settings=e2e_settings,
        )

        trader = TraderService(
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        workflow = DiscoveryWorkflow(
            scraper_service=scraper,
            ai_service=MagicMock(),
            trader_service=trader,
            settings=e2e_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.markets_analyzed == 0
        assert result.orders_placed == 0
