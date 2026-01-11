"""
Prompt templates for AI market analysis.

Contains prompt builders and templates for Gemini interactions.
"""

from datetime import datetime
from typing import Any

from shared.models import Market


class PromptBuilder:
    """
    Builds prompts for Gemini AI market analysis.
    
    Provides various prompt templates for different analysis tasks.
    """
    
    # Base system prompt for market analysis
    SYSTEM_PROMPT = """You are an expert prediction market analyst with deep knowledge of:
- Probability assessment and calibration
- News and event analysis
- Market dynamics and liquidity
- Risk management

Your task is to analyze prediction markets and identify opportunities for short-term profits (within 1 hour).

Key principles:
1. Focus on mispriced markets where current probability differs from true probability
2. Consider time decay - markets closer to resolution have less uncertainty
3. Avoid extreme prices (< 5% or > 95%) - limited upside, high risk
4. Factor in liquidity - ensure positions can be entered/exited
5. Be conservative - only suggest high-confidence opportunities"""

    # Analysis prompt template
    ANALYSIS_TEMPLATE = """{system_prompt}

## Analysis Parameters
- Current Time: {current_time}
- Maximum Suggestions: {max_suggestions}
- Confidence Threshold: {confidence_threshold}

## Markets to Analyze

{markets_text}

## Required Output Format

Respond with ONLY valid JSON in this exact format:
{{
    "suggestions": [
        {{
            "market_id": "string",
            "market_question": "string",
            "recommended_outcome": "Yes" or "No",
            "confidence": 0.0 to 1.0,
            "reasoning": "Brief explanation (2-3 sentences)",
            "suggested_position_size": 0.0 to 1.0,
            "risk_level": "very_low" | "low" | "medium" | "high" | "very_high"
        }}
    ],
    "markets_analyzed": number,
    "overall_market_sentiment": "bullish" | "bearish" | "neutral" | "uncertain"
}}

## Rules
- Only include suggestions with confidence >= {confidence_threshold}
- If no good opportunities exist, return empty suggestions array
- Be specific in reasoning - cite relevant factors
- Position size should reflect confidence and risk"""

    # Quick insight template
    INSIGHT_TEMPLATE = """Provide a brief market insight (2-3 sentences):

Market: {question}
Category: {category}
Current Prices: {prices}
Time to Resolution: {time_to_resolution:.1f} hours

Focus on: key factors, potential risks, price reasonableness."""

    # Risk assessment template
    RISK_TEMPLATE = """Assess the risk of this trade:

Market: {question}
Position Size: ${position_size:.2f} ({position_percent:.1f}% of balance)
Current Balance: ${balance:.2f}
Time to Resolution: {time_to_resolution:.1f} hours
Current Price: {current_price:.0%}

Respond in JSON:
{{
    "risk_score": 1-10,
    "risk_level": "very_low" | "low" | "medium" | "high" | "very_high",
    "concerns": ["list of specific concerns"],
    "recommendation": "proceed" | "reduce_size" | "avoid",
    "max_recommended_position": 0.0 to 1.0
}}"""

    @classmethod
    def build_analysis_prompt(
        cls,
        markets: list[Market],
        max_suggestions: int = 5,
        confidence_threshold: float = 0.7,
    ) -> str:
        """
        Build a market analysis prompt.
        
        Args:
            markets: Markets to analyze
            max_suggestions: Maximum suggestions to return
            confidence_threshold: Minimum confidence for suggestions
            
        Returns:
            Formatted prompt string
        """
        markets_text = cls._format_markets(markets)
        
        return cls.ANALYSIS_TEMPLATE.format(
            system_prompt=cls.SYSTEM_PROMPT,
            current_time=datetime.utcnow().isoformat(),
            max_suggestions=max_suggestions,
            confidence_threshold=confidence_threshold,
            markets_text=markets_text,
        )
    
    @classmethod
    def build_insight_prompt(cls, market: Market) -> str:
        """
        Build a quick insight prompt for a single market.
        
        Args:
            market: Market to analyze
            
        Returns:
            Formatted prompt string
        """
        prices = ", ".join(
            f"{o.name}: {o.price:.0%}" for o in market.outcomes
        )
        
        return cls.INSIGHT_TEMPLATE.format(
            question=market.question,
            category=market.category,
            prices=prices,
            time_to_resolution=market.compute_time_to_resolution(),
        )
    
    @classmethod
    def build_risk_prompt(
        cls,
        market: Market,
        position_size: float,
        balance: float,
        outcome: str,
    ) -> str:
        """
        Build a risk assessment prompt.
        
        Args:
            market: Market for the trade
            position_size: Proposed position size in USDC
            balance: Current wallet balance
            outcome: Outcome being traded (Yes/No)
            
        Returns:
            Formatted prompt string
        """
        position_percent = (position_size / balance * 100) if balance > 0 else 0
        current_price = market.get_outcome_price(outcome) or 0.5
        
        return cls.RISK_TEMPLATE.format(
            question=market.question,
            position_size=position_size,
            position_percent=position_percent,
            balance=balance,
            time_to_resolution=market.compute_time_to_resolution(),
            current_price=current_price,
        )
    
    @classmethod
    def _format_markets(cls, markets: list[Market]) -> str:
        """Format markets list for prompt inclusion."""
        if not markets:
            return "No markets provided."
        
        market_strings = []
        for i, market in enumerate(markets, 1):
            outcomes_str = ", ".join(
                f"{o.name}: {o.price:.1%}" for o in market.outcomes
            )
            time_to_res = market.compute_time_to_resolution()
            
            market_str = f"""### Market {i}
- ID: {market.id}
- Question: {market.question}
- Category: {market.category or 'Unknown'}
- Time to Resolution: {time_to_res:.2f} hours
- Volume: ${market.volume:,.0f}
- Liquidity: ${market.liquidity:,.0f}
- Outcomes: {outcomes_str}
"""
            market_strings.append(market_str)
        
        return "\n".join(market_strings)
    
    @classmethod
    def enhance_prompt_with_context(
        cls,
        base_prompt: str,
        context: dict[str, Any],
    ) -> str:
        """
        Enhance a prompt with additional context.
        
        Args:
            base_prompt: Base prompt to enhance
            context: Additional context to include
            
        Returns:
            Enhanced prompt string
        """
        context_str = "\n## Additional Context\n"
        for key, value in context.items():
            context_str += f"- {key}: {value}\n"
        
        return base_prompt + context_str
