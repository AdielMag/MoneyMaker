"""
Unit tests for shared/gemini_client.py
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.gemini_client import (
    GeminiAPIError,
    GeminiClient,
    MARKET_ANALYSIS_PROMPT,
    get_gemini_client,
)
from shared.models import AIAnalysisResult, AISuggestion, Market, MarketOutcome, RiskLevel


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.gemini_api_key = "test-gemini-key"
    settings.ai = MagicMock()
    settings.ai.model = "gemini-1.5-pro"
    settings.ai.temperature = 0.3
    settings.ai.max_tokens = 2048
    settings.ai.max_suggestions = 5
    return settings


@pytest.fixture
def gemini_client(mock_settings):
    """Create a Gemini client with mock settings."""
    with patch('shared.gemini_client.genai'):
        client = GeminiClient(settings=mock_settings)
        return client


@pytest.fixture
def sample_markets():
    """Create sample markets for testing."""
    return [
        Market(
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
        ),
        Market(
            id="market-002",
            question="Will ETH flip BTC?",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(hours=2),
            volume=30000,
            liquidity=15000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.05),
                MarketOutcome(name="No", price=0.95),
            ],
        ),
    ]


class TestGeminiClient:
    """Tests for GeminiClient class."""
    
    def test_initialization(self, gemini_client, mock_settings):
        """Test client initialization."""
        assert gemini_client.settings == mock_settings
        assert gemini_client._configured is False
    
    def test_ensure_configured(self, gemini_client):
        """Test API configuration."""
        with patch('shared.gemini_client.genai') as mock_genai:
            gemini_client._ensure_configured()
            
            mock_genai.configure.assert_called_once_with(
                api_key=gemini_client.settings.gemini_api_key
            )
            assert gemini_client._configured is True
    
    def test_ensure_configured_once(self, gemini_client):
        """Test API is only configured once."""
        with patch('shared.gemini_client.genai') as mock_genai:
            gemini_client._ensure_configured()
            gemini_client._ensure_configured()
            
            # Should only be called once
            assert mock_genai.configure.call_count == 1


class TestFormatMarketsForPrompt:
    """Tests for market formatting."""
    
    def test_format_markets_basic(self, gemini_client, sample_markets):
        """Test basic market formatting."""
        formatted = gemini_client._format_markets_for_prompt(sample_markets)
        
        assert "market-001" in formatted
        assert "Will BTC reach $100k?" in formatted
        assert "crypto" in formatted
        assert "Yes:" in formatted
        assert "No:" in formatted
    
    def test_format_markets_empty(self, gemini_client):
        """Test formatting empty markets list."""
        formatted = gemini_client._format_markets_for_prompt([])
        assert formatted == ""
    
    def test_format_markets_includes_all_fields(self, gemini_client, sample_markets):
        """Test all required fields are included."""
        formatted = gemini_client._format_markets_for_prompt(sample_markets)
        
        assert "Market ID:" in formatted
        assert "Question:" in formatted
        assert "Category:" in formatted
        assert "Time to Resolution:" in formatted
        assert "Volume:" in formatted
        assert "Liquidity:" in formatted
        assert "Outcomes:" in formatted


class TestParseResponse:
    """Tests for response parsing."""
    
    def test_parse_valid_response(self, gemini_client):
        """Test parsing valid JSON response."""
        response = json.dumps({
            "suggestions": [
                {
                    "market_id": "market-001",
                    "market_question": "Test market",
                    "recommended_outcome": "Yes",
                    "confidence": 0.85,
                    "reasoning": "Strong indicators",
                    "suggested_position_size": 0.1,
                    "risk_level": "low",
                }
            ],
            "markets_analyzed": 2,
            "overall_market_sentiment": "bullish",
        })
        
        result = gemini_client._parse_response(response, 2)
        
        assert isinstance(result, AIAnalysisResult)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].market_id == "market-001"
        assert result.suggestions[0].confidence == 0.85
        assert result.markets_analyzed == 2
    
    def test_parse_response_with_code_block(self, gemini_client):
        """Test parsing response wrapped in markdown code block."""
        inner_json = json.dumps({
            "suggestions": [],
            "markets_analyzed": 1,
            "overall_market_sentiment": "neutral",
        })
        response = f"```json\n{inner_json}\n```"
        
        result = gemini_client._parse_response(response, 1)
        
        assert isinstance(result, AIAnalysisResult)
        assert result.markets_analyzed == 1
    
    def test_parse_empty_suggestions(self, gemini_client):
        """Test parsing response with no suggestions."""
        response = json.dumps({
            "suggestions": [],
            "markets_analyzed": 3,
            "overall_market_sentiment": "uncertain",
        })
        
        result = gemini_client._parse_response(response, 3)
        
        assert len(result.suggestions) == 0
        assert result.overall_market_sentiment == "uncertain"
    
    def test_parse_invalid_json(self, gemini_client):
        """Test parsing invalid JSON response."""
        response = "This is not valid JSON at all!"
        
        result = gemini_client._parse_response(response, 2)
        
        assert isinstance(result, AIAnalysisResult)
        assert len(result.suggestions) == 0
        assert "Failed to parse" in result.reasoning
    
    def test_parse_malformed_suggestion(self, gemini_client):
        """Test parsing response with malformed suggestion."""
        response = json.dumps({
            "suggestions": [
                {"invalid": "data"},  # Missing required fields
                {
                    "market_id": "market-001",
                    "recommended_outcome": "Yes",
                    "confidence": 0.8,
                }
            ],
            "markets_analyzed": 2,
        })
        
        result = gemini_client._parse_response(response, 2)
        
        # Should skip invalid and parse valid
        assert len(result.suggestions) == 1
        assert result.suggestions[0].market_id == "market-001"


class TestParseRiskLevel:
    """Tests for risk level parsing."""
    
    def test_parse_valid_risk_levels(self, gemini_client):
        """Test parsing valid risk level strings."""
        assert gemini_client._parse_risk_level("very_low") == RiskLevel.VERY_LOW
        assert gemini_client._parse_risk_level("low") == RiskLevel.LOW
        assert gemini_client._parse_risk_level("medium") == RiskLevel.MEDIUM
        assert gemini_client._parse_risk_level("high") == RiskLevel.HIGH
        assert gemini_client._parse_risk_level("very_high") == RiskLevel.VERY_HIGH
    
    def test_parse_risk_level_case_insensitive(self, gemini_client):
        """Test risk level parsing is case insensitive."""
        assert gemini_client._parse_risk_level("LOW") == RiskLevel.LOW
        assert gemini_client._parse_risk_level("High") == RiskLevel.HIGH
    
    def test_parse_invalid_risk_level(self, gemini_client):
        """Test parsing invalid risk level defaults to medium."""
        assert gemini_client._parse_risk_level("invalid") == RiskLevel.MEDIUM
        assert gemini_client._parse_risk_level("") == RiskLevel.MEDIUM


class TestAnalyzeMarkets:
    """Tests for analyze_markets method."""
    
    @pytest.mark.asyncio
    async def test_analyze_markets_empty(self, gemini_client):
        """Test analyzing empty markets list."""
        result = await gemini_client.analyze_markets([])
        
        assert isinstance(result, AIAnalysisResult)
        assert len(result.suggestions) == 0
        assert result.markets_analyzed == 0
        assert "No markets provided" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_analyze_markets_success(self, gemini_client, sample_markets):
        """Test successful market analysis."""
        mock_response = json.dumps({
            "suggestions": [
                {
                    "market_id": "market-001",
                    "market_question": "Will BTC reach $100k?",
                    "recommended_outcome": "Yes",
                    "confidence": 0.8,
                    "reasoning": "Strong momentum",
                    "suggested_position_size": 0.1,
                    "risk_level": "medium",
                }
            ],
            "markets_analyzed": 2,
            "overall_market_sentiment": "bullish",
        })
        
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            
            result = await gemini_client.analyze_markets(sample_markets)
            
            assert len(result.suggestions) == 1
            assert result.suggestions[0].market_id == "market-001"
            assert result.overall_market_sentiment == "bullish"
    
    @pytest.mark.asyncio
    async def test_analyze_markets_api_error(self, gemini_client, sample_markets):
        """Test handling API error during analysis."""
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("API Error")
            
            with pytest.raises(GeminiAPIError) as exc_info:
                await gemini_client.analyze_markets(sample_markets)
            
            assert "Failed to analyze markets" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_analyze_markets_respects_max_suggestions(self, gemini_client, sample_markets):
        """Test max_suggestions parameter is passed to prompt."""
        mock_response = json.dumps({
            "suggestions": [],
            "markets_analyzed": 2,
            "overall_market_sentiment": "neutral",
        })
        
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            
            await gemini_client.analyze_markets(sample_markets, max_suggestions=3)
            
            # Check that prompt includes max_suggestions
            call_args = mock_generate.call_args[0][0]
            assert "Maximum Suggestions: 3" in call_args


class TestGetMarketInsight:
    """Tests for get_market_insight method."""
    
    @pytest.mark.asyncio
    async def test_get_market_insight_success(self, gemini_client, sample_markets):
        """Test successful insight generation."""
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "This market shows strong bullish momentum."
            
            insight = await gemini_client.get_market_insight(sample_markets[0])
            
            assert "bullish momentum" in insight
    
    @pytest.mark.asyncio
    async def test_get_market_insight_error(self, gemini_client, sample_markets):
        """Test insight generation error handling."""
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("API Error")
            
            insight = await gemini_client.get_market_insight(sample_markets[0])
            
            assert "Unable to generate insight" in insight


class TestAssessRisk:
    """Tests for assess_risk method."""
    
    @pytest.mark.asyncio
    async def test_assess_risk_success(self, gemini_client, sample_markets):
        """Test successful risk assessment."""
        mock_response = json.dumps({
            "risk_score": 6,
            "risk_level": "medium",
            "concerns": ["Volatile market", "Short time horizon"],
            "recommendation": "proceed",
        })
        
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            
            assessment = await gemini_client.assess_risk(
                market=sample_markets[0],
                position_size=50.0,
                wallet_balance=1000.0,
            )
            
            assert assessment["risk_score"] == 6
            assert assessment["risk_level"] == "medium"
            assert len(assessment["concerns"]) == 2
    
    @pytest.mark.asyncio
    async def test_assess_risk_error(self, gemini_client, sample_markets):
        """Test risk assessment error returns default."""
        with patch.object(gemini_client, '_generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("API Error")
            
            assessment = await gemini_client.assess_risk(
                market=sample_markets[0],
                position_size=50.0,
                wallet_balance=1000.0,
            )
            
            # Should return default values
            assert assessment["risk_score"] == 5
            assert assessment["risk_level"] == "medium"
            assert assessment["recommendation"] == "proceed"


class TestGetGeminiClient:
    """Tests for get_gemini_client helper function."""
    
    def test_get_gemini_client(self):
        """Test helper function creates client."""
        with patch('shared.gemini_client.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.gemini_api_key = "test-key"
            mock_settings.ai = MagicMock()
            mock_get_settings.return_value = mock_settings
            
            with patch('shared.gemini_client.genai'):
                client = get_gemini_client()
                
                assert isinstance(client, GeminiClient)


class TestMarketAnalysisPrompt:
    """Tests for the market analysis prompt."""
    
    def test_prompt_includes_json_format(self):
        """Test prompt specifies JSON format."""
        assert "JSON format" in MARKET_ANALYSIS_PROMPT
    
    def test_prompt_includes_confidence_threshold(self):
        """Test prompt mentions confidence threshold."""
        assert "confidence >= 0.7" in MARKET_ANALYSIS_PROMPT
    
    def test_prompt_includes_risk_levels(self):
        """Test prompt includes risk level options."""
        assert "very_low" in MARKET_ANALYSIS_PROMPT
        assert "low" in MARKET_ANALYSIS_PROMPT
        assert "medium" in MARKET_ANALYSIS_PROMPT
        assert "high" in MARKET_ANALYSIS_PROMPT
        assert "very_high" in MARKET_ANALYSIS_PROMPT
