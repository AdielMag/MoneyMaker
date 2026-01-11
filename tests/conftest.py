"""
Shared pytest fixtures and test configuration for MoneyMaker.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["GCP_PROJECT_ID"] = "test-project"
os.environ["POLYMARKET_API_KEY"] = "test-api-key"
os.environ["POLYMARKET_API_SECRET"] = "test-api-secret"
os.environ["POLYMARKET_WALLET_ADDRESS"] = "0x1234567890abcdef"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["REAL_MONEY_ENABLED"] = "false"
os.environ["FAKE_MONEY_ENABLED"] = "true"

fake = Faker()

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================================================
# Fixture Loading Helpers
# ============================================================================


def load_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON fixture file."""
    filepath = FIXTURES_DIR / filename
    with open(filepath) as f:
        return json.load(f)


# ============================================================================
# Market Data Fixtures
# ============================================================================


@pytest.fixture
def sample_markets() -> list[dict[str, Any]]:
    """Load sample market data from fixtures."""
    return load_fixture("markets.json")["markets"]


@pytest.fixture
def sample_market() -> dict[str, Any]:
    """Return a single sample market."""
    return load_fixture("markets.json")["markets"][0]


@pytest.fixture
def filtered_markets() -> list[dict[str, Any]]:
    """Return pre-filtered markets meeting all criteria."""
    markets = load_fixture("markets.json")["markets"]
    return [m for m in markets if m.get("passes_filter", False)]


# ============================================================================
# Position Data Fixtures
# ============================================================================


@pytest.fixture
def sample_positions() -> list[dict[str, Any]]:
    """Load sample position data from fixtures."""
    return load_fixture("positions.json")["positions"]


@pytest.fixture
def sample_position() -> dict[str, Any]:
    """Return a single sample position."""
    return load_fixture("positions.json")["positions"][0]


@pytest.fixture
def profitable_position() -> dict[str, Any]:
    """Return a position that should trigger take-profit."""
    positions = load_fixture("positions.json")["positions"]
    return next(p for p in positions if p.get("should_take_profit", False))


@pytest.fixture
def losing_position() -> dict[str, Any]:
    """Return a position that should trigger stop-loss."""
    positions = load_fixture("positions.json")["positions"]
    return next(p for p in positions if p.get("should_stop_loss", False))


# ============================================================================
# AI Response Fixtures
# ============================================================================


@pytest.fixture
def sample_ai_responses() -> dict[str, Any]:
    """Load sample AI responses from fixtures."""
    return load_fixture("ai_responses.json")


@pytest.fixture
def valid_ai_suggestion() -> dict[str, Any]:
    """Return a valid AI suggestion response."""
    return load_fixture("ai_responses.json")["valid_suggestion"]


@pytest.fixture
def empty_ai_suggestion() -> dict[str, Any]:
    """Return an AI response with no suggestions."""
    return load_fixture("ai_responses.json")["empty_suggestion"]


# ============================================================================
# Mock Client Fixtures
# ============================================================================


@pytest.fixture
def mock_polymarket_client() -> MagicMock:
    """Create a mocked Polymarket API client."""
    client = MagicMock()
    client.get_markets = AsyncMock(return_value=[])
    client.get_market = AsyncMock(return_value={})
    client.get_positions = AsyncMock(return_value=[])
    client.get_balance = AsyncMock(return_value=1000.0)
    client.place_order = AsyncMock(return_value={"order_id": "test-order-123"})
    client.cancel_order = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_gemini_client() -> MagicMock:
    """Create a mocked Gemini AI client."""
    client = MagicMock()
    client.analyze_markets = AsyncMock(return_value={
        "suggestions": [],
        "confidence": 0.0,
        "reasoning": "No markets analyzed"
    })
    client.generate_content = AsyncMock(return_value=MagicMock(
        text='{"suggestions": [], "confidence": 0.0}'
    ))
    return client


@pytest.fixture
def mock_firestore_client() -> MagicMock:
    """Create a mocked Firestore client."""
    client = MagicMock()
    
    # Mock collection references
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = MagicMock(return_value=MagicMock(
        exists=True,
        to_dict=MagicMock(return_value={})
    ))
    mock_doc.set = AsyncMock()
    mock_doc.update = AsyncMock()
    mock_doc.delete = AsyncMock()
    
    mock_collection.document = MagicMock(return_value=mock_doc)
    mock_collection.where = MagicMock(return_value=mock_collection)
    mock_collection.stream = MagicMock(return_value=iter([]))
    
    client.collection = MagicMock(return_value=mock_collection)
    
    return client


# ============================================================================
# Fake Wallet Fixtures
# ============================================================================


@pytest.fixture
def fake_wallet() -> dict[str, Any]:
    """Return a fake wallet with test balance."""
    return {
        "wallet_id": "test-wallet-001",
        "balance": 1000.0,
        "currency": "USDC",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def empty_wallet() -> dict[str, Any]:
    """Return a fake wallet with zero balance."""
    return {
        "wallet_id": "test-wallet-002",
        "balance": 0.0,
        "currency": "USDC",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def low_balance_wallet() -> dict[str, Any]:
    """Return a fake wallet with balance below minimum trade threshold."""
    return {
        "wallet_id": "test-wallet-003",
        "balance": 5.0,  # Below min_balance_to_trade of 10.0
        "currency": "USDC",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def test_config() -> dict[str, Any]:
    """Return test configuration."""
    return {
        "workflows": {
            "real_money": {
                "enabled": False,
                "scheduler_cron": "0 */2 * * *",
            },
            "fake_money": {
                "enabled": True,
                "scheduler_cron": "*/30 * * * *",
                "initial_balance": 1000.0,
            },
        },
        "trading": {
            "min_balance_to_trade": 10.0,
            "max_bet_amount": 50.0,
            "max_positions": 10,
            "sell_thresholds": {
                "stop_loss_percent": -15,
                "take_profit_percent": 30,
            },
        },
        "market_filters": {
            "min_volume": 1000,
            "max_time_to_resolution_hours": 1,
            "min_liquidity": 500,
            "excluded_categories": ["sports", "entertainment"],
        },
        "ai": {
            "model": "gemini-1.5-pro",
            "max_suggestions": 5,
            "confidence_threshold": 0.7,
        },
    }


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Create a mocked httpx async client."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ============================================================================
# Time Fixtures
# ============================================================================


@pytest.fixture
def fixed_datetime() -> datetime:
    """Return a fixed datetime for consistent testing."""
    return datetime(2024, 6, 15, 12, 0, 0)


@pytest.fixture
def market_close_soon() -> datetime:
    """Return a datetime 30 minutes from now (market closing soon)."""
    return datetime.utcnow() + timedelta(minutes=30)


@pytest.fixture
def market_close_later() -> datetime:
    """Return a datetime 2 hours from now (market closing later)."""
    return datetime.utcnow() + timedelta(hours=2)


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================


@pytest.fixture
def anyio_backend() -> str:
    """Configure anyio backend for async tests."""
    return "asyncio"


# ============================================================================
# Cleanup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_environment() -> Generator[None, None, None]:
    """Reset environment variables after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
