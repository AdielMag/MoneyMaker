# Setup GCP Credentials for MoneyMaker
# This script helps you download your GCP service account credentials

param(
    [string]$ProjectId = "",
    [string]$ServiceAccountEmail = "",
    [string]$OutputPath = "gcp-credentials.json"
)

Write-Host "=== MoneyMaker GCP Credentials Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
$gcloudInstalled = Get-Command gcloud -ErrorAction SilentlyContinue

if (-not $gcloudInstalled) {
    Write-Host "⚠️  gcloud CLI not found. You can:" -ForegroundColor Yellow
    Write-Host "   1. Install it from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    Write-Host "   2. Or download credentials manually from GCP Console" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "See SETUP_GCP_CREDENTIALS.md for manual setup instructions." -ForegroundColor Yellow
    Write-Host ""
    
    # Check if credentials file already exists
    if (Test-Path $OutputPath) {
        Write-Host "✅ Found existing credentials file: $OutputPath" -ForegroundColor Green
        Write-Host "   Make sure it's a valid JSON file, not a directory!" -ForegroundColor Yellow
    } else {
        Write-Host "❌ No credentials file found." -ForegroundColor Red
        Write-Host "   Please create one following the instructions in SETUP_GCP_CREDENTIALS.md" -ForegroundColor Yellow
    }
    exit 1
}

Write-Host "✅ gcloud CLI found" -ForegroundColor Green
Write-Host ""

# Get project ID if not provided
if ([string]::IsNullOrEmpty($ProjectId)) {
    $ProjectId = Read-Host "Enter your GCP Project ID"
}

# Get service account email if not provided
if ([string]::IsNullOrEmpty($ServiceAccountEmail)) {
    Write-Host ""
    Write-Host "Available service accounts in project '$ProjectId':" -ForegroundColor Cyan
    gcloud iam service-accounts list --project=$ProjectId
    
    Write-Host ""
    $ServiceAccountEmail = Read-Host "Enter the service account email (e.g., moneymaker-service@PROJECT_ID.iam.gserviceaccount.com)"
}

# Validate service account email format
if ($ServiceAccountEmail -notmatch '@.*\.iam\.gserviceaccount\.com$') {
    Write-Host "⚠️  Warning: Service account email format looks incorrect" -ForegroundColor Yellow
    Write-Host "   Expected format: name@PROJECT_ID.iam.gserviceaccount.com" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne 'y' -and $continue -ne 'Y') {
        exit 1
    }
}

# Check if output file already exists
if (Test-Path $OutputPath) {
    Write-Host ""
    Write-Host "⚠️  File $OutputPath already exists!" -ForegroundColor Yellow
    $overwrite = Read-Host "Overwrite? (y/N)"
    if ($overwrite -ne 'y' -and $overwrite -ne 'Y') {
        Write-Host "Aborted." -ForegroundColor Red
        exit 1
    }
    Remove-Item $OutputPath -Force
}

Write-Host ""
Write-Host "Downloading credentials..." -ForegroundColor Cyan

try {
    # Create the key
    gcloud iam service-accounts keys create $OutputPath `
        --iam-account=$ServiceAccountEmail `
        --project=$ProjectId
    
    Write-Host ""
    Write-Host "✅ Successfully created credentials file: $OutputPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Verify the file exists and is valid JSON" -ForegroundColor White
    Write-Host "2. Update your .env file with: GCP_PROJECT_ID=$ProjectId" -ForegroundColor White
    Write-Host "3. Restart Docker containers: docker-compose down && docker-compose up -d" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "❌ Error creating credentials:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Please check:" -ForegroundColor Yellow
    Write-Host "  - Project ID is correct" -ForegroundColor Yellow
    Write-Host "  - Service account email is correct" -ForegroundColor Yellow
    Write-Host "  - You have permission to create keys" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "See SETUP_GCP_CREDENTIALS.md for manual setup instructions." -ForegroundColor Yellow
    exit 1
}
