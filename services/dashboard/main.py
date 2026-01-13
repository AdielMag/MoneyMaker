"""
Dashboard Service - Web UI for MoneyMaker fake trading data.

Serves a static dashboard that fetches data from the orchestrator API.
"""

import os
import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

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
        "orchestrator_url": "",  # Empty string means use relative URLs
    })


# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the main dashboard page."""
    html_path = os.path.join(static_dir, "index.html")
    logger.info(f"Serving dashboard from: {html_path}")
    logger.info(f"Static directory: {static_dir}")
    logger.info(f"File exists: {os.path.exists(html_path)}")
    
    if not os.path.exists(html_path):
        logger.error(f"HTML file not found at {html_path}")
        return JSONResponse(
            status_code=404,
            content={"error": f"HTML file not found at {html_path}"}
        )
    return FileResponse(
        html_path,
        media_type="text/html"
    )


# Proxy all API requests to orchestrator (must be last to catch remaining routes)
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_to_orchestrator(path: str, request: Request):
    """Proxy requests to the orchestrator service."""
    # Skip proxy for dashboard-specific routes - these should be handled by other routes above
    excluded_paths = ["", "health", "config"]
    if path in excluded_paths or path.startswith("static/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    
    # Build the full URL to the orchestrator
    url = f"{ORCHESTRATOR_URL}/{path}"
    
    # Forward query parameters
    if request.url.query:
        url += f"?{request.url.query}"
    
    # Forward the request
    async with httpx.AsyncClient() as client:
        try:
            # Get request body if present
            body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
            
            # Forward headers (excluding host and connection)
            headers = dict(request.headers)
            headers.pop("host", None)
            headers.pop("connection", None)
            
            # Make the request
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                timeout=30.0
            )
            
            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
        except httpx.RequestError as e:
            return JSONResponse(
                status_code=502,
                content={"error": f"Failed to connect to orchestrator: {str(e)}"}
            )
