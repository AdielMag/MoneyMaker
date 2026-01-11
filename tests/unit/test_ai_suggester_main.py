"""
Unit tests for AI Suggester service FastAPI endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import (
    AIAnalysisResult,
    AISuggestion,
    Market,
    MarketOutcome,
    RiskLevel,
)


@pytest.fixture
def mock_ai_service():
    """Create a mocked AI suggester service."""
    service = MagicMock()
    service.analyze_markets = AsyncMock(
        return_value=AIAnalysisResult(
            suggestions=[],
            markets_analyzed=0,
        )
    )
    service.get_top_suggestions = AsyncMock(return_value=[])
    service.get_market_insight = AsyncMock(return_value="Market insight")
    service.assess_trade_risk = AsyncMock(return_value={"risk_level": "medium"})
    service.should_trade = AsyncMock(return_value=(True, "Approved", 50.0))
    return service


@pytest.fixture
def sample_market():
    """Create a sample market."""
    return Market(
        id="market-001",
        question="Will BTC reach $100k?",
        category="crypto",
        end_date=datetime.utcnow() + timedelta(hours=1),
        volume=50000,
        liquidity=25000,
        outcomes=[
            MarketOutcome(name="Yes", price=0.35),
            MarketOutcome(name="No", price=0.65),
        ],
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
def client(mock_ai_service):
    """Create test client with mocked service."""
    with patch("services.ai_suggester.main._ai_service", None):
        with patch(
            "services.ai_suggester.main.get_ai_suggester_service",
            return_value=mock_ai_service,
        ):
            import services.ai_suggester.main as ai_main
            from services.ai_suggester.main import app

            # Reset service instance
            ai_main._ai_service = None

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


class TestAnalysisEndpoints:
    """Tests for AI analysis endpoints."""

    def test_analyze_markets_success(
        self, client, mock_ai_service, sample_market, sample_suggestion
    ):
        """Test successful market analysis."""
        mock_ai_service.analyze_markets = AsyncMock(
            return_value=AIAnalysisResult(
                suggestions=[sample_suggestion],
                markets_analyzed=1,
                overall_market_sentiment="bullish",
            )
        )

        response = client.post(
            "/analyze",
            json={
                "markets": [sample_market.model_dump(mode="json")],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["markets_analyzed"] == 1
        assert len(data["suggestions"]) == 1

    def test_analyze_markets_no_valid_markets(self, client, mock_ai_service):
        """Test analysis with no valid markets."""
        response = client.post(
            "/analyze",
            json={
                "markets": [{"invalid": "market"}],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )

        assert response.status_code == 400
        assert "No valid markets" in response.json()["detail"]

    def test_analyze_markets_empty_list(self, client, mock_ai_service):
        """Test analysis with empty markets list."""
        response = client.post(
            "/analyze",
            json={
                "markets": [],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )

        assert response.status_code == 400

    def test_analyze_markets_error(self, client, mock_ai_service, sample_market):
        """Test analysis error handling."""
        mock_ai_service.analyze_markets = AsyncMock(
            side_effect=Exception("AI Service Error")
        )

        response = client.post(
            "/analyze",
            json={
                "markets": [sample_market.model_dump(mode="json")],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )

        assert response.status_code == 500
        assert "AI Service Error" in response.json()["detail"]

    def test_get_top_suggestions(
        self, client, mock_ai_service, sample_market, sample_suggestion
    ):
        """Test getting top suggestions."""
        mock_ai_service.get_top_suggestions = AsyncMock(
            return_value=[sample_suggestion]
        )

        response = client.post(
            "/analyze/top?top_n=3",
            json={
                "markets": [sample_market.model_dump(mode="json")],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["market_id"] == "market-001"

    def test_get_top_suggestions_error(self, client, mock_ai_service, sample_market):
        """Test top suggestions error handling."""
        mock_ai_service.get_top_suggestions = AsyncMock(
            side_effect=Exception("Service Error")
        )

        response = client.post(
            "/analyze/top",
            json={
                "markets": [sample_market.model_dump(mode="json")],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )

        assert response.status_code == 500


class TestInsightEndpoints:
    """Tests for market insight endpoints."""

    def test_get_market_insight(self, client, mock_ai_service, sample_market):
        """Test getting market insight."""
        mock_ai_service.get_market_insight = AsyncMock(
            return_value="BTC showing strong momentum"
        )

        response = client.post(
            "/insight",
            json=sample_market.model_dump(mode="json"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["market_id"] == "market-001"
        assert "BTC showing strong momentum" in data["insight"]

    def test_get_market_insight_error(self, client, mock_ai_service, sample_market):
        """Test insight error handling."""
        mock_ai_service.get_market_insight = AsyncMock(
            side_effect=Exception("Insight Error")
        )

        response = client.post(
            "/insight",
            json=sample_market.model_dump(mode="json"),
        )

        assert response.status_code == 500


class TestRiskEndpoints:
    """Tests for risk assessment endpoints."""

    def test_assess_risk(self, client, mock_ai_service, sample_market):
        """Test risk assessment."""
        mock_ai_service.assess_trade_risk = AsyncMock(
            return_value={
                "risk_level": "medium",
                "risk_factors": ["High volatility"],
                "recommendation": "Proceed with caution",
            }
        )

        response = client.post(
            "/risk?position_size=50&wallet_balance=1000",
            json=sample_market.model_dump(mode="json"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "medium"

    def test_assess_risk_error(self, client, mock_ai_service, sample_market):
        """Test risk assessment error handling."""
        mock_ai_service.assess_trade_risk = AsyncMock(
            side_effect=Exception("Risk Error")
        )

        response = client.post(
            "/risk?position_size=50&wallet_balance=1000",
            json=sample_market.model_dump(mode="json"),
        )

        assert response.status_code == 500


class TestDecisionEndpoints:
    """Tests for trade decision endpoints."""

    def test_should_trade_approved(
        self, client, mock_ai_service, sample_suggestion
    ):
        """Test trade approval decision."""
        mock_ai_service.should_trade = AsyncMock(
            return_value=(True, "High confidence trade", 50.0)
        )

        response = client.post(
            "/decision",
            json={
                "suggestion": sample_suggestion.model_dump(),
                "wallet_balance": 1000.0,
                "max_position_percent": 0.1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["should_trade"] is True
        assert data["reason"] == "High confidence trade"
        assert data["recommended_size"] == 50.0

    def test_should_trade_rejected(self, client, mock_ai_service, sample_suggestion):
        """Test trade rejection decision."""
        mock_ai_service.should_trade = AsyncMock(
            return_value=(False, "Confidence below threshold", 0.0)
        )

        response = client.post(
            "/decision",
            json={
                "suggestion": sample_suggestion.model_dump(),
                "wallet_balance": 1000.0,
                "max_position_percent": 0.1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["should_trade"] is False

    def test_should_trade_error(self, client, mock_ai_service, sample_suggestion):
        """Test decision error handling."""
        mock_ai_service.should_trade = AsyncMock(
            side_effect=Exception("Decision Error")
        )

        response = client.post(
            "/decision",
            json={
                "suggestion": sample_suggestion.model_dump(),
                "wallet_balance": 1000.0,
                "max_position_percent": 0.1,
            },
        )

        assert response.status_code == 500


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_ai_config(self, client):
        """Test getting AI configuration."""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert "model" in data
        assert "max_suggestions" in data
        assert "confidence_threshold" in data
        assert "temperature" in data
