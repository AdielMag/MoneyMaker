"""
Position Monitor Service - FastAPI Application

Provides endpoints for monitoring positions and triggering sells.
"""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.models import HealthResponse, Position, TradingMode
from services.monitor.service import MonitorService, get_monitor_service

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MoneyMaker - Position Monitor",
    description="Position monitoring and automated sell triggers",
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
_monitor_service: MonitorService | None = None


def get_service() -> MonitorService:
    """Get or create monitor service instance."""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = get_monitor_service()
    return _monitor_service


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


# =============================================================================
# Position Endpoints
# =============================================================================


@app.get("/positions/{mode}", tags=["Positions"])
async def get_positions(mode: TradingMode) -> list[dict[str, Any]]:
    """
    Get open positions for a trading mode.
    """
    service = get_service()
    
    try:
        positions = await service.get_positions(mode)
        positions = await service.update_position_prices(positions)
        return [p.model_dump() for p in positions]
    except Exception as e:
        logger.error("get_positions_error", mode=mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions/{mode}/summary", tags=["Positions"])
async def get_positions_summary(mode: TradingMode) -> dict[str, Any]:
    """
    Get summary of current positions.
    """
    service = get_service()
    
    try:
        return await service.get_positions_summary(mode)
    except Exception as e:
        logger.error("get_summary_error", mode=mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Monitoring Endpoints
# =============================================================================


@app.post("/monitor/{mode}", tags=["Monitoring"])
async def monitor_positions(mode: TradingMode) -> dict[str, Any]:
    """
    Monitor all positions and trigger sells as needed.
    
    Checks each position against stop-loss and take-profit thresholds,
    executing sell orders when triggered.
    """
    service = get_service()
    
    try:
        results = await service.monitor_positions(mode)
        return results
    except Exception as e:
        logger.error("monitor_error", mode=mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/check-position", tags=["Monitoring"])
async def check_position(position: dict[str, Any]) -> dict[str, Any]:
    """
    Check if a single position should be sold.
    """
    service = get_service()
    
    try:
        pos = Position(**position)
        should_sell, action, reason = await service.check_position(pos)
        
        return {
            "position_id": pos.id,
            "should_sell": should_sell,
            "action": action,
            "reason": reason,
            "pnl_percent": pos.pnl_percent,
            "thresholds": {
                "stop_loss": service.stop_loss_threshold,
                "take_profit": service.take_profit_threshold,
            },
        }
    except Exception as e:
        logger.error("check_position_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration Endpoint
# =============================================================================


@app.get("/config", tags=["Configuration"])
async def get_monitor_config() -> dict[str, Any]:
    """
    Get current monitoring configuration.
    """
    return {
        "stop_loss_percent": settings.trading.sell_thresholds.stop_loss_percent,
        "take_profit_percent": settings.trading.sell_thresholds.take_profit_percent,
        "max_positions": settings.trading.max_positions,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port + 3,
        reload=settings.api.debug,
    )
