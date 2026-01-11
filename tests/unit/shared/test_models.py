"""
Unit tests for shared/models.py
"""

from datetime import datetime, timedelta

import pytest

from shared.models import (
    # Enums
    TradingMode,
    OrderSide,
    OrderStatus,
    TransactionType,
    RiskLevel,
    # Market models
    MarketOutcome,
    Market,
    # Position models
    Position,
    # Order models
    Order,
    OrderRequest,
    OrderResponse,
    # Wallet models
    Wallet,
    Transaction,
    # AI models
    AISuggestion,
    AIAnalysisResult,
    # Workflow models
    WorkflowState,
    WorkflowRunResult,
    # API models
    HealthResponse,
    ErrorResponse,
    BalanceResponse,
    MarketQueryParams,
)


class TestEnums:
    """Tests for enum types."""
    
    def test_trading_mode_values(self):
        """Test TradingMode enum values."""
        assert TradingMode.REAL.value == "real"
        assert TradingMode.FAKE.value == "fake"
    
    def test_order_side_values(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"
    
    def test_order_status_values(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.FAILED.value == "failed"
    
    def test_transaction_type_values(self):
        """Test TransactionType enum values."""
        assert TransactionType.DEPOSIT.value == "deposit"
        assert TransactionType.BUY.value == "buy"
        assert TransactionType.SELL.value == "sell"
    
    def test_risk_level_values(self):
        """Test RiskLevel enum values."""
        assert RiskLevel.VERY_LOW.value == "very_low"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.VERY_HIGH.value == "very_high"


class TestMarketOutcome:
    """Tests for MarketOutcome model."""
    
    def test_basic_creation(self):
        """Test basic outcome creation."""
        outcome = MarketOutcome(name="Yes", price=0.65)
        assert outcome.name == "Yes"
        assert outcome.price == 0.65
    
    def test_price_rounding(self):
        """Test price is rounded to 4 decimal places."""
        outcome = MarketOutcome(name="Yes", price=0.123456789)
        assert outcome.price == 0.1235
    
    def test_price_validation_min(self):
        """Test price minimum validation."""
        with pytest.raises(ValueError):
            MarketOutcome(name="Yes", price=-0.1)
    
    def test_price_validation_max(self):
        """Test price maximum validation."""
        with pytest.raises(ValueError):
            MarketOutcome(name="Yes", price=1.1)
    
    def test_price_boundary_values(self):
        """Test price at boundary values."""
        outcome_min = MarketOutcome(name="Yes", price=0.0)
        assert outcome_min.price == 0.0
        
        outcome_max = MarketOutcome(name="Yes", price=1.0)
        assert outcome_max.price == 1.0


class TestMarket:
    """Tests for Market model."""
    
    @pytest.fixture
    def sample_market(self):
        """Create a sample market for testing."""
        return Market(
            id="test-market-001",
            question="Will BTC reach $100k?",
            description="Bitcoin price prediction",
            category="crypto",
            end_date=datetime.utcnow() + timedelta(hours=2),
            volume=50000,
            liquidity=25000,
            outcomes=[
                MarketOutcome(name="Yes", price=0.35),
                MarketOutcome(name="No", price=0.65),
            ],
        )
    
    def test_basic_creation(self, sample_market):
        """Test basic market creation."""
        assert sample_market.id == "test-market-001"
        assert sample_market.question == "Will BTC reach $100k?"
        assert len(sample_market.outcomes) == 2
    
    def test_compute_time_to_resolution(self, sample_market):
        """Test time to resolution calculation."""
        hours = sample_market.compute_time_to_resolution()
        assert 1.9 <= hours <= 2.1  # Allow small variance
    
    def test_compute_time_to_resolution_past(self):
        """Test time to resolution for past market."""
        market = Market(
            id="past-market",
            question="Past event",
            end_date=datetime.utcnow() - timedelta(hours=1),
        )
        assert market.compute_time_to_resolution() == 0.0
    
    def test_get_outcome_price_exists(self, sample_market):
        """Test getting price for existing outcome."""
        price = sample_market.get_outcome_price("Yes")
        assert price == 0.35
        
        price = sample_market.get_outcome_price("No")
        assert price == 0.65
    
    def test_get_outcome_price_case_insensitive(self, sample_market):
        """Test outcome price lookup is case insensitive."""
        price = sample_market.get_outcome_price("yes")
        assert price == 0.35
        
        price = sample_market.get_outcome_price("YES")
        assert price == 0.35
    
    def test_get_outcome_price_not_found(self, sample_market):
        """Test getting price for non-existent outcome."""
        price = sample_market.get_outcome_price("Maybe")
        assert price is None


class TestPosition:
    """Tests for Position model."""
    
    @pytest.fixture
    def sample_position(self):
        """Create a sample position for testing."""
        return Position(
            id="pos-001",
            market_id="market-001",
            market_question="Test market",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.35,
            quantity=100,
            entry_value=30.0,
            current_value=35.0,
            mode=TradingMode.FAKE,
        )
    
    def test_basic_creation(self, sample_position):
        """Test basic position creation."""
        assert sample_position.id == "pos-001"
        assert sample_position.entry_price == 0.30
        assert sample_position.current_price == 0.35
        assert sample_position.quantity == 100
    
    def test_calculate_pnl_positive(self, sample_position):
        """Test P&L calculation for profitable position."""
        pnl = sample_position.calculate_pnl()
        expected = ((0.35 - 0.30) / 0.30) * 100
        assert abs(pnl - expected) < 0.01
    
    def test_calculate_pnl_negative(self):
        """Test P&L calculation for losing position."""
        position = Position(
            id="pos-002",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.40,
            current_price=0.30,
            quantity=100,
            entry_value=40.0,
            current_value=30.0,
        )
        pnl = position.calculate_pnl()
        assert pnl < 0
        assert abs(pnl - (-25.0)) < 0.01
    
    def test_calculate_pnl_zero_entry(self):
        """Test P&L calculation with zero entry price."""
        position = Position(
            id="pos-003",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.0,
            current_price=0.30,
            quantity=100,
            entry_value=0.0,
            current_value=30.0,
        )
        assert position.calculate_pnl() == 0.0
    
    def test_should_stop_loss_true(self):
        """Test stop loss trigger when threshold exceeded."""
        position = Position(
            id="pos-004",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.40,
            quantity=100,
            entry_value=50.0,
            current_value=40.0,
            pnl_percent=-20.0,
        )
        assert position.should_stop_loss(threshold=-15.0) is True
    
    def test_should_stop_loss_false(self):
        """Test stop loss not triggered when within threshold."""
        position = Position(
            id="pos-005",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.50,
            current_price=0.47,
            quantity=100,
            entry_value=50.0,
            current_value=47.0,
            pnl_percent=-6.0,
        )
        assert position.should_stop_loss(threshold=-15.0) is False
    
    def test_should_take_profit_true(self):
        """Test take profit trigger when threshold exceeded."""
        position = Position(
            id="pos-006",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.42,
            quantity=100,
            entry_value=30.0,
            current_value=42.0,
            pnl_percent=40.0,
        )
        assert position.should_take_profit(threshold=30.0) is True
    
    def test_should_take_profit_false(self):
        """Test take profit not triggered when within threshold."""
        position = Position(
            id="pos-007",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.30,
            current_price=0.35,
            quantity=100,
            entry_value=30.0,
            current_value=35.0,
            pnl_percent=16.67,
        )
        assert position.should_take_profit(threshold=30.0) is False
    
    def test_update_current_price(self, sample_position):
        """Test updating current price."""
        sample_position.update_current_price(0.50)
        assert sample_position.current_price == 0.50
        assert sample_position.current_value == 50.0  # 0.50 * 100
        assert sample_position.pnl_percent > 0


class TestWallet:
    """Tests for Wallet model."""
    
    @pytest.fixture
    def sample_wallet(self):
        """Create a sample wallet for testing."""
        return Wallet(
            wallet_id="wallet-001",
            balance=1000.0,
            currency="USDC",
        )
    
    def test_basic_creation(self, sample_wallet):
        """Test basic wallet creation."""
        assert sample_wallet.wallet_id == "wallet-001"
        assert sample_wallet.balance == 1000.0
        assert sample_wallet.currency == "USDC"
    
    def test_can_afford_true(self, sample_wallet):
        """Test can_afford returns true when balance sufficient."""
        assert sample_wallet.can_afford(500.0) is True
        assert sample_wallet.can_afford(1000.0) is True
    
    def test_can_afford_false(self, sample_wallet):
        """Test can_afford returns false when balance insufficient."""
        assert sample_wallet.can_afford(1500.0) is False
    
    def test_deduct_success(self, sample_wallet):
        """Test successful balance deduction."""
        result = sample_wallet.deduct(300.0)
        assert result is True
        assert sample_wallet.balance == 700.0
    
    def test_deduct_insufficient_funds(self, sample_wallet):
        """Test deduction fails with insufficient funds."""
        result = sample_wallet.deduct(1500.0)
        assert result is False
        assert sample_wallet.balance == 1000.0  # Unchanged
    
    def test_add(self, sample_wallet):
        """Test adding to balance."""
        sample_wallet.add(500.0)
        assert sample_wallet.balance == 1500.0


class TestAISuggestion:
    """Tests for AISuggestion model."""
    
    def test_basic_creation(self):
        """Test basic suggestion creation."""
        suggestion = AISuggestion(
            market_id="market-001",
            market_question="Test market",
            recommended_outcome="Yes",
            confidence=0.85,
            reasoning="Strong indicators",
        )
        assert suggestion.market_id == "market-001"
        assert suggestion.confidence == 0.85
    
    def test_meets_threshold_true(self):
        """Test meets_threshold returns true above threshold."""
        suggestion = AISuggestion(
            market_id="market-001",
            recommended_outcome="Yes",
            confidence=0.85,
        )
        assert suggestion.meets_threshold(0.7) is True
    
    def test_meets_threshold_false(self):
        """Test meets_threshold returns false below threshold."""
        suggestion = AISuggestion(
            market_id="market-001",
            recommended_outcome="Yes",
            confidence=0.6,
        )
        assert suggestion.meets_threshold(0.7) is False
    
    def test_meets_threshold_exact(self):
        """Test meets_threshold at exact threshold."""
        suggestion = AISuggestion(
            market_id="market-001",
            recommended_outcome="Yes",
            confidence=0.7,
        )
        assert suggestion.meets_threshold(0.7) is True


class TestAIAnalysisResult:
    """Tests for AIAnalysisResult model."""
    
    @pytest.fixture
    def sample_suggestions(self):
        """Create sample suggestions for testing."""
        return [
            AISuggestion(
                market_id="market-001",
                recommended_outcome="Yes",
                confidence=0.9,
            ),
            AISuggestion(
                market_id="market-002",
                recommended_outcome="No",
                confidence=0.75,
            ),
            AISuggestion(
                market_id="market-003",
                recommended_outcome="Yes",
                confidence=0.6,
            ),
        ]
    
    def test_get_high_confidence_suggestions(self, sample_suggestions):
        """Test filtering high confidence suggestions."""
        result = AIAnalysisResult(
            suggestions=sample_suggestions,
            markets_analyzed=3,
        )
        
        high_conf = result.get_high_confidence_suggestions(0.7)
        assert len(high_conf) == 2
        assert all(s.confidence >= 0.7 for s in high_conf)
    
    def test_get_top_suggestions(self, sample_suggestions):
        """Test getting top N suggestions."""
        result = AIAnalysisResult(
            suggestions=sample_suggestions,
            markets_analyzed=3,
        )
        
        top_2 = result.get_top_suggestions(2)
        assert len(top_2) == 2
        assert top_2[0].confidence == 0.9
        assert top_2[1].confidence == 0.75


class TestOrder:
    """Tests for Order model."""
    
    def test_basic_creation(self):
        """Test basic order creation."""
        order = Order(
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.BUY,
            price=0.35,
            quantity=100,
            total_value=35.0,
        )
        assert order.market_id == "market-001"
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING
    
    def test_default_values(self):
        """Test default order values."""
        order = Order(
            market_id="market-001",
            outcome="Yes",
            side=OrderSide.BUY,
            price=0.35,
            quantity=100,
            total_value=35.0,
        )
        assert order.id == ""
        assert order.mode == TradingMode.FAKE
        assert order.filled_at is None
        assert order.error_message is None


class TestMarketQueryParams:
    """Tests for MarketQueryParams model."""
    
    def test_default_values(self):
        """Test default query parameter values."""
        params = MarketQueryParams()
        assert params.limit == 50
        assert params.offset == 0
        assert params.category is None
    
    def test_limit_max_validation(self):
        """Test limit maximum validation."""
        with pytest.raises(ValueError):
            MarketQueryParams(limit=150)
    
    def test_offset_min_validation(self):
        """Test offset minimum validation."""
        with pytest.raises(ValueError):
            MarketQueryParams(offset=-1)
