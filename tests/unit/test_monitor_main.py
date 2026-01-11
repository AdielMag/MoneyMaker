"""
Unit tests for Monitor service FastAPI endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import Position, TradingMode


@pytest.fixture
def mock_monitor_service():
    """Create a mocked monitor service."""
    service = MagicMock()
    service.get_positions = AsyncMock(return_value=[])
    service.update_position_prices = AsyncMock(return_value=[])
    service.get_positions_summary = AsyncMock(
        return_value={
            "total_positions": 0,
            "total_value": 0,
            "total_pnl": 0,
        }
    )
    service.monitor_positions = AsyncMock(
        return_value={
            "positions_checked": 0,
            "sells_triggered": 0,
        }
    )
    service.check_position = AsyncMock(return_value=(False, "hold", "No action needed"))
    service.stop_loss_threshold = -15.0
    service.take_profit_threshold = 30.0
    return service


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
def client(mock_monitor_service):
    """Create test client with mocked service."""
    with patch("services.monitor.main._monitor_service", None):
        with patch(
            "services.monitor.main.get_monitor_service",
            return_value=mock_monitor_service,
        ):
            import services.monitor.main as monitor_main
            from services.monitor.main import app

            # Reset service instance
            monitor_main._monitor_service = None

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


class TestPositionEndpoints:
    """Tests for position endpoints."""

    def test_get_positions_fake(self, client, mock_monitor_service, sample_position):
        """Test getting fake mode positions."""
        mock_monitor_service.get_positions = AsyncMock(return_value=[sample_position])
        mock_monitor_service.update_position_prices = AsyncMock(
            return_value=[sample_position]
        )

        response = client.get("/positions/fake")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "position-001"

    def test_get_positions_real(self, client, mock_monitor_service, sample_position):
        """Test getting real mode positions."""
        sample_position.mode = TradingMode.REAL
        mock_monitor_service.get_positions = AsyncMock(return_value=[sample_position])
        mock_monitor_service.update_position_prices = AsyncMock(
            return_value=[sample_position]
        )

        response = client.get("/positions/real")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_get_positions_empty(self, client, mock_monitor_service):
        """Test getting positions when none exist."""
        mock_monitor_service.get_positions = AsyncMock(return_value=[])
        mock_monitor_service.update_position_prices = AsyncMock(return_value=[])

        response = client.get("/positions/fake")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_positions_error(self, client, mock_monitor_service):
        """Test positions error handling."""
        mock_monitor_service.get_positions = AsyncMock(
            side_effect=Exception("Database Error")
        )

        response = client.get("/positions/fake")

        assert response.status_code == 500
        assert "Database Error" in response.json()["detail"]

    def test_get_positions_summary(self, client, mock_monitor_service):
        """Test getting positions summary."""
        mock_monitor_service.get_positions_summary = AsyncMock(
            return_value={
                "total_positions": 5,
                "total_value": 500.0,
                "total_pnl": 50.0,
                "pnl_percent": 10.0,
            }
        )

        response = client.get("/positions/fake/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_positions"] == 5
        assert data["total_value"] == 500.0
        assert data["total_pnl"] == 50.0

    def test_get_positions_summary_error(self, client, mock_monitor_service):
        """Test summary error handling."""
        mock_monitor_service.get_positions_summary = AsyncMock(
            side_effect=Exception("Summary Error")
        )

        response = client.get("/positions/fake/summary")

        assert response.status_code == 500


class TestMonitoringEndpoints:
    """Tests for monitoring endpoints."""

    def test_monitor_positions_success(self, client, mock_monitor_service):
        """Test successful position monitoring."""
        mock_monitor_service.monitor_positions = AsyncMock(
            return_value={
                "positions_checked": 3,
                "sells_triggered": 1,
                "actions": [
                    {"position_id": "pos-001", "action": "take_profit"}
                ],
            }
        )

        response = client.post("/monitor/fake")

        assert response.status_code == 200
        data = response.json()
        assert data["positions_checked"] == 3
        assert data["sells_triggered"] == 1

    def test_monitor_positions_real(self, client, mock_monitor_service):
        """Test monitoring real mode positions."""
        mock_monitor_service.monitor_positions = AsyncMock(
            return_value={
                "positions_checked": 2,
                "sells_triggered": 0,
            }
        )

        response = client.post("/monitor/real")

        assert response.status_code == 200
        mock_monitor_service.monitor_positions.assert_called_once()

    def test_monitor_positions_error(self, client, mock_monitor_service):
        """Test monitoring error handling."""
        mock_monitor_service.monitor_positions = AsyncMock(
            side_effect=Exception("Monitor Error")
        )

        response = client.post("/monitor/fake")

        assert response.status_code == 500

    def test_check_position_no_action(
        self, client, mock_monitor_service, sample_position
    ):
        """Test checking position that requires no action."""
        mock_monitor_service.check_position = AsyncMock(
            return_value=(False, "hold", "Position within thresholds")
        )

        response = client.post(
            "/check-position",
            json=sample_position.model_dump(mode="json"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["should_sell"] is False
        assert data["action"] == "hold"
        assert "thresholds" in data

    def test_check_position_take_profit(
        self, client, mock_monitor_service, sample_position
    ):
        """Test checking position that triggers take profit."""
        sample_position.pnl_percent = 35.0
        mock_monitor_service.check_position = AsyncMock(
            return_value=(True, "take_profit", "PnL above threshold")
        )

        response = client.post(
            "/check-position",
            json=sample_position.model_dump(mode="json"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["should_sell"] is True
        assert data["action"] == "take_profit"

    def test_check_position_stop_loss(
        self, client, mock_monitor_service, sample_position
    ):
        """Test checking position that triggers stop loss."""
        sample_position.pnl_percent = -20.0
        mock_monitor_service.check_position = AsyncMock(
            return_value=(True, "stop_loss", "PnL below threshold")
        )

        response = client.post(
            "/check-position",
            json=sample_position.model_dump(mode="json"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["should_sell"] is True
        assert data["action"] == "stop_loss"

    def test_check_position_error(self, client, mock_monitor_service, sample_position):
        """Test check position error handling."""
        mock_monitor_service.check_position = AsyncMock(
            side_effect=Exception("Check Error")
        )

        response = client.post(
            "/check-position",
            json=sample_position.model_dump(mode="json"),
        )

        assert response.status_code == 500


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_monitor_config(self, client):
        """Test getting monitor configuration."""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert "stop_loss_percent" in data
        assert "take_profit_percent" in data
        assert "max_positions" in data
