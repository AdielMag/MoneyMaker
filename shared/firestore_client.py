"""
Firestore client for MoneyMaker.

Handles all Firestore database operations for wallets, positions,
transactions, and workflow state.
"""

import uuid
from datetime import datetime
from typing import Any

import structlog
from google.cloud import firestore

from shared.config import Settings, get_settings
from shared.models import (
    Position,
    Transaction,
    TransactionType,
    Wallet,
    WorkflowState,
)

logger = structlog.get_logger(__name__)


class FirestoreClient:
    """Client for Firestore database operations."""

    # Collection names
    WALLETS_COLLECTION = "fake_wallets"
    POSITIONS_COLLECTION = "fake_positions"
    TRANSACTIONS_COLLECTION = "fake_transactions"
    WORKFLOW_STATE_COLLECTION = "workflow_state"

    def __init__(self, settings: Settings | None = None):
        """Initialize Firestore client."""
        self.settings = settings or get_settings()
        self._db: firestore.AsyncClient | None = None

    @property
    def db(self) -> firestore.AsyncClient:
        """Get or create Firestore database client."""
        if self._db is None:
            project_id = self.settings.gcp_project_id
            if not project_id:
                raise ValueError("GCP_PROJECT_ID must be set in settings or environment")
            self._db = firestore.AsyncClient(project=project_id)
        return self._db

    # =============================================================================
    # Wallet Operations
    # =============================================================================

    async def get_wallet(self, wallet_id: str) -> Wallet | None:
        """
        Get wallet by ID.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Wallet if found, None otherwise
        """
        try:
            doc_ref = self.db.collection(self.WALLETS_COLLECTION).document(wallet_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            if not data:
                return None

            return Wallet(
                wallet_id=wallet_id,
                balance=data.get("balance", 0.0),
                currency=data.get("currency", "USDC"),
                created_at=self._parse_datetime(data.get("created_at")),
                updated_at=self._parse_datetime(data.get("updated_at")),
            )
        except Exception as e:
            logger.error("get_wallet_error", wallet_id=wallet_id, error=str(e))
            raise

    async def create_wallet(
        self,
        wallet_id: str,
        initial_balance: float | None = None,
    ) -> Wallet:
        """
        Create a new wallet.

        Args:
            wallet_id: Wallet identifier
            initial_balance: Initial balance (uses default from settings if not provided)

        Returns:
            Created wallet
        """
        if initial_balance is None:
            initial_balance = self.settings.workflows_fake_money.initial_balance

        wallet = Wallet(
            wallet_id=wallet_id,
            balance=initial_balance,
            currency="USDC",
        )

        doc_ref = self.db.collection(self.WALLETS_COLLECTION).document(wallet_id)
        await doc_ref.set(wallet.model_dump(mode="json", exclude={"wallet_id"}))

        logger.info("wallet_created", wallet_id=wallet_id, balance=initial_balance)
        return wallet

    async def get_or_create_wallet(
        self,
        wallet_id: str,
        initial_balance: float | None = None,
    ) -> Wallet:
        """
        Get existing wallet or create new one.

        Args:
            wallet_id: Wallet identifier
            initial_balance: Initial balance for new wallets

        Returns:
            Wallet (existing or newly created)
        """
        wallet = await self.get_wallet(wallet_id)
        if wallet is not None:
            return wallet

        return await self.create_wallet(wallet_id, initial_balance)

    async def update_wallet_balance(
        self,
        wallet_id: str,
        new_balance: float,
    ) -> Wallet:
        """
        Update wallet balance.

        Args:
            wallet_id: Wallet identifier
            new_balance: New balance amount

        Returns:
            Updated wallet
        """
        doc_ref = self.db.collection(self.WALLETS_COLLECTION).document(wallet_id)
        await doc_ref.update(
            {
                "balance": new_balance,
                "updated_at": datetime.utcnow(),
            }
        )

        # Return updated wallet
        wallet = await self.get_wallet(wallet_id)
        if wallet is None:
            raise ValueError(f"Wallet {wallet_id} not found after update")
        return wallet

    # =============================================================================
    # Position Operations
    # =============================================================================

    async def create_position(self, position: Position) -> Position:
        """
        Create a new position.

        Args:
            position: Position to create

        Returns:
            Created position (with generated ID if not provided)
        """
        # Generate ID if not provided
        if not position.id:
            position.id = f"pos-{uuid.uuid4().hex[:8]}"

        doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position.id)
        await doc_ref.set(position.model_dump(mode="json", exclude={"id"}))

        logger.info("position_created", position_id=position.id, market_id=position.market_id)
        return position

    async def get_position(self, position_id: str) -> Position | None:
        """
        Get position by ID.

        Args:
            position_id: Position identifier

        Returns:
            Position if found, None otherwise
        """
        try:
            doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            if not data:
                return None

            # Remove 'id' from data if present to avoid conflict
            data.pop("id", None)
            return Position(
                id=position_id,
                **data,
            )
        except Exception as e:
            logger.error("get_position_error", position_id=position_id, error=str(e))
            raise

    async def get_open_positions(self, mode: Any) -> list[Position]:
        """
        Get all open positions for a trading mode.

        Args:
            mode: TradingMode enum value

        Returns:
            List of open positions
        """
        try:
            # Query positions by mode
            query = (
                self.db.collection(self.POSITIONS_COLLECTION)
                .where("mode", "==", mode.value if hasattr(mode, "value") else str(mode))
            )

            positions = []
            async for doc in query.stream():
                data = doc.to_dict()
                if data:
                    # Remove 'id' from data if present to avoid conflict
                    data.pop("id", None)
                    positions.append(
                        Position(
                            id=doc.id,
                            **data,
                        )
                    )

            logger.info("get_open_positions", mode=mode, count=len(positions))
            return positions
        except Exception as e:
            logger.error("get_open_positions_error", mode=mode, error=str(e))
            raise

    async def update_position(self, position: Position) -> Position:
        """
        Update an existing position.

        Args:
            position: Position with updated data

        Returns:
            Updated position
        """
        doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position.id)
        await doc_ref.update(position.model_dump(mode="json", exclude={"id"}))

        logger.info("position_updated", position_id=position.id)
        return position

    async def delete_position(self, position_id: str) -> bool:
        """
        Delete a position.

        Args:
            position_id: Position identifier

        Returns:
            True if deleted successfully
        """
        doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position_id)
        await doc_ref.delete()

        logger.info("position_deleted", position_id=position_id)
        return True

    # =============================================================================
    # Transaction Operations
    # =============================================================================

    async def create_transaction(
        self,
        wallet_id: str,
        tx_type: TransactionType,
        amount: float,
        balance_before: float,
        balance_after: float,
        reference_id: str | None = None,
        description: str = "",
    ) -> Transaction:
        """
        Create a transaction record.

        Args:
            wallet_id: Wallet identifier
            tx_type: Transaction type
            amount: Transaction amount
            balance_before: Balance before transaction
            balance_after: Balance after transaction
            reference_id: Optional reference (order ID, position ID, etc.)
            description: Transaction description

        Returns:
            Created transaction
        """
        tx_id = f"tx-{uuid.uuid4().hex[:8]}"
        transaction = Transaction(
            id=tx_id,
            wallet_id=wallet_id,
            type=tx_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_id=reference_id,
            description=description,
        )

        doc_ref = self.db.collection(self.TRANSACTIONS_COLLECTION).document(tx_id)
        await doc_ref.set(transaction.model_dump(mode="json", exclude={"id"}))

        logger.info(
            "transaction_created",
            tx_id=tx_id,
            wallet_id=wallet_id,
            type=tx_type.value,
            amount=amount,
        )
        return transaction

    async def get_transactions(
        self,
        wallet_id: str,
        limit: int = 100,
    ) -> list[Transaction]:
        """
        Get transactions for a wallet.

        Args:
            wallet_id: Wallet identifier
            limit: Maximum number of transactions to return

        Returns:
            List of transactions (most recent first)
        """
        try:
            query = (
                self.db.collection(self.TRANSACTIONS_COLLECTION)
                .where("wallet_id", "==", wallet_id)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )

            transactions = []
            async for doc in query.stream():
                data = doc.to_dict()
                if data:
                    # Remove 'id' from data if present to avoid conflict
                    data.pop("id", None)
                    transactions.append(
                        Transaction(
                            id=doc.id,
                            **data,
                        )
                    )

            return transactions
        except Exception as e:
            logger.error("get_transactions_error", wallet_id=wallet_id, error=str(e))
            raise

    # =============================================================================
    # Workflow State Operations
    # =============================================================================

    async def get_workflow_state(
        self,
        workflow_id: str,
        mode: Any,
    ) -> WorkflowState | None:
        """
        Get workflow state.

        Args:
            workflow_id: Workflow identifier (e.g., "discovery", "monitor")
            mode: TradingMode enum value

        Returns:
            WorkflowState if found, None otherwise
        """
        try:
            doc_id = f"{workflow_id}_{mode.value if hasattr(mode, 'value') else str(mode)}"
            doc_ref = self.db.collection(self.WORKFLOW_STATE_COLLECTION).document(doc_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            if not data:
                return None

            return WorkflowState(**data)
        except Exception as e:
            logger.error(
                "get_workflow_state_error",
                workflow_id=workflow_id,
                mode=mode,
                error=str(e),
            )
            raise

    async def update_workflow_state(self, state: WorkflowState) -> WorkflowState:
        """
        Update or create workflow state.

        Args:
            state: WorkflowState to save

        Returns:
            Updated WorkflowState
        """
        doc_id = f"{state.workflow_id}_{state.mode.value}"
        doc_ref = self.db.collection(self.WORKFLOW_STATE_COLLECTION).document(doc_id)
        await doc_ref.set(state.model_dump(mode="json"))

        logger.info(
            "workflow_state_updated",
            workflow_id=state.workflow_id,
            mode=state.mode.value,
            enabled=state.enabled,
        )
        return state

    async def toggle_workflow(
        self,
        workflow_id: str,
        mode: Any,
        enabled: bool,
    ) -> WorkflowState:
        """
        Toggle workflow enabled state.

        Args:
            workflow_id: Workflow identifier
            mode: TradingMode enum value
            enabled: New enabled state

        Returns:
            Updated WorkflowState
        """
        state = await self.get_workflow_state(workflow_id, mode)

        if state is None:
            # Create new state
            state = WorkflowState(
                workflow_id=workflow_id,
                mode=mode,
                enabled=enabled,
            )
        else:
            state.enabled = enabled
            state.updated_at = datetime.utcnow()

        return await self.update_workflow_state(state)

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def _parse_datetime(self, value: Any) -> datetime:
        """Parse datetime from various formats."""
        if value is None:
            return datetime.utcnow()
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Try ISO format
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.utcnow()


# Factory function
def get_firestore_client() -> FirestoreClient:
    """Create and return a FirestoreClient instance."""
    return FirestoreClient()
