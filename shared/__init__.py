"""
MoneyMaker Shared Modules

This package contains shared utilities, clients, and models used across all services.
"""

from shared.config import Settings, get_settings
from shared.models import (
    Market,
    MarketOutcome,
    Position,
    Order,
    OrderSide,
    OrderStatus,
    TradingMode,
    Wallet,
    Transaction,
    TransactionType,
    AISuggestion,
    AIAnalysisResult,
    WorkflowState,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Models
    "Market",
    "MarketOutcome",
    "Position",
    "Order",
    "OrderSide",
    "OrderStatus",
    "TradingMode",
    "Wallet",
    "Transaction",
    "TransactionType",
    "AISuggestion",
    "AIAnalysisResult",
    "WorkflowState",
]
