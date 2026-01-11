"""
End-to-end tests for the monitor workflow.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.orchestrator.workflows import MonitorWorkflow
from shared.models import (
    Position,
    TradingMode,
    Wallet,
)


@pytest.fixture
def e2e_settings():
    """Create settings for e2e tests."""
    settings = MagicMock()
    settings.trading = MagicMock()
    settings.trading.sell_thresholds = MagicMock()
    settings.trading.sell_thresholds.stop_loss_percent = -15.0
    settings.trading.sell_thresholds.take_profit_percent = 30.0
    settings.trading.max_positions = 10
    return settings


@pytest.fixture
def mock_positions():
    """Create mock positions for testing."""
    return [
        Position(
            id="pos-profit",
            market_id="market-001",
            market_question="Will BTC reach $100k?",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.42,  # +40% profit
            quantity=100,
            entry_value=30.0,
            current_value=42.0,
            pnl_percent=40.0,
            mode=TradingMode.FAKE,
        ),
        Position(
            id="pos-loss",
            market_id="market-002",
            market_question="Will ETH flip BTC?",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.40,  # -20% loss
            quantity=80,
            entry_value=40.0,
            current_value=32.0,
            pnl_percent=-20.0,
            mode=TradingMode.FAKE,
        ),
        Position(
            id="pos-neutral",
            market_id="market-003",
            market_question="Will Fed cut rates?",
            outcome="No",
            entry_price=0.85,
            current_price=0.87,  # +2.35% gain
            quantity=60,
            entry_value=51.0,
            current_value=52.2,
            pnl_percent=2.35,
            mode=TradingMode.FAKE,
        ),
    ]


@pytest.mark.e2e
class TestMonitorWorkflowE2E:
    """End-to-end tests for monitor workflow."""

    @pytest.mark.asyncio
    async def test_complete_monitor_flow_triggers_sells(self, e2e_settings, mock_positions):
        """Test complete monitor workflow that triggers sells."""
        # Create mock services
        mock_wallet = Wallet(wallet_id="test", balance=500.0)
        mock_firestore = MagicMock()
        mock_firestore.get_open_positions = AsyncMock(return_value=mock_positions)
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)
        mock_firestore.update_wallet_balance = AsyncMock(return_value=mock_wallet)
        mock_firestore.create_transaction = AsyncMock()
        mock_firestore.delete_position = AsyncMock(return_value=True)

        from services.monitor.service import MonitorService
        from services.trader.service import TraderService

        trader = TraderService(
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        monitor = MonitorService(
            trader_service=trader,
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        workflow = MonitorWorkflow(
            monitor_service=monitor,
            settings=e2e_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        # Should trigger sells for pos-profit (take-profit) and pos-loss (stop-loss)
        assert result.workflow_id == "monitor"
        assert result.success is True
        assert result.orders_placed == 2  # Both profit and loss positions sold

    @pytest.mark.asyncio
    async def test_monitor_no_positions(self, e2e_settings):
        """Test monitor workflow with no open positions."""
        mock_firestore = MagicMock()
        mock_firestore.get_open_positions = AsyncMock(return_value=[])

        from services.monitor.service import MonitorService

        monitor = MonitorService(
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        workflow = MonitorWorkflow(
            monitor_service=monitor,
            settings=e2e_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.orders_placed == 0

    @pytest.mark.asyncio
    async def test_monitor_all_positions_within_threshold(self, e2e_settings):
        """Test monitor when all positions are within thresholds."""
        neutral_positions = [
            Position(
                id="pos-1",
                market_id="market-001",
                outcome="Yes",
                entry_price=0.50,
                current_price=0.52,  # +4%
                quantity=100,
                entry_value=50.0,
                current_value=52.0,
                pnl_percent=4.0,
                mode=TradingMode.FAKE,
            ),
            Position(
                id="pos-2",
                market_id="market-002",
                outcome="No",
                entry_price=0.60,
                current_price=0.57,  # -5%
                quantity=80,
                entry_value=48.0,
                current_value=45.6,
                pnl_percent=-5.0,
                mode=TradingMode.FAKE,
            ),
        ]

        mock_firestore = MagicMock()
        mock_firestore.get_open_positions = AsyncMock(return_value=neutral_positions)

        from services.monitor.service import MonitorService

        trader = MagicMock()
        trader.place_sell_order = AsyncMock()

        monitor = MonitorService(
            trader_service=trader,
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        workflow = MonitorWorkflow(
            monitor_service=monitor,
            settings=e2e_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        assert result.success is True
        assert result.orders_placed == 0
        trader.place_sell_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_edge_case_exactly_at_threshold(self, e2e_settings):
        """Test monitor with position exactly at stop-loss threshold."""
        edge_positions = [
            Position(
                id="pos-edge",
                market_id="market-001",
                outcome="Yes",
                entry_price=0.50,
                current_price=0.425,  # Exactly -15%
                quantity=100,
                entry_value=50.0,
                current_value=42.5,
                pnl_percent=-15.0,
                mode=TradingMode.FAKE,
            ),
        ]

        mock_wallet = Wallet(wallet_id="test", balance=100.0)
        mock_firestore = MagicMock()
        mock_firestore.get_open_positions = AsyncMock(return_value=edge_positions)
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)
        mock_firestore.update_wallet_balance = AsyncMock(return_value=mock_wallet)
        mock_firestore.create_transaction = AsyncMock()
        mock_firestore.delete_position = AsyncMock(return_value=True)

        from services.monitor.service import MonitorService
        from services.trader.service import TraderService

        trader = TraderService(
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        monitor = MonitorService(
            trader_service=trader,
            firestore_client=mock_firestore,
            settings=e2e_settings,
        )

        workflow = MonitorWorkflow(
            monitor_service=monitor,
            settings=e2e_settings,
        )

        result = await workflow.run(TradingMode.FAKE)

        # Should trigger stop-loss at exactly -15%
        assert result.success is True
        assert result.orders_placed == 1
