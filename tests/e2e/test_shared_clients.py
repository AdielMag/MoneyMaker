"""
End-to-end tests for shared client modules.
Tests Firestore, Polymarket, and Gemini clients with mocked external dependencies.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.models import (
    Market,
    MarketOutcome,
    Position,
    RiskLevel,
    TradingMode,
    TransactionType,
    WorkflowState,
)


@pytest.fixture
def mock_firestore_db():
    """Create mock Firestore database."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc = MagicMock()

    # Setup document mock
    mock_doc.get = AsyncMock(return_value=MagicMock(
        exists=True,
        to_dict=MagicMock(return_value={
            "wallet_id": "default",
            "balance": 1000.0,
            "currency": "USDC",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
    ))
    mock_doc.set = AsyncMock()
    mock_doc.update = AsyncMock()
    mock_doc.delete = AsyncMock()

    mock_collection.document = MagicMock(return_value=mock_doc)

    # Setup stream mock for async iteration
    async def mock_stream():
        yield MagicMock(id="pos-1", to_dict=MagicMock(return_value={
            "id": "pos-1",
            "market_id": "market-001",
            "outcome": "Yes",
            "entry_price": 0.3,
            "current_price": 0.4,
            "quantity": 100,
            "entry_value": 30.0,
            "current_value": 40.0,
            "pnl_percent": 33.3,
            "mode": "fake",
        }))

    mock_query = MagicMock()
    mock_query.where = MagicMock(return_value=mock_query)
    mock_query.order_by = MagicMock(return_value=mock_query)
    mock_query.limit = MagicMock(return_value=mock_query)
    mock_query.stream = mock_stream

    mock_collection.where = MagicMock(return_value=mock_query)
    mock_db.collection = MagicMock(return_value=mock_collection)

    return mock_db


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.gcp_project_id = "test-project"
    settings.polymarket_api_key = "test-key"
    settings.polymarket_api_secret = "test-secret"
    settings.polymarket_wallet_address = "0x123"
    settings.gemini_api_key = "test-gemini-key"
    settings.ai = MagicMock()
    settings.ai.model = "gemini-1.5-pro"
    settings.ai.temperature = 0.3
    settings.ai.max_tokens = 2048
    settings.ai.max_suggestions = 5
    settings.workflows_fake_money = MagicMock()
    settings.workflows_fake_money.initial_balance = 1000.0
    return settings


@pytest.mark.e2e
class TestFirestoreClientE2E:
    """End-to-end tests for Firestore client."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings, mock_firestore_db):
        """Setup test fixtures."""
        with patch("shared.firestore_client.get_settings", return_value=mock_settings):
            with patch("shared.firestore_client.firestore.AsyncClient", return_value=mock_firestore_db):
                from shared.firestore_client import FirestoreClient
                self.client = FirestoreClient(settings=mock_settings)
                self.client._db = mock_firestore_db
                self.mock_db = mock_firestore_db
                yield

    @pytest.mark.asyncio
    async def test_get_wallet(self):
        """Test getting a wallet."""
        wallet = await self.client.get_wallet("default")
        assert wallet is not None
        assert wallet.wallet_id == "default"
        assert wallet.balance == 1000.0

    @pytest.mark.asyncio
    async def test_get_wallet_not_found(self):
        """Test getting non-existent wallet."""
        mock_doc = self.mock_db.collection.return_value.document.return_value
        mock_doc.get = AsyncMock(return_value=MagicMock(exists=False))

        wallet = await self.client.get_wallet("nonexistent")
        assert wallet is None

    @pytest.mark.asyncio
    async def test_create_wallet(self):
        """Test creating a wallet."""
        wallet = await self.client.create_wallet("new-wallet", initial_balance=500.0)
        assert wallet.wallet_id == "new-wallet"
        assert wallet.balance == 500.0

    @pytest.mark.asyncio
    async def test_get_or_create_wallet_existing(self):
        """Test get_or_create with existing wallet."""
        wallet = await self.client.get_or_create_wallet("default")
        assert wallet.wallet_id == "default"

    @pytest.mark.asyncio
    async def test_get_or_create_wallet_new(self):
        """Test get_or_create with new wallet."""
        mock_doc = self.mock_db.collection.return_value.document.return_value
        mock_doc.get = AsyncMock(return_value=MagicMock(exists=False))

        wallet = await self.client.get_or_create_wallet("new-wallet", 800.0)
        assert wallet.wallet_id == "new-wallet"

    @pytest.mark.asyncio
    async def test_update_wallet_balance(self):
        """Test updating wallet balance."""
        wallet = await self.client.update_wallet_balance("default", 1500.0)
        assert wallet is not None

    @pytest.mark.asyncio
    async def test_create_position(self):
        """Test creating a position."""
        position = Position(
            id="pos-new",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.3,
            current_price=0.35,
            quantity=100,
            entry_value=30.0,
            current_value=35.0,
            pnl_percent=16.7,
            mode=TradingMode.FAKE,
        )
        result = await self.client.create_position(position)
        assert result.id == "pos-new"

    @pytest.mark.asyncio
    async def test_get_position(self):
        """Test getting a position."""
        mock_doc = self.mock_db.collection.return_value.document.return_value
        mock_doc.get = AsyncMock(return_value=MagicMock(
            exists=True,
            to_dict=MagicMock(return_value={
                "id": "pos-1",
                "market_id": "market-001",
                "outcome": "Yes",
                "entry_price": 0.3,
                "current_price": 0.4,
                "quantity": 100,
                "entry_value": 30.0,
                "current_value": 40.0,
                "pnl_percent": 33.3,
                "mode": "fake",
            })
        ))

        position = await self.client.get_position("pos-1")
        assert position is not None
        assert position.id == "pos-1"

    @pytest.mark.asyncio
    async def test_get_open_positions(self):
        """Test getting open positions."""
        positions = await self.client.get_open_positions(TradingMode.FAKE)
        assert len(positions) == 1
        assert positions[0].id == "pos-1"

    @pytest.mark.asyncio
    async def test_delete_position(self):
        """Test deleting a position."""
        result = await self.client.delete_position("pos-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_create_transaction(self):
        """Test creating a transaction."""
        tx = await self.client.create_transaction(
            wallet_id="default",
            tx_type=TransactionType.BUY,
            amount=30.0,
            balance_before=1000.0,
            balance_after=970.0,
            reference_id="order-001",
            description="Buy order",
        )
        assert tx.wallet_id == "default"
        assert tx.amount == 30.0

    @pytest.mark.asyncio
    async def test_get_workflow_state(self):
        """Test getting workflow state."""
        mock_doc = self.mock_db.collection.return_value.document.return_value
        mock_doc.get = AsyncMock(return_value=MagicMock(
            exists=True,
            to_dict=MagicMock(return_value={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": True,
                "run_count": 5,
            })
        ))

        state = await self.client.get_workflow_state("discovery", TradingMode.FAKE)
        assert state is not None
        assert state.workflow_id == "discovery"
        assert state.enabled is True

    @pytest.mark.asyncio
    async def test_update_workflow_state(self):
        """Test updating workflow state."""
        state = WorkflowState(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            enabled=True,
            run_count=6,
        )
        result = await self.client.update_workflow_state(state)
        assert result.workflow_id == "discovery"

    @pytest.mark.asyncio
    async def test_toggle_workflow(self):
        """Test toggling workflow."""
        mock_doc = self.mock_db.collection.return_value.document.return_value
        mock_doc.get = AsyncMock(return_value=MagicMock(
            exists=True,
            to_dict=MagicMock(return_value={
                "workflow_id": "discovery",
                "mode": "fake",
                "enabled": True,
                "run_count": 5,
            })
        ))

        state = await self.client.toggle_workflow("discovery", TradingMode.FAKE, False)
        assert state.enabled is False

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing the client."""
        await self.client.close()
        assert self.client._db is None


@pytest.mark.e2e
class TestPolymarketClientE2E:
    """End-to-end tests for Polymarket client."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        """Setup test fixtures."""
        with patch("shared.polymarket_client.get_settings", return_value=mock_settings):
            from shared.polymarket_client import PolymarketClient
            self.client = PolymarketClient(settings=mock_settings)
            yield

    def test_sign_request(self):
        """Test request signing."""
        headers = self.client._sign_request("GET", "/test", "", timestamp=1234567890)
        assert "POLY_ADDRESS" in headers
        assert "POLY_SIGNATURE" in headers
        assert "POLY_TIMESTAMP" in headers
        assert "POLY_API_KEY" in headers

    def test_get_base_headers(self):
        """Test getting base headers."""
        headers = self.client._get_base_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_parse_market(self):
        """Test parsing market data."""
        data = {
            "condition_id": "market-001",
            "question": "Will BTC reach $100k?",
            "description": "Test market",
            "category": "crypto",
            "endDate": "2025-01-15T12:00:00Z",
            "volume": 50000,
            "liquidity": 25000,
            "tokens": [
                {"outcome": "Yes", "price": 0.35},
                {"outcome": "No", "price": 0.65},
            ],
        }

        market = self.client._parse_market(data)
        assert market is not None
        assert market.id == "market-001"
        assert market.question == "Will BTC reach $100k?"
        assert len(market.outcomes) == 2

    def test_parse_market_empty(self):
        """Test parsing empty market data."""
        market = self.client._parse_market({})
        assert market is None

    def test_parse_market_with_string_outcomes(self):
        """Test parsing market with string outcomes."""
        data = {
            "id": "market-002",
            "question": "Test?",
            "outcomes": ["Yes", "No"],
            "volume": 1000,
        }

        market = self.client._parse_market(data)
        assert market is not None
        assert len(market.outcomes) == 2

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with self.client as client:
            assert client._client is not None
        assert self.client._client is None

    def test_client_property_creates_client(self):
        """Test that client property creates httpx client if needed."""
        self.client._client = None
        client = self.client.client
        assert client is not None

    @pytest.mark.asyncio
    async def test_parse_market_missing_end_date(self):
        """Test parsing market with missing end date."""
        data = {
            "id": "market-003",
            "question": "Test?",
            "volume": 1000,
        }
        market = self.client._parse_market(data)
        assert market is not None
        # End date defaults to current time


@pytest.mark.e2e
class TestGeminiClientE2E:
    """End-to-end tests for Gemini client."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_settings):
        """Setup test fixtures."""
        with patch("shared.gemini_client.get_settings", return_value=mock_settings):
            with patch("shared.gemini_client.genai") as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content_async = AsyncMock(return_value=MagicMock(
                    text='{"suggestions": [], "markets_analyzed": 0, "overall_market_sentiment": "neutral"}'
                ))
                mock_genai.GenerativeModel = MagicMock(return_value=mock_model)

                from shared.gemini_client import GeminiClient
                self.client = GeminiClient(settings=mock_settings)
                self.mock_genai = mock_genai
                self.mock_model = mock_model
                yield

    def test_format_markets_for_prompt(self):
        """Test formatting markets for prompt."""
        markets = [
            Market(
                id="market-001",
                question="Will BTC reach $100k?",
                category="crypto",
                end_date=datetime.utcnow() + timedelta(hours=1),
                volume=50000,
                liquidity=25000,
                outcomes=[
                    MarketOutcome(name="Yes", price=0.35),
                    MarketOutcome(name="No", price=0.65),
                ],
            ),
        ]

        result = self.client._format_markets_for_prompt(markets)
        assert "market-001" in result
        assert "Will BTC reach $100k?" in result
        assert "crypto" in result

    def test_parse_response_valid(self):
        """Test parsing valid response."""
        response = '{"suggestions": [{"market_id": "m1", "market_question": "Test?", "recommended_outcome": "Yes", "confidence": 0.8, "reasoning": "Test"}], "markets_analyzed": 1, "overall_market_sentiment": "bullish"}'

        result = self.client._parse_response(response, 1)
        assert result.markets_analyzed == 1
        assert len(result.suggestions) == 1

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        result = self.client._parse_response("invalid json", 1)
        assert result.markets_analyzed == 1
        assert len(result.suggestions) == 0
        assert "uncertain" in result.overall_market_sentiment

    def test_parse_response_with_code_block(self):
        """Test parsing response wrapped in code block."""
        response = '```json\n{"suggestions": [], "markets_analyzed": 1, "overall_market_sentiment": "neutral"}\n```'

        result = self.client._parse_response(response, 1)
        assert result.markets_analyzed == 1

    def test_parse_risk_level(self):
        """Test parsing risk level."""
        assert self.client._parse_risk_level("low") == RiskLevel.LOW
        assert self.client._parse_risk_level("HIGH") == RiskLevel.HIGH
        assert self.client._parse_risk_level("invalid") == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_analyze_markets_empty(self):
        """Test analyzing empty markets list."""
        result = await self.client.analyze_markets([])
        assert result.markets_analyzed == 0
        assert len(result.suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_markets_with_data(self):
        """Test analyzing markets with data."""
        # Configure mock to return valid response
        self.mock_model.generate_content_async = AsyncMock(return_value=MagicMock(
            text='{"suggestions": [{"market_id": "m1", "market_question": "Test?", "recommended_outcome": "Yes", "confidence": 0.85, "reasoning": "Test", "suggested_position_size": 0.1, "risk_level": "low"}], "markets_analyzed": 1, "overall_market_sentiment": "bullish"}'
        ))

        markets = [
            Market(
                id="market-001",
                question="Will BTC reach $100k?",
                category="crypto",
                end_date=datetime.utcnow() + timedelta(hours=1),
                volume=50000,
                liquidity=25000,
                outcomes=[
                    MarketOutcome(name="Yes", price=0.35),
                    MarketOutcome(name="No", price=0.65),
                ],
            ),
        ]

        result = await self.client.analyze_markets(markets)
        assert result.markets_analyzed == 1

    def test_ensure_configured(self):
        """Test that _ensure_configured configures the API."""
        self.client._configured = False
        self.client._ensure_configured()
        assert self.client._configured is True

    def test_model_property(self):
        """Test that model property returns/creates model."""
        self.client._model = None
        model = self.client.model
        assert model is not None


@pytest.mark.e2e
class TestConfigE2E:
    """End-to-end tests for configuration module."""

    def test_load_yaml_config_not_found(self):
        """Test loading config when file not found."""
        from pathlib import Path

        from shared.config import load_yaml_config

        result = load_yaml_config(Path("/nonexistent/config.yaml"))
        assert result == {}

    def test_flatten_dict(self):
        """Test flattening nested dictionary."""
        from shared.config import flatten_dict

        nested = {
            "level1": {
                "level2": {
                    "value": "test"
                },
                "other": 123
            },
            "top": "value"
        }

        result = flatten_dict(nested)
        assert result["level1__level2__value"] == "test"
        assert result["level1__other"] == 123
        assert result["top"] == "value"

    def test_settings_validation(self):
        """Test settings validation."""
        from shared.config import Settings

        settings = Settings(environment="test")
        assert settings.environment == "test"
        assert settings.is_test is True
        assert settings.is_production is False

    def test_get_active_mode_real(self):
        """Test get_active_mode with real money enabled."""
        from shared.config import Settings

        settings = Settings(
            environment="test",
            real_money_enabled=True,
            fake_money_enabled=False,
        )
        assert settings.get_active_mode() == "real"

    def test_get_active_mode_fake(self):
        """Test get_active_mode with fake money enabled."""
        from shared.config import Settings

        settings = Settings(
            environment="test",
            real_money_enabled=False,
            fake_money_enabled=True,
        )
        assert settings.get_active_mode() == "fake"

    def test_get_active_mode_none(self):
        """Test get_active_mode with nothing enabled."""
        from shared.config import Settings

        settings = Settings(
            environment="test",
            real_money_enabled=False,
            fake_money_enabled=False,
        )
        assert settings.get_active_mode() == "none"

    def test_settings_is_production(self):
        """Test is_production property."""
        from shared.config import Settings

        settings = Settings(environment="production")
        assert settings.is_production is True

        settings = Settings(environment="test")
        assert settings.is_production is False

    def test_environment_validation_invalid(self):
        """Test that invalid environment raises error."""
        import pytest

        from shared.config import Settings

        with pytest.raises(ValueError):
            Settings(environment="invalid_env")
