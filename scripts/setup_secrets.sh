#!/bin/bash
# MoneyMaker Secrets Setup Script
# Usage: ./scripts/setup_secrets.sh
# This script helps you set up secrets in Google Secret Manager

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "MoneyMaker Secrets Setup"
echo "========================================"

# Check PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: PROJECT_ID environment variable not set${NC}"
    echo "Run: export PROJECT_ID=your-project-id"
    exit 1
fi

echo "Project: $PROJECT_ID"
echo ""

# Function to create or update a secret
create_secret() {
    local secret_name=$1
    local prompt_text=$2
    
    echo -e "${YELLOW}Setting up: ${secret_name}${NC}"
    
    # Check if secret exists
    if gcloud secrets describe $secret_name --project=$PROJECT_ID &>/dev/null; then
        echo "  Secret already exists."
        read -p "  Update with new value? (y/N): " update
        if [ "$update" != "y" ]; then
            echo "  Skipping..."
            return
        fi
    fi
    
    # Prompt for value
    echo -n "  Enter ${prompt_text}: "
    read -s secret_value
    echo ""
    
    if [ -z "$secret_value" ]; then
        echo -e "  ${RED}Empty value, skipping...${NC}"
        return
    fi
    
    # Create or add new version
    if gcloud secrets describe $secret_name --project=$PROJECT_ID &>/dev/null; then
        echo -n "$secret_value" | gcloud secrets versions add $secret_name \
            --project=$PROJECT_ID \
            --data-file=-
        echo -e "  ${GREEN}Secret updated!${NC}"
    else
        echo -n "$secret_value" | gcloud secrets create $secret_name \
            --project=$PROJECT_ID \
            --data-file=-
        echo -e "  ${GREEN}Secret created!${NC}"
    fi
}

# Set up each secret
echo ""
echo "Setting up Polymarket credentials..."
echo "(Get these from your Polymarket account)"
echo ""

create_secret "polymarket-api-key" "Polymarket API Key"
create_secret "polymarket-api-secret" "Polymarket API Secret"
create_secret "polymarket-wallet-address" "Polymarket Wallet Address (0x...)"

echo ""
echo "Setting up Gemini AI credentials..."
echo "(Get this from https://makersuite.google.com/app/apikey)"
echo ""

create_secret "gemini-api-key" "Gemini API Key"

echo ""
echo "========================================"
echo -e "${GREEN}Secrets setup complete!${NC}"
echo "========================================"
echo ""
echo "Verify secrets:"
echo "  gcloud secrets list --project=$PROJECT_ID"
echo ""
