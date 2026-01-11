"""
Trader service implementation.

Handles order execution for both real and fake trading modes.
"""

from datetime import datetime
from uuid import uuid4

import structlog

from shared.config import Settings, get_settings
from shared.firestore_client import FirestoreClient, get_firestore_client
from shared.models import (
    AISuggestion,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    TradingMode,
    TransactionType,
)
from shared.polymarket_client import PolymarketAPIError, PolymarketClient

logger = structlog.get_logger(__name__)


class TraderService:
    """
    Service for executing trades on Polymarket.

    Supports both real money (Polymarket API) and fake money (Firestore) modes.
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient | None = None,
        firestore_client: FirestoreClient | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize trader service.

        Args:
            polymarket_client: Optional Polymarket client for real trades
            firestore_client: Optional Firestore client for fake trades
            settings: Optional Settings instance
        """
        self.settings = settings or get_settings()
        self._polymarket_client = polymarket_client
        self._firestore_client = firestore_client

    @property
    def polymarket_client(self) -> PolymarketClient:
        """Get or create Polymarket client."""
        if self._polymarket_client is None:
            self._polymarket_client = PolymarketClient(self.settings)
        return self._polymarket_client

    @property
    def firestore_client(self) -> FirestoreClient:
        """Get or create Firestore client."""
        if self._firestore_client is None:
            self._firestore_client = get_firestore_client()
        return self._firestore_client

    async def get_balance(self, mode: TradingMode) -> float:
        """
        Get current balance for trading mode.

        Args:
            mode: Trading mode (real or fake)

        Returns:
            Current balance in USDC
        """
        if mode == TradingMode.REAL:
            async with self.polymarket_client as client:
                return await client.get_balance()
        else:
            wallet = await self.firestore_client.get_or_create_wallet()
            return wallet.balance

    async def can_trade(self, mode: TradingMode, amount: float) -> tuple[bool, str]:
        """
        Check if trading is possible.

        Args:
            mode: Trading mode
            amount: Amount to trade

        Returns:
            Tuple of (can_trade, reason)
        """
        # Check if mode is enabled
        if mode == TradingMode.REAL and not self.settings.real_money_enabled:
            return False, "Real money trading is disabled"

        if mode == TradingMode.FAKE and not self.settings.fake_money_enabled:
            return False, "Fake money trading is disabled"

        # Check balance
        balance = await self.get_balance(mode)
        min_balance = self.settings.trading.min_balance_to_trade

        if balance < min_balance:
            return False, f"Balance ${balance:.2f} below minimum ${min_balance:.2f}"

        if balance < amount:
            return False, f"Insufficient balance: ${balance:.2f} < ${amount:.2f}"

        return True, "OK"

    async def place_buy_order(
        self,
        market_id: str,
        outcome: str,
        amount: float,
        price: float,
        mode: TradingMode,
    ) -> Order:
        """
        Place a buy order.

        Args:
            market_id: Market condition ID
            outcome: Outcome to buy (Yes/No)
            amount: Amount to spend in USDC
            price: Limit price (0-1)
            mode: Trading mode

        Returns:
            Order object with status
        """
        quantity = amount / price if price > 0 else 0

        logger.info(
            "placing_buy_order",
            market_id=market_id,
            outcome=outcome,
            amount=amount,
            price=price,
            mode=mode.value,
        )

        if mode == TradingMode.REAL:
            return await self._place_real_order(
                market_id=market_id,
                outcome=outcome,
                side=OrderSide.BUY,
                price=price,
                quantity=quantity,
            )
        else:
            return await self._place_fake_order(
                market_id=market_id,
                outcome=outcome,
                side=OrderSide.BUY,
                price=price,
                quantity=quantity,
                amount=amount,
            )

    async def place_sell_order(
        self,
        position: Position,
        price: float | None = None,
    ) -> Order:
        """
        Place a sell order to close a position.

        Args:
            position: Position to close
            price: Optional limit price (uses current if None)

        Returns:
            Order object with status
        """
        if price is None:
            price = position.current_price

        logger.info(
            "placing_sell_order",
            position_id=position.id,
            market_id=position.market_id,
            outcome=position.outcome,
            quantity=position.quantity,
            mode=position.mode.value,
        )

        if position.mode == TradingMode.REAL:
            return await self._place_real_order(
                market_id=position.market_id,
                outcome=position.outcome,
                side=OrderSide.SELL,
                price=price,
                quantity=position.quantity,
            )
        else:
            return await self._close_fake_position(position, price)

    async def _place_real_order(
        self,
        market_id: str,
        outcome: str,
        side: OrderSide,
        price: float,
        quantity: float,
    ) -> Order:
        """Place a real order on Polymarket."""
        try:
            async with self.polymarket_client as client:
                order = await client.place_order(
                    market_id=market_id,
                    outcome=outcome,
                    side=side,
                    price=price,
                    quantity=quantity,
                )

            logger.info(
                "real_order_placed",
                order_id=order.id,
                status=order.status.value,
            )
            return order

        except PolymarketAPIError as e:
            logger.error("real_order_failed", error=str(e))
            return Order(
                market_id=market_id,
                outcome=outcome,
                side=side,
                price=price,
                quantity=quantity,
                total_value=price * quantity,
                status=OrderStatus.FAILED,
                mode=TradingMode.REAL,
                error_message=str(e),
            )

    async def _place_fake_order(
        self,
        market_id: str,
        outcome: str,
        side: OrderSide,
        price: float,
        quantity: float,
        amount: float,
    ) -> Order:
        """Place a fake order in Firestore."""
        order_id = str(uuid4())

        # Get wallet and check balance
        wallet = await self.firestore_client.get_or_create_wallet()

        if not wallet.can_afford(amount):
            return Order(
                id=order_id,
                market_id=market_id,
                outcome=outcome,
                side=side,
                price=price,
                quantity=quantity,
                total_value=amount,
                status=OrderStatus.FAILED,
                mode=TradingMode.FAKE,
                error_message="Insufficient balance",
            )

        # Deduct from wallet
        balance_before = wallet.balance
        wallet.deduct(amount)
        await self.firestore_client.update_wallet_balance(wallet.wallet_id, wallet.balance)

        # Record transaction
        await self.firestore_client.create_transaction(
            wallet_id=wallet.wallet_id,
            tx_type=TransactionType.BUY,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            reference_id=order_id,
            description=f"Buy {outcome} on {market_id}",
        )

        # Create position
        position = Position(
            id=str(uuid4()),
            market_id=market_id,
            outcome=outcome,
            entry_price=price,
            current_price=price,
            quantity=quantity,
            entry_value=amount,
            current_value=amount,
            mode=TradingMode.FAKE,
        )
        await self.firestore_client.create_position(position)

        order = Order(
            id=order_id,
            market_id=market_id,
            outcome=outcome,
            side=side,
            price=price,
            quantity=quantity,
            total_value=amount,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
            filled_at=datetime.utcnow(),
        )

        logger.info(
            "fake_order_placed",
            order_id=order_id,
            position_id=position.id,
            amount=amount,
        )

        return order

    async def _close_fake_position(self, position: Position, price: float) -> Order:
        """Close a fake position."""
        order_id = str(uuid4())
        sale_value = price * position.quantity

        # Get wallet and add proceeds
        wallet = await self.firestore_client.get_or_create_wallet()
        balance_before = wallet.balance
        wallet.add(sale_value)
        await self.firestore_client.update_wallet_balance(wallet.wallet_id, wallet.balance)

        # Record transaction
        await self.firestore_client.create_transaction(
            wallet_id=wallet.wallet_id,
            tx_type=TransactionType.SELL,
            amount=sale_value,
            balance_before=balance_before,
            balance_after=wallet.balance,
            reference_id=position.id,
            description=f"Sell {position.outcome} on {position.market_id}",
        )

        # Delete position
        await self.firestore_client.delete_position(position.id)

        order = Order(
            id=order_id,
            market_id=position.market_id,
            outcome=position.outcome,
            side=OrderSide.SELL,
            price=price,
            quantity=position.quantity,
            total_value=sale_value,
            status=OrderStatus.FILLED,
            mode=TradingMode.FAKE,
            filled_at=datetime.utcnow(),
        )

        logger.info(
            "fake_position_closed",
            order_id=order_id,
            position_id=position.id,
            pnl=sale_value - position.entry_value,
        )

        return order

    async def execute_suggestion(
        self,
        suggestion: AISuggestion,
        position_size: float,
        mode: TradingMode,
    ) -> Order:
        """
        Execute a trade based on AI suggestion.

        Args:
            suggestion: AI suggestion to execute
            position_size: Amount to trade
            mode: Trading mode

        Returns:
            Order object with status
        """
        # Estimate price from suggestion
        # In real implementation, would fetch current market price
        estimated_price = 0.5  # Placeholder

        return await self.place_buy_order(
            market_id=suggestion.market_id,
            outcome=suggestion.recommended_outcome,
            amount=position_size,
            price=estimated_price,
            mode=mode,
        )


# Factory function
def get_trader_service() -> TraderService:
    """Create and return a TraderService instance."""
    return TraderService()
