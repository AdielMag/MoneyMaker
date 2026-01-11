"""
MoneyMaker Shared Modules

This package contains shared utilities, clients, and models used across all services.
"""

from shared.config import Settings, get_settings
from shared.models import (
    AIAnalysisResult,
    AISuggestion,
    Market,
    MarketOutcome,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    TradingMode,
    Transaction,
    TransactionType,
    Wallet,
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
