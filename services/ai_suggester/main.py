"""
AI Suggester Service - FastAPI Application

Provides endpoints for AI-powered market analysis.
"""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from services.ai_suggester.service import AISuggesterService, get_ai_suggester_service
from shared.config import get_settings
from shared.models import AIAnalysisResult, AISuggestion, HealthResponse, Market

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MoneyMaker - AI Suggester",
    description="AI-powered market analysis and trading suggestions",
    version="0.1.0",
)

# CORS removed - requests come through dashboard proxy (server-to-server, no CORS needed)
settings = get_settings()

# Service instance
_ai_service: AISuggesterService | None = None


def get_service() -> AISuggesterService:
    """Get or create AI suggester service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = get_ai_suggester_service()
    return _ai_service


# =============================================================================
# Request/Response Models
# =============================================================================


class AnalyzeMarketsRequest(BaseModel):
    """Request model for market analysis."""

    markets: list[dict[str, Any]] = Field(..., description="Markets to analyze")
    max_suggestions: int = Field(default=5, ge=1, le=10)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class TradeDecisionRequest(BaseModel):
    """Request model for trade decision."""

    suggestion: dict[str, Any] = Field(..., description="AI suggestion to evaluate")
    wallet_balance: float = Field(..., gt=0, description="Current wallet balance")
    max_position_percent: float = Field(default=0.1, gt=0, le=0.5)


class TradeDecisionResponse(BaseModel):
    """Response model for trade decision."""

    should_trade: bool
    reason: str
    recommended_size: float


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


# =============================================================================
# Analysis Endpoints
# =============================================================================


@app.post("/analyze", response_model=AIAnalysisResult, tags=["Analysis"])
async def analyze_markets(request: AnalyzeMarketsRequest) -> AIAnalysisResult:
    """
    Analyze markets and generate trading suggestions.

    Accepts a list of markets and returns AI-generated suggestions
    with confidence scores and reasoning.
    """
    service = get_service()

    try:
        # Convert dict markets to Market objects
        markets = []
        for m in request.markets:
            try:
                markets.append(Market(**m))
            except Exception as e:
                logger.warning("invalid_market_data", error=str(e))
                continue

        if not markets:
            raise HTTPException(status_code=400, detail="No valid markets provided")

        result = await service.analyze_markets(
            markets=markets,
            max_suggestions=request.max_suggestions,
            confidence_threshold=request.confidence_threshold,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("analyze_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/top", tags=["Analysis"])
async def get_top_suggestions(
    request: AnalyzeMarketsRequest,
    top_n: int = Query(default=3, ge=1, le=10),
) -> list[AISuggestion]:
    """
    Get top N suggestions by confidence.
    """
    service = get_service()

    try:
        markets = [Market(**m) for m in request.markets]
        suggestions = await service.get_top_suggestions(markets, top_n=top_n)
        return suggestions
    except Exception as e:
        logger.error("top_suggestions_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/insight", tags=["Analysis"])
async def get_market_insight(market: dict[str, Any]) -> dict[str, str]:
    """
    Get a brief AI insight for a single market.
    """
    service = get_service()

    try:
        market_obj = Market(**market)
        insight = await service.get_market_insight(market_obj)
        return {"market_id": market_obj.id, "insight": insight}
    except Exception as e:
        logger.error("insight_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/risk", tags=["Analysis"])
async def assess_risk(
    market: dict[str, Any],
    position_size: float = Query(..., gt=0),
    wallet_balance: float = Query(..., gt=0),
) -> dict[str, Any]:
    """
    Assess the risk of a potential trade.
    """
    service = get_service()

    try:
        market_obj = Market(**market)
        assessment = await service.assess_trade_risk(
            market=market_obj,
            position_size=position_size,
            wallet_balance=wallet_balance,
        )
        return assessment
    except Exception as e:
        logger.error("risk_assessment_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/decision", response_model=TradeDecisionResponse, tags=["Analysis"])
async def should_trade(request: TradeDecisionRequest) -> TradeDecisionResponse:
    """
    Determine if a suggested trade should be executed.
    """
    service = get_service()

    try:
        suggestion = AISuggestion(**request.suggestion)
        should_trade, reason, size = await service.should_trade(
            suggestion=suggestion,
            wallet_balance=request.wallet_balance,
            max_position_percent=request.max_position_percent,
        )
        return TradeDecisionResponse(
            should_trade=should_trade,
            reason=reason,
            recommended_size=size,
        )
    except Exception as e:
        logger.error("decision_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration Endpoint
# =============================================================================


@app.get("/config", tags=["Configuration"])
async def get_ai_config() -> dict[str, Any]:
    """
    Get current AI configuration.
    """
    settings = get_settings()
    return {
        "model": settings.ai.model,
        "max_suggestions": settings.ai.max_suggestions,
        "confidence_threshold": settings.ai.confidence_threshold,
        "temperature": settings.ai.temperature,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port + 1,  # Different port from scraper
        reload=settings.api.debug,
    )
