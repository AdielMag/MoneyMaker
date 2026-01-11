"""
Gemini AI client for MoneyMaker.

Provides async interface to Google's Gemini AI for:
- Market analysis
- Trading suggestions
- Risk assessment
"""

import json
from datetime import datetime
from typing import Any

import google.generativeai as genai
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.config import Settings, get_settings
from shared.models import AIAnalysisResult, AISuggestion, Market, RiskLevel

logger = structlog.get_logger(__name__)


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors."""
    pass


# System prompt for market analysis
MARKET_ANALYSIS_PROMPT = """You are an expert prediction market analyst. Your task is to analyze prediction markets and identify opportunities for short-term profits (within 1 hour).

For each market, consider:
1. Current probability vs likely true probability
2. Time until resolution
3. Recent news or events that could affect outcome
4. Trading volume and liquidity
5. Risk/reward ratio

Provide your analysis in the following JSON format:
{
    "suggestions": [
        {
            "market_id": "string",
            "market_question": "string",
            "recommended_outcome": "Yes" or "No",
            "confidence": 0.0 to 1.0,
            "reasoning": "Brief explanation",
            "suggested_position_size": 0.0 to 1.0 (fraction of available balance),
            "risk_level": "very_low", "low", "medium", "high", or "very_high"
        }
    ],
    "markets_analyzed": number,
    "overall_market_sentiment": "bullish", "bearish", "neutral", or "uncertain"
}

Rules:
- Only suggest markets where you have confidence >= 0.7
- Focus on markets with clear, time-bound outcomes
- Avoid markets that are too close to resolution (< 5 minutes)
- Consider the current price - look for mispriced markets
- Be conservative with position sizing for high-risk suggestions
- If no good opportunities exist, return empty suggestions array

IMPORTANT: Return ONLY valid JSON, no additional text."""


class GeminiClient:
    """
    Client for Google's Gemini AI.
    
    Provides market analysis and trading suggestions using
    large language model capabilities.
    """
    
    def __init__(self, settings: Settings | None = None):
        """
        Initialize Gemini client.
        
        Args:
            settings: Settings instance. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self._configured = False
        self._model: genai.GenerativeModel | None = None
    
    def _ensure_configured(self) -> None:
        """Ensure Gemini API is configured."""
        if not self._configured:
            genai.configure(api_key=self.settings.gemini_api_key)
            self._configured = True
    
    @property
    def model(self) -> genai.GenerativeModel:
        """Get Gemini model instance."""
        self._ensure_configured()
        if self._model is None:
            self._model = genai.GenerativeModel(
                model_name=self.settings.ai.model,
                generation_config={
                    "temperature": self.settings.ai.temperature,
                    "max_output_tokens": self.settings.ai.max_tokens,
                    "response_mime_type": "application/json",
                },
            )
        return self._model
    
    def _format_markets_for_prompt(self, markets: list[Market]) -> str:
        """
        Format market data for the AI prompt.
        
        Args:
            markets: List of markets to analyze
            
        Returns:
            Formatted string for prompt
        """
        market_strings = []
        
        for market in markets:
            time_to_resolution = market.compute_time_to_resolution()
            
            outcomes_str = ", ".join(
                f"{o.name}: {o.price:.2%}" for o in market.outcomes
            )
            
            market_str = f"""
Market ID: {market.id}
Question: {market.question}
Category: {market.category}
Time to Resolution: {time_to_resolution:.2f} hours
Volume: ${market.volume:,.0f}
Liquidity: ${market.liquidity:,.0f}
Outcomes: {outcomes_str}
"""
            market_strings.append(market_str)
        
        return "\n---\n".join(market_strings)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def analyze_markets(
        self,
        markets: list[Market],
        max_suggestions: int | None = None,
    ) -> AIAnalysisResult:
        """
        Analyze markets and get trading suggestions.
        
        Args:
            markets: List of markets to analyze
            max_suggestions: Maximum suggestions to return
            
        Returns:
            AIAnalysisResult with suggestions
        """
        if not markets:
            return AIAnalysisResult(
                suggestions=[],
                markets_analyzed=0,
                overall_market_sentiment="neutral",
                reasoning="No markets provided for analysis",
            )
        
        if max_suggestions is None:
            max_suggestions = self.settings.ai.max_suggestions
        
        logger.info("analyzing_markets", count=len(markets))
        
        # Format markets for prompt
        markets_text = self._format_markets_for_prompt(markets)
        
        prompt = f"""{MARKET_ANALYSIS_PROMPT}

Current Time: {datetime.utcnow().isoformat()}
Maximum Suggestions: {max_suggestions}

Markets to Analyze:
{markets_text}
"""
        
        try:
            response = await self._generate_content(prompt)
            result = self._parse_response(response, len(markets))
            
            logger.info(
                "analysis_complete",
                markets_analyzed=result.markets_analyzed,
                suggestions_count=len(result.suggestions),
            )
            
            return result
            
        except Exception as e:
            logger.error("analyze_markets_error", error=str(e))
            raise GeminiAPIError(f"Failed to analyze markets: {str(e)}")
    
    async def _generate_content(self, prompt: str) -> str:
        """
        Generate content from Gemini.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated text response
        """
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error("gemini_generate_error", error=str(e))
            raise GeminiAPIError(f"Gemini API error: {str(e)}")
    
    def _parse_response(self, response_text: str, markets_count: int) -> AIAnalysisResult:
        """
        Parse Gemini response into AIAnalysisResult.
        
        Args:
            response_text: Raw response from Gemini
            markets_count: Number of markets analyzed
            
        Returns:
            Parsed AIAnalysisResult
        """
        try:
            # Clean response text
            text = response_text.strip()
            
            # Handle potential markdown code blocks
            if text.startswith("```"):
                # Remove code block markers
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            data = json.loads(text)
            
            suggestions = []
            for item in data.get("suggestions", []):
                try:
                    suggestion = AISuggestion(
                        market_id=item.get("market_id", ""),
                        market_question=item.get("market_question", ""),
                        recommended_outcome=item.get("recommended_outcome", ""),
                        confidence=float(item.get("confidence", 0)),
                        reasoning=item.get("reasoning", ""),
                        suggested_position_size=float(item.get("suggested_position_size", 0.1)),
                        risk_level=self._parse_risk_level(item.get("risk_level", "medium")),
                    )
                    suggestions.append(suggestion)
                except Exception as e:
                    logger.warning("parse_suggestion_error", error=str(e))
                    continue
            
            return AIAnalysisResult(
                suggestions=suggestions,
                markets_analyzed=data.get("markets_analyzed", markets_count),
                overall_market_sentiment=data.get("overall_market_sentiment", "neutral"),
            )
            
        except json.JSONDecodeError as e:
            logger.error("json_parse_error", error=str(e), response=response_text[:500])
            # Return empty result on parse error
            return AIAnalysisResult(
                suggestions=[],
                markets_analyzed=markets_count,
                overall_market_sentiment="uncertain",
                reasoning=f"Failed to parse AI response: {str(e)}",
            )
    
    def _parse_risk_level(self, value: str) -> RiskLevel:
        """Parse risk level string to enum."""
        try:
            return RiskLevel(value.lower())
        except ValueError:
            return RiskLevel.MEDIUM
    
    async def get_market_insight(self, market: Market) -> str:
        """
        Get a brief insight for a single market.
        
        Args:
            market: Market to analyze
            
        Returns:
            Brief insight text
        """
        prompt = f"""Provide a brief (2-3 sentences) insight about this prediction market:

Question: {market.question}
Category: {market.category}
Current Prices: {", ".join(f"{o.name}: {o.price:.0%}" for o in market.outcomes)}
Time to Resolution: {market.compute_time_to_resolution():.1f} hours

Focus on: key factors affecting the outcome, potential risks, and whether the current prices seem reasonable."""
        
        try:
            response = await self._generate_content(prompt)
            return response.strip()
        except Exception as e:
            logger.error("get_insight_error", market_id=market.id, error=str(e))
            return f"Unable to generate insight: {str(e)}"
    
    async def assess_risk(
        self,
        market: Market,
        position_size: float,
        wallet_balance: float,
    ) -> dict[str, Any]:
        """
        Assess risk of a potential trade.
        
        Args:
            market: Market to trade
            position_size: Proposed position size
            wallet_balance: Current wallet balance
            
        Returns:
            Risk assessment dictionary
        """
        position_percent = (position_size / wallet_balance * 100) if wallet_balance > 0 else 0
        
        prompt = f"""Assess the risk of this trade:

Market: {market.question}
Proposed Position: ${position_size:.2f} ({position_percent:.1f}% of balance)
Wallet Balance: ${wallet_balance:.2f}
Time to Resolution: {market.compute_time_to_resolution():.1f} hours

Respond in JSON format:
{{
    "risk_score": 1-10,
    "risk_level": "very_low/low/medium/high/very_high",
    "concerns": ["list of concerns"],
    "recommendation": "proceed/reduce_size/avoid"
}}"""
        
        try:
            response = await self._generate_content(prompt)
            return json.loads(response.strip())
        except Exception as e:
            logger.error("assess_risk_error", error=str(e))
            return {
                "risk_score": 5,
                "risk_level": "medium",
                "concerns": ["Unable to assess risk"],
                "recommendation": "proceed",
            }


# Convenience function for creating client
def get_gemini_client() -> GeminiClient:
    """Create and return a Gemini client instance."""
    return GeminiClient()
