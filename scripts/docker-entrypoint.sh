#!/bin/bash
set -e

# Start with debugpy if enabled
if [ "$DEBUGPY_ENABLED" = "true" ]; then
    echo "Debug mode enabled. Starting with debugpy on port 5678..."
    if [ "$DEBUGPY_WAIT_FOR_ATTACH" = "true" ]; then
        echo "Waiting for debugger to attach..."
        python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m uvicorn "$@" --host 0.0.0.0 --port ${PORT:-8080}
    else
        python -m debugpy --listen 0.0.0.0:5678 -m uvicorn "$@" --host 0.0.0.0 --port ${PORT:-8080}
    fi
else
    # Normal startup
    exec uvicorn "$@" --host 0.0.0.0 --port ${PORT:-8080}
fi
