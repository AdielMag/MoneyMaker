"""
Polymarket API client for MoneyMaker.

Provides async interface to Polymarket's CLOB API for:
- Fetching markets
- Getting positions
- Placing/cancelling orders
- Checking balances
"""

import hashlib
import hmac
import time
from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.config import Settings, get_settings
from shared.models import Market, MarketOutcome, Order, OrderSide, OrderStatus, Position, TradingMode

logger = structlog.get_logger(__name__)


class PolymarketAPIError(Exception):
    """Custom exception for Polymarket API errors."""
    
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PolymarketClient:
    """
    Async client for Polymarket CLOB API.
    
    Handles authentication, request signing, and provides typed methods
    for all trading operations.
    """
    
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, settings: Settings | None = None):
        """
        Initialize Polymarket client.
        
        Args:
            settings: Settings instance. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self.api_key = self.settings.polymarket_api_key
        self.api_secret = self.settings.polymarket_api_secret
        self.wallet_address = self.settings.polymarket_wallet_address
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "PolymarketClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers=self._get_base_headers(),
        )
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_base_headers(self) -> dict[str, str]:
        """Get base headers for requests."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _sign_request(
        self,
        method: str,
        path: str,
        body: str = "",
        timestamp: int | None = None,
    ) -> dict[str, str]:
        """
        Sign a request for Polymarket authentication.
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body as string
            timestamp: Unix timestamp in milliseconds
            
        Returns:
            Headers with authentication signature
        """
        if not timestamp:
            timestamp = int(time.time() * 1000)
        
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return {
            "POLY_ADDRESS": self.wallet_address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": str(timestamp),
            "POLY_API_KEY": self.api_key,
        }
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=self._get_base_headers(),
            )
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        """
        Make an HTTP request to Polymarket API.
        
        Args:
            method: HTTP method
            path: API path
            params: Query parameters
            json_data: JSON body data
            authenticated: Whether to sign the request
            
        Returns:
            JSON response data
            
        Raises:
            PolymarketAPIError: If request fails
        """
        url = f"{self.BASE_URL}{path}"
        headers = {}
        
        if authenticated:
            body = ""
            if json_data:
                import json
                body = json.dumps(json_data)
            headers.update(self._sign_request(method, path, body))
        
        logger.debug(
            "polymarket_request",
            method=method,
            path=path,
            authenticated=authenticated,
        )
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            )
            
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise PolymarketAPIError(
                    f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                    response=error_data,
                )
            
            return response.json() if response.content else {}
            
        except httpx.RequestError as e:
            logger.error("polymarket_request_error", error=str(e))
            raise PolymarketAPIError(f"Request failed: {str(e)}")
    
    async def get_markets(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        """
        Get list of markets from Polymarket.
        
        Args:
            active_only: Only return active markets
            limit: Maximum number of markets
            offset: Pagination offset
            
        Returns:
            List of Market objects
        """
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active_only).lower(),
        }
        
        # Use Gamma API for market data
        url = f"{self.GAMMA_URL}/markets"
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("get_markets_error", error=str(e))
            raise PolymarketAPIError(f"Failed to get markets: {str(e)}")
        
        markets = []
        for item in data:
            try:
                market = self._parse_market(item)
                if market:
                    markets.append(market)
            except Exception as e:
                logger.warning("parse_market_error", market_id=item.get("id"), error=str(e))
                continue
        
        return markets
    
    async def get_market(self, market_id: str) -> Market | None:
        """
        Get a specific market by ID.
        
        Args:
            market_id: Market condition ID
            
        Returns:
            Market object or None if not found
        """
        url = f"{self.GAMMA_URL}/markets/{market_id}"
        
        try:
            response = await self.client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return self._parse_market(data)
        except Exception as e:
            logger.error("get_market_error", market_id=market_id, error=str(e))
            raise PolymarketAPIError(f"Failed to get market: {str(e)}")
    
    def _parse_market(self, data: dict[str, Any]) -> Market | None:
        """Parse API response into Market model."""
        if not data:
            return None
        
        # Parse outcomes
        outcomes = []
        tokens = data.get("tokens", []) or data.get("outcomes", [])
        
        for token in tokens:
            if isinstance(token, dict):
                outcomes.append(MarketOutcome(
                    name=token.get("outcome", token.get("name", "Unknown")),
                    price=float(token.get("price", 0.5)),
                ))
            elif isinstance(token, str):
                outcomes.append(MarketOutcome(name=token, price=0.5))
        
        # Parse end date
        end_date_str = data.get("endDate") or data.get("end_date_iso")
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except Exception:
                end_date = datetime.utcnow()
        else:
            end_date = datetime.utcnow()
        
        return Market(
            id=data.get("condition_id") or data.get("id", ""),
            question=data.get("question", ""),
            description=data.get("description", ""),
            category=data.get("category", data.get("groupItemTitle", "")),
            end_date=end_date,
            volume=float(data.get("volume", 0) or 0),
            liquidity=float(data.get("liquidity", 0) or 0),
            outcomes=outcomes,
        )
    
    async def get_balance(self) -> float:
        """
        Get USDC balance for the configured wallet.
        
        Returns:
            Balance in USDC
        """
        path = "/balance"
        
        try:
            data = await self._request("GET", path, authenticated=True)
            return float(data.get("balance", 0))
        except Exception as e:
            logger.error("get_balance_error", error=str(e))
            raise PolymarketAPIError(f"Failed to get balance: {str(e)}")
    
    async def get_positions(self) -> list[Position]:
        """
        Get open positions for the configured wallet.
        
        Returns:
            List of Position objects
        """
        path = "/positions"
        
        try:
            data = await self._request("GET", path, authenticated=True)
        except Exception as e:
            logger.error("get_positions_error", error=str(e))
            raise PolymarketAPIError(f"Failed to get positions: {str(e)}")
        
        positions = []
        for item in data.get("positions", []):
            try:
                position = Position(
                    id=item.get("id", ""),
                    market_id=item.get("market_id", item.get("condition_id", "")),
                    outcome=item.get("outcome", ""),
                    entry_price=float(item.get("avg_price", 0)),
                    current_price=float(item.get("current_price", item.get("avg_price", 0))),
                    quantity=float(item.get("size", 0)),
                    entry_value=float(item.get("cost_basis", 0)),
                    current_value=float(item.get("current_value", 0)),
                    mode=TradingMode.REAL,
                )
                position.pnl_percent = position.calculate_pnl()
                positions.append(position)
            except Exception as e:
                logger.warning("parse_position_error", error=str(e))
                continue
        
        return positions
    
    async def place_order(
        self,
        market_id: str,
        outcome: str,
        side: OrderSide,
        price: float,
        quantity: float,
    ) -> Order:
        """
        Place an order on Polymarket.
        
        Args:
            market_id: Market condition ID
            outcome: Outcome to trade (e.g., "Yes", "No")
            side: Buy or sell
            price: Limit price (0-1)
            quantity: Number of shares
            
        Returns:
            Order object with status
        """
        path = "/order"
        
        order_data = {
            "market": market_id,
            "outcome": outcome,
            "side": side.value,
            "price": price,
            "size": quantity,
            "type": "limit",
        }
        
        order = Order(
            market_id=market_id,
            outcome=outcome,
            side=side,
            price=price,
            quantity=quantity,
            total_value=price * quantity,
            mode=TradingMode.REAL,
        )
        
        try:
            data = await self._request("POST", path, json_data=order_data, authenticated=True)
            order.id = data.get("order_id", data.get("id", ""))
            order.status = OrderStatus.PENDING
            
            if data.get("status") == "filled":
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.utcnow()
            
            logger.info(
                "order_placed",
                order_id=order.id,
                market_id=market_id,
                side=side.value,
                price=price,
                quantity=quantity,
            )
            
            return order
            
        except PolymarketAPIError as e:
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            logger.error("place_order_error", error=str(e), market_id=market_id)
            return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        path = f"/order/{order_id}"
        
        try:
            await self._request("DELETE", path, authenticated=True)
            logger.info("order_cancelled", order_id=order_id)
            return True
        except Exception as e:
            logger.error("cancel_order_error", order_id=order_id, error=str(e))
            return False
    
    async def get_order_book(self, market_id: str) -> dict[str, Any]:
        """
        Get order book for a market.
        
        Args:
            market_id: Market condition ID
            
        Returns:
            Order book data with bids and asks
        """
        path = f"/book"
        params = {"market": market_id}
        
        try:
            return await self._request("GET", path, params=params)
        except Exception as e:
            logger.error("get_order_book_error", market_id=market_id, error=str(e))
            raise PolymarketAPIError(f"Failed to get order book: {str(e)}")


# Convenience function for creating client
async def get_polymarket_client() -> PolymarketClient:
    """Create and return a Polymarket client instance."""
    client = PolymarketClient()
    return client
