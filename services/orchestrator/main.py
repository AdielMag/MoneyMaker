"""
Orchestrator Service - Main FastAPI Application

Main entry point for the MoneyMaker trading system.
Provides unified API for all trading operations.
"""

import asyncio
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from services.orchestrator.service import OrchestratorService, get_orchestrator_service
from shared.config import get_settings
from shared.models import (
    BalanceResponse,
    HealthResponse,
    TradingMode,
    WorkflowRunResult,
)

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MoneyMaker - Orchestrator",
    description="AI-Powered Polymarket Trading System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS removed - requests come through dashboard proxy (server-to-server, no CORS needed)
settings = get_settings()

# Service instance
_orchestrator: OrchestratorService | None = None


def get_service() -> OrchestratorService:
    """Get or create orchestrator service instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = get_orchestrator_service()
    return _orchestrator


# =============================================================================
# Request/Response Models
# =============================================================================


class WorkflowTriggerRequest(BaseModel):
    """Request model for triggering a workflow."""

    mode: TradingMode = Field(default=TradingMode.FAKE, description="Trading mode")


class ToggleWorkflowRequest(BaseModel):
    """Request model for toggling a workflow."""

    workflow_id: str = Field(..., description="Workflow ID (discovery or monitor)")
    mode: TradingMode = Field(..., description="Trading mode")
    enabled: bool = Field(..., description="New enabled state")


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint."""
    return {"status": "ready"}


@app.get("/status", tags=["Health"])
async def system_status() -> dict[str, Any]:
    """
    Get overall system status.

    Returns system configuration, balances, and position summary.
    """
    service = get_service()

    try:
        # Set timeout to 30 seconds for status check
        return await asyncio.wait_for(
            service.get_system_status(),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        logger.error("status_timeout")
        raise HTTPException(
            status_code=504,
            detail="Status check timed out. One or more services may be slow to respond."
        )
    except Exception as e:
        logger.error("status_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Workflow Endpoints
# =============================================================================


@app.post("/workflow/discover", response_model=WorkflowRunResult, tags=["Workflows"])
async def trigger_discovery(request: WorkflowTriggerRequest) -> WorkflowRunResult:
    """
    Trigger the market discovery and betting workflow.

    1. Checks available balance
    2. Scrapes and filters markets
    3. Analyzes with AI
    4. Places buy orders for top suggestions

    Note: This is a long-running operation. Timeout is set to 240 seconds.
    """
    service = get_service()

    try:
        # Set timeout to 240 seconds for workflow execution
        timeout_seconds = 240.0
        result = await asyncio.wait_for(
            service.run_discovery(request.mode),
            timeout=timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        logger.error("discovery_timeout", mode=request.mode.value)
        raise HTTPException(
            status_code=504,
            detail=f"Discovery workflow timed out after {timeout_seconds} seconds. "
                   f"The operation may still be processing in the background."
        )
    except Exception as e:
        logger.error("discovery_error", mode=request.mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/monitor", response_model=WorkflowRunResult, tags=["Workflows"])
async def trigger_monitor(request: WorkflowTriggerRequest) -> WorkflowRunResult:
    """
    Trigger the position monitoring workflow.

    1. Gets open positions
    2. Updates current prices
    3. Checks against stop-loss/take-profit thresholds
    4. Executes sell orders as needed
    """
    service = get_service()

    try:
        result = await service.run_monitor(request.mode)
        return result
    except Exception as e:
        logger.error("monitor_error", mode=request.mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/toggle", tags=["Workflows"])
async def toggle_workflow(request: ToggleWorkflowRequest) -> dict[str, Any]:
    """
    Enable or disable a workflow.
    """
    service = get_service()

    try:
        state = await service.toggle_workflow(
            workflow_id=request.workflow_id,
            mode=request.mode,
            enabled=request.enabled,
        )
        return {
            "success": True,
            "workflow_id": request.workflow_id,
            "mode": request.mode.value,
            "enabled": state.enabled,
        }
    except Exception as e:
        logger.error("toggle_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflow/{workflow_id}/state", tags=["Workflows"])
async def get_workflow_state(
    workflow_id: str,
    mode: TradingMode = Query(..., description="Trading mode"),
) -> dict[str, Any]:
    """
    Get current state of a workflow.
    """
    service = get_service()

    try:
        state = await service.get_workflow_state(workflow_id, mode)
        if state is None:
            return {"exists": False, "workflow_id": workflow_id, "mode": mode.value}
        return {"exists": True, **state.model_dump()}
    except Exception as e:
        logger.error("get_state_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Market Endpoints
# =============================================================================


@app.get("/markets", tags=["Markets"])
async def get_markets(
    limit: int = Query(default=50, le=100, ge=1),
    filtered: bool = Query(default=True, description="Apply default filters"),
) -> list[dict[str, Any]]:
    """
    Get available markets.

    Note: This operation may take time as it fetches and filters markets from Polymarket.
    Timeout is set to 240 seconds to allow for slow API responses.
    """
    service = get_service()

    try:
        # Set timeout to 240 seconds (4 minutes) - Cloud Run default is 300s
        # This gives us time to complete but ensures we return before Cloud Run times out
        timeout_seconds = 240.0
        return await asyncio.wait_for(
            service.get_markets(limit=limit, filtered=filtered),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error(
            "get_markets_timeout",
            limit=limit,
            filtered=filtered,
            timeout_seconds=timeout_seconds
        )
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {timeout_seconds} seconds. "
                   f"The market fetching operation took too long. Try reducing the limit parameter."
        )
    except Exception as e:
        logger.error("get_markets_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


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
        # Set timeout to 60 seconds for position fetching
        return await asyncio.wait_for(
            service.get_positions(mode),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.error("get_positions_timeout", mode=mode.value)
        raise HTTPException(
            status_code=504,
            detail="Position fetching timed out. The operation may be slow due to price updates."
        )
    except Exception as e:
        logger.error("get_positions_error", mode=mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Balance Endpoints
# =============================================================================


@app.get("/balance/{mode}", response_model=BalanceResponse, tags=["Balance"])
async def get_balance(mode: TradingMode) -> BalanceResponse:
    """
    Get current balance for trading mode.
    """
    service = get_service()

    try:
        balance = await service.get_balance(mode)
        return BalanceResponse(
            mode=mode,
            balance=balance,
            available_for_trading=balance >= settings.trading.min_balance_to_trade,
        )
    except Exception as e:
        logger.error("get_balance_error", mode=mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration Endpoints
# =============================================================================


@app.get("/config", tags=["Configuration"])
async def get_config() -> dict[str, Any]:
    """
    Get current system configuration.
    """
    return {
        "trading": {
            "min_balance_to_trade": settings.trading.min_balance_to_trade,
            "max_bet_amount": settings.trading.max_bet_amount,
            "max_positions": settings.trading.max_positions,
            "stop_loss_percent": settings.trading.sell_thresholds.stop_loss_percent,
            "take_profit_percent": settings.trading.sell_thresholds.take_profit_percent,
        },
        "market_filters": {
            "min_volume": settings.market_filters.min_volume,
            "max_time_to_resolution_hours": settings.market_filters.max_time_to_resolution_hours,
            "min_liquidity": settings.market_filters.min_liquidity,
            "excluded_categories": settings.market_filters.excluded_categories,
        },
        "ai": {
            "model": settings.ai.model,
            "max_suggestions": settings.ai.max_suggestions,
            "confidence_threshold": settings.ai.confidence_threshold,
        },
        "feature_flags": {
            "real_money_enabled": settings.real_money_enabled,
            "fake_money_enabled": settings.fake_money_enabled,
        },
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
