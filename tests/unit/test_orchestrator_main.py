"""
Unit tests for Orchestrator service FastAPI endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import (
    TradingMode,
    WorkflowRunResult,
    WorkflowState,
)


@pytest.fixture
def mock_orchestrator_service():
    """Create a mocked orchestrator service."""
    service = MagicMock()
    service.get_system_status = AsyncMock(
        return_value={
            "status": "healthy",
            "mode": "fake",
            "balance": 1000.0,
            "positions": 0,
        }
    )
    service.run_discovery = AsyncMock(
        return_value=WorkflowRunResult(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            success=True,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            markets_analyzed=10,
            suggestions_generated=3,
            orders_placed=2,
        )
    )
    service.run_monitor = AsyncMock(
        return_value=WorkflowRunResult(
            workflow_id="monitor",
            mode=TradingMode.FAKE,
            success=True,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
    )
    service.toggle_workflow = AsyncMock(
        return_value=WorkflowState(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            enabled=True,
        )
    )
    service.get_workflow_state = AsyncMock(
        return_value=WorkflowState(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            enabled=True,
        )
    )
    service.get_markets = AsyncMock(return_value=[])
    service.get_positions = AsyncMock(return_value=[])
    service.get_balance = AsyncMock(return_value=1000.0)
    return service


@pytest.fixture
def sample_workflow_result():
    """Create a sample workflow result."""
    return WorkflowRunResult(
        workflow_id="discovery",
        mode=TradingMode.FAKE,
        success=True,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        markets_analyzed=10,
        suggestions_generated=3,
        orders_placed=2,
    )


@pytest.fixture
def sample_workflow_state():
    """Create a sample workflow state."""
    return WorkflowState(
        workflow_id="discovery",
        mode=TradingMode.FAKE,
        enabled=True,
        last_run=datetime.utcnow(),
        run_count=5,
    )


@pytest.fixture
def client(mock_orchestrator_service):
    """Create test client with mocked service."""
    with patch("services.orchestrator.main._orchestrator", None):
        with patch(
            "services.orchestrator.main.get_orchestrator_service",
            return_value=mock_orchestrator_service,
        ):
            from services.orchestrator.main import app

            # Reset service instance
            import services.orchestrator.main as orchestrator_main

            orchestrator_main._orchestrator = None

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

    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_system_status(self, client, mock_orchestrator_service):
        """Test system status endpoint."""
        mock_orchestrator_service.get_system_status = AsyncMock(
            return_value={
                "status": "healthy",
                "mode": "fake",
                "balance": 1000.0,
                "positions": 3,
                "workflows": {"discovery": True, "monitor": True},
            }
        )

        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["balance"] == 1000.0

    def test_system_status_error(self, client, mock_orchestrator_service):
        """Test status error handling."""
        mock_orchestrator_service.get_system_status = AsyncMock(
            side_effect=Exception("Status Error")
        )

        response = client.get("/status")

        assert response.status_code == 500


class TestWorkflowEndpoints:
    """Tests for workflow endpoints."""

    def test_trigger_discovery_fake(
        self, client, mock_orchestrator_service, sample_workflow_result
    ):
        """Test triggering discovery workflow in fake mode."""
        mock_orchestrator_service.run_discovery = AsyncMock(
            return_value=sample_workflow_result
        )

        response = client.post(
            "/workflow/discover",
            json={"mode": "fake"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "discovery"
        assert data["success"] is True
        assert data["markets_analyzed"] == 10

    def test_trigger_discovery_real(
        self, client, mock_orchestrator_service, sample_workflow_result
    ):
        """Test triggering discovery workflow in real mode."""
        sample_workflow_result.mode = TradingMode.REAL
        mock_orchestrator_service.run_discovery = AsyncMock(
            return_value=sample_workflow_result
        )

        response = client.post(
            "/workflow/discover",
            json={"mode": "real"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "real"

    def test_trigger_discovery_error(self, client, mock_orchestrator_service):
        """Test discovery workflow error handling."""
        mock_orchestrator_service.run_discovery = AsyncMock(
            side_effect=Exception("Discovery Error")
        )

        response = client.post(
            "/workflow/discover",
            json={"mode": "fake"},
        )

        assert response.status_code == 500

    def test_trigger_monitor(self, client, mock_orchestrator_service):
        """Test triggering monitor workflow."""
        monitor_result = WorkflowRunResult(
            workflow_id="monitor",
            mode=TradingMode.FAKE,
            success=True,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        mock_orchestrator_service.run_monitor = AsyncMock(return_value=monitor_result)

        response = client.post(
            "/workflow/monitor",
            json={"mode": "fake"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "monitor"
        assert data["success"] is True

    def test_trigger_monitor_error(self, client, mock_orchestrator_service):
        """Test monitor workflow error handling."""
        mock_orchestrator_service.run_monitor = AsyncMock(
            side_effect=Exception("Monitor Error")
        )

        response = client.post(
            "/workflow/monitor",
            json={"mode": "fake"},
        )

        assert response.status_code == 500

    def test_toggle_workflow_enable(
        self, client, mock_orchestrator_service, sample_workflow_state
    ):
        """Test enabling a workflow."""
        mock_orchestrator_service.toggle_workflow = AsyncMock(
            return_value=sample_workflow_state
        )

        response = client.post(
            "/workflow/toggle",
            json={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workflow_id"] == "discovery"
        assert data["enabled"] is True

    def test_toggle_workflow_disable(
        self, client, mock_orchestrator_service, sample_workflow_state
    ):
        """Test disabling a workflow."""
        sample_workflow_state.enabled = False
        mock_orchestrator_service.toggle_workflow = AsyncMock(
            return_value=sample_workflow_state
        )

        response = client.post(
            "/workflow/toggle",
            json={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    def test_toggle_workflow_error(self, client, mock_orchestrator_service):
        """Test toggle workflow error handling."""
        mock_orchestrator_service.toggle_workflow = AsyncMock(
            side_effect=Exception("Toggle Error")
        )

        response = client.post(
            "/workflow/toggle",
            json={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": True,
            },
        )

        assert response.status_code == 500

    def test_get_workflow_state_exists(
        self, client, mock_orchestrator_service, sample_workflow_state
    ):
        """Test getting existing workflow state."""
        mock_orchestrator_service.get_workflow_state = AsyncMock(
            return_value=sample_workflow_state
        )

        response = client.get("/workflow/discovery/state?mode=fake")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["workflow_id"] == "discovery"

    def test_get_workflow_state_not_exists(self, client, mock_orchestrator_service):
        """Test getting non-existent workflow state."""
        mock_orchestrator_service.get_workflow_state = AsyncMock(return_value=None)

        response = client.get("/workflow/unknown/state?mode=fake")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False

    def test_get_workflow_state_error(self, client, mock_orchestrator_service):
        """Test workflow state error handling."""
        mock_orchestrator_service.get_workflow_state = AsyncMock(
            side_effect=Exception("State Error")
        )

        response = client.get("/workflow/discovery/state?mode=fake")

        assert response.status_code == 500


class TestMarketEndpoints:
    """Tests for market endpoints."""

    def test_get_markets_filtered(self, client, mock_orchestrator_service):
        """Test getting filtered markets."""
        mock_orchestrator_service.get_markets = AsyncMock(
            return_value=[
                {"id": "market-001", "question": "Will BTC hit $100k?"},
                {"id": "market-002", "question": "Will ETH flip BTC?"},
            ]
        )

        response = client.get("/markets?limit=10&filtered=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_markets_unfiltered(self, client, mock_orchestrator_service):
        """Test getting unfiltered markets."""
        mock_orchestrator_service.get_markets = AsyncMock(
            return_value=[{"id": "market-001"}]
        )

        response = client.get("/markets?filtered=false")

        assert response.status_code == 200

    def test_get_markets_error(self, client, mock_orchestrator_service):
        """Test markets error handling."""
        mock_orchestrator_service.get_markets = AsyncMock(
            side_effect=Exception("Markets Error")
        )

        response = client.get("/markets")

        assert response.status_code == 500


class TestPositionEndpoints:
    """Tests for position endpoints."""

    def test_get_positions_fake(self, client, mock_orchestrator_service):
        """Test getting fake mode positions."""
        mock_orchestrator_service.get_positions = AsyncMock(
            return_value=[
                {"id": "pos-001", "market_id": "market-001", "pnl_percent": 10.0}
            ]
        )

        response = client.get("/positions/fake")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_get_positions_real(self, client, mock_orchestrator_service):
        """Test getting real mode positions."""
        mock_orchestrator_service.get_positions = AsyncMock(return_value=[])

        response = client.get("/positions/real")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_positions_error(self, client, mock_orchestrator_service):
        """Test positions error handling."""
        mock_orchestrator_service.get_positions = AsyncMock(
            side_effect=Exception("Positions Error")
        )

        response = client.get("/positions/fake")

        assert response.status_code == 500


class TestBalanceEndpoints:
    """Tests for balance endpoints."""

    def test_get_balance_fake(self, client, mock_orchestrator_service):
        """Test getting fake mode balance."""
        mock_orchestrator_service.get_balance = AsyncMock(return_value=1000.0)

        response = client.get("/balance/fake")

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "fake"
        assert data["balance"] == 1000.0
        assert data["available_for_trading"] is True

    def test_get_balance_real(self, client, mock_orchestrator_service):
        """Test getting real mode balance."""
        mock_orchestrator_service.get_balance = AsyncMock(return_value=500.0)

        response = client.get("/balance/real")

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "real"

    def test_get_balance_low(self, client, mock_orchestrator_service):
        """Test balance below trading threshold."""
        mock_orchestrator_service.get_balance = AsyncMock(return_value=5.0)

        response = client.get("/balance/fake")

        assert response.status_code == 200
        data = response.json()
        assert data["available_for_trading"] is False

    def test_get_balance_error(self, client, mock_orchestrator_service):
        """Test balance error handling."""
        mock_orchestrator_service.get_balance = AsyncMock(
            side_effect=Exception("Balance Error")
        )

        response = client.get("/balance/fake")

        assert response.status_code == 500


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_config(self, client):
        """Test getting system configuration."""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert "trading" in data
        assert "market_filters" in data
        assert "ai" in data
        assert "feature_flags" in data

        # Check trading config
        assert "min_balance_to_trade" in data["trading"]
        assert "max_bet_amount" in data["trading"]
        assert "max_positions" in data["trading"]

        # Check market filters
        assert "min_volume" in data["market_filters"]
        assert "max_time_to_resolution_hours" in data["market_filters"]

        # Check AI config
        assert "model" in data["ai"]
        assert "max_suggestions" in data["ai"]

        # Check feature flags
        assert "real_money_enabled" in data["feature_flags"]
        assert "fake_money_enabled" in data["feature_flags"]
