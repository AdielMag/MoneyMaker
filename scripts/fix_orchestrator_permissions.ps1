# Fix Orchestrator Permissions
# This script updates the Cloud Run orchestrator service to use the correct service account
# Usage: .\scripts\fix_orchestrator_permissions.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Fix Orchestrator Permissions" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check PROJECT_ID
if (-not $env:PROJECT_ID) {
    Write-Host "ERROR: PROJECT_ID environment variable not set" -ForegroundColor Red
    Write-Host 'Run: $env:PROJECT_ID = "your-project-id"' -ForegroundColor Yellow
    exit 1
}

if (-not $env:REGION) {
    Write-Host "ERROR: REGION environment variable not set" -ForegroundColor Red
    Write-Host 'Run: $env:REGION = "us-central1"' -ForegroundColor Yellow
    exit 1
}

$PROJECT_ID = $env:PROJECT_ID
$REGION = $env:REGION
$SERVICE_NAME = "moneymaker-orchestrator"
$SA_NAME = "moneymaker-service"
$SA_EMAIL = "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

Write-Host "Project: $PROJECT_ID" -ForegroundColor White
Write-Host "Region: $REGION" -ForegroundColor White
Write-Host "Service: $SERVICE_NAME" -ForegroundColor White
Write-Host ""

# Step 1: Create service account if it doesn't exist
Write-Host "Step 1: Checking service account..." -ForegroundColor Yellow
$ErrorActionPreference = "SilentlyContinue"
$saExists = gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID 2>&1
$ErrorActionPreference = "Stop"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Creating service account $SA_EMAIL..." -ForegroundColor White
    gcloud iam service-accounts create $SA_NAME `
        --display-name="MoneyMaker Service Account" `
        --project=$PROJECT_ID

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to create service account" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Service account created" -ForegroundColor Green
} else {
    Write-Host "  Service account already exists" -ForegroundColor Green
}

# Step 2: Grant necessary IAM roles
Write-Host ""
Write-Host "Step 2: Granting IAM roles..." -ForegroundColor Yellow

$ROLES = @(
    @{Role="roles/datastore.user"; Description="Firestore access"},
    @{Role="roles/secretmanager.secretAccessor"; Description="Secret Manager access"},
    @{Role="roles/run.invoker"; Description="Cloud Run invoker"},
    @{Role="roles/logging.logWriter"; Description="Logging"}
)

foreach ($roleInfo in $ROLES) {
    Write-Host "  Adding $($roleInfo.Role)..." -ForegroundColor White
    $ErrorActionPreference = "SilentlyContinue"
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:${SA_EMAIL}" `
        --role=$roleInfo.Role `
        --quiet 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    Write-Host "    $($roleInfo.Description)" -ForegroundColor Gray
}

Write-Host "  All roles granted" -ForegroundColor Green

# Step 2b: Grant Secret Manager access at secret level (more explicit)
Write-Host ""
Write-Host "Step 2b: Granting Secret Manager access to individual secrets..." -ForegroundColor Yellow

$SECRETS = @(
    "polymarket-api-key",
    "polymarket-api-secret",
    "gemini-api-key"
)

foreach ($secretName in $SECRETS) {
    Write-Host "  Granting access to secret: $secretName..." -ForegroundColor White
    $ErrorActionPreference = "SilentlyContinue"
    gcloud secrets add-iam-policy-binding $secretName `
        --member="serviceAccount:${SA_EMAIL}" `
        --role="roles/secretmanager.secretAccessor" `
        --project=$PROJECT_ID `
        --quiet 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Access granted" -ForegroundColor Gray
    } else {
        Write-Host "    Warning: May already have access or secret doesn't exist" -ForegroundColor Yellow
    }
}

# Step 3: Update Cloud Run service to use the service account
Write-Host ""
Write-Host "Step 3: Updating Cloud Run service..." -ForegroundColor Yellow
Write-Host "  Setting service account to $SA_EMAIL..." -ForegroundColor White

gcloud run services update $SERVICE_NAME `
    --region=$REGION `
    --project=$PROJECT_ID `
    --service-account=$SA_EMAIL

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Failed to update service" -ForegroundColor Red
    exit 1
}

Write-Host "  Service updated successfully" -ForegroundColor Green

# Step 4: Verify the update
Write-Host ""
Write-Host "Step 4: Verifying update..." -ForegroundColor Yellow

$currentSA = gcloud run services describe $SERVICE_NAME `
    --region=$REGION `
    --project=$PROJECT_ID `
    --format='value(spec.template.spec.serviceAccountName)' 2>&1

if ($currentSA -eq $SA_EMAIL) {
    Write-Host "  Service account is correctly set: $currentSA" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Service account may not be set correctly" -ForegroundColor Yellow
    Write-Host "    Current: $currentSA" -ForegroundColor Yellow
    Write-Host "    Expected: $SA_EMAIL" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Done! The orchestrator should now have" -ForegroundColor Green
Write-Host "proper permissions to access Firestore." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
