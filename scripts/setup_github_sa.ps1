# MoneyMaker GitHub Actions Service Account Setup
# Usage: .\scripts\setup_github_sa.ps1
# This script creates a service account for GitHub Actions and generates a key

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GitHub Actions Service Account Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check PROJECT_ID
if (-not $env:PROJECT_ID) {
    Write-Host "ERROR: PROJECT_ID environment variable not set" -ForegroundColor Red
    Write-Host 'Run: $env:PROJECT_ID = "your-project-id"'
    exit 1
}

$PROJECT_ID = $env:PROJECT_ID
Write-Host "Project: $PROJECT_ID"
Write-Host ""

$SA_NAME = "github-actions"
$SA_EMAIL = "$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
$KEY_FILE = "github-actions-key.json"

# Check if service account already exists
Write-Host "Checking if service account exists..." -ForegroundColor Yellow
$ErrorActionPreference = "SilentlyContinue"
$saExists = gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID 2>&1
$ErrorActionPreference = "Stop"

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Service account already exists: $SA_EMAIL" -ForegroundColor Green
} else {
    Write-Host "Creating service account..."
    gcloud iam service-accounts create $SA_NAME `
        --display-name="GitHub Actions" `
        --project=$PROJECT_ID
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to create service account" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Service account created: $SA_EMAIL" -ForegroundColor Green
}

Write-Host ""
Write-Host "Granting necessary IAM roles..." -ForegroundColor Yellow

# Required roles for Cloud Run deployment
$ROLES = @(
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin"
)

$ErrorActionPreference = "SilentlyContinue"
foreach ($role in $ROLES) {
    Write-Host "  Adding $role..."
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$SA_EMAIL" `
        --role="$role" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Done" -ForegroundColor Green
    } else {
        Write-Host "    Warning: Could not add role (may already exist)" -ForegroundColor Yellow
    }
}
$ErrorActionPreference = "Stop"
Write-Host "  IAM roles processed!" -ForegroundColor Green

Write-Host ""
Write-Host "Creating service account key..." -ForegroundColor Yellow

# Remove old key file if exists
if (Test-Path $KEY_FILE) {
    Remove-Item $KEY_FILE
}

gcloud iam service-accounts keys create $KEY_FILE `
    --iam-account=$SA_EMAIL `
    --project=$PROJECT_ID

Write-Host "  Key saved to: $KEY_FILE" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Go to your GitHub repository:"
Write-Host "   Settings -> Secrets and variables -> Actions"
Write-Host ""
Write-Host "2. Create these repository secrets:"
Write-Host ""
Write-Host "   GCP_PROJECT_ID" -ForegroundColor Yellow
Write-Host "   Value: $PROJECT_ID"
Write-Host ""
Write-Host "   GCP_SA_KEY" -ForegroundColor Yellow
Write-Host "   Value: Copy the entire contents of $KEY_FILE"
Write-Host ""
Write-Host "   To copy the key contents to clipboard, run:"
Write-Host "   Get-Content $KEY_FILE | Set-Clipboard" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Delete $KEY_FILE after adding to GitHub!" -ForegroundColor Red
Write-Host "   Remove-Item $KEY_FILE"
Write-Host ""
