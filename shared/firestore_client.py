"""
Firestore client for MoneyMaker.

Provides async interface to Google Cloud Firestore for:
- Fake wallet management
- Position tracking
- Transaction history
- Workflow state
"""

from datetime import datetime
from uuid import uuid4

import structlog
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from shared.config import Settings, get_settings
from shared.models import (
    Position,
    TradingMode,
    Transaction,
    TransactionType,
    Wallet,
    WorkflowState,
)

logger = structlog.get_logger(__name__)


class FirestoreError(Exception):
    """Custom exception for Firestore errors."""

    pass


class FirestoreClient:
    """
    Async client for Google Cloud Firestore.

    Manages all persistent storage for fake trading mode including:
    - Wallets and balances
    - Open positions
    - Transaction history
    - Workflow state
    """

    # Collection names
    WALLETS_COLLECTION = "fake_wallets"
    POSITIONS_COLLECTION = "fake_positions"
    TRANSACTIONS_COLLECTION = "fake_transactions"
    WORKFLOW_STATE_COLLECTION = "workflow_state"
    MARKET_CACHE_COLLECTION = "market_cache"

    def __init__(self, settings: Settings | None = None):
        """
        Initialize Firestore client.

        Args:
            settings: Settings instance. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self._db: AsyncClient | None = None

    @property
    def db(self) -> AsyncClient:
        """Get Firestore client, creating if needed."""
        if self._db is None:
            self._db = firestore.AsyncClient(project=self.settings.gcp_project_id)
        return self._db

    async def close(self) -> None:
        """Close the Firestore client."""
        if self._db:
            self._db.close()
            self._db = None

    # =========================================================================
    # Wallet Operations
    # =========================================================================

    async def get_wallet(self, wallet_id: str = "default") -> Wallet | None:
        """
        Get a wallet by ID.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Wallet object or None if not found
        """
        try:
            doc_ref = self.db.collection(self.WALLETS_COLLECTION).document(wallet_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            return Wallet(
                wallet_id=wallet_id,
                balance=data.get("balance", 0),
                currency=data.get("currency", "USDC"),
                created_at=data.get("created_at", datetime.utcnow()),
                updated_at=data.get("updated_at", datetime.utcnow()),
            )
        except Exception as e:
            logger.error("get_wallet_error", wallet_id=wallet_id, error=str(e))
            raise FirestoreError(f"Failed to get wallet: {str(e)}")

    async def create_wallet(
        self,
        wallet_id: str = "default",
        initial_balance: float | None = None,
    ) -> Wallet:
        """
        Create a new wallet.

        Args:
            wallet_id: Wallet identifier
            initial_balance: Starting balance. Uses config default if None.

        Returns:
            Created Wallet object
        """
        if initial_balance is None:
            initial_balance = self.settings.workflows_fake_money.initial_balance

        wallet = Wallet(
            wallet_id=wallet_id,
            balance=initial_balance,
        )

        try:
            doc_ref = self.db.collection(self.WALLETS_COLLECTION).document(wallet_id)
            await doc_ref.set(wallet.model_dump())
            logger.info("wallet_created", wallet_id=wallet_id, balance=initial_balance)
            return wallet
        except Exception as e:
            logger.error("create_wallet_error", wallet_id=wallet_id, error=str(e))
            raise FirestoreError(f"Failed to create wallet: {str(e)}")

    async def get_or_create_wallet(
        self,
        wallet_id: str = "default",
        initial_balance: float | None = None,
    ) -> Wallet:
        """
        Get existing wallet or create new one.

        Args:
            wallet_id: Wallet identifier
            initial_balance: Starting balance for new wallet

        Returns:
            Wallet object
        """
        wallet = await self.get_wallet(wallet_id)
        if wallet is None:
            wallet = await self.create_wallet(wallet_id, initial_balance)
        return wallet

    async def update_wallet_balance(
        self,
        wallet_id: str,
        new_balance: float,
    ) -> Wallet:
        """
        Update wallet balance.

        Args:
            wallet_id: Wallet identifier
            new_balance: New balance value

        Returns:
            Updated Wallet object
        """
        try:
            doc_ref = self.db.collection(self.WALLETS_COLLECTION).document(wallet_id)
            await doc_ref.update(
                {
                    "balance": new_balance,
                    "updated_at": datetime.utcnow(),
                }
            )

            wallet = await self.get_wallet(wallet_id)
            if wallet is None:
                raise FirestoreError(f"Wallet {wallet_id} not found after update")

            logger.info("wallet_balance_updated", wallet_id=wallet_id, new_balance=new_balance)
            return wallet
        except Exception as e:
            logger.error("update_wallet_error", wallet_id=wallet_id, error=str(e))
            raise FirestoreError(f"Failed to update wallet: {str(e)}")

    # =========================================================================
    # Position Operations
    # =========================================================================

    async def create_position(self, position: Position) -> Position:
        """
        Create a new position.

        Args:
            position: Position to create

        Returns:
            Created Position with ID
        """
        if not position.id:
            position.id = str(uuid4())

        try:
            doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position.id)
            await doc_ref.set(position.model_dump(mode="json"))
            logger.info(
                "position_created",
                position_id=position.id,
                market_id=position.market_id,
                outcome=position.outcome,
            )
            return position
        except Exception as e:
            logger.error("create_position_error", error=str(e))
            raise FirestoreError(f"Failed to create position: {str(e)}")

    async def get_position(self, position_id: str) -> Position | None:
        """
        Get a position by ID.

        Args:
            position_id: Position identifier

        Returns:
            Position object or None if not found
        """
        try:
            doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return None

            return Position(**doc.to_dict())
        except Exception as e:
            logger.error("get_position_error", position_id=position_id, error=str(e))
            raise FirestoreError(f"Failed to get position: {str(e)}")

    async def get_open_positions(self, mode: TradingMode = TradingMode.FAKE) -> list[Position]:
        """
        Get all open positions for a trading mode.

        Args:
            mode: Trading mode (real or fake)

        Returns:
            List of Position objects
        """
        try:
            query = self.db.collection(self.POSITIONS_COLLECTION).where("mode", "==", mode.value)

            positions = []
            async for doc in query.stream():
                try:
                    positions.append(Position(**doc.to_dict()))
                except Exception as e:
                    logger.warning("parse_position_error", doc_id=doc.id, error=str(e))
                    continue

            return positions
        except Exception as e:
            logger.error("get_open_positions_error", mode=mode.value, error=str(e))
            raise FirestoreError(f"Failed to get positions: {str(e)}")

    async def update_position(self, position: Position) -> Position:  # pragma: no cover
        """
        Update an existing position.

        Args:
            position: Position with updated values

        Returns:
            Updated Position
        """
        try:
            doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position.id)
            await doc_ref.update(position.model_dump(mode="json"))
            logger.info("position_updated", position_id=position.id)
            return position
        except Exception as e:
            logger.error("update_position_error", position_id=position.id, error=str(e))
            raise FirestoreError(f"Failed to update position: {str(e)}")

    async def delete_position(self, position_id: str) -> bool:
        """
        Delete a position (when closed).

        Args:
            position_id: Position identifier

        Returns:
            True if deleted successfully
        """
        try:
            doc_ref = self.db.collection(self.POSITIONS_COLLECTION).document(position_id)
            await doc_ref.delete()
            logger.info("position_deleted", position_id=position_id)
            return True
        except Exception as e:
            logger.error("delete_position_error", position_id=position_id, error=str(e))
            return False

    # =========================================================================
    # Transaction Operations
    # =========================================================================

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
            reference_id: Related order/position ID
            description: Transaction description

        Returns:
            Created Transaction
        """
        tx = Transaction(
            id=str(uuid4()),
            wallet_id=wallet_id,
            type=tx_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_id=reference_id,
            description=description,
        )

        try:
            doc_ref = self.db.collection(self.TRANSACTIONS_COLLECTION).document(tx.id)
            await doc_ref.set(tx.model_dump(mode="json"))
            logger.info(
                "transaction_created",
                tx_id=tx.id,
                type=tx_type.value,
                amount=amount,
            )
            return tx
        except Exception as e:
            logger.error("create_transaction_error", error=str(e))
            raise FirestoreError(f"Failed to create transaction: {str(e)}")

    async def get_transactions(  # pragma: no cover
        self,
        wallet_id: str,
        limit: int = 100,
    ) -> list[Transaction]:
        """
        Get transactions for a wallet.

        Args:
            wallet_id: Wallet identifier
            limit: Maximum number of transactions

        Returns:
            List of Transaction objects (newest first)
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
                try:
                    transactions.append(Transaction(**doc.to_dict()))
                except Exception as e:
                    logger.warning("parse_transaction_error", doc_id=doc.id, error=str(e))
                    continue

            return transactions
        except Exception as e:
            logger.error("get_transactions_error", wallet_id=wallet_id, error=str(e))
            raise FirestoreError(f"Failed to get transactions: {str(e)}")

    # =========================================================================
    # Workflow State Operations
    # =========================================================================

    async def get_workflow_state(
        self,
        workflow_id: str,
        mode: TradingMode,
    ) -> WorkflowState | None:
        """
        Get workflow state.

        Args:
            workflow_id: Workflow identifier
            mode: Trading mode

        Returns:
            WorkflowState or None if not found
        """
        doc_id = f"{workflow_id}_{mode.value}"

        try:
            doc_ref = self.db.collection(self.WORKFLOW_STATE_COLLECTION).document(doc_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return None

            return WorkflowState(**doc.to_dict())
        except Exception as e:
            logger.error("get_workflow_state_error", workflow_id=workflow_id, error=str(e))
            raise FirestoreError(f"Failed to get workflow state: {str(e)}")

    async def update_workflow_state(self, state: WorkflowState) -> WorkflowState:
        """
        Update workflow state.

        Args:
            state: WorkflowState to save

        Returns:
            Updated WorkflowState
        """
        doc_id = f"{state.workflow_id}_{state.mode.value}"
        state.updated_at = datetime.utcnow()

        try:
            doc_ref = self.db.collection(self.WORKFLOW_STATE_COLLECTION).document(doc_id)
            await doc_ref.set(state.model_dump(mode="json"))
            logger.info(
                "workflow_state_updated",
                workflow_id=state.workflow_id,
                mode=state.mode.value,
                enabled=state.enabled,
            )
            return state
        except Exception as e:
            logger.error("update_workflow_state_error", error=str(e))
            raise FirestoreError(f"Failed to update workflow state: {str(e)}")

    async def toggle_workflow(
        self,
        workflow_id: str,
        mode: TradingMode,
        enabled: bool,
    ) -> WorkflowState:
        """
        Toggle a workflow's enabled state.

        Args:
            workflow_id: Workflow identifier
            mode: Trading mode
            enabled: New enabled state

        Returns:
            Updated WorkflowState
        """
        state = await self.get_workflow_state(workflow_id, mode)

        if state is None:
            state = WorkflowState(
                workflow_id=workflow_id,
                mode=mode,
                enabled=enabled,
            )
        else:
            state.enabled = enabled

        return await self.update_workflow_state(state)


# Convenience function for creating client
def get_firestore_client() -> FirestoreClient:
    """Create and return a Firestore client instance."""
    return FirestoreClient()
