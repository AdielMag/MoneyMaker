"""
Trader Service - FastAPI Application

Provides endpoints for executing trades.
"""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from services.trader.service import TraderService, get_trader_service
from shared.config import get_settings
from shared.models import (
    BalanceResponse,
    HealthResponse,
    Order,
    Position,
    TradingMode,
)

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MoneyMaker - Trader",
    description="Order execution service for real and fake trading",
    version="0.1.0",
)

# CORS removed - requests come through dashboard proxy (server-to-server, no CORS needed)
settings = get_settings()

# Service instance
_trader_service: TraderService | None = None


def get_service() -> TraderService:
    """Get or create trader service instance."""
    global _trader_service
    if _trader_service is None:
        _trader_service = get_trader_service()
    return _trader_service


# =============================================================================
# Request/Response Models
# =============================================================================


class BuyOrderRequest(BaseModel):
    """Request model for placing a buy order."""

    market_id: str = Field(..., description="Market condition ID")
    outcome: str = Field(..., description="Outcome to buy (Yes/No)")
    amount: float = Field(..., gt=0, description="Amount to spend in USDC")
    price: float = Field(..., gt=0, le=1, description="Limit price (0-1)")
    mode: TradingMode = Field(default=TradingMode.FAKE, description="Trading mode")


class SellOrderRequest(BaseModel):
    """Request model for placing a sell order."""

    position: dict[str, Any] = Field(..., description="Position to close")
    price: float | None = Field(default=None, description="Limit price (optional)")


class ExecuteSuggestionRequest(BaseModel):
    """Request model for executing AI suggestion."""

    suggestion: dict[str, Any] = Field(..., description="AI suggestion")
    position_size: float = Field(..., gt=0, description="Amount to trade")
    mode: TradingMode = Field(default=TradingMode.FAKE, description="Trading mode")


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


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
        min_balance = settings.trading.min_balance_to_trade

        return BalanceResponse(
            mode=mode,
            balance=balance,
            available_for_trading=balance >= min_balance,
        )
    except Exception as e:
        logger.error("get_balance_error", mode=mode.value, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/can-trade", tags=["Balance"])
async def can_trade(
    mode: TradingMode = Query(..., description="Trading mode"),
    amount: float = Query(..., gt=0, description="Amount to trade"),
) -> dict[str, Any]:
    """
    Check if trading is possible for given amount.
    """
    service = get_service()

    try:
        can_trade, reason = await service.can_trade(mode, amount)
        return {
            "can_trade": can_trade,
            "reason": reason,
            "mode": mode.value,
            "amount": amount,
        }
    except Exception as e:
        logger.error("can_trade_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Order Endpoints
# =============================================================================


@app.post("/orders/buy", response_model=Order, tags=["Orders"])
async def place_buy_order(request: BuyOrderRequest) -> Order:
    """
    Place a buy order.
    """
    service = get_service()

    try:
        # Check if we can trade
        can_trade, reason = await service.can_trade(request.mode, request.amount)
        if not can_trade:
            raise HTTPException(status_code=400, detail=reason)

        order = await service.place_buy_order(
            market_id=request.market_id,
            outcome=request.outcome,
            amount=request.amount,
            price=request.price,
            mode=request.mode,
        )

        return order

    except HTTPException:
        raise
    except Exception as e:
        logger.error("buy_order_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/sell", response_model=Order, tags=["Orders"])
async def place_sell_order(request: SellOrderRequest) -> Order:
    """
    Place a sell order to close a position.
    """
    service = get_service()

    try:
        position = Position(**request.position)
        order = await service.place_sell_order(position, request.price)
        return order

    except Exception as e:
        logger.error("sell_order_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/execute-suggestion", response_model=Order, tags=["Orders"])
async def execute_suggestion(request: ExecuteSuggestionRequest) -> Order:
    """
    Execute a trade based on AI suggestion.
    """
    service = get_service()

    try:
        from shared.models import AISuggestion

        suggestion = AISuggestion(**request.suggestion)

        # Check if we can trade
        can_trade, reason = await service.can_trade(request.mode, request.position_size)
        if not can_trade:
            raise HTTPException(status_code=400, detail=reason)

        order = await service.execute_suggestion(
            suggestion=suggestion,
            position_size=request.position_size,
            mode=request.mode,
        )

        return order

    except HTTPException:
        raise
    except Exception as e:
        logger.error("execute_suggestion_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration Endpoint
# =============================================================================


@app.get("/config", tags=["Configuration"])
async def get_trading_config() -> dict[str, Any]:
    """
    Get current trading configuration.
    """
    return {
        "min_balance_to_trade": settings.trading.min_balance_to_trade,
        "max_bet_amount": settings.trading.max_bet_amount,
        "max_positions": settings.trading.max_positions,
        "real_money_enabled": settings.real_money_enabled,
        "fake_money_enabled": settings.fake_money_enabled,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port + 2,
        reload=settings.api.debug,
    )
