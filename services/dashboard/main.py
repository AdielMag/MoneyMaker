"""
Dashboard Service - Web UI for MoneyMaker fake trading data.

Serves a static dashboard that fetches data from the orchestrator API.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="MoneyMaker Dashboard",
    description="Web dashboard for viewing fake trading data",
    version="0.1.0",
)

# CORS for API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get orchestrator URL from environment
ORCHESTRATOR_URL = os.getenv(
    "ORCHESTRATOR_URL",
    "http://localhost:8000"
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dashboard"}


@app.get("/config")
async def get_config():
    """Return configuration for the frontend."""
    return JSONResponse({
        "orchestrator_url": ORCHESTRATOR_URL,
    })


# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the main dashboard page."""
    return FileResponse(os.path.join(static_dir, "index.html"))
