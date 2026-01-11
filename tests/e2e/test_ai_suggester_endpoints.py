"""
End-to-end tests for the AI Suggester service FastAPI endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import AIAnalysisResult, AISuggestion, Market, MarketOutcome, RiskLevel


@pytest.fixture
def mock_markets():
    """Create mock markets for testing."""
    return [
        Market(
            id="market-001",
            question="Will BTC reach $100k?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=45),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        ),
        Market(
            id="market-002",
            question="Will ETH flip BTC?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(minutes=30),
            volume=30000,
            liquidity=15000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.10),
                MarketOutcome(name="No", price=0.90),
            ],
        ),
    ]


@pytest.fixture
def mock_ai_suggestions():
    """Create mock AI suggestions."""
    return AIAnalysisResult(
        suggestions=[
            AISuggestion(
                market_id="market-001",
                market_question="Will BTC reach $100k?",
                recommended_outcome="Yes",
                confidence=0.82,
                reasoning="Strong bullish momentum",
                suggested_position_size=0.1,
                risk_level=RiskLevel.MEDIUM,
            ),
            AISuggestion(
                market_id="market-002",
                market_question="Will ETH flip BTC?",
                recommended_outcome="No",
                confidence=0.90,
                reasoning="Unlikely in short term",
                suggested_position_size=0.15,
                risk_level=RiskLevel.LOW,
            ),
        ],
        markets_analyzed=2,
        overall_market_sentiment="bullish",
    )


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.api = MagicMock()
    settings.api.cors_origins = ["*"]
    settings.ai = MagicMock()
    settings.ai.model = "gemini-1.5-pro"
    settings.ai.max_suggestions = 5
    settings.ai.confidence_threshold = 0.7
    settings.ai.temperature = 0.3
    settings.trading = MagicMock()
    settings.trading.min_balance_to_trade = 10.0
    settings.trading.max_bet_amount = 50.0
    return settings


@pytest.fixture
def mock_ai_service(mock_ai_suggestions):
    """Create mock AI suggester service."""
    service = MagicMock()
    service.analyze_markets = AsyncMock(return_value=mock_ai_suggestions)
    service.get_top_suggestions = AsyncMock(return_value=mock_ai_suggestions.suggestions)
    service.get_market_insight = AsyncMock(return_value="BTC showing strong momentum")
    service.assess_trade_risk = AsyncMock(return_value={
        "risk_score": 5,
        "risk_level": "medium",
        "concerns": [],
        "recommendation": "proceed"
    })
    service.should_trade = AsyncMock(return_value=(True, "Trade approved", 25.0))
    return service


@pytest.mark.e2e
class TestAISuggesterEndpointsE2E:
    """End-to-end tests for AI suggester endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings, mock_ai_service):
        """Setup test fixtures."""
        with patch("services.ai_suggester.main.get_settings", return_value=mock_settings):
            with patch("services.ai_suggester.main.get_ai_suggester_service", return_value=mock_ai_service):
                with patch("services.ai_suggester.main._ai_service", None):
                    from services.ai_suggester import main
                    main._ai_service = None
                    self.client = TestClient(main.app)
                    self.mock_service = mock_ai_service
                    yield

    def test_health_check(self):
        """Test health endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_analyze_markets(self, mock_markets):
        """Test market analysis endpoint."""
        market_data = [m.model_dump(mode="json") for m in mock_markets]
        response = self.client.post(
            "/analyze",
            json={
                "markets": market_data,
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert "markets_analyzed" in data
        assert data["markets_analyzed"] == 2

    def test_analyze_markets_no_valid_markets(self):
        """Test analysis with no valid markets."""
        response = self.client.post(
            "/analyze",
            json={
                "markets": [{"invalid": "data"}],
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )
        assert response.status_code == 400
        assert "No valid markets" in response.json()["detail"]

    def test_get_top_suggestions(self, mock_markets):
        """Test getting top suggestions."""
        market_data = [m.model_dump(mode="json") for m in mock_markets]
        response = self.client.post(
            "/analyze/top?top_n=3",
            json={
                "markets": market_data,
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # Mock returns 2 suggestions

    def test_get_market_insight(self, mock_markets):
        """Test getting market insight."""
        market_data = mock_markets[0].model_dump(mode="json")
        response = self.client.post("/insight", json=market_data)
        assert response.status_code == 200
        data = response.json()
        assert "market_id" in data
        assert "insight" in data
        assert data["market_id"] == "market-001"

    def test_assess_risk(self, mock_markets):
        """Test risk assessment endpoint."""
        market_data = mock_markets[0].model_dump(mode="json")
        response = self.client.post(
            "/risk?position_size=50&wallet_balance=500",
            json=market_data,
        )
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "risk_level" in data
        assert "recommendation" in data

    def test_should_trade_decision(self, mock_ai_suggestions):
        """Test trade decision endpoint."""
        suggestion_data = mock_ai_suggestions.suggestions[0].model_dump(mode="json")
        response = self.client.post(
            "/decision",
            json={
                "suggestion": suggestion_data,
                "wallet_balance": 500.0,
                "max_position_percent": 0.1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "should_trade" in data
        assert "reason" in data
        assert "recommended_size" in data
        assert data["should_trade"] is True

    def test_get_ai_config(self, mock_settings):
        """Test getting AI configuration."""
        response = self.client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "model" in data
        assert "max_suggestions" in data
        assert "confidence_threshold" in data
        assert "temperature" in data

    def test_analyze_markets_error_handling(self, mock_markets):
        """Test error handling for analysis endpoint."""
        self.mock_service.analyze_markets = AsyncMock(side_effect=Exception("AI Error"))
        market_data = [m.model_dump(mode="json") for m in mock_markets]
        response = self.client.post(
            "/analyze",
            json={
                "markets": market_data,
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )
        assert response.status_code == 500

    def test_get_top_suggestions_error_handling(self, mock_markets):
        """Test error handling for top suggestions endpoint."""
        self.mock_service.get_top_suggestions = AsyncMock(side_effect=Exception("Error"))
        market_data = [m.model_dump(mode="json") for m in mock_markets]
        response = self.client.post(
            "/analyze/top",
            json={
                "markets": market_data,
                "max_suggestions": 5,
                "confidence_threshold": 0.7,
            },
        )
        assert response.status_code == 500

    def test_get_insight_error_handling(self, mock_markets):
        """Test error handling for insight endpoint."""
        self.mock_service.get_market_insight = AsyncMock(side_effect=Exception("Error"))
        market_data = mock_markets[0].model_dump(mode="json")
        response = self.client.post("/insight", json=market_data)
        assert response.status_code == 500

    def test_assess_risk_error_handling(self, mock_markets):
        """Test error handling for risk assessment endpoint."""
        self.mock_service.assess_trade_risk = AsyncMock(side_effect=Exception("Error"))
        market_data = mock_markets[0].model_dump(mode="json")
        response = self.client.post(
            "/risk?position_size=50&wallet_balance=500",
            json=market_data,
        )
        assert response.status_code == 500

    def test_trade_decision_error_handling(self, mock_ai_suggestions):
        """Test error handling for trade decision endpoint."""
        self.mock_service.should_trade = AsyncMock(side_effect=Exception("Error"))
        suggestion_data = mock_ai_suggestions.suggestions[0].model_dump(mode="json")
        response = self.client.post(
            "/decision",
            json={
                "suggestion": suggestion_data,
                "wallet_balance": 500.0,
                "max_position_percent": 0.1,
            },
        )
        assert response.status_code == 500
