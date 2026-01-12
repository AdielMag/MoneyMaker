#!/bin/bash
# MoneyMaker GitHub Actions Service Account Setup
# Usage: ./scripts/setup_github_sa.sh
# This script creates a service account for GitHub Actions and generates a key

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "========================================"
echo "GitHub Actions Service Account Setup"
echo "========================================"

# Check PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: PROJECT_ID environment variable not set${NC}"
    echo "Run: export PROJECT_ID=your-project-id"
    exit 1
fi

echo "Project: $PROJECT_ID"
echo ""

SA_NAME="github-actions"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="github-actions-key.json"

# Check if service account already exists
echo -e "${YELLOW}Checking if service account exists...${NC}"
if gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID &>/dev/null; then
    echo -e "  ${GREEN}Service account already exists: ${SA_EMAIL}${NC}"
else
    echo "Creating service account..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="GitHub Actions" \
        --project=$PROJECT_ID
    echo -e "  ${GREEN}Service account created: ${SA_EMAIL}${NC}"
fi

echo ""
echo -e "${YELLOW}Granting necessary IAM roles...${NC}"

# Required roles for Cloud Run deployment
ROLES=(
    "roles/run.admin"
    "roles/artifactregistry.writer"
    "roles/iam.serviceAccountUser"
    "roles/storage.admin"
)

for role in "${ROLES[@]}"; do
    echo "  Adding $role..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --quiet &>/dev/null
done
echo -e "  ${GREEN}All roles granted!${NC}"

echo ""
echo -e "${YELLOW}Creating service account key...${NC}"

# Remove old key file if exists
if [ -f "$KEY_FILE" ]; then
    rm "$KEY_FILE"
fi

gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account=$SA_EMAIL \
    --project=$PROJECT_ID

echo -e "  ${GREEN}Key saved to: ${KEY_FILE}${NC}"

echo ""
echo "========================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo "1. Go to your GitHub repository:"
echo "   Settings → Secrets and variables → Actions"
echo ""
echo "2. Create these repository secrets:"
echo ""
echo -e "   ${YELLOW}GCP_PROJECT_ID${NC}"
echo "   Value: $PROJECT_ID"
echo ""
echo -e "   ${YELLOW}GCP_SA_KEY${NC}"
echo "   Value: Copy the entire contents of ${KEY_FILE}"
echo ""
echo "   To copy the key contents, run:"
echo -e "   ${CYAN}cat ${KEY_FILE}${NC}"
echo ""
echo -e "${RED}IMPORTANT: Delete ${KEY_FILE} after adding to GitHub!${NC}"
echo "   rm ${KEY_FILE}"
echo ""
