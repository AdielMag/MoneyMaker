"""
Orchestrator service implementation.

Coordinates all trading workflows and provides unified API.
"""

from datetime import datetime
from typing import Any

import structlog

from shared.config import Settings, get_settings
from shared.firestore_client import FirestoreClient, get_firestore_client
from shared.models import TradingMode, WorkflowRunResult, WorkflowState
from services.orchestrator.workflows import DiscoveryWorkflow, MonitorWorkflow
from services.scraper.service import ScraperService, get_scraper_service
from services.ai_suggester.service import AISuggesterService, get_ai_suggester_service
from services.trader.service import TraderService, get_trader_service
from services.monitor.service import MonitorService, get_monitor_service

logger = structlog.get_logger(__name__)


class OrchestratorService:
    """
    Main orchestrator service.
    
    Coordinates all trading workflows and provides unified API
    for the entire trading system.
    """
    
    def __init__(
        self,
        scraper_service: ScraperService | None = None,
        ai_service: AISuggesterService | None = None,
        trader_service: TraderService | None = None,
        monitor_service: MonitorService | None = None,
        firestore_client: FirestoreClient | None = None,
        settings: Settings | None = None,
    ):
        """Initialize orchestrator with all services."""
        self.settings = settings or get_settings()
        
        self.scraper = scraper_service or get_scraper_service()
        self.ai = ai_service or get_ai_suggester_service()
        self.trader = trader_service or get_trader_service()
        self.monitor = monitor_service or get_monitor_service()
        self._firestore_client = firestore_client
        
        # Create workflows
        self.discovery_workflow = DiscoveryWorkflow(
            scraper_service=self.scraper,
            ai_service=self.ai,
            trader_service=self.trader,
            settings=self.settings,
        )
        
        self.monitor_workflow = MonitorWorkflow(
            monitor_service=self.monitor,
            settings=self.settings,
        )
    
    @property
    def firestore_client(self) -> FirestoreClient:
        """Get or create Firestore client."""
        if self._firestore_client is None:
            self._firestore_client = get_firestore_client()
        return self._firestore_client
    
    async def run_discovery(self, mode: TradingMode) -> WorkflowRunResult:
        """
        Run the discovery workflow.
        
        Args:
            mode: Trading mode
            
        Returns:
            WorkflowRunResult
        """
        # Update workflow state
        await self._update_workflow_state("discovery", mode, running=True)
        
        try:
            result = await self.discovery_workflow.run(mode)
            
            # Update state with result
            await self._update_workflow_state(
                "discovery", mode,
                running=False,
                last_error=result.errors[0] if result.errors else None,
            )
            
            return result
            
        except Exception as e:
            await self._update_workflow_state(
                "discovery", mode,
                running=False,
                last_error=str(e),
            )
            raise
    
    async def run_monitor(self, mode: TradingMode) -> WorkflowRunResult:
        """
        Run the monitoring workflow.
        
        Args:
            mode: Trading mode
            
        Returns:
            WorkflowRunResult
        """
        # Update workflow state
        await self._update_workflow_state("monitor", mode, running=True)
        
        try:
            result = await self.monitor_workflow.run(mode)
            
            # Update state with result
            await self._update_workflow_state(
                "monitor", mode,
                running=False,
                last_error=result.errors[0] if result.errors else None,
            )
            
            return result
            
        except Exception as e:
            await self._update_workflow_state(
                "monitor", mode,
                running=False,
                last_error=str(e),
            )
            raise
    
    async def _update_workflow_state(
        self,
        workflow_id: str,
        mode: TradingMode,
        running: bool = False,
        last_error: str | None = None,
    ) -> None:
        """Update workflow state in Firestore."""
        try:
            state = await self.firestore_client.get_workflow_state(workflow_id, mode)
            
            if state is None:
                state = WorkflowState(
                    workflow_id=workflow_id,
                    mode=mode,
                    enabled=True,
                )
            
            if running:
                state.last_run = datetime.utcnow()
                state.run_count += 1
            
            state.last_error = last_error
            state.updated_at = datetime.utcnow()
            
            await self.firestore_client.update_workflow_state(state)
            
        except Exception as e:
            logger.warning("update_workflow_state_error", error=str(e))
    
    async def toggle_workflow(
        self,
        workflow_id: str,
        mode: TradingMode,
        enabled: bool,
    ) -> WorkflowState:
        """
        Enable or disable a workflow.
        
        Args:
            workflow_id: Workflow to toggle
            mode: Trading mode
            enabled: New enabled state
            
        Returns:
            Updated WorkflowState
        """
        return await self.firestore_client.toggle_workflow(workflow_id, mode, enabled)
    
    async def get_workflow_state(
        self,
        workflow_id: str,
        mode: TradingMode,
    ) -> WorkflowState | None:
        """Get current state of a workflow."""
        return await self.firestore_client.get_workflow_state(workflow_id, mode)
    
    async def get_balance(self, mode: TradingMode) -> float:
        """Get balance for trading mode."""
        return await self.trader.get_balance(mode)
    
    async def get_positions(self, mode: TradingMode) -> list[dict[str, Any]]:
        """Get open positions for trading mode."""
        positions = await self.monitor.get_positions(mode)
        positions = await self.monitor.update_position_prices(positions)
        return [p.model_dump() for p in positions]
    
    async def get_markets(
        self,
        limit: int = 50,
        filtered: bool = True,
    ) -> list[dict[str, Any]]:
        """Get available markets."""
        if filtered:
            markets, _ = await self.scraper.get_filtered_markets(limit=limit)
        else:
            markets = await self.scraper.get_markets(limit=limit)
        return [m.model_dump() for m in markets]
    
    async def get_system_status(self) -> dict[str, Any]:
        """Get overall system status."""
        try:
            fake_balance = await self.get_balance(TradingMode.FAKE)
        except Exception:
            fake_balance = 0
        
        try:
            real_balance = await self.get_balance(TradingMode.REAL) if self.settings.real_money_enabled else 0
        except Exception:
            real_balance = 0
        
        try:
            fake_positions = await self.monitor.get_positions_summary(TradingMode.FAKE)
        except Exception:
            fake_positions = {"count": 0}
        
        return {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "config": {
                "real_money_enabled": self.settings.real_money_enabled,
                "fake_money_enabled": self.settings.fake_money_enabled,
                "active_mode": self.settings.get_active_mode(),
            },
            "balances": {
                "fake": fake_balance,
                "real": real_balance,
            },
            "positions": {
                "fake": fake_positions,
            },
            "thresholds": {
                "stop_loss": self.settings.trading.sell_thresholds.stop_loss_percent,
                "take_profit": self.settings.trading.sell_thresholds.take_profit_percent,
            },
        }


# Factory function
def get_orchestrator_service() -> OrchestratorService:
    """Create and return an OrchestratorService instance."""
    return OrchestratorService()
