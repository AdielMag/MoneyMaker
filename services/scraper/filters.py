"""
Market filtering logic for MoneyMaker.

Applies configurable filters to markets to identify tradeable opportunities.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from shared.config import Settings, get_settings
from shared.models import Market

def _get_debug_log_path() -> str:
    """Get path to debug log file that works in both Docker and local."""
    project_root = Path(__file__).parent.parent.parent
    cursor_log = project_root / ".cursor" / "debug.log"
    cursor_log.parent.mkdir(exist_ok=True)
    return str(cursor_log)

logger = structlog.get_logger(__name__)


@dataclass
class FilterResult:
    """Result of filtering a market."""

    passed: bool
    market: Market
    reason: str | None = None

    def __str__(self) -> str:
        if self.passed:
            return f"PASS: {self.market.id}"
        return f"FAIL: {self.market.id} - {self.reason}"


class MarketFilter:
    """
    Filters markets based on configurable criteria.

    Criteria include:
    - Time to resolution
    - Trading volume
    - Liquidity
    - Category exclusions
    - Price range (avoid extreme probabilities)
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize market filter.

        Args:
            settings: Settings instance. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self.config = self.settings.market_filters

    def filter_market(self, market: Market) -> FilterResult:
        """
        Apply all filters to a single market.

        Args:
            market: Market to filter

        Returns:
            FilterResult indicating pass/fail and reason
        """
        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:62","message":"filter_market entry","data":{"market_id":market.id[:30] if market.id else "unknown","volume":market.volume,"liquidity":market.liquidity,"category":market.category,"outcomes_count":len(market.outcomes) if market.outcomes else 0},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        # Check time to resolution
        time_check = self._check_time_to_resolution(market)
        if not time_check.passed:
            # #region agent log
            try:
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:74","message":"Time check failed","data":{"market_id":market.id[:30] if market.id else "unknown","reason":time_check.reason},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return time_check

        # Check volume
        volume_check = self._check_volume(market)
        if not volume_check.passed:
            # #region agent log
            try:
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:79","message":"Volume check failed","data":{"market_id":market.id[:30] if market.id else "unknown","volume":market.volume,"min_volume":self.config.min_volume,"reason":volume_check.reason},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return volume_check

        # Check liquidity
        liquidity_check = self._check_liquidity(market)
        if not liquidity_check.passed:
            # #region agent log
            try:
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:84","message":"Liquidity check failed","data":{"market_id":market.id[:30] if market.id else "unknown","liquidity":market.liquidity,"min_liquidity":self.config.min_liquidity,"reason":liquidity_check.reason},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return liquidity_check

        # Check category
        category_check = self._check_category(market)
        if not category_check.passed:
            # #region agent log
            try:
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:89","message":"Category check failed","data":{"market_id":market.id[:30] if market.id else "unknown","category":market.category,"excluded":self.config.excluded_categories,"reason":category_check.reason},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return category_check

        # Check price range
        price_check = self._check_price_range(market)
        if not price_check.passed:
            # #region agent log
            try:
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:94","message":"Price check failed","data":{"market_id":market.id[:30] if market.id else "unknown","outcomes":[{o.name:o.price for o in market.outcomes}],"min_price":self.config.min_price,"max_price":self.config.max_price,"reason":price_check.reason},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return price_check

        # All checks passed
        market.passes_filter = True
        market.filter_reason = None

        # #region agent log
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:101","message":"All checks passed","data":{"market_id":market.id[:30] if market.id else "unknown"},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        return FilterResult(passed=True, market=market)

    def filter_markets(self, markets: list[Market]) -> tuple[list[Market], list[FilterResult]]:
        """
        Apply filters to multiple markets.

        Args:
            markets: List of markets to filter

        Returns:
            Tuple of (passing markets, all filter results)
        """
        results = []
        passing = []
        reason_counts = {}

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:95","message":"filter_markets entry","data":{"markets_count":len(markets),"config":{"min_volume":self.config.min_volume,"max_time_hours":self.config.max_time_to_resolution_hours,"min_liquidity":self.config.min_liquidity,"excluded_categories":self.config.excluded_categories}},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        for market in markets:
            result = self.filter_market(market)
            results.append(result)

            if result.passed:
                passing.append(result.market)
            else:
                reason = result.reason or "Unknown"
                reason_key = reason.split("(")[0].strip()
                reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1
                logger.debug(
                    "market_filtered_out",
                    market_id=market.id,
                    reason=result.reason,
                )

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:127","message":"filter_markets complete","data":{"total":len(markets),"passed":len(passing),"filtered_out":len(markets)-len(passing),"reason_counts":reason_counts},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        logger.info(
            "markets_filtered",
            total=len(markets),
            passed=len(passing),
            filtered_out=len(markets) - len(passing),
        )

        return passing, results

    def _check_time_to_resolution(self, market: Market) -> FilterResult:
        """Check if market resolves within allowed timeframe."""
        time_to_resolution = market.compute_time_to_resolution()
        market.time_to_resolution_hours = time_to_resolution

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/filters.py:132","message":"Time check for market","data":{"market_id":market.id[:20] if market.id else "unknown","time_to_resolution":time_to_resolution,"end_date":str(market.end_date) if market.end_date else "none","max_hours":self.config.max_time_to_resolution_hours},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        # Filter out markets that have already ended
        if time_to_resolution <= 0:
            market.passes_filter = False
            market.filter_reason = "Market has already ended"
            return FilterResult(
                passed=False,
                market=market,
                reason="Market has already ended",
            )

        # Filter out markets that resolve too far in the future
        max_hours = self.config.max_time_to_resolution_hours
        if time_to_resolution > max_hours:
            market.passes_filter = False
            market.filter_reason = (
                f"Time to resolution ({time_to_resolution:.1f}h) exceeds maximum ({max_hours}h)"
            )
            return FilterResult(
                passed=False,
                market=market,
                reason=f"Time to resolution ({time_to_resolution:.1f}h) exceeds maximum ({max_hours}h)",
            )

        # Filter out markets that resolve too soon (< 5 minutes)
        min_hours = 5 / 60  # 5 minutes
        if time_to_resolution < min_hours:
            market.passes_filter = False
            market.filter_reason = (
                f"Market resolves too soon ({time_to_resolution * 60:.0f} minutes)"
            )
            return FilterResult(
                passed=False,
                market=market,
                reason=f"Market resolves too soon ({time_to_resolution * 60:.0f} minutes)",
            )

        return FilterResult(passed=True, market=market)

    def _check_volume(self, market: Market) -> FilterResult:
        """Check if market has sufficient trading volume."""
        min_volume = self.config.min_volume

        if market.volume < min_volume:
            market.passes_filter = False
            market.filter_reason = (
                f"Volume (${market.volume:,.0f}) below minimum (${min_volume:,.0f})"
            )
            return FilterResult(
                passed=False,
                market=market,
                reason=f"Volume (${market.volume:,.0f}) below minimum (${min_volume:,.0f})",
            )

        return FilterResult(passed=True, market=market)

    def _check_liquidity(self, market: Market) -> FilterResult:
        """Check if market has sufficient liquidity."""
        min_liquidity = self.config.min_liquidity

        if market.liquidity < min_liquidity:
            market.passes_filter = False
            market.filter_reason = (
                f"Liquidity (${market.liquidity:,.0f}) below minimum (${min_liquidity:,.0f})"
            )
            return FilterResult(
                passed=False,
                market=market,
                reason=f"Liquidity (${market.liquidity:,.0f}) below minimum (${min_liquidity:,.0f})",
            )

        return FilterResult(passed=True, market=market)

    def _check_category(self, market: Market) -> FilterResult:
        """Check if market category is allowed."""
        excluded = self.config.excluded_categories

        if market.category.lower() in [c.lower() for c in excluded]:
            market.passes_filter = False
            market.filter_reason = f"Category '{market.category}' is excluded"
            return FilterResult(
                passed=False,
                market=market,
                reason=f"Category '{market.category}' is excluded",
            )

        return FilterResult(passed=True, market=market)

    def _check_price_range(self, market: Market) -> FilterResult:
        """Check if market prices are within tradeable range."""
        min_price = self.config.min_price
        max_price = self.config.max_price

        for outcome in market.outcomes:
            # Skip if price is too extreme (too close to 0 or 1)
            if outcome.price < min_price or outcome.price > max_price:
                continue
            # At least one outcome has a reasonable price
            return FilterResult(passed=True, market=market)

        # All outcomes have extreme prices
        market.passes_filter = False
        market.filter_reason = (
            f"All outcome prices are extreme (outside {min_price:.0%}-{max_price:.0%})"
        )
        return FilterResult(
            passed=False,
            market=market,
            reason=f"All outcome prices are extreme (outside {min_price:.0%}-{max_price:.0%})",
        )

    def get_filter_summary(self, results: list[FilterResult]) -> dict[str, Any]:
        """
        Generate a summary of filter results.

        Args:
            results: List of filter results

        Returns:
            Summary dictionary with statistics
        """
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]

        # Count failure reasons
        reason_counts: dict[str, int] = {}
        for result in failed:
            reason_key = result.reason.split("(")[0].strip() if result.reason else "Unknown"
            reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1

        return {
            "total_markets": len(results),
            "passed": len(passed),
            "filtered_out": len(failed),
            "pass_rate": len(passed) / len(results) * 100 if results else 0,
            "failure_reasons": reason_counts,
        }
