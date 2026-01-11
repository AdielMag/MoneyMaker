"""
End-to-end integration tests for service modules.
Tests service layer functionality with mocked dependencies.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.models import (
    AIAnalysisResult,
    AISuggestion,
    Market,
    MarketOutcome,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    RiskLevel,
    TradingMode,
    Wallet,
    WorkflowState,
)


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
    ]


@pytest.fixture
def mock_settings():
    """Create mock settings."""
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
    settings.gcp_project_id = "test-project"
    settings.workflows_fake_money = MagicMock()
    settings.workflows_fake_money.initial_balance = 1000.0
    return settings


@pytest.mark.e2e
class TestScraperServiceE2E:
    """End-to-end tests for scraper service."""

    @pytest.fixture
    def mock_polymarket(self, mock_markets):
        """Create mock Polymarket client."""
        client = MagicMock()
        client.get_markets = AsyncMock(return_value=mock_markets)
        client.get_market = AsyncMock(return_value=mock_markets[0])
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.mark.asyncio
    async def test_get_markets(self, mock_settings, mock_polymarket, mock_markets):
        """Test getting markets."""
        from services.scraper.service import ScraperService

        service = ScraperService(
            polymarket_client=mock_polymarket,
            settings=mock_settings,
        )

        markets = await service.get_markets(limit=50)
        assert len(markets) == 2
        assert markets[0].id == "market-001"

    @pytest.mark.asyncio
    async def test_get_filtered_markets(self, mock_settings, mock_polymarket, mock_markets):
        """Test getting filtered markets."""
        from services.scraper.service import ScraperService

        service = ScraperService(
            polymarket_client=mock_polymarket,
            settings=mock_settings,
        )

        markets, summary = await service.get_filtered_markets(limit=50)
        assert "total_markets" in summary

    @pytest.mark.asyncio
    async def test_get_filtered_markets_empty(self, mock_settings):
        """Test getting filtered markets when none available."""
        from services.scraper.service import ScraperService

        mock_client = MagicMock()
        mock_client.get_markets = AsyncMock(return_value=[])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        service = ScraperService(
            polymarket_client=mock_client,
            settings=mock_settings,
        )

        markets, summary = await service.get_filtered_markets(limit=50)
        assert len(markets) == 0
        assert summary["total_markets"] == 0

    @pytest.mark.asyncio
    async def test_get_market(self, mock_settings, mock_polymarket, mock_markets):
        """Test getting a single market."""
        from services.scraper.service import ScraperService

        service = ScraperService(
            polymarket_client=mock_polymarket,
            settings=mock_settings,
        )

        market = await service.get_market("market-001")
        assert market is not None
        assert market.id == "market-001"

    @pytest.mark.asyncio
    async def test_get_tradeable_markets(self, mock_settings, mock_polymarket, mock_markets):
        """Test getting tradeable markets."""
        from services.scraper.service import ScraperService

        service = ScraperService(
            polymarket_client=mock_polymarket,
            settings=mock_settings,
        )

        markets = await service.get_tradeable_markets(max_markets=10)
        # Markets should be sorted by volume
        assert len(markets) <= 10

    def test_apply_custom_filter(self, mock_settings, mock_markets):
        """Test applying custom filters."""
        from services.scraper.service import ScraperService

        service = ScraperService(settings=mock_settings)

        # Filter by category
        result = service.apply_custom_filter(mock_markets, category="crypto")
        assert len(result) == 2

        # Filter by min volume
        result = service.apply_custom_filter(mock_markets, min_volume=40000)
        assert len(result) == 1

        # Filter by max time hours
        result = service.apply_custom_filter(mock_markets, max_time_hours=0.5)
        # Both markets are within 1 hour


@pytest.mark.e2e
class TestAISuggesterServiceE2E:
    """End-to-end tests for AI suggester service."""

    @pytest.fixture
    def mock_gemini(self):
        """Create mock Gemini client."""
        client = MagicMock()
        client.analyze_markets = AsyncMock(return_value=AIAnalysisResult(
            suggestions=[
                AISuggestion(
                    market_id="market-001",
                    market_question="Will BTC reach $100k?",
                    recommended_outcome="Yes",
                    confidence=0.85,
                    reasoning="Strong momentum",
                    suggested_position_size=0.1,
                    risk_level=RiskLevel.MEDIUM,
                ),
            ],
            markets_analyzed=1,
            overall_market_sentiment="bullish",
        ))
        client.get_market_insight = AsyncMock(return_value="BTC shows strong momentum")
        client.assess_risk = AsyncMock(return_value={
            "risk_score": 5,
            "risk_level": "medium",
            "concerns": [],
            "recommendation": "proceed",
        })
        return client

    @pytest.mark.asyncio
    async def test_analyze_markets(self, mock_settings, mock_gemini, mock_markets):
        """Test analyzing markets."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        result = await service.analyze_markets(mock_markets)
        assert result.markets_analyzed > 0

    @pytest.mark.asyncio
    async def test_analyze_markets_empty(self, mock_settings, mock_gemini):
        """Test analyzing empty markets list."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        result = await service.analyze_markets([])
        assert result.markets_analyzed == 0

    @pytest.mark.asyncio
    async def test_get_top_suggestions(self, mock_settings, mock_gemini, mock_markets):
        """Test getting top suggestions."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        suggestions = await service.get_top_suggestions(mock_markets, top_n=3)
        assert len(suggestions) <= 3

    @pytest.mark.asyncio
    async def test_get_market_insight(self, mock_settings, mock_gemini, mock_markets):
        """Test getting market insight."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        insight = await service.get_market_insight(mock_markets[0])
        assert insight is not None

    @pytest.mark.asyncio
    async def test_assess_trade_risk(self, mock_settings, mock_gemini, mock_markets):
        """Test assessing trade risk."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        assessment = await service.assess_trade_risk(
            market=mock_markets[0],
            position_size=25.0,
            wallet_balance=500.0,
        )
        assert "risk_score" in assessment

    @pytest.mark.asyncio
    async def test_should_trade_approved(self, mock_settings, mock_gemini):
        """Test trade approval logic - approved."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        suggestion = AISuggestion(
            market_id="market-001",
            market_question="Test?",
            recommended_outcome="Yes",
            confidence=0.85,
            reasoning="Test",
            suggested_position_size=0.1,
        )

        should_trade, reason, size = await service.should_trade(
            suggestion=suggestion,
            wallet_balance=500.0,
        )
        assert should_trade is True

    @pytest.mark.asyncio
    async def test_should_trade_low_confidence(self, mock_settings, mock_gemini):
        """Test trade approval logic - low confidence."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        suggestion = AISuggestion(
            market_id="market-001",
            market_question="Test?",
            recommended_outcome="Yes",
            confidence=0.5,  # Below threshold
            reasoning="Test",
            suggested_position_size=0.1,
        )

        should_trade, reason, size = await service.should_trade(
            suggestion=suggestion,
            wallet_balance=500.0,
        )
        assert should_trade is False
        assert "below threshold" in reason.lower()

    @pytest.mark.asyncio
    async def test_should_trade_low_balance(self, mock_settings, mock_gemini):
        """Test trade approval logic - low balance."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        suggestion = AISuggestion(
            market_id="market-001",
            market_question="Test?",
            recommended_outcome="Yes",
            confidence=0.85,
            reasoning="Test",
            suggested_position_size=0.1,
        )

        should_trade, reason, size = await service.should_trade(
            suggestion=suggestion,
            wallet_balance=5.0,  # Below minimum
        )
        assert should_trade is False
        assert "below minimum" in reason.lower()

    def test_filter_suggestions_by_risk(self, mock_settings, mock_gemini):
        """Test filtering suggestions by risk level."""
        from services.ai_suggester.service import AISuggesterService

        service = AISuggesterService(
            gemini_client=mock_gemini,
            settings=mock_settings,
        )

        suggestions = [
            AISuggestion(
                market_id="m1",
                market_question="Test?",
                recommended_outcome="Yes",
                confidence=0.85,
                reasoning="Test",
                risk_level=RiskLevel.LOW,
            ),
            AISuggestion(
                market_id="m2",
                market_question="Test?",
                recommended_outcome="Yes",
                confidence=0.85,
                reasoning="Test",
                risk_level=RiskLevel.HIGH,
            ),
        ]

        filtered = service.filter_suggestions_by_risk(suggestions, max_risk_level="medium")
        assert len(filtered) == 1
        assert filtered[0].risk_level == RiskLevel.LOW


@pytest.mark.e2e
class TestTraderServiceE2E:
    """End-to-end tests for trader service."""

    @pytest.fixture
    def mock_firestore(self):
        """Create mock Firestore client."""
        client = MagicMock()
        client.get_or_create_wallet = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=500.0,
        ))
        client.get_wallet = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=500.0,
        ))
        client.update_wallet_balance = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=475.0,
        ))
        client.create_transaction = AsyncMock()
        client.create_position = AsyncMock()
        client.delete_position = AsyncMock(return_value=True)
        client.get_open_positions = AsyncMock(return_value=[])
        return client

    @pytest.mark.asyncio
    async def test_get_balance_fake(self, mock_settings, mock_firestore):
        """Test getting fake balance."""
        from services.trader.service import TraderService

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        balance = await service.get_balance(TradingMode.FAKE)
        assert balance == 500.0

    @pytest.mark.asyncio
    async def test_can_trade_sufficient_balance(self, mock_settings, mock_firestore):
        """Test can trade with sufficient balance."""
        from services.trader.service import TraderService

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        can_trade, reason = await service.can_trade(TradingMode.FAKE, 25.0)
        assert can_trade is True

    @pytest.mark.asyncio
    async def test_can_trade_insufficient_balance(self, mock_settings, mock_firestore):
        """Test can trade with insufficient balance."""
        from services.trader.service import TraderService

        mock_firestore.get_or_create_wallet = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=5.0,  # Below minimum
        ))

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        can_trade, reason = await service.can_trade(TradingMode.FAKE, 25.0)
        assert can_trade is False

    @pytest.mark.asyncio
    async def test_place_buy_order_fake(self, mock_settings, mock_firestore):
        """Test placing fake buy order."""
        from services.trader.service import TraderService

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        order = await service.place_buy_order(
            market_id="market-001",
            outcome="Yes",
            amount=25.0,
            price=0.35,
            mode=TradingMode.FAKE,
        )

        assert order.market_id == "market-001"
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_place_sell_order_fake(self, mock_settings, mock_firestore):
        """Test placing fake sell order."""
        from services.trader.service import TraderService

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        position = Position(
            id="pos-001",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.42,
            quantity=100,
            entry_value=30.0,
            current_value=42.0,
            pnl_percent=40.0,
            mode=TradingMode.FAKE,
        )

        order = await service.place_sell_order(position)

        assert order.market_id == "market-001"
        assert order.side == OrderSide.SELL
        assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_execute_suggestion(self, mock_settings, mock_firestore):
        """Test executing AI suggestion."""
        from services.trader.service import TraderService

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        suggestion = AISuggestion(
            market_id="market-001",
            market_question="Will BTC reach $100k?",
            recommended_outcome="Yes",
            confidence=0.85,
            reasoning="Strong momentum",
            suggested_position_size=0.1,
        )

        order = await service.execute_suggestion(
            suggestion=suggestion,
            position_size=25.0,
            mode=TradingMode.FAKE,
        )

        assert order.market_id == "market-001"


@pytest.mark.e2e
class TestMonitorServiceE2E:
    """End-to-end tests for monitor service."""

    @pytest.fixture
    def mock_firestore_with_positions(self):
        """Create mock Firestore with positions."""
        client = MagicMock()
        positions = [
            Position(
                id="pos-001",
                market_id="market-001",
                outcome="Yes",
                entry_price=0.30,
                current_price=0.42,
                quantity=100,
                entry_value=30.0,
                current_value=42.0,
                pnl_percent=40.0,  # Above take profit
                mode=TradingMode.FAKE,
            ),
            Position(
                id="pos-002",
                market_id="market-002",
                outcome="No",
                entry_price=0.50,
                current_price=0.40,
                quantity=80,
                entry_value=40.0,
                current_value=32.0,
                pnl_percent=-20.0,  # Below stop loss
                mode=TradingMode.FAKE,
            ),
        ]
        client.get_open_positions = AsyncMock(return_value=positions)
        client.get_or_create_wallet = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=500.0,
        ))
        client.update_wallet_balance = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=574.0,
        ))
        client.create_transaction = AsyncMock()
        client.delete_position = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_trader(self):
        """Create mock trader service."""
        trader = MagicMock()
        trader.place_sell_order = AsyncMock(return_value=Order(
            id="order-001",
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.SELL,
            price=0.42,
            quantity=100,
            total_value=42.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        ))
        return trader

    @pytest.mark.asyncio
    async def test_get_positions(self, mock_settings, mock_firestore_with_positions):
        """Test getting positions."""
        from services.monitor.service import MonitorService

        service = MonitorService(
            firestore_client=mock_firestore_with_positions,
            settings=mock_settings,
        )

        positions = await service.get_positions(TradingMode.FAKE)
        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_check_position_take_profit(self, mock_settings, mock_firestore_with_positions):
        """Test checking position - take profit triggered."""
        from services.monitor.service import MonitorService

        service = MonitorService(
            firestore_client=mock_firestore_with_positions,
            settings=mock_settings,
        )

        position = Position(
            id="pos-001",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.42,
            quantity=100,
            entry_value=30.0,
            current_value=42.0,
            pnl_percent=40.0,
            mode=TradingMode.FAKE,
        )

        should_sell, action, reason = await service.check_position(position)
        assert should_sell is True
        assert action == "take_profit"

    @pytest.mark.asyncio
    async def test_check_position_stop_loss(self, mock_settings, mock_firestore_with_positions):
        """Test checking position - stop loss triggered."""
        from services.monitor.service import MonitorService

        service = MonitorService(
            firestore_client=mock_firestore_with_positions,
            settings=mock_settings,
        )

        position = Position(
            id="pos-002",
            market_id="market-002",
            outcome="No",
            entry_price=0.50,
            current_price=0.40,
            quantity=80,
            entry_value=40.0,
            current_value=32.0,
            pnl_percent=-20.0,
            mode=TradingMode.FAKE,
        )

        should_sell, action, reason = await service.check_position(position)
        assert should_sell is True
        assert action == "stop_loss"

    @pytest.mark.asyncio
    async def test_check_position_hold(self, mock_settings, mock_firestore_with_positions):
        """Test checking position - hold."""
        from services.monitor.service import MonitorService

        service = MonitorService(
            firestore_client=mock_firestore_with_positions,
            settings=mock_settings,
        )

        position = Position(
            id="pos-003",
            market_id="market-003",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.52,
            quantity=100,
            entry_value=50.0,
            current_value=52.0,
            pnl_percent=4.0,  # Within thresholds
            mode=TradingMode.FAKE,
        )

        should_sell, action, reason = await service.check_position(position)
        assert should_sell is False
        assert action == "hold"

    @pytest.mark.asyncio
    async def test_get_positions_summary(self, mock_settings, mock_firestore_with_positions):
        """Test getting positions summary."""
        from services.monitor.service import MonitorService

        service = MonitorService(
            firestore_client=mock_firestore_with_positions,
            settings=mock_settings,
        )

        summary = await service.get_positions_summary(TradingMode.FAKE)
        assert "count" in summary
        assert summary["count"] == 2


@pytest.mark.e2e
class TestOrchestratorServiceE2E:
    """End-to-end tests for orchestrator service."""

    @pytest.fixture
    def mock_all_services(self, mock_settings):
        """Create all mock services."""
        scraper = MagicMock()
        scraper.get_filtered_markets = AsyncMock(return_value=([], {}))
        scraper.get_markets = AsyncMock(return_value=[])

        ai = MagicMock()
        ai.analyze_markets = AsyncMock(return_value=AIAnalysisResult(
            suggestions=[],
            markets_analyzed=0,
        ))

        trader = MagicMock()
        trader.get_balance = AsyncMock(return_value=500.0)
        trader.can_trade = AsyncMock(return_value=(True, "OK"))

        monitor = MagicMock()
        monitor.get_positions = AsyncMock(return_value=[])
        monitor.update_position_prices = AsyncMock(return_value=[])
        monitor.get_positions_summary = AsyncMock(return_value={"count": 0})

        firestore = MagicMock()
        firestore.get_workflow_state = AsyncMock(return_value=None)
        firestore.update_workflow_state = AsyncMock()
        firestore.toggle_workflow = AsyncMock(return_value=WorkflowState(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            enabled=True,
        ))
        firestore.get_or_create_wallet = AsyncMock(return_value=Wallet(
            wallet_id="default",
            balance=500.0,
        ))

        return {
            "scraper": scraper,
            "ai": ai,
            "trader": trader,
            "monitor": monitor,
            "firestore": firestore,
        }

    @pytest.mark.asyncio
    async def test_get_system_status(self, mock_settings, mock_all_services):
        """Test getting system status."""
        from services.orchestrator.service import OrchestratorService

        service = OrchestratorService(
            scraper_service=mock_all_services["scraper"],
            ai_service=mock_all_services["ai"],
            trader_service=mock_all_services["trader"],
            monitor_service=mock_all_services["monitor"],
            firestore_client=mock_all_services["firestore"],
            settings=mock_settings,
        )

        status = await service.get_system_status()
        assert "status" in status
        assert "balances" in status
        assert status["status"] == "operational"

    @pytest.mark.asyncio
    async def test_toggle_workflow(self, mock_settings, mock_all_services):
        """Test toggling workflow."""
        from services.orchestrator.service import OrchestratorService

        service = OrchestratorService(
            scraper_service=mock_all_services["scraper"],
            ai_service=mock_all_services["ai"],
            trader_service=mock_all_services["trader"],
            monitor_service=mock_all_services["monitor"],
            firestore_client=mock_all_services["firestore"],
            settings=mock_settings,
        )

        state = await service.toggle_workflow("discovery", TradingMode.FAKE, False)
        assert state is not None

    @pytest.mark.asyncio
    async def test_get_workflow_state(self, mock_settings, mock_all_services):
        """Test getting workflow state."""
        from services.orchestrator.service import OrchestratorService

        service = OrchestratorService(
            scraper_service=mock_all_services["scraper"],
            ai_service=mock_all_services["ai"],
            trader_service=mock_all_services["trader"],
            monitor_service=mock_all_services["monitor"],
            firestore_client=mock_all_services["firestore"],
            settings=mock_settings,
        )

        result = await service.get_workflow_state("discovery", TradingMode.FAKE)
        # Returns None since mock returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_balance(self, mock_settings, mock_all_services):
        """Test getting balance."""
        from services.orchestrator.service import OrchestratorService

        service = OrchestratorService(
            scraper_service=mock_all_services["scraper"],
            ai_service=mock_all_services["ai"],
            trader_service=mock_all_services["trader"],
            monitor_service=mock_all_services["monitor"],
            firestore_client=mock_all_services["firestore"],
            settings=mock_settings,
        )

        balance = await service.get_balance(TradingMode.FAKE)
        assert balance == 500.0

    @pytest.mark.asyncio
    async def test_get_positions(self, mock_settings, mock_all_services):
        """Test getting positions."""
        from services.orchestrator.service import OrchestratorService

        service = OrchestratorService(
            scraper_service=mock_all_services["scraper"],
            ai_service=mock_all_services["ai"],
            trader_service=mock_all_services["trader"],
            monitor_service=mock_all_services["monitor"],
            firestore_client=mock_all_services["firestore"],
            settings=mock_settings,
        )

        positions = await service.get_positions(TradingMode.FAKE)
        assert isinstance(positions, list)

    @pytest.mark.asyncio
    async def test_get_markets(self, mock_settings, mock_all_services):
        """Test getting markets."""
        from services.orchestrator.service import OrchestratorService

        service = OrchestratorService(
            scraper_service=mock_all_services["scraper"],
            ai_service=mock_all_services["ai"],
            trader_service=mock_all_services["trader"],
            monitor_service=mock_all_services["monitor"],
            firestore_client=mock_all_services["firestore"],
            settings=mock_settings,
        )

        # Filtered markets
        markets = await service.get_markets(limit=50, filtered=True)
        assert isinstance(markets, list)

        # Unfiltered markets
        markets = await service.get_markets(limit=50, filtered=False)
        assert isinstance(markets, list)
