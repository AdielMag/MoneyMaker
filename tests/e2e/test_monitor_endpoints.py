"""
End-to-end tests for the Monitor service FastAPI endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import Position, TradingMode


@pytest.fixture
def mock_positions():
    """Create mock positions for testing."""
    return [
        Position(
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
        ),
        Position(
            id="pos-002",
            market_id="market-002",
            market_question="Will ETH flip BTC?",
            outcome="No",
            entry_price=0.50,
            current_price=0.40,
            quantity=80,
            entry_value=40.0,
            current_value=32.0,
            pnl_percent=-20.0,
            mode=TradingMode.FAKE,
        ),
    ]


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.api = MagicMock()
    settings.api.cors_origins = ["*"]
    settings.trading = MagicMock()
    settings.trading.sell_thresholds = MagicMock()
    settings.trading.sell_thresholds.stop_loss_percent = -15.0
    settings.trading.sell_thresholds.take_profit_percent = 30.0
    settings.trading.max_positions = 10
    return settings


@pytest.fixture
def mock_monitor_service(mock_positions):
    """Create mock monitor service."""
    service = MagicMock()
    service.get_positions = AsyncMock(return_value=mock_positions)
    service.update_position_prices = AsyncMock(return_value=mock_positions)
    service.get_positions_summary = AsyncMock(return_value={
        "count": 2,
        "total_value": 74.0,
        "total_pnl": 4.0,
        "pnl_percent": 5.7,
    })
    service.monitor_positions = AsyncMock(return_value={
        "positions_checked": 2,
        "sells_triggered": 2,
        "errors": [],
    })
    service.check_position = AsyncMock(return_value=(True, "take_profit", "PnL exceeded threshold"))
    service.stop_loss_threshold = -15.0
    service.take_profit_threshold = 30.0
    return service


@pytest.mark.e2e
class TestMonitorEndpointsE2E:
    """End-to-end tests for monitor endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings, mock_monitor_service):
        """Setup test fixtures."""
        with patch("services.monitor.main.get_settings", return_value=mock_settings):
            with patch("services.monitor.main.get_monitor_service", return_value=mock_monitor_service):
                with patch("services.monitor.main._monitor_service", None):
                    from services.monitor import main
                    main._monitor_service = None
                    self.client = TestClient(main.app)
                    self.mock_service = mock_monitor_service
                    yield

    def test_health_check(self):
        """Test health endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_get_positions_fake_mode(self):
        """Test getting positions for fake trading mode."""
        response = self.client.get("/positions/fake")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "pos-001"

    def test_get_positions_real_mode(self):
        """Test getting positions for real trading mode."""
        response = self.client.get("/positions/real")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_positions_summary(self):
        """Test getting positions summary."""
        response = self.client.get("/positions/fake/summary")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "total_value" in data
        assert "total_pnl" in data
        assert data["count"] == 2

    def test_monitor_positions_fake(self):
        """Test monitoring positions for fake mode."""
        response = self.client.post("/monitor/fake")
        assert response.status_code == 200
        data = response.json()
        assert "positions_checked" in data
        assert "sells_triggered" in data
        assert data["positions_checked"] == 2

    def test_monitor_positions_real(self):
        """Test monitoring positions for real mode."""
        response = self.client.post("/monitor/real")
        assert response.status_code == 200
        data = response.json()
        assert "positions_checked" in data

    def test_check_position(self, mock_positions):
        """Test checking a single position."""
        position_data = mock_positions[0].model_dump(mode="json")
        response = self.client.post("/check-position", json=position_data)
        assert response.status_code == 200
        data = response.json()
        assert "position_id" in data
        assert "should_sell" in data
        assert "action" in data
        assert "reason" in data
        assert "pnl_percent" in data
        assert "thresholds" in data
        assert data["position_id"] == "pos-001"
        assert data["should_sell"] is True

    def test_get_monitor_config(self):
        """Test getting monitor configuration."""
        response = self.client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "stop_loss_percent" in data
        assert "take_profit_percent" in data
        assert "max_positions" in data
        # Values come from actual settings loaded by the app

    def test_get_positions_error_handling(self):
        """Test error handling for get positions endpoint."""
        self.mock_service.get_positions = AsyncMock(side_effect=Exception("DB Error"))
        response = self.client.get("/positions/fake")
        assert response.status_code == 500
        assert "DB Error" in response.json()["detail"]

    def test_get_positions_summary_error_handling(self):
        """Test error handling for positions summary endpoint."""
        self.mock_service.get_positions_summary = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/positions/fake/summary")
        assert response.status_code == 500

    def test_monitor_positions_error_handling(self):
        """Test error handling for monitor positions endpoint."""
        self.mock_service.monitor_positions = AsyncMock(side_effect=Exception("Monitor failed"))
        response = self.client.post("/monitor/fake")
        assert response.status_code == 500

    def test_check_position_error_handling(self, mock_positions):
        """Test error handling for check position endpoint."""
        self.mock_service.check_position = AsyncMock(side_effect=Exception("Check failed"))
        position_data = mock_positions[0].model_dump(mode="json")
        response = self.client.post("/check-position", json=position_data)
        assert response.status_code == 500
