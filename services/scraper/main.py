"""
Market Scraper Service - FastAPI Application

Provides endpoints for fetching and filtering Polymarket markets.
"""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.models import HealthResponse, ErrorResponse, Market, MarketQueryParams
from services.scraper.service import ScraperService, get_scraper_service

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MoneyMaker - Market Scraper",
    description="Scrapes and filters Polymarket markets for trading opportunities",
    version="0.1.0",
)

# Add CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service instance
_scraper_service: ScraperService | None = None


def get_service() -> ScraperService:
    """Get or create scraper service instance."""
    global _scraper_service
    if _scraper_service is None:
        _scraper_service = get_scraper_service()
    return _scraper_service


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict[str, str]:
    """Readiness check - verifies service can connect to dependencies."""
    # Could add Polymarket API health check here
    return {"status": "ready"}


# =============================================================================
# Market Endpoints
# =============================================================================


@app.get("/markets", response_model=list[Market], tags=["Markets"])
async def get_markets(
    limit: int = Query(default=50, le=100, ge=1, description="Maximum markets to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    filtered: bool = Query(default=True, description="Apply default filters"),
) -> list[Market]:
    """
    Get markets from Polymarket.
    
    Returns active markets, optionally filtered by default criteria.
    """
    service = get_service()
    
    try:
        if filtered:
            markets, _ = await service.get_filtered_markets(limit=limit, offset=offset)
        else:
            markets = await service.get_markets(limit=limit, offset=offset)
        
        return markets
    except Exception as e:
        logger.error("get_markets_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/markets/tradeable", response_model=list[Market], tags=["Markets"])
async def get_tradeable_markets(
    max_markets: int = Query(default=20, le=50, ge=1, description="Maximum markets to return"),
) -> list[Market]:
    """
    Get markets ready for trading.
    
    Returns filtered markets sorted by volume/opportunity.
    """
    service = get_service()
    
    try:
        markets = await service.get_tradeable_markets(max_markets=max_markets)
        return markets
    except Exception as e:
        logger.error("get_tradeable_markets_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/markets/{market_id}", response_model=Market, tags=["Markets"])
async def get_market(market_id: str) -> Market:
    """
    Get a specific market by ID.
    """
    service = get_service()
    
    try:
        market = await service.get_market(market_id)
        if market is None:
            raise HTTPException(status_code=404, detail=f"Market {market_id} not found")
        return market
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_market_error", market_id=market_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/markets/filter", tags=["Markets"])
async def filter_markets(
    category: str | None = Query(default=None, description="Filter by category"),
    min_volume: int | None = Query(default=None, ge=0, description="Minimum volume"),
    max_time_hours: float | None = Query(default=None, ge=0, description="Max hours to resolution"),
    limit: int = Query(default=50, le=100, ge=1, description="Maximum markets to return"),
) -> dict[str, Any]:
    """
    Fetch and filter markets with custom criteria.
    
    Returns filtered markets and summary statistics.
    """
    service = get_service()
    
    try:
        # Fetch base markets
        markets, summary = await service.get_filtered_markets(limit=limit * 2)
        
        # Apply custom filters
        if category or min_volume is not None or max_time_hours is not None:
            markets = service.apply_custom_filter(
                markets,
                category=category,
                min_volume=min_volume,
                max_time_hours=max_time_hours,
            )
        
        # Limit results
        markets = markets[:limit]
        
        return {
            "markets": [m.model_dump() for m in markets],
            "count": len(markets),
            "filter_summary": summary,
            "applied_filters": {
                "category": category,
                "min_volume": min_volume,
                "max_time_hours": max_time_hours,
            },
        }
    except Exception as e:
        logger.error("filter_markets_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/markets/summary", tags=["Markets"])
async def get_markets_summary() -> dict[str, Any]:
    """
    Get summary statistics about available markets.
    """
    service = get_service()
    
    try:
        # Fetch a batch of markets
        markets, summary = await service.get_filtered_markets(limit=100)
        
        # Calculate additional stats
        if markets:
            avg_volume = sum(m.volume for m in markets) / len(markets)
            avg_liquidity = sum(m.liquidity for m in markets) / len(markets)
            categories = list(set(m.category for m in markets if m.category))
        else:
            avg_volume = 0
            avg_liquidity = 0
            categories = []
        
        return {
            **summary,
            "average_volume": avg_volume,
            "average_liquidity": avg_liquidity,
            "categories": categories,
        }
    except Exception as e:
        logger.error("get_summary_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Filter Configuration Endpoint
# =============================================================================


@app.get("/filters/config", tags=["Configuration"])
async def get_filter_config() -> dict[str, Any]:
    """
    Get current filter configuration.
    """
    settings = get_settings()
    config = settings.market_filters
    
    return {
        "min_volume": config.min_volume,
        "max_time_to_resolution_hours": config.max_time_to_resolution_hours,
        "min_liquidity": config.min_liquidity,
        "excluded_categories": config.excluded_categories,
        "min_price": config.min_price,
        "max_price": config.max_price,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
    )
