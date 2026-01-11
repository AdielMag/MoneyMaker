# MoneyMaker Deployment Guide

This guide provides step-by-step instructions for deploying MoneyMaker to Google Cloud Platform (GCP).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [GCP Project Setup](#gcp-project-setup)
3. [Local Development Setup](#local-development-setup)
4. [API Credentials Setup](#api-credentials-setup)
5. [Firestore Setup](#firestore-setup)
6. [Secret Manager Setup](#secret-manager-setup)
7. [Artifact Registry Setup](#artifact-registry-setup)
8. [Building Docker Images](#building-docker-images)
9. [Cloud Run Deployment](#cloud-run-deployment)
10. [Cloud Scheduler Setup](#cloud-scheduler-setup)
11. [GitHub Actions CI/CD Setup](#github-actions-cicd-setup)
12. [Monitoring and Logging](#monitoring-and-logging)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

Install the following tools on your local machine:

```bash
# Python 3.11+
python --version  # Should be 3.11 or higher

# Google Cloud SDK
# Download from: https://cloud.google.com/sdk/docs/install
gcloud --version

# Docker
docker --version

# Terraform (optional, for infrastructure as code)
terraform --version

# Git
git --version
```

### Required Accounts

1. **Google Cloud Platform Account** - [Sign up](https://cloud.google.com/free)
2. **Polymarket Account** - [Create account](https://polymarket.com) and get API credentials
3. **Google AI Studio** - [Get Gemini API key](https://makersuite.google.com/app/apikey)
4. **GitHub Account** - For CI/CD pipelines
5. **Codecov Account** (optional) - For coverage reporting

---

## GCP Project Setup

### Step 1: Create a New Project

**For Bash/Linux/macOS:**
```bash
# Set your project ID (must be globally unique)
export PROJECT_ID="moneymaker-trading-$(date +%s)"
export REGION="us-central1"
```

**For PowerShell/Windows:**
```powershell
# Set your project ID (must be globally unique)
$env:PROJECT_ID = "moneymaker-trading-$(Get-Date -Format 'yyyyMMddHHmmss')"
$env:REGION = "us-central1"
```

**Then run (both platforms):**

# Create the project
gcloud projects create $PROJECT_ID --name="MoneyMaker Trading"

# Set as current project
gcloud config set project $PROJECT_ID

# Link billing account (required for Cloud Run)
# List available billing accounts
gcloud billing accounts list

# Link billing (replace BILLING_ACCOUNT_ID)
gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

### Step 2: Enable Required APIs

```bash
# Enable all required GCP APIs
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled
```

### Step 3: Create Service Account

```bash
# Create service account for Cloud Run services
gcloud iam service-accounts create moneymaker-service \
  --display-name="MoneyMaker Service Account"

# Grant necessary roles
export SA_EMAIL="moneymaker-service@${PROJECT_ID}.iam.gserviceaccount.com"

# Firestore access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"

# Secret Manager access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Run invoker (for internal service communication)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

# Logging
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

---

## Local Development Setup

### Step 1: Clone and Set Up Environment

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/MoneyMaker.git
cd MoneyMaker

# Create virtual environment
python -m venv venv
```

**Activate virtual environment:**

```powershell
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

```bash
# On macOS/Linux:
source venv/bin/activate
```

**Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 2: Configure Environment Variables

```bash
# Copy the example environment file
cp config/env.example .env

# Edit .env with your credentials
# On Windows:
notepad .env
# On macOS/Linux:
nano .env
```

**Required environment variables:**

```env
# Environment
ENVIRONMENT=development

# GCP
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Polymarket
POLYMARKET_API_KEY=your-polymarket-api-key
POLYMARKET_API_SECRET=your-polymarket-api-secret
POLYMARKET_WALLET_ADDRESS=0xYourWalletAddress

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key

# Feature Flags
REAL_MONEY_ENABLED=false
FAKE_MONEY_ENABLED=true
```

### Step 3: Download Service Account Key (for local development)

```bash
# Create key for local development
gcloud iam service-accounts keys create ./service-account.json \
  --iam-account=$SA_EMAIL
```

**Set environment variable:**

```powershell
# On Windows PowerShell:
$env:GOOGLE_APPLICATION_CREDENTIALS = "$(Get-Location)\service-account.json"
```

```bash
# On macOS/Linux:
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/service-account.json"
```

### Step 4: Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov --cov-report=html

# Run only unit tests
pytest tests/unit -v
```

### Step 5: Run Locally

```bash
# Start the orchestrator service
uvicorn services.orchestrator.main:app --reload --port 8000

# Access API documentation
# Open http://localhost:8000/docs in your browser
```

---

## API Credentials Setup

### Polymarket API

1. Go to [Polymarket](https://polymarket.com) and create an account
2. Navigate to API settings or developer portal
3. Generate API key and secret
4. Note your wallet address

### Gemini AI API

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy and save the API key securely

---

## Firestore Setup

### Step 1: Create Firestore Database

```bash
# Create Firestore database in Native mode
gcloud firestore databases create \
  --location=$REGION \
  --type=firestore-native
```

### Step 2: Create Indexes (if needed)

Create a file `firestore.indexes.json`:

```json
{
  "indexes": [
    {
      "collectionGroup": "fake_positions",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "mode", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "fake_transactions",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "wallet_id", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

Deploy indexes:

```bash
gcloud firestore indexes create --file=firestore.indexes.json
```

### Step 3: Initialize Default Data (Optional)

You can use the Python script to initialize the fake wallet:

```python
# scripts/init_firestore.py
import asyncio
from shared.firestore_client import FirestoreClient

async def init():
    client = FirestoreClient()
    
    # Create default wallet with initial balance
    wallet = await client.create_wallet("default", initial_balance=1000.0)
    print(f"Created wallet: {wallet.wallet_id} with balance ${wallet.balance}")
    
    # Initialize workflow states
    from shared.models import TradingMode, WorkflowState
    
    for workflow_id in ["discovery", "monitor"]:
        for mode in [TradingMode.FAKE, TradingMode.REAL]:
            state = WorkflowState(
                workflow_id=workflow_id,
                mode=mode,
                enabled=(mode == TradingMode.FAKE),
            )
            await client.update_workflow_state(state)
            print(f"Initialized {workflow_id} workflow for {mode.value} mode")

if __name__ == "__main__":
    asyncio.run(init())
```

Run it:

```bash
python scripts/init_firestore.py
```

---

## Secret Manager Setup

Store sensitive credentials in Secret Manager:

```bash
# Store Polymarket API key
echo -n "your-polymarket-api-key" | \
  gcloud secrets create polymarket-api-key --data-file=-

# Store Polymarket API secret
echo -n "your-polymarket-api-secret" | \
  gcloud secrets create polymarket-api-secret --data-file=-

# Store Polymarket wallet address
echo -n "0xYourWalletAddress" | \
  gcloud secrets create polymarket-wallet-address --data-file=-

# Store Gemini API key
echo -n "your-gemini-api-key" | \
  gcloud secrets create gemini-api-key --data-file=-

# Verify secrets were created
gcloud secrets list
```

---

## Artifact Registry Setup

Create a Docker repository for your images:

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create moneymaker \
  --repository-format=docker \
  --location=$REGION \
  --description="MoneyMaker Docker images"

# Configure Docker to use Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

---

## Building Docker Images

### Build All Images Locally

```bash
# Set image tag
export TAG="v1.0.0"
export REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/moneymaker"

# Build orchestrator
docker build \
  -t ${REGISTRY}/orchestrator:${TAG} \
  -f services/orchestrator/Dockerfile .

# Build scraper
docker build \
  -t ${REGISTRY}/scraper:${TAG} \
  -f services/scraper/Dockerfile .

# Build AI suggester
docker build \
  -t ${REGISTRY}/ai-suggester:${TAG} \
  -f services/ai_suggester/Dockerfile .

# Build trader
docker build \
  -t ${REGISTRY}/trader:${TAG} \
  -f services/trader/Dockerfile .

# Build monitor
docker build \
  -t ${REGISTRY}/monitor:${TAG} \
  -f services/monitor/Dockerfile .
```

### Push Images to Artifact Registry

```bash
# Push all images
docker push ${REGISTRY}/orchestrator:${TAG}
docker push ${REGISTRY}/scraper:${TAG}
docker push ${REGISTRY}/ai-suggester:${TAG}
docker push ${REGISTRY}/trader:${TAG}
docker push ${REGISTRY}/monitor:${TAG}
```

### Using Cloud Build (Alternative)

Create `cloudbuild.yaml`:

```yaml
steps:
  # Build and push orchestrator
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_REGISTRY}/orchestrator:${TAG}', '-f', 'services/orchestrator/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGISTRY}/orchestrator:${TAG}']

  # Build and push scraper
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_REGISTRY}/scraper:${TAG}', '-f', 'services/scraper/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGISTRY}/scraper:${TAG}']

  # Build and push AI suggester
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_REGISTRY}/ai-suggester:${TAG}', '-f', 'services/ai_suggester/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGISTRY}/ai-suggester:${TAG}']

  # Build and push trader
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_REGISTRY}/trader:${TAG}', '-f', 'services/trader/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGISTRY}/trader:${TAG}']

  # Build and push monitor
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_REGISTRY}/monitor:${TAG}', '-f', 'services/monitor/Dockerfile', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGISTRY}/monitor:${TAG}']

substitutions:
  _REGISTRY: '${REGION}-docker.pkg.dev/${PROJECT_ID}/moneymaker'
  TAG: 'latest'

options:
  logging: CLOUD_LOGGING_ONLY
```

Run Cloud Build:

```bash
gcloud builds submit --config=cloudbuild.yaml --substitutions=TAG=v1.0.0
```

---

## Cloud Run Deployment

### Deploy Orchestrator (Main Service)

```bash
# Deploy orchestrator service
gcloud run deploy moneymaker-orchestrator \
  --image=${REGISTRY}/orchestrator:${TAG} \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=$SA_EMAIL \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=300 \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION}" \
  --set-secrets="POLYMARKET_API_KEY=polymarket-api-key:latest,POLYMARKET_API_SECRET=polymarket-api-secret:latest,POLYMARKET_WALLET_ADDRESS=polymarket-wallet-address:latest,GEMINI_API_KEY=gemini-api-key:latest"

# Get the service URL
export ORCHESTRATOR_URL=$(gcloud run services describe moneymaker-orchestrator \
  --region=$REGION \
  --format='value(status.url)')

echo "Orchestrator URL: $ORCHESTRATOR_URL"
```

### Deploy Other Services (Optional)

If deploying microservices individually:

```bash
# Deploy scraper
gcloud run deploy moneymaker-scraper \
  --image=${REGISTRY}/scraper:${TAG} \
  --region=$REGION \
  --platform=managed \
  --no-allow-unauthenticated \
  --service-account=$SA_EMAIL \
  --memory=256Mi \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="POLYMARKET_API_KEY=polymarket-api-key:latest"

# Deploy AI suggester
gcloud run deploy moneymaker-ai-suggester \
  --image=${REGISTRY}/ai-suggester:${TAG} \
  --region=$REGION \
  --platform=managed \
  --no-allow-unauthenticated \
  --service-account=$SA_EMAIL \
  --memory=512Mi \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"

# Deploy trader
gcloud run deploy moneymaker-trader \
  --image=${REGISTRY}/trader:${TAG} \
  --region=$REGION \
  --platform=managed \
  --no-allow-unauthenticated \
  --service-account=$SA_EMAIL \
  --memory=256Mi \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="POLYMARKET_API_KEY=polymarket-api-key:latest,POLYMARKET_API_SECRET=polymarket-api-secret:latest"

# Deploy monitor
gcloud run deploy moneymaker-monitor \
  --image=${REGISTRY}/monitor:${TAG} \
  --region=$REGION \
  --platform=managed \
  --no-allow-unauthenticated \
  --service-account=$SA_EMAIL \
  --memory=256Mi \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID}"
```

### Verify Deployment

```bash
# Test health endpoint
curl ${ORCHESTRATOR_URL}/health

# Expected response:
# {"status":"healthy","version":"0.1.0","timestamp":"..."}

# Test system status
curl ${ORCHESTRATOR_URL}/status
```

---

## Cloud Scheduler Setup

### Option 1: Using Terraform

```bash
cd infra

# Initialize Terraform
terraform init

# Review the plan
terraform plan \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="orchestrator_url=${ORCHESTRATOR_URL}"

# Apply the configuration
terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="orchestrator_url=${ORCHESTRATOR_URL}"
```

### Option 2: Using gcloud Commands

```bash
# Create scheduler service account
gcloud iam service-accounts create moneymaker-scheduler \
  --display-name="MoneyMaker Cloud Scheduler"

export SCHEDULER_SA="moneymaker-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant Cloud Run invoker role
gcloud run services add-iam-policy-binding moneymaker-orchestrator \
  --region=$REGION \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker"

# Create discovery job for fake money (every 30 minutes)
gcloud scheduler jobs create http moneymaker-discovery-fake \
  --location=$REGION \
  --schedule="*/30 * * * *" \
  --uri="${ORCHESTRATOR_URL}/workflow/discover" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"mode":"fake"}' \
  --oidc-service-account-email=$SCHEDULER_SA \
  --oidc-token-audience=$ORCHESTRATOR_URL

# Create monitor job for fake money (every 5 minutes)
gcloud scheduler jobs create http moneymaker-monitor-fake \
  --location=$REGION \
  --schedule="*/5 * * * *" \
  --uri="${ORCHESTRATOR_URL}/workflow/monitor" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"mode":"fake"}' \
  --oidc-service-account-email=$SCHEDULER_SA \
  --oidc-token-audience=$ORCHESTRATOR_URL

# Create discovery job for real money (paused by default)
gcloud scheduler jobs create http moneymaker-discovery-real \
  --location=$REGION \
  --schedule="0 */2 * * *" \
  --uri="${ORCHESTRATOR_URL}/workflow/discover" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"mode":"real"}' \
  --oidc-service-account-email=$SCHEDULER_SA \
  --oidc-token-audience=$ORCHESTRATOR_URL

# Pause real money job (safety)
gcloud scheduler jobs pause moneymaker-discovery-real --location=$REGION

# List all jobs
gcloud scheduler jobs list --location=$REGION
```

### Test Scheduler Jobs

```bash
# Manually trigger discovery job
gcloud scheduler jobs run moneymaker-discovery-fake --location=$REGION

# Check logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=moneymaker-orchestrator" --limit=20
```

---

## GitHub Actions CI/CD Setup

### Step 1: Create Service Account for GitHub Actions

```bash
# Create deployment service account
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

export DEPLOYER_SA="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser"

# Create key for GitHub Actions
gcloud iam service-accounts keys create github-deployer-key.json \
  --iam-account=$DEPLOYER_SA
```

### Step 2: Configure GitHub Secrets

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add:

| Secret Name | Value |
|-------------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | Contents of `github-deployer-key.json` (base64 encoded) |
| `CODECOV_TOKEN` | Your Codecov token (optional) |

```bash
# Encode the service account key
cat github-deployer-key.json | base64

# Copy the output and paste it as GCP_SA_KEY secret
```

### Step 3: Test the Pipeline

```bash
# Create a new tag to trigger deployment
git tag v1.0.0
git push origin v1.0.0
```

---

## Monitoring and Logging

### View Logs

```bash
# View orchestrator logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=moneymaker-orchestrator" \
  --limit=50 \
  --format="table(timestamp,jsonPayload.message)"

# View scheduler job logs
gcloud logging read "resource.type=cloud_scheduler_job" \
  --limit=20

# Stream logs in real-time
gcloud alpha run services logs tail moneymaker-orchestrator --region=$REGION
```

### Set Up Alerts

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --display-name="MoneyMaker High Error Rate" \
  --condition-display-name="Error rate > 5%" \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class="5xx"'
```

### Cloud Console Dashboards

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Select `moneymaker-orchestrator`
3. View metrics: requests, latency, errors
4. Go to **Logs** tab for detailed logs

---

## Troubleshooting

### Common Issues

#### 1. Cloud Run deployment fails

```bash
# Check build logs
gcloud builds list --limit=5

# View specific build logs
gcloud builds log BUILD_ID

# Common fixes:
# - Ensure Dockerfile is correct
# - Check if all dependencies are in requirements.txt
# - Verify service account permissions
```

#### 2. Scheduler jobs fail with 401/403

```bash
# Verify service account has invoker role
gcloud run services get-iam-policy moneymaker-orchestrator --region=$REGION

# Re-add invoker role if missing
gcloud run services add-iam-policy-binding moneymaker-orchestrator \
  --region=$REGION \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker"
```

#### 3. Firestore permission denied

```bash
# Verify service account has Firestore access
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:${SA_EMAIL}"

# Re-add Firestore role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"
```

#### 4. Secret access denied

```bash
# List secret versions
gcloud secrets versions list polymarket-api-key

# Grant access to specific secret
gcloud secrets add-iam-policy-binding polymarket-api-key \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

#### 5. API errors from Polymarket/Gemini

```bash
# Test API credentials locally
curl -X GET "https://gamma-api.polymarket.com/markets?limit=1"

# Check if secrets are set correctly in Cloud Run
gcloud run services describe moneymaker-orchestrator \
  --region=$REGION \
  --format="yaml(spec.template.spec.containers[0].env)"
```

### Health Checks

```bash
# Check service health
curl ${ORCHESTRATOR_URL}/health

# Check system status
curl ${ORCHESTRATOR_URL}/status

# Check specific endpoint
curl ${ORCHESTRATOR_URL}/balance/fake
```

### Rollback Deployment

```bash
# List revisions
gcloud run revisions list --service=moneymaker-orchestrator --region=$REGION

# Rollback to previous revision
gcloud run services update-traffic moneymaker-orchestrator \
  --region=$REGION \
  --to-revisions=REVISION_NAME=100
```

---

## Cost Optimization

### Cloud Run
- Set `min-instances=0` for services that can cold start
- Use appropriate memory/CPU settings
- Enable CPU throttling for non-latency-sensitive services

### Firestore
- Use efficient queries with proper indexes
- Implement caching for frequently accessed data
- Clean up old transaction records periodically

### Cloud Scheduler
- Adjust job frequency based on trading needs
- Pause jobs during non-trading hours if applicable

### Estimated Monthly Costs (Low Usage)

| Service | Estimated Cost |
|---------|----------------|
| Cloud Run | $5-20 |
| Firestore | $1-5 |
| Cloud Scheduler | $0.10/job/month |
| Secret Manager | $0.06/secret/month |
| Artifact Registry | $0.10/GB |
| **Total** | **~$10-30/month** |

---

## Production Checklist

- [ ] GCP project created with billing enabled
- [ ] All required APIs enabled
- [ ] Service accounts created with correct permissions
- [ ] Firestore database created
- [ ] Secrets stored in Secret Manager
- [ ] Docker images built and pushed
- [ ] Cloud Run services deployed
- [ ] Cloud Scheduler jobs created
- [ ] GitHub Actions secrets configured
- [ ] Health endpoints verified
- [ ] Logs and monitoring set up
- [ ] Alerts configured
- [ ] Real money mode disabled by default
- [ ] Documentation updated with actual URLs

---

## Next Steps

After deployment:

1. **Test fake money mode** - Run discovery and monitor workflows
2. **Review logs** - Ensure no errors in Cloud Logging
3. **Adjust configuration** - Fine-tune thresholds and filters
4. **Monitor performance** - Watch metrics in Cloud Console
5. **Enable real money (carefully)** - Only after thorough testing

---

## Support

For issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Cloud Run and Scheduler logs
3. Open an issue on GitHub with logs and configuration
