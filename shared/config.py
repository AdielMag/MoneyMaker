"""
Configuration management for MoneyMaker.

Loads configuration from YAML files and environment variables.
Environment variables take precedence over YAML config.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkflowConfig(BaseSettings):
    """Configuration for a trading workflow."""

    enabled: bool = False
    scheduler_cron: str = "0 */2 * * *"
    initial_balance: float = 1000.0


class SellThresholds(BaseSettings):
    """Sell threshold configuration."""

    stop_loss_percent: float = -15.0
    take_profit_percent: float = 30.0


class TradingConfig(BaseSettings):
    """Trading configuration."""

    min_balance_to_trade: float = 10.0
    max_bet_amount: float = 50.0
    max_positions: int = 10
    sell_thresholds: SellThresholds = Field(default_factory=SellThresholds)


class MarketFiltersConfig(BaseSettings):
    """Market filtering configuration."""

    min_volume: int = 1000
    max_time_to_resolution_hours: float = 1.0
    min_liquidity: int = 500
    excluded_categories: list[str] = Field(default_factory=lambda: ["sports", "entertainment"])
    min_price: float = 0.05
    max_price: float = 0.95


class AIConfig(BaseSettings):
    """AI configuration."""

    model: str = "gemini-1.5-pro"
    max_suggestions: int = 5
    confidence_threshold: float = 0.7
    temperature: float = 0.3
    max_tokens: int = 2048


class APIConfig(BaseSettings):
    """API server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from various formats."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try to parse as JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # If it's a comma-separated string, split it
            if "," in v:
                return [origin.strip() for origin in v.split(",")]
            # Otherwise, treat as single origin
            return [v]
        return ["*"]


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    include_timestamp: bool = True


class Settings(BaseSettings):
    """
    Main settings class for MoneyMaker.

    Settings are loaded from:
    1. Default values
    2. config/config.yaml
    3. Environment variables (highest priority)
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = Field(default="development")

    # GCP
    gcp_project_id: str = Field(default="")
    gcp_region: str = Field(default="us-central1")

    # Polymarket
    polymarket_api_key: str = Field(default="")
    polymarket_api_secret: str = Field(default="")
    polymarket_wallet_address: str = Field(default="")
    polymarket_private_key: str = Field(default="")

    # Gemini
    gemini_api_key: str = Field(default="")

    # Feature Flags
    real_money_enabled: bool = Field(default=False)
    fake_money_enabled: bool = Field(default=True)

    # Nested configs
    workflows_real_money: WorkflowConfig = Field(default_factory=WorkflowConfig)
    workflows_fake_money: WorkflowConfig = Field(
        default_factory=lambda: WorkflowConfig(enabled=True)
    )
    trading: TradingConfig = Field(default_factory=TradingConfig)
    market_filters: MarketFiltersConfig = Field(default_factory=MarketFiltersConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "test"

    def get_active_mode(self) -> str:
        """Get the currently active trading mode."""
        if self.real_money_enabled:
            return "real"
        elif self.fake_money_enabled:
            return "fake"
        return "none"


def load_yaml_config(config_path: Path | None = None) -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to config/config.yaml

    Returns:
        Dictionary with configuration values
    """
    if config_path is None:
        # Try multiple locations
        possible_paths = [
            Path("config/config.yaml"),
            Path("../config/config.yaml"),
            Path(__file__).parent.parent / "config" / "config.yaml",
        ]
        for path in possible_paths:
            if path.exists():
                config_path = path
                break

    if config_path is None or not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "__") -> dict[str, Any]:
    """
    Flatten a nested dictionary for environment variable style keys.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator between keys

    Returns:
        Flattened dictionary
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Settings are loaded once and cached for performance.
    Call this function to access settings throughout the application.

    Returns:
        Settings instance
    """
    # Load YAML config first
    yaml_config = load_yaml_config()

    # Flatten nested config for pydantic-settings
    flat_config = flatten_dict(yaml_config)

    # Convert to uppercase for env var style
    env_style_config = {k.upper(): v for k, v in flat_config.items()}

    # Set as environment variables (only if not already set)
    for key, value in env_style_config.items():
        if key not in os.environ and value is not None:
            if isinstance(value, (list, dict)):
                os.environ[key] = json.dumps(value)
            elif isinstance(value, bool):
                os.environ[key] = str(value).lower()
            else:
                os.environ[key] = str(value)

    return Settings()


def reset_settings() -> None:
    """Reset cached settings. Useful for testing."""
    get_settings.cache_clear()
