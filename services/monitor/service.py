"""
Position Monitor service implementation.

Monitors positions and triggers sells based on thresholds.
"""

from datetime import datetime
from typing import Any

import structlog

from shared.config import Settings, get_settings
from shared.firestore_client import FirestoreClient, get_firestore_client
from shared.models import Order, Position, TradingMode
from shared.polymarket_client import PolymarketClient
from services.trader.service import TraderService, get_trader_service

logger = structlog.get_logger(__name__)


class MonitorService:
    """
    Service for monitoring trading positions.
    
    Checks positions against configured thresholds and triggers
    sell orders when stop-loss or take-profit levels are reached.
    """
    
    def __init__(
        self,
        trader_service: TraderService | None = None,
        polymarket_client: PolymarketClient | None = None,
        firestore_client: FirestoreClient | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize monitor service.
        
        Args:
            trader_service: Optional TraderService for executing sells
            polymarket_client: Optional Polymarket client for real positions
            firestore_client: Optional Firestore client for fake positions
            settings: Optional Settings instance
        """
        self.settings = settings or get_settings()
        self._trader_service = trader_service
        self._polymarket_client = polymarket_client
        self._firestore_client = firestore_client
    
    @property
    def trader_service(self) -> TraderService:
        """Get or create trader service."""
        if self._trader_service is None:
            self._trader_service = get_trader_service()
        return self._trader_service
    
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
    
    @property
    def stop_loss_threshold(self) -> float:
        """Get stop-loss threshold from settings."""
        return self.settings.trading.sell_thresholds.stop_loss_percent
    
    @property
    def take_profit_threshold(self) -> float:
        """Get take-profit threshold from settings."""
        return self.settings.trading.sell_thresholds.take_profit_percent
    
    async def get_positions(self, mode: TradingMode) -> list[Position]:
        """
        Get open positions for a trading mode.
        
        Args:
            mode: Trading mode (real or fake)
            
        Returns:
            List of open positions
        """
        if mode == TradingMode.REAL:
            async with self.polymarket_client as client:
                return await client.get_positions()
        else:
            return await self.firestore_client.get_open_positions(mode)
    
    async def update_position_prices(
        self,
        positions: list[Position],
    ) -> list[Position]:
        """
        Update current prices for positions.
        
        Args:
            positions: Positions to update
            
        Returns:
            Positions with updated prices
        """
        if not positions:
            return []
        
        # Group by market to minimize API calls
        market_ids = set(p.market_id for p in positions)
        
        # Fetch current prices
        # In production, would use order book or market data
        # For now, keeping existing prices as placeholder
        
        for position in positions:
            # Calculate P&L
            position.pnl_percent = position.calculate_pnl()
        
        return positions
    
    async def check_position(
        self,
        position: Position,
    ) -> tuple[bool, str, str | None]:
        """
        Check if a position should be sold.
        
        Args:
            position: Position to check
            
        Returns:
            Tuple of (should_sell, action, reason)
        """
        # Check stop-loss
        if position.should_stop_loss(self.stop_loss_threshold):
            return True, "stop_loss", f"P&L {position.pnl_percent:.1f}% <= {self.stop_loss_threshold}%"
        
        # Check take-profit
        if position.should_take_profit(self.take_profit_threshold):
            return True, "take_profit", f"P&L {position.pnl_percent:.1f}% >= {self.take_profit_threshold}%"
        
        return False, "hold", None
    
    async def monitor_positions(
        self,
        mode: TradingMode,
    ) -> dict[str, Any]:
        """
        Monitor all positions for a trading mode.
        
        Checks each position against thresholds and executes
        sell orders as needed.
        
        Args:
            mode: Trading mode to monitor
            
        Returns:
            Summary of monitoring results
        """
        logger.info("monitoring_positions", mode=mode.value)
        
        # Get positions
        positions = await self.get_positions(mode)
        
        if not positions:
            logger.info("no_positions_to_monitor", mode=mode.value)
            return {
                "mode": mode.value,
                "positions_checked": 0,
                "sells_triggered": 0,
                "stop_losses": 0,
                "take_profits": 0,
                "errors": [],
            }
        
        # Update prices
        positions = await self.update_position_prices(positions)
        
        # Check each position
        results = {
            "mode": mode.value,
            "positions_checked": len(positions),
            "sells_triggered": 0,
            "stop_losses": 0,
            "take_profits": 0,
            "orders": [],
            "errors": [],
        }
        
        for position in positions:
            should_sell, action, reason = await self.check_position(position)
            
            if should_sell:
                try:
                    order = await self.trader_service.place_sell_order(position)
                    results["sells_triggered"] += 1
                    
                    if action == "stop_loss":
                        results["stop_losses"] += 1
                    elif action == "take_profit":
                        results["take_profits"] += 1
                    
                    results["orders"].append({
                        "position_id": position.id,
                        "market_id": position.market_id,
                        "action": action,
                        "reason": reason,
                        "order_id": order.id,
                        "order_status": order.status.value,
                    })
                    
                    logger.info(
                        "position_sold",
                        position_id=position.id,
                        action=action,
                        pnl_percent=position.pnl_percent,
                    )
                    
                except Exception as e:
                    error_msg = f"Failed to sell position {position.id}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error("sell_error", position_id=position.id, error=str(e))
        
        logger.info(
            "monitoring_complete",
            mode=mode.value,
            positions=results["positions_checked"],
            sells=results["sells_triggered"],
        )
        
        return results
    
    async def get_positions_summary(
        self,
        mode: TradingMode,
    ) -> dict[str, Any]:
        """
        Get summary of current positions.
        
        Args:
            mode: Trading mode
            
        Returns:
            Summary dictionary
        """
        positions = await self.get_positions(mode)
        positions = await self.update_position_prices(positions)
        
        if not positions:
            return {
                "mode": mode.value,
                "count": 0,
                "total_value": 0,
                "total_pnl_percent": 0,
                "profitable": 0,
                "losing": 0,
                "near_stop_loss": 0,
                "near_take_profit": 0,
            }
        
        total_entry_value = sum(p.entry_value for p in positions)
        total_current_value = sum(p.current_value for p in positions)
        total_pnl_percent = ((total_current_value - total_entry_value) / total_entry_value * 100) if total_entry_value > 0 else 0
        
        profitable = sum(1 for p in positions if p.pnl_percent > 0)
        losing = sum(1 for p in positions if p.pnl_percent < 0)
        
        # Count positions near thresholds
        near_stop_loss = sum(
            1 for p in positions
            if p.pnl_percent <= self.stop_loss_threshold + 5  # Within 5% of stop-loss
        )
        near_take_profit = sum(
            1 for p in positions
            if p.pnl_percent >= self.take_profit_threshold - 10  # Within 10% of take-profit
        )
        
        return {
            "mode": mode.value,
            "count": len(positions),
            "total_entry_value": total_entry_value,
            "total_current_value": total_current_value,
            "total_pnl_percent": total_pnl_percent,
            "profitable": profitable,
            "losing": losing,
            "near_stop_loss": near_stop_loss,
            "near_take_profit": near_take_profit,
            "positions": [
                {
                    "id": p.id,
                    "market_id": p.market_id,
                    "outcome": p.outcome,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "pnl_percent": p.pnl_percent,
                }
                for p in positions
            ],
        }
    
    def should_trigger_alert(
        self,
        position: Position,
        alert_threshold: float = 10.0,
    ) -> tuple[bool, str | None]:
        """
        Check if position should trigger an alert.
        
        Args:
            position: Position to check
            alert_threshold: P&L threshold for alerts
            
        Returns:
            Tuple of (should_alert, reason)
        """
        # Alert if approaching stop-loss
        if position.pnl_percent <= self.stop_loss_threshold + 5:
            return True, f"Approaching stop-loss: {position.pnl_percent:.1f}%"
        
        # Alert if approaching take-profit
        if position.pnl_percent >= self.take_profit_threshold - 10:
            return True, f"Approaching take-profit: {position.pnl_percent:.1f}%"
        
        # Alert on large moves
        if abs(position.pnl_percent) >= alert_threshold:
            direction = "gain" if position.pnl_percent > 0 else "loss"
            return True, f"Large {direction}: {position.pnl_percent:.1f}%"
        
        return False, None


# Factory function
def get_monitor_service() -> MonitorService:
    """Create and return a MonitorService instance."""
    return MonitorService()
