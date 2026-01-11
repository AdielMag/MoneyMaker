"""
AI Suggester service implementation.

Coordinates AI analysis for market suggestions.
"""

from typing import Any

import structlog

from shared.config import Settings, get_settings
from shared.gemini_client import GeminiClient, get_gemini_client
from shared.models import AIAnalysisResult, AISuggestion, Market
from services.ai_suggester.prompts import PromptBuilder

logger = structlog.get_logger(__name__)


class AISuggesterService:
    """
    Service for AI-powered market analysis and suggestions.
    
    Uses Gemini AI to analyze markets and generate trading recommendations.
    """
    
    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize AI suggester service.
        
        Args:
            gemini_client: Optional Gemini client instance
            settings: Optional Settings instance
        """
        self.settings = settings or get_settings()
        self._gemini_client = gemini_client
        self.prompt_builder = PromptBuilder()
    
    @property
    def gemini_client(self) -> GeminiClient:
        """Get or create Gemini client."""
        if self._gemini_client is None:
            self._gemini_client = get_gemini_client()
        return self._gemini_client
    
    async def analyze_markets(
        self,
        markets: list[Market],
        max_suggestions: int | None = None,
        confidence_threshold: float | None = None,
    ) -> AIAnalysisResult:
        """
        Analyze markets and generate trading suggestions.
        
        Args:
            markets: Markets to analyze
            max_suggestions: Maximum suggestions to return
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            AIAnalysisResult with suggestions
        """
        if max_suggestions is None:
            max_suggestions = self.settings.ai.max_suggestions
        
        if confidence_threshold is None:
            confidence_threshold = self.settings.ai.confidence_threshold
        
        logger.info(
            "analyzing_markets",
            count=len(markets),
            max_suggestions=max_suggestions,
            threshold=confidence_threshold,
        )
        
        if not markets:
            return AIAnalysisResult(
                suggestions=[],
                markets_analyzed=0,
                reasoning="No markets provided for analysis",
            )
        
        # Use Gemini client for analysis
        result = await self.gemini_client.analyze_markets(
            markets=markets,
            max_suggestions=max_suggestions,
        )
        
        # Filter by confidence threshold
        high_confidence = result.get_high_confidence_suggestions(confidence_threshold)
        
        logger.info(
            "analysis_complete",
            total_suggestions=len(result.suggestions),
            high_confidence=len(high_confidence),
            sentiment=result.overall_market_sentiment,
        )
        
        # Return result with only high-confidence suggestions
        return AIAnalysisResult(
            suggestions=high_confidence,
            analysis_timestamp=result.analysis_timestamp,
            markets_analyzed=result.markets_analyzed,
            overall_market_sentiment=result.overall_market_sentiment,
            reasoning=result.reasoning,
        )
    
    async def get_top_suggestions(
        self,
        markets: list[Market],
        top_n: int = 3,
    ) -> list[AISuggestion]:
        """
        Get top N suggestions by confidence.
        
        Args:
            markets: Markets to analyze
            top_n: Number of top suggestions to return
            
        Returns:
            List of top suggestions
        """
        result = await self.analyze_markets(
            markets=markets,
            max_suggestions=top_n * 2,  # Fetch more to filter
        )
        
        return result.get_top_suggestions(top_n)
    
    async def get_market_insight(self, market: Market) -> str:
        """
        Get a brief insight for a single market.
        
        Args:
            market: Market to analyze
            
        Returns:
            Brief insight text
        """
        return await self.gemini_client.get_market_insight(market)
    
    async def assess_trade_risk(
        self,
        market: Market,
        position_size: float,
        wallet_balance: float,
    ) -> dict[str, Any]:
        """
        Assess the risk of a potential trade.
        
        Args:
            market: Market for the trade
            position_size: Proposed position size
            wallet_balance: Current wallet balance
            
        Returns:
            Risk assessment dictionary
        """
        return await self.gemini_client.assess_risk(
            market=market,
            position_size=position_size,
            wallet_balance=wallet_balance,
        )
    
    async def should_trade(
        self,
        suggestion: AISuggestion,
        wallet_balance: float,
        max_position_percent: float = 0.1,
    ) -> tuple[bool, str, float]:
        """
        Determine if a suggested trade should be executed.
        
        Args:
            suggestion: AI suggestion to evaluate
            wallet_balance: Current wallet balance
            max_position_percent: Maximum position as % of balance
            
        Returns:
            Tuple of (should_trade, reason, recommended_size)
        """
        # Check confidence threshold
        min_confidence = self.settings.ai.confidence_threshold
        if suggestion.confidence < min_confidence:
            return False, f"Confidence {suggestion.confidence:.0%} below threshold {min_confidence:.0%}", 0.0
        
        # Calculate position size
        max_bet = self.settings.trading.max_bet_amount
        suggested_size = wallet_balance * suggestion.suggested_position_size
        
        # Cap at maximum
        position_size = min(suggested_size, max_bet, wallet_balance * max_position_percent)
        
        # Check minimum balance
        min_balance = self.settings.trading.min_balance_to_trade
        if wallet_balance < min_balance:
            return False, f"Balance ${wallet_balance:.2f} below minimum ${min_balance:.2f}", 0.0
        
        if position_size < 1.0:
            return False, f"Position size ${position_size:.2f} too small", 0.0
        
        return True, "Trade approved", position_size
    
    def filter_suggestions_by_risk(
        self,
        suggestions: list[AISuggestion],
        max_risk_level: str = "medium",
    ) -> list[AISuggestion]:
        """
        Filter suggestions by risk level.
        
        Args:
            suggestions: Suggestions to filter
            max_risk_level: Maximum acceptable risk level
            
        Returns:
            Filtered suggestions
        """
        risk_order = ["very_low", "low", "medium", "high", "very_high"]
        max_index = risk_order.index(max_risk_level)
        
        return [
            s for s in suggestions
            if risk_order.index(s.risk_level.value) <= max_index
        ]


# Factory function
def get_ai_suggester_service() -> AISuggesterService:
    """Create and return an AISuggesterService instance."""
    return AISuggesterService()
