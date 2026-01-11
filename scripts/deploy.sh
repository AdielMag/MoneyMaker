#!/bin/bash
# MoneyMaker Deployment Script
# Usage: ./scripts/deploy.sh [service] [tag]
# Example: ./scripts/deploy.sh orchestrator v1.0.0
# Example: ./scripts/deploy.sh all latest

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE=${1:-"all"}
TAG=${2:-"latest"}

# Check required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: PROJECT_ID environment variable not set${NC}"
    echo "Run: export PROJECT_ID=your-project-id"
    exit 1
fi

if [ -z "$REGION" ]; then
    export REGION="us-central1"
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/moneymaker"
SA_EMAIL="moneymaker-service@${PROJECT_ID}.iam.gserviceaccount.com"

echo "========================================"
echo "MoneyMaker Deployment"
echo "========================================"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE"
echo "Tag: $TAG"
echo "========================================"

# Function to build and deploy a service
deploy_service() {
    local service_name=$1
    local port=$2
    
    echo ""
    echo -e "${YELLOW}Deploying ${service_name}...${NC}"
    
    # Build Docker image
    echo "  Building Docker image..."
    docker build \
        -t ${REGISTRY}/${service_name}:${TAG} \
        -f services/${service_name}/Dockerfile \
        .
    
    # Push to Artifact Registry
    echo "  Pushing to Artifact Registry..."
    docker push ${REGISTRY}/${service_name}:${TAG}
    
    # Deploy to Cloud Run
    echo "  Deploying to Cloud Run..."
    gcloud run deploy moneymaker-${service_name} \
        --image=${REGISTRY}/${service_name}:${TAG} \
        --region=$REGION \
        --platform=managed \
        --service-account=$SA_EMAIL \
        --memory=512Mi \
        --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION}" \
        --set-secrets="POLYMARKET_API_KEY=polymarket-api-key:latest,POLYMARKET_API_SECRET=polymarket-api-secret:latest,GEMINI_API_KEY=gemini-api-key:latest" \
        --quiet
    
    # Get service URL
    local url=$(gcloud run services describe moneymaker-${service_name} \
        --region=$REGION \
        --format='value(status.url)')
    
    echo -e "  ${GREEN}Deployed: ${url}${NC}"
}

# Configure Docker for Artifact Registry
echo ""
echo "Configuring Docker..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Deploy based on service argument
case $SERVICE in
    "orchestrator")
        deploy_service "orchestrator" 8000
        ;;
    "scraper")
        deploy_service "scraper" 8001
        ;;
    "ai_suggester"|"ai-suggester")
        deploy_service "ai_suggester" 8002
        ;;
    "trader")
        deploy_service "trader" 8003
        ;;
    "monitor")
        deploy_service "monitor" 8004
        ;;
    "all")
        deploy_service "orchestrator" 8000
        deploy_service "scraper" 8001
        deploy_service "ai_suggester" 8002
        deploy_service "trader" 8003
        deploy_service "monitor" 8004
        ;;
    *)
        echo -e "${RED}Unknown service: $SERVICE${NC}"
        echo "Available services: orchestrator, scraper, ai_suggester, trader, monitor, all"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo -e "${GREEN}Deployment complete!${NC}"
echo "========================================"

# Get orchestrator URL for reference
ORCH_URL=$(gcloud run services describe moneymaker-orchestrator \
    --region=$REGION \
    --format='value(status.url)' 2>/dev/null || echo "Not deployed")

echo ""
echo "Orchestrator URL: $ORCH_URL"
echo ""
echo "Test commands:"
echo "  curl ${ORCH_URL}/health"
echo "  curl ${ORCH_URL}/status"
echo ""
