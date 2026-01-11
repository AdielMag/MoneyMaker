"""
Unit tests for shared/firestore_client.py
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.firestore_client import (
    FirestoreClient,
    get_firestore_client,
)
from shared.models import Position, TradingMode, TransactionType, WorkflowState


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.gcp_project_id = "test-project"
    settings.workflows_fake_money = MagicMock()
    settings.workflows_fake_money.initial_balance = 1000.0
    return settings


@pytest.fixture
def firestore_client(mock_settings):
    """Create a Firestore client with mock settings."""
    client = FirestoreClient(settings=mock_settings)
    # Mock the database
    client._db = MagicMock()
    return client


@pytest.fixture
def mock_document():
    """Create a mock Firestore document."""
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {}
    return doc


@pytest.fixture
def mock_doc_ref():
    """Create a mock document reference."""
    doc_ref = MagicMock()
    doc_ref.get = AsyncMock()
    doc_ref.set = AsyncMock()
    doc_ref.update = AsyncMock()
    doc_ref.delete = AsyncMock()
    return doc_ref


class TestFirestoreClient:
    """Tests for FirestoreClient class."""

    def test_initialization(self, firestore_client, mock_settings):
        """Test client initialization."""
        assert firestore_client.settings == mock_settings

    def test_collection_names(self):
        """Test collection name constants."""
        assert FirestoreClient.WALLETS_COLLECTION == "fake_wallets"
        assert FirestoreClient.POSITIONS_COLLECTION == "fake_positions"
        assert FirestoreClient.TRANSACTIONS_COLLECTION == "fake_transactions"
        assert FirestoreClient.WORKFLOW_STATE_COLLECTION == "workflow_state"


class TestWalletOperations:
    """Tests for wallet operations."""

    @pytest.mark.asyncio
    async def test_get_wallet_exists(self, firestore_client, mock_doc_ref, mock_document):
        """Test getting existing wallet."""
        mock_document.to_dict.return_value = {
            "balance": 500.0,
            "currency": "USDC",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        wallet = await firestore_client.get_wallet("test-wallet")

        assert wallet is not None
        assert wallet.wallet_id == "test-wallet"
        assert wallet.balance == 500.0

    @pytest.mark.asyncio
    async def test_get_wallet_not_found(self, firestore_client, mock_doc_ref):
        """Test getting non-existent wallet."""
        mock_document = MagicMock()
        mock_document.exists = False
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        wallet = await firestore_client.get_wallet("nonexistent")

        assert wallet is None

    @pytest.mark.asyncio
    async def test_create_wallet(self, firestore_client, mock_doc_ref):
        """Test creating new wallet."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        wallet = await firestore_client.create_wallet("new-wallet", 1000.0)

        assert wallet.wallet_id == "new-wallet"
        assert wallet.balance == 1000.0
        mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_wallet_default_balance(
        self, firestore_client, mock_doc_ref, mock_settings
    ):
        """Test creating wallet with default balance."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        wallet = await firestore_client.create_wallet("default-wallet")

        assert wallet.balance == mock_settings.workflows_fake_money.initial_balance

    @pytest.mark.asyncio
    async def test_get_or_create_wallet_exists(self, firestore_client, mock_doc_ref, mock_document):
        """Test get_or_create when wallet exists."""
        mock_document.to_dict.return_value = {
            "balance": 750.0,
            "currency": "USDC",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        wallet = await firestore_client.get_or_create_wallet("existing")

        assert wallet.balance == 750.0
        mock_doc_ref.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_wallet_creates(self, firestore_client, mock_doc_ref):
        """Test get_or_create creates when wallet doesn't exist."""
        # First call returns not exists, second call for create
        mock_not_exists = MagicMock()
        mock_not_exists.exists = False
        mock_doc_ref.get.return_value = mock_not_exists

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        wallet = await firestore_client.get_or_create_wallet("new")

        assert wallet is not None
        mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_wallet_balance(self, firestore_client, mock_doc_ref, mock_document):
        """Test updating wallet balance."""
        # Setup for update call
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        # Setup for get call after update
        mock_document.to_dict.return_value = {
            "balance": 1500.0,
            "currency": "USDC",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        mock_doc_ref.get.return_value = mock_document

        wallet = await firestore_client.update_wallet_balance("test-wallet", 1500.0)

        assert wallet.balance == 1500.0
        mock_doc_ref.update.assert_called_once()


class TestPositionOperations:
    """Tests for position operations."""

    @pytest.mark.asyncio
    async def test_create_position(self, firestore_client, mock_doc_ref):
        """Test creating new position."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        position = Position(
            id="pos-001",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.35,
            current_price=0.35,
            quantity=100,
            entry_value=35.0,
            current_value=35.0,
        )

        result = await firestore_client.create_position(position)

        assert result.id == "pos-001"
        mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_position_generates_id(self, firestore_client, mock_doc_ref):
        """Test position ID is generated if not provided."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        position = Position(
            id="",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.35,
            current_price=0.35,
            quantity=100,
            entry_value=35.0,
            current_value=35.0,
        )

        result = await firestore_client.create_position(position)

        assert result.id != ""
        assert len(result.id) > 0

    @pytest.mark.asyncio
    async def test_get_position_exists(self, firestore_client, mock_doc_ref, mock_document):
        """Test getting existing position."""
        mock_document.to_dict.return_value = {
            "id": "pos-001",
            "market_id": "market-001",
            "outcome": "Yes",
            "entry_price": 0.35,
            "current_price": 0.40,
            "quantity": 100,
            "entry_value": 35.0,
            "current_value": 40.0,
            "mode": "fake",
            "created_at": datetime.utcnow().isoformat(),
        }
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        position = await firestore_client.get_position("pos-001")

        assert position is not None
        assert position.id == "pos-001"
        assert position.entry_price == 0.35

    @pytest.mark.asyncio
    async def test_get_position_not_found(self, firestore_client, mock_doc_ref):
        """Test getting non-existent position."""
        mock_document = MagicMock()
        mock_document.exists = False
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        position = await firestore_client.get_position("nonexistent")

        assert position is None

    @pytest.mark.asyncio
    async def test_get_open_positions(self, firestore_client):
        """Test getting open positions for a mode."""
        # Mock query and stream
        mock_doc1 = MagicMock()
        mock_doc1.to_dict.return_value = {
            "id": "pos-001",
            "market_id": "market-001",
            "outcome": "Yes",
            "entry_price": 0.35,
            "current_price": 0.40,
            "quantity": 100,
            "entry_value": 35.0,
            "current_value": 40.0,
            "mode": "fake",
            "created_at": datetime.utcnow().isoformat(),
        }

        mock_query = MagicMock()

        async def mock_stream():
            yield mock_doc1

        mock_query.stream = mock_stream
        firestore_client.db.collection.return_value.where.return_value = mock_query

        positions = await firestore_client.get_open_positions(TradingMode.FAKE)

        assert len(positions) == 1
        assert positions[0].id == "pos-001"

    @pytest.mark.asyncio
    async def test_update_position(self, firestore_client, mock_doc_ref):
        """Test updating position."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        position = Position(
            id="pos-001",
            market_id="market-001",
            outcome="Yes",
            entry_price=0.35,
            current_price=0.45,
            quantity=100,
            entry_value=35.0,
            current_value=45.0,
            pnl_percent=28.57,
        )

        result = await firestore_client.update_position(position)

        assert result.id == "pos-001"
        mock_doc_ref.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_position(self, firestore_client, mock_doc_ref):
        """Test deleting position."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        result = await firestore_client.delete_position("pos-001")

        assert result is True
        mock_doc_ref.delete.assert_called_once()


class TestTransactionOperations:
    """Tests for transaction operations."""

    @pytest.mark.asyncio
    async def test_create_transaction(self, firestore_client, mock_doc_ref):
        """Test creating transaction record."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        tx = await firestore_client.create_transaction(
            wallet_id="wallet-001",
            tx_type=TransactionType.BUY,
            amount=50.0,
            balance_before=1000.0,
            balance_after=950.0,
            reference_id="order-001",
            description="Buy Yes on market-001",
        )

        assert tx.wallet_id == "wallet-001"
        assert tx.type == TransactionType.BUY
        assert tx.amount == 50.0
        mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_transactions(self, firestore_client):
        """Test getting transactions for wallet."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "id": "tx-001",
            "wallet_id": "wallet-001",
            "type": "buy",
            "amount": 50.0,
            "balance_before": 1000.0,
            "balance_after": 950.0,
            "created_at": datetime.utcnow().isoformat(),
        }

        mock_query = MagicMock()

        async def mock_stream():
            yield mock_doc

        mock_query.stream = mock_stream
        mock_query.limit.return_value = mock_query
        firestore_client.db.collection.return_value.where.return_value.order_by.return_value = (
            mock_query
        )

        transactions = await firestore_client.get_transactions("wallet-001", limit=10)

        assert len(transactions) == 1
        assert transactions[0].wallet_id == "wallet-001"


class TestWorkflowStateOperations:
    """Tests for workflow state operations."""

    @pytest.mark.asyncio
    async def test_get_workflow_state_exists(self, firestore_client, mock_doc_ref, mock_document):
        """Test getting existing workflow state."""
        mock_document.to_dict.return_value = {
            "workflow_id": "discovery",
            "mode": "fake",
            "enabled": True,
            "run_count": 5,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        state = await firestore_client.get_workflow_state("discovery", TradingMode.FAKE)

        assert state is not None
        assert state.workflow_id == "discovery"
        assert state.enabled is True

    @pytest.mark.asyncio
    async def test_get_workflow_state_not_found(self, firestore_client, mock_doc_ref):
        """Test getting non-existent workflow state."""
        mock_document = MagicMock()
        mock_document.exists = False
        mock_doc_ref.get.return_value = mock_document

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        state = await firestore_client.get_workflow_state("nonexistent", TradingMode.FAKE)

        assert state is None

    @pytest.mark.asyncio
    async def test_update_workflow_state(self, firestore_client, mock_doc_ref):
        """Test updating workflow state."""
        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        state = WorkflowState(
            workflow_id="discovery",
            mode=TradingMode.FAKE,
            enabled=True,
            run_count=10,
        )

        result = await firestore_client.update_workflow_state(state)

        assert result.workflow_id == "discovery"
        mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_workflow_creates_new(self, firestore_client, mock_doc_ref):
        """Test toggling workflow creates state if not exists."""
        # First get returns not found
        mock_not_exists = MagicMock()
        mock_not_exists.exists = False
        mock_doc_ref.get.return_value = mock_not_exists

        firestore_client.db.collection.return_value.document.return_value = mock_doc_ref

        state = await firestore_client.toggle_workflow("new-workflow", TradingMode.FAKE, True)

        assert state.workflow_id == "new-workflow"
        assert state.enabled is True


class TestGetFirestoreClient:
    """Tests for get_firestore_client helper function."""

    def test_get_firestore_client(self):
        """Test helper function creates client."""
        with patch("shared.firestore_client.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.gcp_project_id = "test-project"
            mock_get_settings.return_value = mock_settings

            client = get_firestore_client()

            assert isinstance(client, FirestoreClient)
