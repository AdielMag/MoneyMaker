"""
Unit tests for shared/polymarket_client.py
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shared.models import Market, OrderSide, OrderStatus, Position, TradingMode
from shared.polymarket_client import (
    PolymarketAPIError,
    PolymarketClient,
    get_polymarket_client,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.polymarket_api_key = "test-api-key"
    settings.polymarket_api_secret = "test-api-secret"
    settings.polymarket_wallet_address = "0x1234567890abcdef"
    return settings


@pytest.fixture
def polymarket_client(mock_settings):
    """Create a Polymarket client with mock settings."""
    return PolymarketClient(settings=mock_settings)


class TestPolymarketClient:
    """Tests for PolymarketClient class."""
    
    def test_initialization(self, polymarket_client, mock_settings):
        """Test client initialization."""
        assert polymarket_client.api_key == "test-api-key"
        assert polymarket_client.api_secret == "test-api-secret"
        assert polymarket_client.wallet_address == "0x1234567890abcdef"
    
    def test_get_base_headers(self, polymarket_client):
        """Test base headers generation."""
        headers = polymarket_client._get_base_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
    
    def test_sign_request(self, polymarket_client):
        """Test request signing."""
        headers = polymarket_client._sign_request(
            method="GET",
            path="/test",
            body="",
            timestamp=1234567890000,
        )
        assert "POLY_ADDRESS" in headers
        assert "POLY_SIGNATURE" in headers
        assert "POLY_TIMESTAMP" in headers
        assert "POLY_API_KEY" in headers
        assert headers["POLY_ADDRESS"] == "0x1234567890abcdef"
        assert headers["POLY_TIMESTAMP"] == "1234567890000"


class TestPolymarketClientAsyncContext:
    """Tests for async context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self, polymarket_client):
        """Test that context manager creates HTTP client."""
        async with polymarket_client as client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)
    
    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, polymarket_client):
        """Test that context manager closes HTTP client."""
        async with polymarket_client:
            pass
        assert polymarket_client._client is None


class TestParseMarket:
    """Tests for market parsing."""
    
    def test_parse_market_basic(self, polymarket_client):
        """Test parsing basic market data."""
        data = {
            "condition_id": "market-001",
            "question": "Will it rain tomorrow?",
            "description": "Weather prediction",
            "category": "weather",
            "endDate": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
            "volume": 10000,
            "liquidity": 5000,
            "tokens": [
                {"outcome": "Yes", "price": 0.6},
                {"outcome": "No", "price": 0.4},
            ],
        }
        
        market = polymarket_client._parse_market(data)
        
        assert market is not None
        assert market.id == "market-001"
        assert market.question == "Will it rain tomorrow?"
        assert market.volume == 10000
        assert len(market.outcomes) == 2
    
    def test_parse_market_empty_data(self, polymarket_client):
        """Test parsing empty data returns None."""
        assert polymarket_client._parse_market({}) is None
        assert polymarket_client._parse_market(None) is None
    
    def test_parse_market_missing_fields(self, polymarket_client):
        """Test parsing market with missing fields."""
        data = {
            "id": "market-002",
            "question": "Test question",
        }
        
        market = polymarket_client._parse_market(data)
        
        assert market is not None
        assert market.id == "market-002"
        assert market.volume == 0
        assert len(market.outcomes) == 0


class TestGetMarkets:
    """Tests for get_markets method."""
    
    @pytest.mark.asyncio
    async def test_get_markets_success(self, polymarket_client):
        """Test successful markets fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "condition_id": "market-001",
                "question": "Test market 1",
                "endDate": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
                "tokens": [{"outcome": "Yes", "price": 0.5}],
            },
            {
                "condition_id": "market-002",
                "question": "Test market 2",
                "endDate": (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z",
                "tokens": [{"outcome": "Yes", "price": 0.3}],
            },
        ]
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(polymarket_client, 'client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            
            markets = await polymarket_client.get_markets(limit=10)
            
            assert len(markets) == 2
            assert markets[0].id == "market-001"
            assert markets[1].id == "market-002"
    
    @pytest.mark.asyncio
    async def test_get_markets_empty(self, polymarket_client):
        """Test empty markets response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(polymarket_client, 'client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            
            markets = await polymarket_client.get_markets()
            
            assert markets == []
    
    @pytest.mark.asyncio
    async def test_get_markets_error(self, polymarket_client):
        """Test markets fetch error handling."""
        with patch.object(polymarket_client, 'client') as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            
            with pytest.raises(PolymarketAPIError) as exc_info:
                await polymarket_client.get_markets()
            
            assert "Failed to get markets" in str(exc_info.value)


class TestGetMarket:
    """Tests for get_market method."""
    
    @pytest.mark.asyncio
    async def test_get_market_success(self, polymarket_client):
        """Test successful single market fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "condition_id": "market-001",
            "question": "Test market",
            "endDate": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(polymarket_client, 'client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            
            market = await polymarket_client.get_market("market-001")
            
            assert market is not None
            assert market.id == "market-001"
    
    @pytest.mark.asyncio
    async def test_get_market_not_found(self, polymarket_client):
        """Test market not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(polymarket_client, 'client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            
            market = await polymarket_client.get_market("nonexistent")
            
            assert market is None


class TestGetBalance:
    """Tests for get_balance method."""
    
    @pytest.mark.asyncio
    async def test_get_balance_success(self, polymarket_client):
        """Test successful balance fetch."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.return_value = {"balance": 1000.50}
            
            balance = await polymarket_client.get_balance()
            
            assert balance == 1000.50
            mock_request.assert_called_once_with("GET", "/balance", authenticated=True)
    
    @pytest.mark.asyncio
    async def test_get_balance_error(self, polymarket_client):
        """Test balance fetch error handling."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            with pytest.raises(PolymarketAPIError) as exc_info:
                await polymarket_client.get_balance()
            
            assert "Failed to get balance" in str(exc_info.value)


class TestGetPositions:
    """Tests for get_positions method."""
    
    @pytest.mark.asyncio
    async def test_get_positions_success(self, polymarket_client):
        """Test successful positions fetch."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.return_value = {
                "positions": [
                    {
                        "id": "pos-001",
                        "market_id": "market-001",
                        "outcome": "Yes",
                        "avg_price": 0.35,
                        "current_price": 0.40,
                        "size": 100,
                        "cost_basis": 35.0,
                        "current_value": 40.0,
                    }
                ]
            }
            
            positions = await polymarket_client.get_positions()
            
            assert len(positions) == 1
            assert positions[0].id == "pos-001"
            assert positions[0].mode == TradingMode.REAL
    
    @pytest.mark.asyncio
    async def test_get_positions_empty(self, polymarket_client):
        """Test empty positions response."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.return_value = {"positions": []}
            
            positions = await polymarket_client.get_positions()
            
            assert positions == []


class TestPlaceOrder:
    """Tests for place_order method."""
    
    @pytest.mark.asyncio
    async def test_place_order_success(self, polymarket_client):
        """Test successful order placement."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.return_value = {
                "order_id": "order-123",
                "status": "pending",
            }
            
            order = await polymarket_client.place_order(
                market_id="market-001",
                outcome="Yes",
                side=OrderSide.BUY,
                price=0.35,
                quantity=100,
            )
            
            assert order.id == "order-123"
            assert order.market_id == "market-001"
            assert order.side == OrderSide.BUY
            assert order.status == OrderStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_place_order_filled(self, polymarket_client):
        """Test order that fills immediately."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.return_value = {
                "order_id": "order-124",
                "status": "filled",
            }
            
            order = await polymarket_client.place_order(
                market_id="market-001",
                outcome="Yes",
                side=OrderSide.BUY,
                price=0.35,
                quantity=100,
            )
            
            assert order.status == OrderStatus.FILLED
            assert order.filled_at is not None
    
    @pytest.mark.asyncio
    async def test_place_order_error(self, polymarket_client):
        """Test order placement error."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.side_effect = PolymarketAPIError("Insufficient funds")
            
            order = await polymarket_client.place_order(
                market_id="market-001",
                outcome="Yes",
                side=OrderSide.BUY,
                price=0.35,
                quantity=100,
            )
            
            assert order.status == OrderStatus.FAILED
            assert "Insufficient funds" in order.error_message


class TestCancelOrder:
    """Tests for cancel_order method."""
    
    @pytest.mark.asyncio
    async def test_cancel_order_success(self, polymarket_client):
        """Test successful order cancellation."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.return_value = {}
            
            result = await polymarket_client.cancel_order("order-123")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_cancel_order_error(self, polymarket_client):
        """Test order cancellation error."""
        with patch.object(polymarket_client, '_request') as mock_request:
            mock_request.side_effect = Exception("Order not found")
            
            result = await polymarket_client.cancel_order("nonexistent")
            
            assert result is False


class TestGetPolymarketClient:
    """Tests for get_polymarket_client helper function."""
    
    @pytest.mark.asyncio
    async def test_get_polymarket_client(self):
        """Test helper function creates client."""
        with patch('shared.polymarket_client.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.polymarket_api_key = "test-key"
            mock_settings.polymarket_api_secret = "test-secret"
            mock_settings.polymarket_wallet_address = "0x123"
            mock_get_settings.return_value = mock_settings
            
            client = await get_polymarket_client()
            
            assert isinstance(client, PolymarketClient)
