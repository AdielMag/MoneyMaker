"""
Initialize Firestore with default data for MoneyMaker.

Usage:
    python scripts/init_firestore.py

This script creates:
- Default wallet with initial balance
- Workflow states for discovery and monitor workflows
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.firestore_client import FirestoreClient
from shared.models import TradingMode, WorkflowState


async def init_wallet(client: FirestoreClient, initial_balance: float = 1000.0) -> None:
    """Initialize default wallet."""
    print(f"Creating default wallet with ${initial_balance} balance...")
    
    existing = await client.get_wallet("default")
    if existing:
        print(f"  Wallet already exists with ${existing.balance} balance")
        response = input("  Reset to initial balance? (y/N): ")
        if response.lower() == 'y':
            wallet = await client.update_wallet_balance("default", initial_balance)
            print(f"  Wallet reset to ${wallet.balance}")
        else:
            print("  Skipping wallet reset")
    else:
        wallet = await client.create_wallet("default", initial_balance)
        print(f"  Created wallet: {wallet.wallet_id} with ${wallet.balance}")


async def init_workflow_states(client: FirestoreClient) -> None:
    """Initialize workflow states."""
    print("\nInitializing workflow states...")
    
    workflows = ["discovery", "monitor"]
    modes = [TradingMode.FAKE, TradingMode.REAL]
    
    for workflow_id in workflows:
        for mode in modes:
            # Check if state exists
            existing = await client.get_workflow_state(workflow_id, mode)
            
            if existing:
                print(f"  {workflow_id}/{mode.value}: exists (enabled={existing.enabled}, runs={existing.run_count})")
            else:
                # Create new state - only enable fake mode by default
                state = WorkflowState(
                    workflow_id=workflow_id,
                    mode=mode,
                    enabled=(mode == TradingMode.FAKE),
                )
                await client.update_workflow_state(state)
                print(f"  {workflow_id}/{mode.value}: created (enabled={state.enabled})")


async def verify_connection(client: FirestoreClient) -> bool:
    """Verify Firestore connection."""
    print("Verifying Firestore connection...")
    try:
        # Try to read from a collection (use a valid test ID, not reserved __ prefix)
        await client.get_wallet("connection-test")
        print("  Connection successful!")
        return True
    except Exception as e:
        error_msg = str(e)
        # "not found" errors mean connection works, document just doesn't exist
        if "not found" in error_msg.lower() or "Failed to get wallet" in error_msg:
            print("  Connection successful!")
            return True
        print(f"  Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure GCP_PROJECT_ID is set correctly")
        print("  2. Ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid service account key")
        print("  3. Ensure the service account has Firestore access")
        return False


async def main() -> None:
    """Main initialization function."""
    print("=" * 60)
    print("MoneyMaker Firestore Initialization")
    print("=" * 60)
    print()
    
    # Check environment
    project_id = os.environ.get("GCP_PROJECT_ID")
    credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    
    print(f"Project ID: {project_id or 'NOT SET'}")
    print(f"Credentials: {credentials or 'NOT SET'}")
    print()
    
    if not project_id:
        print("ERROR: GCP_PROJECT_ID environment variable not set")
        if sys.platform == "win32":
            print('Run: $env:GCP_PROJECT_ID = "your-project-id"')
        else:
            print("Run: export GCP_PROJECT_ID=your-project-id")
        sys.exit(1)
    
    client = FirestoreClient()
    
    # Verify connection
    if not await verify_connection(client):
        sys.exit(1)
    
    print()
    
    # Initialize wallet
    await init_wallet(client)
    
    # Initialize workflow states
    await init_workflow_states(client)
    
    print()
    print("=" * 60)
    print("Initialization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Start the orchestrator: uvicorn services.orchestrator.main:app --reload")
    print("  2. Check system status: curl http://localhost:8000/status")
    print("  3. Trigger discovery: curl -X POST http://localhost:8000/workflow/discover -H 'Content-Type: application/json' -d '{\"mode\": \"fake\"}'")


if __name__ == "__main__":
    asyncio.run(main())
