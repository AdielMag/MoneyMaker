"""
End-to-end tests for the Trader service FastAPI endpoints.
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
def mock_order():
    """Create mock order for testing."""
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
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_position():
    """Create mock position for testing."""
    return Position(
        id="pos-001",
        market_id="market-001",
        market_question="Will BTC reach $100k?",
        outcome="Yes",
        entry_price=0.30,
        current_price=0.42,
        quantity=100,
        entry_value=30.0,
        current_value=42.0,
        pnl_percent=40.0,
        mode=TradingMode.FAKE,
    )


@pytest.fixture
def mock_suggestion():
    """Create mock AI suggestion."""
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
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.api = MagicMock()
    settings.api.cors_origins = ["*"]
    settings.trading = MagicMock()
    settings.trading.min_balance_to_trade = 10.0
    settings.trading.max_bet_amount = 50.0
    settings.trading.max_positions = 10
    settings.real_money_enabled = False
    settings.fake_money_enabled = True
    return settings


@pytest.fixture
def mock_trader_service(mock_order):
    """Create mock trader service."""
    service = MagicMock()
    service.get_balance = AsyncMock(return_value=500.0)
    service.can_trade = AsyncMock(return_value=(True, "Trading allowed"))
    service.place_buy_order = AsyncMock(return_value=mock_order)
    service.place_sell_order = AsyncMock(return_value=mock_order)
    service.execute_suggestion = AsyncMock(return_value=mock_order)
    return service


@pytest.mark.e2e
class TestTraderEndpointsE2E:
    """End-to-end tests for trader endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings, mock_trader_service):
        """Setup test fixtures."""
        with patch("services.trader.main.get_settings", return_value=mock_settings):
            with patch("services.trader.main.get_trader_service", return_value=mock_trader_service):
                with patch("services.trader.main._trader_service", None):
                    from services.trader import main
                    main._trader_service = None
                    self.client = TestClient(main.app)
                    self.mock_service = mock_trader_service
                    yield

    def test_health_check(self):
        """Test health endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_get_balance_fake(self):
        """Test getting balance for fake mode."""
        response = self.client.get("/balance/fake")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "balance" in data
        assert "available_for_trading" in data
        assert data["balance"] == 500.0
        assert data["available_for_trading"] is True

    def test_get_balance_real(self):
        """Test getting balance for real mode."""
        response = self.client.get("/balance/real")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "real"

    def test_can_trade(self):
        """Test can trade endpoint."""
        response = self.client.get("/can-trade?mode=fake&amount=25.0")
        assert response.status_code == 200
        data = response.json()
        assert "can_trade" in data
        assert "reason" in data
        assert "mode" in data
        assert "amount" in data
        assert data["can_trade"] is True

    def test_place_buy_order(self):
        """Test placing a buy order."""
        response = self.client.post(
            "/orders/buy",
            json={
                "market_id": "market-001",
                "outcome": "Yes",
                "amount": 25.0,
                "price": 0.35,
                "mode": "fake",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "order-001"
        assert data["market_id"] == "market-001"
        assert data["status"] == "filled"

    def test_place_buy_order_insufficient_balance(self):
        """Test placing buy order with insufficient balance."""
        self.mock_service.can_trade = AsyncMock(return_value=(False, "Insufficient balance"))
        response = self.client.post(
            "/orders/buy",
            json={
                "market_id": "market-001",
                "outcome": "Yes",
                "amount": 1000.0,
                "price": 0.35,
                "mode": "fake",
            },
        )
        assert response.status_code == 400
        assert "Insufficient balance" in response.json()["detail"]

    def test_place_sell_order(self, mock_position):
        """Test placing a sell order."""
        position_data = mock_position.model_dump(mode="json")
        response = self.client.post(
            "/orders/sell",
            json={
                "position": position_data,
                "price": 0.42,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "order-001"

    def test_execute_suggestion(self, mock_suggestion):
        """Test executing AI suggestion."""
        suggestion_data = mock_suggestion.model_dump(mode="json")
        response = self.client.post(
            "/orders/execute-suggestion",
            json={
                "suggestion": suggestion_data,
                "position_size": 25.0,
                "mode": "fake",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "order-001"

    def test_execute_suggestion_cannot_trade(self, mock_suggestion):
        """Test executing suggestion when trading not allowed."""
        self.mock_service.can_trade = AsyncMock(return_value=(False, "Max positions reached"))
        suggestion_data = mock_suggestion.model_dump(mode="json")
        response = self.client.post(
            "/orders/execute-suggestion",
            json={
                "suggestion": suggestion_data,
                "position_size": 25.0,
                "mode": "fake",
            },
        )
        assert response.status_code == 400
        assert "Max positions reached" in response.json()["detail"]

    def test_get_trading_config(self, mock_settings):
        """Test getting trading configuration."""
        response = self.client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "min_balance_to_trade" in data
        assert "max_bet_amount" in data
        assert "max_positions" in data
        assert "real_money_enabled" in data
        assert "fake_money_enabled" in data

    def test_get_balance_error_handling(self):
        """Test error handling for get balance endpoint."""
        self.mock_service.get_balance = AsyncMock(side_effect=Exception("DB Error"))
        response = self.client.get("/balance/fake")
        assert response.status_code == 500

    def test_can_trade_error_handling(self):
        """Test error handling for can trade endpoint."""
        self.mock_service.can_trade = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/can-trade?mode=fake&amount=25.0")
        assert response.status_code == 500

    def test_place_buy_order_error_handling(self):
        """Test error handling for buy order endpoint."""
        self.mock_service.place_buy_order = AsyncMock(side_effect=Exception("Order failed"))
        response = self.client.post(
            "/orders/buy",
            json={
                "market_id": "market-001",
                "outcome": "Yes",
                "amount": 25.0,
                "price": 0.35,
                "mode": "fake",
            },
        )
        assert response.status_code == 500

    def test_place_sell_order_error_handling(self, mock_position):
        """Test error handling for sell order endpoint."""
        self.mock_service.place_sell_order = AsyncMock(side_effect=Exception("Sell failed"))
        position_data = mock_position.model_dump(mode="json")
        response = self.client.post(
            "/orders/sell",
            json={
                "position": position_data,
            },
        )
        assert response.status_code == 500

    def test_execute_suggestion_error_handling(self, mock_suggestion):
        """Test error handling for execute suggestion endpoint."""
        self.mock_service.execute_suggestion = AsyncMock(side_effect=Exception("Execution failed"))
        suggestion_data = mock_suggestion.model_dump(mode="json")
        response = self.client.post(
            "/orders/execute-suggestion",
            json={
                "suggestion": suggestion_data,
                "position_size": 25.0,
                "mode": "fake",
            },
        )
        assert response.status_code == 500
