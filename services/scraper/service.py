"""
Scraper service implementation.

Coordinates market fetching and filtering.
"""

import os
from pathlib import Path
from typing import Any

import structlog

from services.scraper.filters import MarketFilter
from shared.config import Settings, get_settings
from shared.models import Market
from shared.polymarket_client import PolymarketClient

def _get_debug_log_path() -> str:
    """Get path to debug log file that works in both Docker and local."""
    project_root = Path(__file__).parent.parent.parent
    cursor_log = project_root / ".cursor" / "debug.log"
    cursor_log.parent.mkdir(exist_ok=True)
    return str(cursor_log)

logger = structlog.get_logger(__name__)


class ScraperService:
    """
    Service for scraping and filtering Polymarket markets.

    Combines Polymarket API access with filtering logic to
    identify tradeable market opportunities.
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient | None = None,
        market_filter: MarketFilter | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize scraper service.

        Args:
            polymarket_client: Optional Polymarket client instance
            market_filter: Optional MarketFilter instance
            settings: Optional Settings instance
        """
        self.settings = settings or get_settings()
        self._polymarket_client = polymarket_client
        self._market_filter = market_filter or MarketFilter(self.settings)

    @property
    def polymarket_client(self) -> PolymarketClient:
        """Get or create Polymarket client."""
        if self._polymarket_client is None:
            self._polymarket_client = PolymarketClient(self.settings)
        return self._polymarket_client

    @property
    def market_filter(self) -> MarketFilter:
        """Get market filter."""
        return self._market_filter

    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        parallel: bool = False,
    ) -> list[Market]:
        """
        Fetch markets from Polymarket.

        Args:
            limit: Maximum number of markets to fetch
            offset: Pagination offset
            parallel: Use parallel fetching for large requests

        Returns:
            List of Market objects
        """
        logger.info("fetching_markets", limit=limit, offset=offset, parallel=parallel)

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"scraper/service.py:74","message":"get_markets entry","data":{"limit":limit,"offset":offset,"parallel":parallel},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        async with self.polymarket_client as client:
            if parallel and limit > 100:
                # Use parallel fetching for large requests
                markets = await client.get_markets_parallel(
                    active_only=True,
                )
                # Apply limit after fetching (since parallel fetch gets all available)
                markets = markets[:limit]
                # #region agent log
                import json, time
                try:
                    with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"scraper/service.py:83","message":"Parallel fetch complete","data":{"markets_count":len(markets),"limit":limit},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion
            else:
                markets = await client.get_markets(
                    active_only=True,
                    limit=limit,
                    offset=offset,
                )
                # #region agent log
                import json, time
                try:
                    with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"scraper/service.py:91","message":"Regular fetch complete","data":{"markets_count":len(markets),"limit":limit,"offset":offset},"timestamp":int(time.time()*1000)})+"\n")
                except: pass
                # #endregion

        logger.info("markets_fetched", count=len(markets))
        return markets

    async def get_filtered_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        parallel: bool = True,
    ) -> tuple[list[Market], dict[str, Any]]:
        """
        Fetch and filter markets.

        Args:
            limit: Maximum markets to fetch
            offset: Pagination offset
            parallel: Use parallel fetching for faster loading

        Returns:
            Tuple of (filtered markets, filter summary)
        """
        # Fetch markets (use parallel for large fetches)
        markets = await self.get_markets(limit=limit, offset=offset, parallel=parallel)

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/service.py:112","message":"Before filtering","data":{"markets_count":len(markets)},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        if not markets:
            # #region agent log
            import json, time
            try:
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"scraper/service.py:115","message":"No markets fetched - returning empty","data":{},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return [], {"total_markets": 0, "passed": 0, "filtered_out": 0}

        # Apply filters
        filtered, results = self.market_filter.filter_markets(markets)
        summary = self.market_filter.get_filter_summary(results)

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/service.py:118","message":"After filtering","data":{"total":summary["total_markets"],"passed":summary["passed"],"filtered_out":summary["filtered_out"],"failure_reasons":summary.get("failure_reasons",{})},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        logger.info(
            "markets_filtered",
            total=summary["total_markets"],
            passed=summary["passed"],
            filtered_out=summary["filtered_out"],
        )

        return filtered, summary

    async def get_market(self, market_id: str) -> Market | None:
        """
        Fetch a single market by ID.

        Args:
            market_id: Market condition ID

        Returns:
            Market object or None if not found
        """
        async with self.polymarket_client as client:
            return await client.get_market(market_id)

    async def get_tradeable_markets(
        self,
        max_markets: int = 50,
    ) -> list[Market]:
        """
        Get markets that are ready for trading.

        Fetches, filters, and returns markets sorted by opportunity.

        Args:
            max_markets: Maximum markets to return

        Returns:
            List of tradeable markets
        """
        # Fetch plenty of markets - Polymarket has thousands
        fetch_limit = 500

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/service.py:159","message":"get_tradeable_markets entry","data":{"fetch_limit":fetch_limit,"max_markets":max_markets},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        filtered, _ = await self.get_filtered_markets(limit=fetch_limit)

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/service.py:161","message":"Filtered markets received","data":{"filtered_count":len(filtered)},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        # Sort by volume (most active first)
        sorted_markets = sorted(
            filtered,
            key=lambda m: m.volume,
            reverse=True,
        )

        result = sorted_markets[:max_markets]

        # #region agent log
        import json, time
        try:
            with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"scraper/service.py:170","message":"get_tradeable_markets exit","data":{"returned_count":len(result)},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion

        return result

    def apply_custom_filter(
        self,
        markets: list[Market],
        category: str | None = None,
        min_volume: int | None = None,
        max_time_hours: float | None = None,
    ) -> list[Market]:
        """
        Apply custom filters to a list of markets.

        Useful for API queries with specific requirements.

        Args:
            markets: Markets to filter
            category: Filter by category (None = all)
            min_volume: Minimum volume override
            max_time_hours: Max time to resolution override

        Returns:
            Filtered markets
        """
        result = markets

        if category:
            result = [m for m in result if m.category.lower() == category.lower()]

        if min_volume is not None:
            result = [m for m in result if m.volume >= min_volume]

        if max_time_hours is not None:
            result = [m for m in result if m.compute_time_to_resolution() <= max_time_hours]

        return result


# Factory function
def get_scraper_service() -> ScraperService:
    """Create and return a ScraperService instance."""
    return ScraperService()
