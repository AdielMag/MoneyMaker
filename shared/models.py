"""
Pydantic models for MoneyMaker.

Defines all data models used across services.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Enums
# =============================================================================


class TradingMode(str, Enum):
    """Trading mode - real or fake money."""

    REAL = "real"
    FAKE = "fake"


class OrderSide(str, Enum):
    """Order side - buy or sell."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order execution status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TransactionType(str, Enum):
    """Transaction type for wallet operations."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BUY = "buy"
    SELL = "sell"
    FEE = "fee"


class RiskLevel(str, Enum):
    """Risk level for AI suggestions."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# =============================================================================
# Market Models
# =============================================================================


class MarketOutcome(BaseModel):
    """Represents a possible outcome in a market."""

    name: str
    price: float = Field(ge=0.0, le=1.0)

    @field_validator("price")
    @classmethod
    def round_price(cls, v: float) -> float:
        """Round price to 4 decimal places."""
        return round(v, 4)


class Market(BaseModel):
    """Represents a prediction market."""

    id: str
    question: str
    description: str = ""
    category: str = ""
    end_date: datetime
    volume: float = 0.0
    liquidity: float = 0.0
    outcomes: list[MarketOutcome] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Computed fields for filtering
    time_to_resolution_hours: float | None = None
    passes_filter: bool = True
    filter_reason: str | None = None

    def compute_time_to_resolution(self) -> float:
        """Calculate hours until market resolution."""
        now = datetime.now(timezone.utc)  # noqa: UP017
        # Handle both timezone-aware and naive end_dates
        end_date = self.end_date
        if end_date.tzinfo is None:
            # If end_date is naive, assume UTC
            end_date = end_date.replace(tzinfo=timezone.utc)  # noqa: UP017
        if end_date <= now:
            return 0.0
        delta = end_date - now
        return delta.total_seconds() / 3600

    def get_outcome_price(self, outcome_name: str) -> float | None:
        """Get price for a specific outcome."""
        for outcome in self.outcomes:
            if outcome.name.lower() == outcome_name.lower():
                return outcome.price
        return None


# =============================================================================
# Position Models
# =============================================================================


class Position(BaseModel):
    """Represents an open trading position."""

    id: str
    market_id: str
    market_question: str = ""
    outcome: str
    entry_price: float = Field(ge=0.0, le=1.0)
    current_price: float = Field(ge=0.0, le=1.0)
    quantity: float = Field(gt=0)
    entry_value: float = Field(ge=0)
    current_value: float = Field(ge=0)
    pnl_percent: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    mode: TradingMode = TradingMode.FAKE

    def calculate_pnl(self) -> float:
        """Calculate current P&L percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    def should_stop_loss(self, threshold: float = -15.0) -> bool:
        """Check if position should trigger stop loss."""
        return self.pnl_percent <= threshold

    def should_take_profit(self, threshold: float = 30.0) -> bool:
        """Check if position should trigger take profit."""
        return self.pnl_percent >= threshold

    def update_current_price(self, new_price: float) -> None:
        """Update current price and recalculate values."""
        self.current_price = new_price
        self.current_value = new_price * self.quantity
        self.pnl_percent = self.calculate_pnl()


# =============================================================================
# Order Models
# =============================================================================


class Order(BaseModel):
    """Represents a trading order."""

    id: str = ""
    market_id: str
    outcome: str
    side: OrderSide
    price: float = Field(ge=0.0, le=1.0)
    quantity: float = Field(gt=0)
    total_value: float = Field(ge=0)
    status: OrderStatus = OrderStatus.PENDING
    mode: TradingMode = TradingMode.FAKE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None
    error_message: str | None = None

    @field_validator("total_value", mode="before")
    @classmethod
    def calculate_total(cls, v: float, info: Any) -> float:
        """Calculate total value if not provided."""
        if v == 0 and "price" in info.data and "quantity" in info.data:
            return info.data["price"] * info.data["quantity"]
        return v


class OrderRequest(BaseModel):
    """Request model for placing an order."""

    market_id: str
    outcome: str
    side: OrderSide
    amount: float = Field(gt=0, description="Amount to spend/receive in USDC")
    mode: TradingMode = TradingMode.FAKE


class OrderResponse(BaseModel):
    """Response model after placing an order."""

    success: bool
    order: Order | None = None
    error: str | None = None


# =============================================================================
# Wallet Models
# =============================================================================


class Wallet(BaseModel):
    """Represents a trading wallet."""

    wallet_id: str
    balance: float = Field(ge=0)
    currency: str = "USDC"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def can_afford(self, amount: float) -> bool:
        """Check if wallet can afford a transaction."""
        return self.balance >= amount

    def deduct(self, amount: float) -> bool:
        """Deduct amount from balance."""
        if not self.can_afford(amount):
            return False
        self.balance -= amount
        self.updated_at = datetime.utcnow()
        return True

    def add(self, amount: float) -> None:
        """Add amount to balance."""
        self.balance += amount
        self.updated_at = datetime.utcnow()


class Transaction(BaseModel):
    """Represents a wallet transaction."""

    id: str
    wallet_id: str
    type: TransactionType
    amount: float
    balance_before: float
    balance_after: float
    reference_id: str | None = None  # Order ID or position ID
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# AI Models
# =============================================================================


class AISuggestion(BaseModel):
    """AI suggestion for a market trade."""

    market_id: str
    market_question: str = ""
    recommended_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    suggested_position_size: float = Field(ge=0.0, le=1.0, default=0.1)
    risk_level: RiskLevel = RiskLevel.MEDIUM

    def meets_threshold(self, threshold: float = 0.7) -> bool:
        """Check if suggestion meets confidence threshold."""
        return self.confidence >= threshold


class AIAnalysisResult(BaseModel):
    """Result of AI market analysis."""

    suggestions: list[AISuggestion] = Field(default_factory=list)
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    markets_analyzed: int = 0
    overall_market_sentiment: str = "neutral"
    reasoning: str = ""

    def get_high_confidence_suggestions(self, threshold: float = 0.7) -> list[AISuggestion]:
        """Get suggestions that meet confidence threshold."""
        return [s for s in self.suggestions if s.meets_threshold(threshold)]

    def get_top_suggestions(self, n: int = 5) -> list[AISuggestion]:
        """Get top N suggestions by confidence."""
        sorted_suggestions = sorted(self.suggestions, key=lambda s: s.confidence, reverse=True)
        return sorted_suggestions[:n]


# =============================================================================
# Workflow Models
# =============================================================================


class WorkflowState(BaseModel):
    """State of a trading workflow."""

    workflow_id: str
    mode: TradingMode
    enabled: bool = False
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    last_error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowRunResult(BaseModel):
    """Result of a workflow run."""

    workflow_id: str
    mode: TradingMode
    success: bool
    started_at: datetime
    completed_at: datetime
    markets_analyzed: int = 0
    suggestions_generated: int = 0
    orders_placed: int = 0
    errors: list[str] = Field(default_factory=list)


# =============================================================================
# API Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BalanceResponse(BaseModel):
    """Balance inquiry response."""

    mode: TradingMode
    balance: float
    currency: str = "USDC"
    available_for_trading: bool = True


class MarketQueryParams(BaseModel):
    """Query parameters for market filtering."""

    category: str | None = None
    min_volume: int | None = None
    max_time_to_resolution_hours: float | None = None
    min_liquidity: int | None = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)
