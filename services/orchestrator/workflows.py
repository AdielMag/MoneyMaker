"""
Trading workflow implementations.

Defines the core trading workflows: discovery and monitoring.
"""

from datetime import datetime
from typing import Any

import structlog

from shared.config import Settings, get_settings
from shared.models import TradingMode, WorkflowRunResult
from services.scraper.service import ScraperService, get_scraper_service
from services.ai_suggester.service import AISuggesterService, get_ai_suggester_service
from services.trader.service import TraderService, get_trader_service
from services.monitor.service import MonitorService, get_monitor_service

logger = structlog.get_logger(__name__)


class DiscoveryWorkflow:
    """
    Market discovery and betting workflow.
    
    1. Check if funds are available
    2. Scrape and filter markets
    3. Analyze with AI
    4. Place buy orders for top suggestions
    """
    
    def __init__(
        self,
        scraper_service: ScraperService | None = None,
        ai_service: AISuggesterService | None = None,
        trader_service: TraderService | None = None,
        settings: Settings | None = None,
    ):
        """Initialize workflow with services."""
        self.settings = settings or get_settings()
        self.scraper = scraper_service or get_scraper_service()
        self.ai = ai_service or get_ai_suggester_service()
        self.trader = trader_service or get_trader_service()
    
    async def run(self, mode: TradingMode) -> WorkflowRunResult:
        """
        Execute the discovery workflow.
        
        Args:
            mode: Trading mode (real or fake)
            
        Returns:
            WorkflowRunResult with execution details
        """
        started_at = datetime.utcnow()
        errors: list[str] = []
        markets_analyzed = 0
        suggestions_generated = 0
        orders_placed = 0
        
        logger.info("discovery_workflow_started", mode=mode.value)
        
        try:
            # Step 1: Check if we can trade
            min_balance = self.settings.trading.min_balance_to_trade
            can_trade, reason = await self.trader.can_trade(mode, min_balance)
            
            if not can_trade:
                logger.info("cannot_trade", reason=reason)
                return WorkflowRunResult(
                    workflow_id="discovery",
                    mode=mode,
                    success=False,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    errors=[reason],
                )
            
            # Step 2: Get tradeable markets
            markets = await self.scraper.get_tradeable_markets(
                max_markets=self.settings.ai.max_suggestions * 3,
            )
            markets_analyzed = len(markets)
            
            if not markets:
                logger.info("no_markets_found")
                return WorkflowRunResult(
                    workflow_id="discovery",
                    mode=mode,
                    success=True,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    markets_analyzed=0,
                )
            
            # Step 3: Get AI suggestions
            analysis = await self.ai.analyze_markets(markets)
            suggestions = analysis.get_top_suggestions(self.settings.ai.max_suggestions)
            suggestions_generated = len(suggestions)
            
            if not suggestions:
                logger.info("no_suggestions_generated")
                return WorkflowRunResult(
                    workflow_id="discovery",
                    mode=mode,
                    success=True,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    markets_analyzed=markets_analyzed,
                    suggestions_generated=0,
                )
            
            # Step 4: Execute top suggestions
            balance = await self.trader.get_balance(mode)
            max_orders = self.settings.trading.max_positions
            
            for suggestion in suggestions[:max_orders]:
                should_trade, reason, position_size = await self.ai.should_trade(
                    suggestion=suggestion,
                    wallet_balance=balance,
                )
                
                if not should_trade:
                    logger.debug("suggestion_skipped", reason=reason)
                    continue
                
                try:
                    order = await self.trader.execute_suggestion(
                        suggestion=suggestion,
                        position_size=position_size,
                        mode=mode,
                    )
                    
                    if order.status.value in ["filled", "pending"]:
                        orders_placed += 1
                        balance -= position_size
                        
                except Exception as e:
                    error_msg = f"Order failed for {suggestion.market_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error("order_failed", error=str(e))
            
            success = orders_placed > 0 or not suggestions
            
        except Exception as e:
            errors.append(str(e))
            logger.error("discovery_workflow_error", error=str(e))
            success = False
        
        result = WorkflowRunResult(
            workflow_id="discovery",
            mode=mode,
            success=success,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            markets_analyzed=markets_analyzed,
            suggestions_generated=suggestions_generated,
            orders_placed=orders_placed,
            errors=errors,
        )
        
        logger.info(
            "discovery_workflow_completed",
            success=success,
            markets=markets_analyzed,
            suggestions=suggestions_generated,
            orders=orders_placed,
        )
        
        return result


class MonitorWorkflow:
    """
    Position monitoring workflow.
    
    1. Get open positions
    2. Update prices
    3. Check thresholds
    4. Execute sells as needed
    """
    
    def __init__(
        self,
        monitor_service: MonitorService | None = None,
        settings: Settings | None = None,
    ):
        """Initialize workflow with services."""
        self.settings = settings or get_settings()
        self.monitor = monitor_service or get_monitor_service()
    
    async def run(self, mode: TradingMode) -> WorkflowRunResult:
        """
        Execute the monitoring workflow.
        
        Args:
            mode: Trading mode (real or fake)
            
        Returns:
            WorkflowRunResult with execution details
        """
        started_at = datetime.utcnow()
        errors: list[str] = []
        
        logger.info("monitor_workflow_started", mode=mode.value)
        
        try:
            results = await self.monitor.monitor_positions(mode)
            
            errors = results.get("errors", [])
            sells_triggered = results.get("sells_triggered", 0)
            positions_checked = results.get("positions_checked", 0)
            
            success = len(errors) == 0 or sells_triggered > 0
            
        except Exception as e:
            errors.append(str(e))
            logger.error("monitor_workflow_error", error=str(e))
            success = False
            sells_triggered = 0
            positions_checked = 0
        
        result = WorkflowRunResult(
            workflow_id="monitor",
            mode=mode,
            success=success,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            markets_analyzed=positions_checked,
            orders_placed=sells_triggered,
            errors=errors,
        )
        
        logger.info(
            "monitor_workflow_completed",
            success=success,
            positions_checked=positions_checked,
            sells_triggered=sells_triggered,
        )
        
        return result
