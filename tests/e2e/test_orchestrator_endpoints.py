"""
End-to-end tests for the Orchestrator service FastAPI endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from shared.models import TradingMode, WorkflowRunResult, WorkflowState


@pytest.fixture
def mock_workflow_result():
    """Create mock workflow result."""
    return WorkflowRunResult(
        workflow_id="discovery",
        mode=TradingMode.FAKE,
        success=True,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        markets_analyzed=5,
        suggestions_generated=3,
        orders_placed=2,
        errors=[],
    )


@pytest.fixture
def mock_workflow_state():
    """Create mock workflow state."""
    return WorkflowState(
        workflow_id="discovery",
        mode=TradingMode.FAKE,
        enabled=True,
        run_count=10,
        last_run=datetime.utcnow(),
    )


@pytest.fixture
def mock_markets():
    """Create mock markets for testing."""
    return [
        {
            "id": "market-001",
            "question": "Will BTC reach $100k?",
            "category": "crypto",
            "volume": 50000,
            "liquidity": 25000,
        },
        {
            "id": "market-002",
            "question": "Will ETH flip BTC?",
            "category": "crypto",
            "volume": 30000,
            "liquidity": 15000,
        },
    ]


@pytest.fixture
def mock_positions():
    """Create mock positions for testing."""
    return [
        {
            "id": "pos-001",
            "market_id": "market-001",
            "outcome": "Yes",
            "entry_price": 0.30,
            "current_price": 0.42,
            "quantity": 100,
            "pnl_percent": 40.0,
            "mode": "fake",
        },
    ]


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
    settings.trading.sell_thresholds = MagicMock()
    settings.trading.sell_thresholds.stop_loss_percent = -15.0
    settings.trading.sell_thresholds.take_profit_percent = 30.0
    settings.market_filters = MagicMock()
    settings.market_filters.min_volume = 1000
    settings.market_filters.max_time_to_resolution_hours = 1.0
    settings.market_filters.min_liquidity = 500
    settings.market_filters.excluded_categories = ["sports"]
    settings.ai = MagicMock()
    settings.ai.model = "gemini-1.5-pro"
    settings.ai.max_suggestions = 5
    settings.ai.confidence_threshold = 0.7
    settings.real_money_enabled = False
    settings.fake_money_enabled = True
    settings.get_active_mode = MagicMock(return_value="fake")
    return settings


@pytest.fixture
def mock_orchestrator_service(mock_workflow_result, mock_workflow_state, mock_markets, mock_positions):
    """Create mock orchestrator service."""
    service = MagicMock()
    service.run_discovery = AsyncMock(return_value=mock_workflow_result)
    service.run_monitor = AsyncMock(return_value=WorkflowRunResult(
        workflow_id="monitor",
        mode=TradingMode.FAKE,
        success=True,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        orders_placed=1,
    ))
    service.toggle_workflow = AsyncMock(return_value=mock_workflow_state)
    service.get_workflow_state = AsyncMock(return_value=mock_workflow_state)
    service.get_markets = AsyncMock(return_value=mock_markets)
    service.get_positions = AsyncMock(return_value=mock_positions)
    service.get_balance = AsyncMock(return_value=500.0)
    service.get_system_status = AsyncMock(return_value={
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "real_money_enabled": False,
            "fake_money_enabled": True,
            "active_mode": "fake",
        },
        "balances": {"fake": 500.0, "real": 0.0},
        "positions": {"fake": {"count": 1}},
        "thresholds": {"stop_loss": -15.0, "take_profit": 30.0},
    })
    return service


@pytest.mark.e2e
class TestOrchestratorEndpointsE2E:
    """End-to-end tests for orchestrator endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings, mock_orchestrator_service):
        """Setup test fixtures."""
        from services.orchestrator import main

        # Save original
        original_get_service = main.get_service
        original_orchestrator = main._orchestrator

        # Override
        main._orchestrator = mock_orchestrator_service
        main.get_service = lambda: mock_orchestrator_service

        self.client = TestClient(main.app)
        self.mock_service = mock_orchestrator_service

        yield

        # Restore
        main.get_service = original_get_service
        main._orchestrator = original_orchestrator

    def test_health_check(self):
        """Test health endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_readiness_check(self):
        """Test readiness endpoint."""
        response = self.client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_system_status(self):
        """Test system status endpoint."""
        response = self.client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "config" in data
        assert "balances" in data
        assert "positions" in data
        assert data["status"] == "operational"

    def test_trigger_discovery_workflow(self):
        """Test triggering discovery workflow."""
        response = self.client.post(
            "/workflow/discover",
            json={"mode": "fake"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "discovery"
        assert data["success"] is True
        assert data["markets_analyzed"] == 5
        assert data["suggestions_generated"] == 3
        assert data["orders_placed"] == 2

    def test_trigger_monitor_workflow(self):
        """Test triggering monitor workflow."""
        response = self.client.post(
            "/workflow/monitor",
            json={"mode": "fake"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "monitor"
        assert data["success"] is True

    def test_toggle_workflow(self):
        """Test toggling workflow."""
        response = self.client.post(
            "/workflow/toggle",
            json={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "workflow_id" in data
        assert "mode" in data
        assert "enabled" in data
        assert data["success"] is True

    def test_get_workflow_state_exists(self):
        """Test getting existing workflow state."""
        response = self.client.get("/workflow/discovery/state?mode=fake")
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["workflow_id"] == "discovery"
        assert data["enabled"] is True

    def test_get_workflow_state_not_exists(self):
        """Test getting non-existent workflow state."""
        self.mock_service.get_workflow_state = AsyncMock(return_value=None)
        response = self.client.get("/workflow/unknown/state?mode=fake")
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False

    def test_get_markets(self):
        """Test getting markets."""
        response = self.client.get("/markets?limit=50&filtered=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "market-001"

    def test_get_positions(self):
        """Test getting positions."""
        response = self.client.get("/positions/fake")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "pos-001"

    def test_get_balance(self, mock_settings):
        """Test getting balance."""
        response = self.client.get("/balance/fake")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "balance" in data
        assert "available_for_trading" in data
        assert data["balance"] == 500.0

    def test_get_config(self, mock_settings):
        """Test getting configuration."""
        response = self.client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "trading" in data
        assert "market_filters" in data
        assert "ai" in data
        assert "feature_flags" in data

    def test_trigger_discovery_error_handling(self):
        """Test error handling for discovery workflow."""
        self.mock_service.run_discovery = AsyncMock(side_effect=Exception("Discovery failed"))
        response = self.client.post(
            "/workflow/discover",
            json={"mode": "fake"},
        )
        assert response.status_code == 500
        assert "Discovery failed" in response.json()["detail"]

    def test_trigger_monitor_error_handling(self):
        """Test error handling for monitor workflow."""
        self.mock_service.run_monitor = AsyncMock(side_effect=Exception("Monitor failed"))
        response = self.client.post(
            "/workflow/monitor",
            json={"mode": "fake"},
        )
        assert response.status_code == 500

    def test_toggle_workflow_error_handling(self):
        """Test error handling for toggle workflow."""
        self.mock_service.toggle_workflow = AsyncMock(side_effect=Exception("Toggle failed"))
        response = self.client.post(
            "/workflow/toggle",
            json={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": False,
            },
        )
        assert response.status_code == 500

    def test_get_workflow_state_error_handling(self):
        """Test error handling for get workflow state."""
        self.mock_service.get_workflow_state = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/workflow/discovery/state?mode=fake")
        assert response.status_code == 500

    def test_get_markets_error_handling(self):
        """Test error handling for get markets."""
        self.mock_service.get_markets = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/markets")
        assert response.status_code == 500

    def test_get_positions_error_handling(self):
        """Test error handling for get positions."""
        self.mock_service.get_positions = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/positions/fake")
        assert response.status_code == 500

    def test_get_balance_error_handling(self):
        """Test error handling for get balance."""
        self.mock_service.get_balance = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/balance/fake")
        assert response.status_code == 500

    def test_status_error_handling(self):
        """Test error handling for status endpoint."""
        self.mock_service.get_system_status = AsyncMock(side_effect=Exception("Error"))
        response = self.client.get("/status")
        assert response.status_code == 500
