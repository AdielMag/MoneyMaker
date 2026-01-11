"""
Unit tests for shared/config.py
"""

import os
from pathlib import Path

import pytest
import yaml

from shared.config import (
    AIConfig,
    MarketFiltersConfig,
    SellThresholds,
    Settings,
    TradingConfig,
    WorkflowConfig,
    flatten_dict,
    get_settings,
    load_yaml_config,
    reset_settings,
)


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Reset settings cache before each test."""
    reset_settings()
    yield
    reset_settings()


class TestWorkflowConfig:
    """Tests for WorkflowConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = WorkflowConfig()
        assert config.enabled is False
        assert config.scheduler_cron == "0 */2 * * *"
        assert config.initial_balance == 1000.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = WorkflowConfig(
            enabled=True,
            scheduler_cron="*/15 * * * *",
            initial_balance=5000.0,
        )
        assert config.enabled is True
        assert config.scheduler_cron == "*/15 * * * *"
        assert config.initial_balance == 5000.0


class TestSellThresholds:
    """Tests for SellThresholds model."""

    def test_default_values(self):
        """Test default threshold values."""
        thresholds = SellThresholds()
        assert thresholds.stop_loss_percent == -15.0
        assert thresholds.take_profit_percent == 30.0

    def test_custom_values(self):
        """Test custom threshold values."""
        thresholds = SellThresholds(
            stop_loss_percent=-10.0,
            take_profit_percent=25.0,
        )
        assert thresholds.stop_loss_percent == -10.0
        assert thresholds.take_profit_percent == 25.0


class TestTradingConfig:
    """Tests for TradingConfig model."""

    def test_default_values(self):
        """Test default trading configuration."""
        config = TradingConfig()
        assert config.min_balance_to_trade == 10.0
        assert config.max_bet_amount == 50.0
        assert config.max_positions == 10
        assert isinstance(config.sell_thresholds, SellThresholds)

    def test_nested_thresholds(self):
        """Test nested sell thresholds."""
        config = TradingConfig(
            sell_thresholds=SellThresholds(
                stop_loss_percent=-20.0,
                take_profit_percent=40.0,
            )
        )
        assert config.sell_thresholds.stop_loss_percent == -20.0
        assert config.sell_thresholds.take_profit_percent == 40.0


class TestMarketFiltersConfig:
    """Tests for MarketFiltersConfig model."""

    def test_default_values(self):
        """Test default market filter values."""
        config = MarketFiltersConfig()
        assert config.min_volume == 1000
        assert config.max_time_to_resolution_hours == 1.0
        assert config.min_liquidity == 500
        assert "sports" in config.excluded_categories
        assert "entertainment" in config.excluded_categories
        assert config.min_price == 0.05
        assert config.max_price == 0.95

    def test_custom_categories(self):
        """Test custom excluded categories."""
        config = MarketFiltersConfig(
            excluded_categories=["crypto", "politics"],
        )
        assert "crypto" in config.excluded_categories
        assert "politics" in config.excluded_categories
        assert "sports" not in config.excluded_categories


class TestAIConfig:
    """Tests for AIConfig model."""

    def test_default_values(self):
        """Test default AI configuration."""
        config = AIConfig()
        assert config.model == "gemini-1.5-pro"
        assert config.max_suggestions == 5
        assert config.confidence_threshold == 0.7
        assert config.temperature == 0.3
        assert config.max_tokens == 2048

    def test_custom_model(self):
        """Test custom model configuration."""
        config = AIConfig(
            model="gemini-1.5-flash",
            temperature=0.5,
        )
        assert config.model == "gemini-1.5-flash"
        assert config.temperature == 0.5


class TestSettings:
    """Tests for main Settings class."""

    def test_default_values(self):
        """Test default settings values."""
        # Clear environment variables to test actual defaults
        env_backup = {}
        for key in ["ENVIRONMENT", "GCP_PROJECT_ID"]:
            if key in os.environ:
                env_backup[key] = os.environ.pop(key)
        
        try:
            reset_settings()
            settings = Settings()
            assert settings.environment == "development"
            assert settings.gcp_project_id == ""
            assert settings.real_money_enabled is False
            assert settings.fake_money_enabled is True
        finally:
            # Restore environment variables
            os.environ.update(env_backup)

    def test_environment_validation_valid(self):
        """Test valid environment values."""
        for env in ["development", "staging", "production", "test"]:
            settings = Settings(environment=env)
            assert settings.environment == env

    def test_environment_validation_invalid(self):
        """Test invalid environment value."""
        with pytest.raises(ValueError) as exc_info:
            Settings(environment="invalid")
        assert "must be one of" in str(exc_info.value)

    def test_is_production(self):
        """Test is_production property."""
        settings = Settings(environment="production")
        assert settings.is_production is True

        settings = Settings(environment="development")
        assert settings.is_production is False

    def test_is_test(self):
        """Test is_test property."""
        settings = Settings(environment="test")
        assert settings.is_test is True

        settings = Settings(environment="development")
        assert settings.is_test is False

    def test_get_active_mode_real(self):
        """Test get_active_mode returns real when enabled."""
        settings = Settings(real_money_enabled=True, fake_money_enabled=False)
        assert settings.get_active_mode() == "real"

    def test_get_active_mode_fake(self):
        """Test get_active_mode returns fake when enabled."""
        settings = Settings(real_money_enabled=False, fake_money_enabled=True)
        assert settings.get_active_mode() == "fake"

    def test_get_active_mode_none(self):
        """Test get_active_mode returns none when nothing enabled."""
        settings = Settings(real_money_enabled=False, fake_money_enabled=False)
        assert settings.get_active_mode() == "none"

    def test_get_active_mode_real_priority(self):
        """Test real mode takes priority when both enabled."""
        settings = Settings(real_money_enabled=True, fake_money_enabled=True)
        assert settings.get_active_mode() == "real"


class TestFlattenDict:
    """Tests for flatten_dict function."""

    def test_flat_dict(self):
        """Test already flat dictionary."""
        d = {"a": 1, "b": 2}
        result = flatten_dict(d)
        assert result == {"a": 1, "b": 2}

    def test_nested_dict(self):
        """Test nested dictionary."""
        d = {"level1": {"level2": {"value": 42}}}
        result = flatten_dict(d)
        assert result == {"level1__level2__value": 42}

    def test_mixed_dict(self):
        """Test mixed flat and nested dictionary."""
        d = {"flat": "value", "nested": {"key": "nested_value"}}
        result = flatten_dict(d)
        assert result == {
            "flat": "value",
            "nested__key": "nested_value",
        }

    def test_custom_separator(self):
        """Test custom separator."""
        d = {"a": {"b": 1}}
        result = flatten_dict(d, sep=".")
        assert result == {"a.b": 1}


class TestLoadYamlConfig:
    """Tests for load_yaml_config function."""

    def test_missing_file(self):
        """Test loading non-existent file."""
        result = load_yaml_config(Path("/nonexistent/config.yaml"))
        assert result == {}

    def test_valid_yaml(self, tmp_path):
        """Test loading valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_data = {"trading": {"max_bet_amount": 100.0}}
        config_file.write_text(yaml.dump(config_data))

        result = load_yaml_config(config_file)
        assert result == config_data

    def test_empty_yaml(self, tmp_path):
        """Test loading empty YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        result = load_yaml_config(config_file)
        assert result == {}


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_settings_instance(self):
        """Test that get_settings returns Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_caching(self):
        """Test that settings are cached."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reset_clears_cache(self):
        """Test that reset_settings clears cache."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()
        # Different instances after reset
        assert settings1 is not settings2

    def test_environment_override(self):
        """Test environment variable overrides."""
        os.environ["ENVIRONMENT"] = "test"
        os.environ["GCP_PROJECT_ID"] = "test-project"

        reset_settings()
        settings = get_settings()

        assert settings.environment == "test"
        assert settings.gcp_project_id == "test-project"
