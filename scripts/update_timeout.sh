#!/bin/bash
# Script to update Cloud Run service timeout
# Usage: ./scripts/update_timeout.sh [service_name]
# Example: ./scripts/update_timeout.sh orchestrator

set -e

SERVICE=${1:-"orchestrator"}
REGION=${REGION:-"us-central1"}

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: PROJECT_ID environment variable not set"
    echo "Run: export PROJECT_ID=your-project-id"
    exit 1
fi

CLOUD_RUN_NAME="moneymaker-${SERVICE//_/-}"

echo "Updating timeout for $CLOUD_RUN_NAME..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

gcloud run services update $CLOUD_RUN_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --timeout=900 \
    --quiet

echo ""
echo "✅ Timeout updated to 900 seconds (15 minutes)"
echo ""
echo "Verify with:"
echo "  gcloud run services describe $CLOUD_RUN_NAME --region=$REGION --format='value(spec.template.spec.timeoutSeconds)'"
