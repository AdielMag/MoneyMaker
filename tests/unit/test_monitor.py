"""
Unit tests for position monitor service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.monitor.service import MonitorService, get_monitor_service
from shared.models import Order, OrderStatus, Position, TradingMode


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.trading = MagicMock()
    settings.trading.sell_thresholds = MagicMock()
    settings.trading.sell_thresholds.stop_loss_percent = -15.0
    settings.trading.sell_thresholds.take_profit_percent = 30.0
    settings.trading.max_positions = 10
    return settings


@pytest.fixture
def mock_trader():
    """Create mock trader service."""
    trader = MagicMock()
    trader.place_sell_order = AsyncMock(
        return_value=Order(
            id="order-001",
            market_id="market-001",
            outcome="Yes",
            side="sell",
            price=0.40,
            quantity=100,
            total_value=40.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        )
    )
    return trader


@pytest.fixture
def mock_firestore():
    """Create mock Firestore client."""
    client = MagicMock()
    client.get_open_positions = AsyncMock(return_value=[])
    return client


@pytest.fixture
def profitable_position():
    """Create a position that should trigger take-profit."""
    return Position(
        id="pos-profit",
        market_id="market-001",
        outcome="Yes",
        entry_price=0.30,
        current_price=0.42,
        quantity=100,
        entry_value=30.0,
        current_value=42.0,
        pnl_percent=40.0,  # Above 30% take-profit
        mode=TradingMode.FAKE,
    )


@pytest.fixture
def losing_position():
    """Create a position that should trigger stop-loss."""
    return Position(
        id="pos-loss",
        market_id="market-002",
        outcome="Yes",
        entry_price=0.50,
        current_price=0.40,
        quantity=100,
        entry_value=50.0,
        current_value=40.0,
        pnl_percent=-20.0,  # Below -15% stop-loss
        mode=TradingMode.FAKE,
    )


@pytest.fixture
def neutral_position():
    """Create a position that should not trigger any sell."""
    return Position(
        id="pos-neutral",
        market_id="market-003",
        outcome="Yes",
        entry_price=0.35,
        current_price=0.38,
        quantity=100,
        entry_value=35.0,
        current_value=38.0,
        pnl_percent=8.57,  # Between thresholds
        mode=TradingMode.FAKE,
    )


class TestMonitorService:
    """Tests for MonitorService."""

    def test_stop_loss_threshold(self, mock_settings):
        """Test stop-loss threshold property."""
        service = MonitorService(settings=mock_settings)

        assert service.stop_loss_threshold == -15.0

    def test_take_profit_threshold(self, mock_settings):
        """Test take-profit threshold property."""
        service = MonitorService(settings=mock_settings)

        assert service.take_profit_threshold == 30.0

    @pytest.mark.asyncio
    async def test_check_position_stop_loss(self, mock_settings, mock_trader, losing_position):
        """Test stop-loss trigger."""
        service = MonitorService(
            trader_service=mock_trader,
            settings=mock_settings,
        )

        should_sell, action, reason = await service.check_position(losing_position)

        assert should_sell is True
        assert action == "stop_loss"
        assert "-20.0%" in reason or "-15%" in reason

    @pytest.mark.asyncio
    async def test_check_position_take_profit(
        self, mock_settings, mock_trader, profitable_position
    ):
        """Test take-profit trigger."""
        service = MonitorService(
            trader_service=mock_trader,
            settings=mock_settings,
        )

        should_sell, action, reason = await service.check_position(profitable_position)

        assert should_sell is True
        assert action == "take_profit"
        assert "40.0%" in reason or "30%" in reason

    @pytest.mark.asyncio
    async def test_check_position_hold(self, mock_settings, mock_trader, neutral_position):
        """Test position that should be held."""
        service = MonitorService(
            trader_service=mock_trader,
            settings=mock_settings,
        )

        should_sell, action, reason = await service.check_position(neutral_position)

        assert should_sell is False
        assert action == "hold"

    @pytest.mark.asyncio
    async def test_check_position_exact_stop_loss(self, mock_settings, mock_trader):
        """Test position at exactly stop-loss threshold."""
        position = Position(
            id="pos-exact",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.425,
            quantity=100,
            entry_value=50.0,
            current_value=42.5,
            pnl_percent=-15.0,  # Exactly at threshold
            mode=TradingMode.FAKE,
        )

        service = MonitorService(
            trader_service=mock_trader,
            settings=mock_settings,
        )

        should_sell, action, _ = await service.check_position(position)

        assert should_sell is True
        assert action == "stop_loss"

    @pytest.mark.asyncio
    async def test_check_position_exact_take_profit(self, mock_settings, mock_trader):
        """Test position at exactly take-profit threshold."""
        position = Position(
            id="pos-exact",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.39,
            quantity=100,
            entry_value=30.0,
            current_value=39.0,
            pnl_percent=30.0,  # Exactly at threshold
            mode=TradingMode.FAKE,
        )

        service = MonitorService(
            trader_service=mock_trader,
            settings=mock_settings,
        )

        should_sell, action, _ = await service.check_position(position)

        assert should_sell is True
        assert action == "take_profit"

    @pytest.mark.asyncio
    async def test_check_position_just_above_stop_loss(self, mock_settings, mock_trader):
        """Test position just above stop-loss (should not trigger)."""
        position = Position(
            id="pos-close",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.428,
            quantity=100,
            entry_value=50.0,
            current_value=42.8,
            pnl_percent=-14.4,  # Just above -15%
            mode=TradingMode.FAKE,
        )

        service = MonitorService(
            trader_service=mock_trader,
            settings=mock_settings,
        )

        should_sell, action, _ = await service.check_position(position)

        assert should_sell is False
        assert action == "hold"

    @pytest.mark.asyncio
    async def test_monitor_positions_empty(self, mock_settings, mock_trader, mock_firestore):
        """Test monitoring with no positions."""
        service = MonitorService(
            trader_service=mock_trader,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        results = await service.monitor_positions(TradingMode.FAKE)

        assert results["positions_checked"] == 0
        assert results["sells_triggered"] == 0

    @pytest.mark.asyncio
    async def test_monitor_positions_triggers_sell(
        self, mock_settings, mock_trader, mock_firestore, losing_position
    ):
        """Test monitoring triggers sell for losing position."""
        mock_firestore.get_open_positions = AsyncMock(return_value=[losing_position])

        service = MonitorService(
            trader_service=mock_trader,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        results = await service.monitor_positions(TradingMode.FAKE)

        assert results["positions_checked"] == 1
        assert results["sells_triggered"] == 1
        assert results["stop_losses"] == 1
        mock_trader.place_sell_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_positions_summary(
        self, mock_settings, mock_trader, mock_firestore, neutral_position
    ):
        """Test getting positions summary."""
        mock_firestore.get_open_positions = AsyncMock(return_value=[neutral_position])

        service = MonitorService(
            trader_service=mock_trader,
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        summary = await service.get_positions_summary(TradingMode.FAKE)

        assert summary["count"] == 1
        assert summary["profitable"] == 1
        assert summary["losing"] == 0

    def test_should_trigger_alert_near_stop_loss(self, mock_settings):
        """Test alert trigger near stop-loss."""
        position = Position(
            id="pos-alert",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.44,
            quantity=100,
            entry_value=50.0,
            current_value=44.0,
            pnl_percent=-12.0,  # Within 5% of -15%
            mode=TradingMode.FAKE,
        )

        service = MonitorService(settings=mock_settings)
        should_alert, reason = service.should_trigger_alert(position)

        assert should_alert is True
        assert "stop-loss" in reason


class TestGetMonitorService:
    """Tests for factory function."""

    def test_get_monitor_service(self):
        """Test factory creates service."""
        with patch("services.monitor.service.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock()

            service = get_monitor_service()

            assert isinstance(service, MonitorService)
