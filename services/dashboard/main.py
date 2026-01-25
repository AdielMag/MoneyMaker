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
    # Check orchestrator connectivity
    orchestrator_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health", timeout=2.0)
            if response.status_code == 200:
                orchestrator_status = "connected"
            else:
                orchestrator_status = "unhealthy"
    except Exception as e:
        orchestrator_status = f"disconnected: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "dashboard",
        "orchestrator_url": ORCHESTRATOR_URL,
        "orchestrator_status": orchestrator_status
    }


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


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "127.0.0.1")

    print("Starting MoneyMaker Dashboard...")
    print(f"Dashboard URL: http://{host}:{port}")
    print(f"Orchestrator URL: {ORCHESTRATOR_URL}")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
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
    
    # Determine timeout based on endpoint
    # Endpoints that might take longer (scraping, workflows) get extended timeout
    slow_endpoints = ["markets", "workflow"]
    is_slow_endpoint = any(slow in path.lower() for slow in slow_endpoints)
    
    # Use longer timeout for slow endpoints (60s) vs normal endpoints (30s)
    # Cloud Run default timeout is 300s, so we have room
    timeout_seconds = 60.0 if is_slow_endpoint else 30.0
    
    # Use httpx.Timeout with separate connect, read, write timeouts
    timeout = httpx.Timeout(
        connect=10.0,  # Connection timeout
        read=timeout_seconds,  # Read timeout (time to wait for response)
        write=10.0,  # Write timeout
        pool=5.0  # Pool timeout
    )
    
    # Forward the request
    async with httpx.AsyncClient(timeout=timeout) as client:
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
            )
            
            # Handle 503 Service Unavailable with better error message
            if response.status_code == 503:
                logger.warning(
                    f"Orchestrator returned 503 Service Unavailable for {path} "
                    f"(method={request.method}, orchestrator_url={ORCHESTRATOR_URL})"
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Orchestrator service is temporarily unavailable",
                        "message": "The remote orchestrator service returned a 503 error. This may indicate: "
                                  "the service is restarting/scaling, the request exceeded Cloud Run's timeout limit, "
                                  "or the service is temporarily overloaded.",
                        "orchestrator_url": ORCHESTRATOR_URL,
                        "path": path,
                        "suggestion": "Please try again in a few moments. If this is a timeout issue, try reducing the request size "
                                     "(e.g., lower limit for markets). If the issue persists, check the orchestrator service status in GCP."
                    }
                )
            
            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
        except httpx.TimeoutException as e:
            logger.warning(
                f"Request to orchestrator timed out for {path} "
                f"(timeout={timeout_seconds}s, method={request.method}, orchestrator_url={ORCHESTRATOR_URL})"
            )
            return JSONResponse(
                status_code=504,  # Gateway Timeout
                content={
                    "error": "Request to orchestrator timed out",
                    "message": f"The request to the orchestrator took longer than {timeout_seconds} seconds to complete. "
                              f"This may happen if the orchestrator is processing a large request or is under heavy load.",
                    "orchestrator_url": ORCHESTRATOR_URL,
                    "path": path,
                    "timeout_seconds": timeout_seconds,
                    "suggestion": "Try again in a few moments, or reduce the request size (e.g., lower limit for markets)."
                }
            )
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to orchestrator at {ORCHESTRATOR_URL}"
            if "Connection refused" in str(e) or "Name or service not known" in str(e):
                error_msg += ". Is the orchestrator running?"
            elif "timeout" in str(e).lower():
                error_msg += ". Request timed out."
            else:
                error_msg += f": {str(e)}"
            
            logger.error(
                f"Request error to orchestrator for {path}: {error_msg}",
                exc_info=True
            )
            
            return JSONResponse(
                status_code=502,
                content={
                    "error": error_msg,
                    "orchestrator_url": ORCHESTRATOR_URL,
                    "path": path,
                    "detail": str(e)
                }
            )
