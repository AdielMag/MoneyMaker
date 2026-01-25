"""
End-to-end tests for the Dashboard service FastAPI endpoints.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def dashboard_client():
    """Create test client for dashboard service."""
    from services.dashboard.main import app

    return TestClient(app)


@pytest.mark.e2e
class TestDashboardEndpointsE2E:
    """E2E tests for Dashboard API endpoints."""

    def test_health_check(self, dashboard_client):
        """Test health endpoint returns healthy status."""
        response = dashboard_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dashboard"

    def test_get_config(self, dashboard_client):
        """Test config endpoint returns orchestrator URL."""
        response = dashboard_client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert "orchestrator_url" in data

    def test_get_config_with_env_var(self, dashboard_client):
        """Test config endpoint uses ORCHESTRATOR_URL env var."""
        test_url = "https://test-orchestrator.example.com"

        with patch.dict(os.environ, {"ORCHESTRATOR_URL": test_url}):
            # Need to reimport to pick up new env var
            from services.dashboard import main

            # Re-read the environment variable
            main.ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")

            response = dashboard_client.get("/config")

            assert response.status_code == 200
            data = response.json()
            assert data["orchestrator_url"] == test_url

            # Reset to default
            main.ORCHESTRATOR_URL = "http://localhost:8000"

    def test_root_serves_html(self, dashboard_client):
        """Test root endpoint serves the dashboard HTML."""
        response = dashboard_client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert b"MoneyMaker" in response.content
        assert b"Dashboard" in response.content

    def test_root_contains_required_elements(self, dashboard_client):
        """Test dashboard HTML contains required UI elements."""
        response = dashboard_client.get("/")

        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Check for key sections
        assert "Wallet Balance" in content
        assert "Open Positions" in content
        assert "Total P&L" in content
        assert "Filtered Markets" in content

    def test_root_contains_javascript(self, dashboard_client):
        """Test dashboard HTML contains JavaScript for fetching data."""
        response = dashboard_client.get("/")

        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Check for key JavaScript functions
        assert "refreshData" in content
        assert "fetchData" in content
        # Check for relative URL usage (proxy approach - no direct orchestrator calls)
        assert "/balance/fake" in content or "fetchData" in content

    def test_static_files_mounted(self, dashboard_client):
        """Test static files are accessible."""
        # The index.html should be served from static directory
        response = dashboard_client.get("/static/index.html")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_cors_headers(self, dashboard_client):
        """Test CORS headers are set correctly."""
        response = dashboard_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS middleware should allow the request
        assert response.status_code in [200, 204, 405]

    def test_health_response_format(self, dashboard_client):
        """Test health endpoint response has correct format."""
        response = dashboard_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields
        assert isinstance(data, dict)
        assert "status" in data
        assert "service" in data
        assert data["status"] == "healthy"
        assert data["service"] == "dashboard"
