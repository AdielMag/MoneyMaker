"""
Trader service implementation.

Handles order execution for both real and fake trading modes.
"""

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
from shared.polymarket_client import PolymarketClient

logger = structlog.get_logger(__name__)


class TraderService:
    """
    Service for executing trades.

    Handles both real money (via Polymarket API) and fake money
    (via Firestore) trading operations.
    """

    def __init__(
        self,
        firestore_client: FirestoreClient | None = None,
        polymarket_client: PolymarketClient | None = None,
        settings: Settings | None = None,
    ):
        """Initialize trader service."""
        self.settings = settings or get_settings()
        self._firestore_client = firestore_client
        self._polymarket_client = polymarket_client

    @property
    def firestore_client(self) -> FirestoreClient:
        """Get or create Firestore client."""
        if self._firestore_client is None:
            self._firestore_client = get_firestore_client()
        return self._firestore_client

    @property
    def polymarket_client(self) -> PolymarketClient:
        """Get or create Polymarket client."""
        if self._polymarket_client is None:
            from shared.polymarket_client import PolymarketClient

            self._polymarket_client = PolymarketClient(self.settings)
        return self._polymarket_client

    async def get_balance(self, mode: TradingMode) -> float:
        """
        Get current balance for trading mode.

        Args:
            mode: Trading mode

        Returns:
            Current balance in USDC
        """
        if mode == TradingMode.REAL:
            # Get real balance from Polymarket
            async with self.polymarket_client as client:
                return await client.get_balance()
        else:
            # Get fake balance from Firestore
            wallet = await self.firestore_client.get_or_create_wallet("default")
            return wallet.balance

    async def can_trade(
        self,
        mode: TradingMode,
        amount: float,
    ) -> tuple[bool, str]:
        """
        Check if trading is possible for given amount.

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
            return False, f"Balance ${balance:.2f} is below minimum ${min_balance:.2f}"

        if balance < amount:
            return False, f"Insufficient balance: ${balance:.2f} < ${amount:.2f}"

        # Check max bet amount
        max_bet = self.settings.trading.max_bet_amount
        if amount > max_bet:
            return False, f"Amount ${amount:.2f} exceeds max bet ${max_bet:.2f}"

        # Check max positions (for fake mode)
        if mode == TradingMode.FAKE:
            positions = await self.firestore_client.get_open_positions(mode)
            max_positions = self.settings.trading.max_positions
            if len(positions) >= max_positions:
                return False, f"Maximum positions ({max_positions}) reached"

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
            Order object
        """
        logger.info(
            "placing_buy_order",
            market_id=market_id,
            outcome=outcome,
            amount=amount,
            price=price,
            mode=mode.value,
        )

        # Calculate quantity
        quantity = amount / price if price > 0 else 0

        if mode == TradingMode.REAL:
            # Place real order via Polymarket
            async with self.polymarket_client as client:
                order = await client.place_order(
                    market_id=market_id,
                    outcome=outcome,
                    side=OrderSide.BUY,
                    amount=amount,
                    price=price,
                )
                return order
        else:
            # Place fake order via Firestore
            wallet = await self.firestore_client.get_or_create_wallet("default")
            balance_before = wallet.balance

            # Check if we can afford it
            if not wallet.can_afford(amount):
                order = Order(
                    market_id=market_id,
                    outcome=outcome,
                    side=OrderSide.BUY,
                    price=price,
                    quantity=quantity,
                    total_value=amount,
                    status=OrderStatus.FAILED,
                    mode=mode,
                    error_message=f"Insufficient balance: ${wallet.balance:.2f} < ${amount:.2f}",
                )
                logger.warning("buy_order_failed", reason=order.error_message)
                return order

            # Deduct from wallet
            if not wallet.deduct(amount):
                order = Order(
                    market_id=market_id,
                    outcome=outcome,
                    side=OrderSide.BUY,
                    price=price,
                    quantity=quantity,
                    total_value=amount,
                    status=OrderStatus.FAILED,
                    mode=mode,
                    error_message="Failed to deduct from wallet",
                )
                logger.warning("buy_order_failed", reason=order.error_message)
                return order

            # Update wallet in Firestore
            await self.firestore_client.update_wallet_balance("default", wallet.balance)

            # Create transaction
            await self.firestore_client.create_transaction(
                wallet_id="default",
                tx_type=TransactionType.BUY,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                reference_id=f"order-{market_id}",
                description=f"Buy {outcome} on {market_id}",
            )

            # Create position
            position = Position(
                id="",
                market_id=market_id,
                outcome=outcome,
                entry_price=price,
                current_price=price,
                quantity=quantity,
                entry_value=amount,
                current_value=amount,
                mode=mode,
            )
            position = await self.firestore_client.create_position(position)

            # Create order record
            order = Order(
                id=f"order-{position.id}",
                market_id=market_id,
                outcome=outcome,
                side=OrderSide.BUY,
                price=price,
                quantity=quantity,
                total_value=amount,
                status=OrderStatus.FILLED,
                mode=mode,
            )

            logger.info("buy_order_filled", order_id=order.id, position_id=position.id)
            return order

    async def place_sell_order(
        self,
        position: Position,
        price: float | None = None,
    ) -> Order:
        """
        Place a sell order to close a position.

        Args:
            position: Position to close
            price: Sell price (uses current price if not provided)

        Returns:
            Order object
        """
        if price is None:
            price = position.current_price

        logger.info(
            "placing_sell_order",
            position_id=position.id,
            market_id=position.market_id,
            price=price,
        )

        # Calculate proceeds
        proceeds = price * position.quantity

        if position.mode == TradingMode.REAL:
            # Place real sell order via Polymarket
            async with self.polymarket_client as client:
                order = await client.place_order(
                    market_id=position.market_id,
                    outcome=position.outcome,
                    side=OrderSide.SELL,
                    amount=proceeds,
                    price=price,
                )
                return order
        else:
            # Place fake sell order via Firestore
            wallet = await self.firestore_client.get_or_create_wallet("default")
            balance_before = wallet.balance

            # Add proceeds to wallet
            wallet.add(proceeds)

            # Update wallet in Firestore
            await self.firestore_client.update_wallet_balance("default", wallet.balance)

            # Create transaction
            await self.firestore_client.create_transaction(
                wallet_id="default",
                tx_type=TransactionType.SELL,
                amount=proceeds,
                balance_before=balance_before,
                balance_after=wallet.balance,
                reference_id=position.id,
                description=f"Sell {position.outcome} on {position.market_id}",
            )

            # Delete position
            await self.firestore_client.delete_position(position.id)

            # Create order record
            order = Order(
                id=f"order-sell-{position.id}",
                market_id=position.market_id,
                outcome=position.outcome,
                side=OrderSide.SELL,
                price=price,
                quantity=position.quantity,
                total_value=proceeds,
                status=OrderStatus.FILLED,
                mode=position.mode,
            )

            logger.info("sell_order_filled", order_id=order.id, position_id=position.id)
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
            suggestion: AI suggestion
            position_size: Amount to trade
            mode: Trading mode

        Returns:
            Order object
        """
        logger.info(
            "executing_suggestion",
            market_id=suggestion.market_id,
            outcome=suggestion.recommended_outcome,
            position_size=position_size,
            mode=mode.value,
        )

        # Use suggested price or fetch current market price
        # For now, use a default price based on confidence
        # In production, would fetch from market data
        price = 0.5  # Default price, should be fetched from market

        return await self.place_buy_order(
            market_id=suggestion.market_id,
            outcome=suggestion.recommended_outcome,
            amount=position_size,
            price=price,
            mode=mode,
        )


# Factory function
def get_trader_service() -> TraderService:
    """Create and return a TraderService instance."""
    return TraderService()
