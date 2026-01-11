"""
Unit tests for Trader service FastAPI endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import (
    AISuggestion,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    RiskLevel,
    TradingMode,
)


@pytest.fixture
def mock_trader_service():
    """Create a mocked trader service."""
    service = MagicMock()
    service.get_balance = AsyncMock(return_value=1000.0)
    service.can_trade = AsyncMock(return_value=(True, "Trading enabled"))
    service.place_buy_order = AsyncMock(
        return_value=Order(
            id="order-001",
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.BUY,
            price=0.35,
            quantity=100,
            total_value=35.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        )
    )
    service.place_sell_order = AsyncMock(
        return_value=Order(
            id="order-002",
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.SELL,
            price=0.40,
            quantity=100,
            total_value=40.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        )
    )
    service.execute_suggestion = AsyncMock(
        return_value=Order(
            id="order-003",
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.BUY,
            price=0.35,
            quantity=100,
            total_value=35.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        )
    )
    return service


@pytest.fixture
def sample_order():
    """Create a sample order."""
    return Order(
        id="order-001",
        market_id="market-001",
        outcome="Yes",
        side=OrderSide.BUY,
        price=0.35,
        quantity=100,
        total_value=35.0,
        status=OrderStatus.FILLED,
        mode=TradingMode.FAKE,
    )


@pytest.fixture
def sample_position():
    """Create a sample position."""
    return Position(
        id="position-001",
        market_id="market-001",
        market_question="Will BTC reach $100k?",
        outcome="Yes",
        entry_price=0.30,
        current_price=0.35,
        quantity=100,
        entry_value=30.0,
        current_value=35.0,
        pnl_percent=16.67,
        created_at=datetime.utcnow(),
        mode=TradingMode.FAKE,
    )


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


@pytest.fixture
def client(mock_trader_service):
    """Create test client with mocked service."""
    with patch("services.trader.main._trader_service", None):
        with patch(
            "services.trader.main.get_trader_service",
            return_value=mock_trader_service,
        ):
            from services.trader.main import app

            # Reset service instance
            import services.trader.main as trader_main

            trader_main._trader_service = None

            with TestClient(app) as test_client:
                yield test_client


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestBalanceEndpoints:
    """Tests for balance endpoints."""

    def test_get_balance_fake(self, client, mock_trader_service):
        """Test getting fake mode balance."""
        mock_trader_service.get_balance = AsyncMock(return_value=1000.0)

        response = client.get("/balance/fake")

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "fake"
        assert data["balance"] == 1000.0
        assert data["available_for_trading"] is True

    def test_get_balance_real(self, client, mock_trader_service):
        """Test getting real mode balance."""
        mock_trader_service.get_balance = AsyncMock(return_value=500.0)

        response = client.get("/balance/real")

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "real"
        assert data["balance"] == 500.0

    def test_get_balance_low(self, client, mock_trader_service):
        """Test getting balance below trading threshold."""
        mock_trader_service.get_balance = AsyncMock(return_value=5.0)

        response = client.get("/balance/fake")

        assert response.status_code == 200
        data = response.json()
        assert data["balance"] == 5.0
        assert data["available_for_trading"] is False

    def test_get_balance_error(self, client, mock_trader_service):
        """Test balance error handling."""
        mock_trader_service.get_balance = AsyncMock(
            side_effect=Exception("Balance Error")
        )

        response = client.get("/balance/fake")

        assert response.status_code == 500

    def test_can_trade_yes(self, client, mock_trader_service):
        """Test can trade check when trading is possible."""
        mock_trader_service.can_trade = AsyncMock(
            return_value=(True, "Trading enabled")
        )

        response = client.get("/can-trade?mode=fake&amount=50")

        assert response.status_code == 200
        data = response.json()
        assert data["can_trade"] is True
        assert data["mode"] == "fake"
        assert data["amount"] == 50.0

    def test_can_trade_no(self, client, mock_trader_service):
        """Test can trade check when trading is not possible."""
        mock_trader_service.can_trade = AsyncMock(
            return_value=(False, "Insufficient balance")
        )

        response = client.get("/can-trade?mode=fake&amount=5000")

        assert response.status_code == 200
        data = response.json()
        assert data["can_trade"] is False
        assert "Insufficient balance" in data["reason"]

    def test_can_trade_error(self, client, mock_trader_service):
        """Test can trade error handling."""
        mock_trader_service.can_trade = AsyncMock(
            side_effect=Exception("Trade Check Error")
        )

        response = client.get("/can-trade?mode=fake&amount=50")

        assert response.status_code == 500


class TestOrderEndpoints:
    """Tests for order endpoints."""

    def test_place_buy_order_success(self, client, mock_trader_service, sample_order):
        """Test placing a successful buy order."""
        mock_trader_service.can_trade = AsyncMock(return_value=(True, "OK"))
        mock_trader_service.place_buy_order = AsyncMock(return_value=sample_order)

        response = client.post(
            "/orders/buy",
            json={
                "market_id": "market-001",
                "outcome": "Yes",
                "amount": 50.0,
                "price": 0.35,
                "mode": "fake",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "order-001"
        assert data["side"] == "buy"
        assert data["status"] == "filled"

    def test_place_buy_order_cannot_trade(self, client, mock_trader_service):
        """Test buy order when trading is not possible."""
        mock_trader_service.can_trade = AsyncMock(
            return_value=(False, "Insufficient balance")
        )

        response = client.post(
            "/orders/buy",
            json={
                "market_id": "market-001",
                "outcome": "Yes",
                "amount": 5000.0,
                "price": 0.35,
                "mode": "fake",
            },
        )

        assert response.status_code == 400
        assert "Insufficient balance" in response.json()["detail"]

    def test_place_buy_order_error(self, client, mock_trader_service):
        """Test buy order error handling."""
        mock_trader_service.can_trade = AsyncMock(return_value=(True, "OK"))
        mock_trader_service.place_buy_order = AsyncMock(
            side_effect=Exception("Order Error")
        )

        response = client.post(
            "/orders/buy",
            json={
                "market_id": "market-001",
                "outcome": "Yes",
                "amount": 50.0,
                "price": 0.35,
                "mode": "fake",
            },
        )

        assert response.status_code == 500

    def test_place_sell_order_success(
        self, client, mock_trader_service, sample_position
    ):
        """Test placing a successful sell order."""
        sell_order = Order(
            id="order-002",
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.SELL,
            price=0.40,
            quantity=100,
            total_value=40.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        )
        mock_trader_service.place_sell_order = AsyncMock(return_value=sell_order)

        response = client.post(
            "/orders/sell",
            json={
                "position": sample_position.model_dump(mode="json"),
                "price": 0.40,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["side"] == "sell"
        assert data["status"] == "filled"

    def test_place_sell_order_no_price(
        self, client, mock_trader_service, sample_position
    ):
        """Test selling with no limit price (market order)."""
        sell_order = Order(
            id="order-002",
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.SELL,
            price=0.35,
            quantity=100,
            total_value=35.0,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
        )
        mock_trader_service.place_sell_order = AsyncMock(return_value=sell_order)

        response = client.post(
            "/orders/sell",
            json={
                "position": sample_position.model_dump(mode="json"),
            },
        )

        assert response.status_code == 200

    def test_place_sell_order_error(
        self, client, mock_trader_service, sample_position
    ):
        """Test sell order error handling."""
        mock_trader_service.place_sell_order = AsyncMock(
            side_effect=Exception("Sell Error")
        )

        response = client.post(
            "/orders/sell",
            json={
                "position": sample_position.model_dump(mode="json"),
            },
        )

        assert response.status_code == 500


class TestSuggestionEndpoints:
    """Tests for suggestion execution endpoints."""

    def test_execute_suggestion_success(
        self, client, mock_trader_service, sample_suggestion, sample_order
    ):
        """Test executing AI suggestion successfully."""
        mock_trader_service.can_trade = AsyncMock(return_value=(True, "OK"))
        mock_trader_service.execute_suggestion = AsyncMock(return_value=sample_order)

        response = client.post(
            "/orders/execute-suggestion",
            json={
                "suggestion": sample_suggestion.model_dump(),
                "position_size": 50.0,
                "mode": "fake",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "order-001"

    def test_execute_suggestion_cannot_trade(
        self, client, mock_trader_service, sample_suggestion
    ):
        """Test suggestion execution when trading is not possible."""
        mock_trader_service.can_trade = AsyncMock(
            return_value=(False, "Trading disabled")
        )

        response = client.post(
            "/orders/execute-suggestion",
            json={
                "suggestion": sample_suggestion.model_dump(),
                "position_size": 50.0,
                "mode": "fake",
            },
        )

        assert response.status_code == 400

    def test_execute_suggestion_error(
        self, client, mock_trader_service, sample_suggestion
    ):
        """Test suggestion execution error handling."""
        mock_trader_service.can_trade = AsyncMock(return_value=(True, "OK"))
        mock_trader_service.execute_suggestion = AsyncMock(
            side_effect=Exception("Execution Error")
        )

        response = client.post(
            "/orders/execute-suggestion",
            json={
                "suggestion": sample_suggestion.model_dump(),
                "position_size": 50.0,
                "mode": "fake",
            },
        )

        assert response.status_code == 500


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_trading_config(self, client):
        """Test getting trading configuration."""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert "min_balance_to_trade" in data
        assert "max_bet_amount" in data
        assert "max_positions" in data
        assert "real_money_enabled" in data
        assert "fake_money_enabled" in data
