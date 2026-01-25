"""
Unit tests for trader service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.trader.service import TraderService, get_trader_service
from shared.models import (
    AISuggestion,
    OrderSide,
    OrderStatus,
    Position,
    TradingMode,
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
    settings.workflows_fake_money = MagicMock()
    settings.workflows_fake_money.initial_balance = 1000.0
    return settings


@pytest.fixture
def mock_firestore():
    """Create mock Firestore client."""
    client = MagicMock()

    # Mock wallet
    mock_wallet = MagicMock()
    mock_wallet.wallet_id = "test-wallet"
    mock_wallet.balance = 1000.0
    mock_wallet.can_afford = MagicMock(return_value=True)
    mock_wallet.deduct = MagicMock(return_value=True)
    mock_wallet.add = MagicMock()

    client.get_or_create_wallet = AsyncMock(return_value=mock_wallet)
    client.get_wallet = AsyncMock(return_value=mock_wallet)
    client.update_wallet_balance = AsyncMock(return_value=mock_wallet)
    client.create_transaction = AsyncMock()
    client.create_position = AsyncMock()
    client.delete_position = AsyncMock(return_value=True)
    client.get_open_positions = AsyncMock(return_value=[])

    return client


@pytest.fixture
def sample_position():
    """Create a sample position."""
    return Position(
        id="pos-001",
        market_id="market-001",
        outcome="Yes",
        entry_price=0.35,
        current_price=0.40,
        quantity=100,
        entry_value=35.0,
        current_value=40.0,
        mode=TradingMode.FAKE,
    )


class TestTraderService:
    """Tests for TraderService."""

    @pytest.mark.asyncio
    async def test_get_balance_fake(self, mock_settings, mock_firestore):
        """Test getting fake balance."""
        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        balance = await service.get_balance(TradingMode.FAKE)

        assert balance == 1000.0
        mock_firestore.get_or_create_wallet.assert_called_once()

    @pytest.mark.asyncio
    async def test_can_trade_fake_enabled(self, mock_settings, mock_firestore):
        """Test can_trade when fake trading is enabled."""
        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        can_trade, reason = await service.can_trade(TradingMode.FAKE, 50.0)

        assert can_trade is True
        assert reason == "OK"

    @pytest.mark.asyncio
    async def test_can_trade_real_disabled(self, mock_settings, mock_firestore):
        """Test can_trade when real trading is disabled."""
        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        can_trade, reason = await service.can_trade(TradingMode.REAL, 50.0)

        assert can_trade is False
        assert "disabled" in reason

    @pytest.mark.asyncio
    async def test_can_trade_insufficient_balance(self, mock_settings, mock_firestore):
        """Test can_trade with insufficient balance."""
        # Set low balance
        mock_wallet = MagicMock()
        mock_wallet.balance = 5.0
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        can_trade, reason = await service.can_trade(TradingMode.FAKE, 50.0)

        assert can_trade is False
        assert "below minimum" in reason or "Insufficient" in reason

    @pytest.mark.asyncio
    async def test_place_buy_order_fake(self, mock_settings, mock_firestore):
        """Test placing fake buy order."""
        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        order = await service.place_buy_order(
            market_id="market-001",
            outcome="Yes",
            amount=50.0,
            price=0.35,
            mode=TradingMode.FAKE,
        )

        assert order.status == OrderStatus.FILLED
        assert order.mode == TradingMode.FAKE
        assert order.market_id == "market-001"
        mock_firestore.create_position.assert_called_once()
        mock_firestore.create_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_buy_order_fake_insufficient_funds(self, mock_settings, mock_firestore):
        """Test placing fake buy order with insufficient funds."""
        mock_wallet = MagicMock()
        mock_wallet.balance = 1000.0
        mock_wallet.can_afford = MagicMock(return_value=False)
        mock_firestore.get_or_create_wallet = AsyncMock(return_value=mock_wallet)

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        order = await service.place_buy_order(
            market_id="market-001",
            outcome="Yes",
            amount=50.0,
            price=0.35,
            mode=TradingMode.FAKE,
        )

        assert order.status == OrderStatus.FAILED
        assert "Insufficient" in order.error_message

    @pytest.mark.asyncio
    async def test_place_sell_order_fake(self, mock_settings, mock_firestore, sample_position):
        """Test placing fake sell order."""
        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        order = await service.place_sell_order(sample_position, price=0.40)

        assert order.status == OrderStatus.FILLED
        assert order.side == OrderSide.SELL
        mock_firestore.delete_position.assert_called_once()
        mock_firestore.create_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_suggestion(self, mock_settings, mock_firestore):
        """Test executing AI suggestion."""
        suggestion = AISuggestion(
            market_id="market-001",
            market_question="Test market",
            recommended_outcome="Yes",
            confidence=0.85,
        )

        service = TraderService(
            firestore_client=mock_firestore,
            settings=mock_settings,
        )

        order = await service.execute_suggestion(
            suggestion=suggestion,
            position_size=50.0,
            mode=TradingMode.FAKE,
        )

        assert order.market_id == "market-001"
        assert order.outcome == "Yes"


class TestGetTraderService:
    """Tests for factory function."""

    def test_get_trader_service(self):
        """Test factory creates service."""
        with patch("services.trader.service.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock()

            service = get_trader_service()

            assert isinstance(service, TraderService)
