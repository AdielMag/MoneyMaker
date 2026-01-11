"""
Unit tests for orchestrator service.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.orchestrator.service import OrchestratorService, get_orchestrator_service
from services.orchestrator.workflows import DiscoveryWorkflow, MonitorWorkflow
from shared.models import (
    AIAnalysisResult,
    AISuggestion,
    Market,
    MarketOutcome,
    Order,
    OrderStatus,
    TradingMode,
    WorkflowRunResult,
    WorkflowState,
)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.real_money_enabled = False
    settings.fake_money_enabled = True
    settings.trading = MagicMock()
    settings.trading.min_balance_to_trade = 10.0
    settings.trading.max_bet_amount = 50.0
    settings.trading.max_positions = 10
    settings.trading.sell_thresholds = MagicMock()
    settings.trading.sell_thresholds.stop_loss_percent = -15.0
    settings.trading.sell_thresholds.take_profit_percent = 30.0
    settings.ai = MagicMock()
    settings.ai.max_suggestions = 5
    settings.ai.confidence_threshold = 0.7
    settings.get_active_mode = MagicMock(return_value="fake")
    return settings


@pytest.fixture
def mock_scraper():
    """Create mock scraper service."""
    scraper = MagicMock()
    scraper.get_tradeable_markets = AsyncMock(
        return_value=[
            Market(
                id="market-001",
                question="Test market",
                end_date=datetime.utcnow(),
                outcomes=[MarketOutcome(name="Yes", price=0.5)],
            )
        ]
    )
    scraper.get_filtered_markets = AsyncMock(return_value=([], {}))
    scraper.get_markets = AsyncMock(return_value=[])
    return scraper


@pytest.fixture
def mock_ai():
    """Create mock AI service."""
    ai = MagicMock()
    ai.analyze_markets = AsyncMock(
        return_value=AIAnalysisResult(
            suggestions=[
                AISuggestion(
                    market_id="market-001",
                    recommended_outcome="Yes",
                    confidence=0.85,
                )
            ],
            markets_analyzed=1,
        )
    )
    ai.should_trade = AsyncMock(return_value=(True, "OK", 50.0))
    return ai


@pytest.fixture
def mock_trader():
    """Create mock trader service."""
    trader = MagicMock()
    trader.get_balance = AsyncMock(return_value=1000.0)
    trader.can_trade = AsyncMock(return_value=(True, "OK"))
    trader.execute_suggestion = AsyncMock(
        return_value=Order(
            id="order-001",
            market_id="market-001",
            outcome="Yes",
            side="buy",
            price=0.35,
            quantity=100,
            total_value=35.0,
            status=OrderStatus.FILLED,
        )
    )
    return trader


@pytest.fixture
def mock_monitor():
    """Create mock monitor service."""
    monitor = MagicMock()
    monitor.get_positions = AsyncMock(return_value=[])
    monitor.update_position_prices = AsyncMock(return_value=[])
    monitor.monitor_positions = AsyncMock(
        return_value={
            "positions_checked": 0,
            "sells_triggered": 0,
            "errors": [],
        }
    )
    monitor.get_positions_summary = AsyncMock(return_value={"count": 0})
    return monitor


@pytest.fixture
def mock_firestore():
    """Create mock Firestore client."""
    client = MagicMock()
    client.get_workflow_state = AsyncMock(return_value=None)
    client.update_workflow_state = AsyncMock()
    client.toggle_workflow = AsyncMock(
        return_value=WorkflowState(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            enabled=True,
        )
    )
    return client


class TestDiscoveryWorkflow:
    """Tests for DiscoveryWorkflow."""

    @pytest.mark.asyncio
    async def test_run_success(self, mock_settings, mock_scraper, mock_ai, mock_trader):
        """Test successful discovery workflow run."""
        workflow = DiscoveryWorkflow(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            settings=mock_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.workflow_id == "discovery"
        assert result.orders_placed >= 0

    @pytest.mark.asyncio
    async def test_run_cannot_trade(self, mock_settings, mock_scraper, mock_ai, mock_trader):
        """Test workflow when trading is not possible."""
        mock_trader.can_trade = AsyncMock(return_value=(False, "Insufficient balance"))

        workflow = DiscoveryWorkflow(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            settings=mock_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_run_no_markets(self, mock_settings, mock_scraper, mock_ai, mock_trader):
        """Test workflow with no markets found."""
        mock_scraper.get_tradeable_markets = AsyncMock(return_value=[])

        workflow = DiscoveryWorkflow(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            settings=mock_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.markets_analyzed == 0

    @pytest.mark.asyncio
    async def test_run_no_suggestions(self, mock_settings, mock_scraper, mock_ai, mock_trader):
        """Test workflow with no AI suggestions."""
        mock_ai.analyze_markets = AsyncMock(
            return_value=AIAnalysisResult(
                suggestions=[],
                markets_analyzed=1,
            )
        )

        workflow = DiscoveryWorkflow(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            settings=mock_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.suggestions_generated == 0


class TestMonitorWorkflow:
    """Tests for MonitorWorkflow."""

    @pytest.mark.asyncio
    async def test_run_success(self, mock_settings, mock_monitor):
        """Test successful monitor workflow run."""
        workflow = MonitorWorkflow(
            monitor_service=mock_monitor,
            settings=mock_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.workflow_id == "monitor"

    @pytest.mark.asyncio
    async def test_run_with_sells(self, mock_settings, mock_monitor):
        """Test workflow that triggers sells."""
        mock_monitor.monitor_positions = AsyncMock(
            return_value={
                "positions_checked": 3,
                "sells_triggered": 1,
                "stop_losses": 1,
                "take_profits": 0,
                "errors": [],
            }
        )

        workflow = MonitorWorkflow(
            monitor_service=mock_monitor,
            settings=mock_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.orders_placed == 1


class TestOrchestratorService:
    """Tests for OrchestratorService."""

    @pytest.mark.asyncio
    async def test_run_discovery(
        self, mock_settings, mock_scraper, mock_ai, mock_trader, mock_monitor, mock_firestore
    ):
        """Test running discovery workflow through orchestrator."""
        service = OrchestratorService(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            monitor_service=mock_monitor,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        result = await service.run_discovery(TradingMode.FAKE)

        assert isinstance(result, WorkflowRunResult)
        mock_firestore.update_workflow_state.assert_called()

    @pytest.mark.asyncio
    async def test_run_monitor(
        self, mock_settings, mock_scraper, mock_ai, mock_trader, mock_monitor, mock_firestore
    ):
        """Test running monitor workflow through orchestrator."""
        service = OrchestratorService(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            monitor_service=mock_monitor,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        result = await service.run_monitor(TradingMode.FAKE)

        assert isinstance(result, WorkflowRunResult)

    @pytest.mark.asyncio
    async def test_toggle_workflow(
        self, mock_settings, mock_scraper, mock_ai, mock_trader, mock_monitor, mock_firestore
    ):
        """Test toggling workflow state."""
        service = OrchestratorService(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            monitor_service=mock_monitor,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        state = await service.toggle_workflow("discovery", TradingMode.FAKE, True)

        assert state.enabled is True
        mock_firestore.toggle_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_status(
        self, mock_settings, mock_scraper, mock_ai, mock_trader, mock_monitor, mock_firestore
    ):
        """Test getting system status."""
        service = OrchestratorService(
            scraper_service=mock_scraper,
            ai_service=mock_ai,
            trader_service=mock_trader,
            monitor_service=mock_monitor,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        status = await service.get_system_status()

        assert "status" in status
        assert "balances" in status
        assert "config" in status


class TestGetOrchestratorService:
    """Tests for factory function."""

    def test_get_orchestrator_service(self):
        """Test factory creates service."""
        with patch("services.orchestrator.service.get_settings") as mock:
            mock.return_value = MagicMock()

            service = get_orchestrator_service()

            assert isinstance(service, OrchestratorService)
