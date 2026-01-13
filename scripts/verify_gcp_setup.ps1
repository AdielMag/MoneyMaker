# Verify GCP Setup for MoneyMaker
# This script helps verify your GCP credentials and permissions

param(
    [string]$ProjectId = ""
)

Write-Host "=== MoneyMaker GCP Setup Verification ===" -ForegroundColor Cyan
Write-Host ""

# Check if credentials file exists
$credentialsPath = "gcp-credentials.json"
if (-not (Test-Path $credentialsPath)) {
    Write-Host "❌ Credentials file not found: $credentialsPath" -ForegroundColor Red
    Write-Host "   Please create it following SETUP_GCP_CREDENTIALS.md" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Credentials file found" -ForegroundColor Green

# Read and validate credentials
try {
    $credentials = Get-Content $credentialsPath | ConvertFrom-Json
    
    if (-not $credentials.project_id) {
        Write-Host "❌ Invalid credentials file: missing project_id" -ForegroundColor Red
        exit 1
    }
    
    $credProjectId = $credentials.project_id
    Write-Host "✅ Credentials file is valid JSON" -ForegroundColor Green
    Write-Host "   Project ID in credentials: $credProjectId" -ForegroundColor Cyan
    
    # Get project ID from .env if not provided
    if ([string]::IsNullOrEmpty($ProjectId)) {
        if (Test-Path ".env") {
            $envContent = Get-Content ".env"
            $envProjectId = ($envContent | Select-String -Pattern "^GCP_PROJECT_ID=(.+)$").Matches.Groups[1].Value
            if ($envProjectId) {
                $ProjectId = $envProjectId
            }
        }
    }
    
    if ([string]::IsNullOrEmpty($ProjectId)) {
        $ProjectId = $credProjectId
        Write-Host "   Using project ID from credentials file" -ForegroundColor Yellow
    }
    
    Write-Host "   Project ID to use: $ProjectId" -ForegroundColor Cyan
    
    # Check if project IDs match
    if ($credProjectId -ne $ProjectId) {
        Write-Host ""
        Write-Host "⚠️  WARNING: Project ID mismatch!" -ForegroundColor Yellow
        Write-Host "   Credentials file: $credProjectId" -ForegroundColor Yellow
        Write-Host "   Environment: $ProjectId" -ForegroundColor Yellow
        Write-Host "   They should match!" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Project IDs match" -ForegroundColor Green
    }
    
} catch {
    Write-Host "❌ Error reading credentials file: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Checking Required Permissions ===" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
$gcloudInstalled = Get-Command gcloud -ErrorAction SilentlyContinue

if ($gcloudInstalled) {
    Write-Host "✅ gcloud CLI found" -ForegroundColor Green
    Write-Host ""
    Write-Host "Checking service account permissions..." -ForegroundColor Cyan
    
    $serviceAccountEmail = $credentials.client_email
    
    try {
        # Get IAM policy for the project
        Write-Host "   Service Account: $serviceAccountEmail" -ForegroundColor White
        
        # Check if Firestore API is enabled
        Write-Host ""
        Write-Host "Checking if Firestore API is enabled..." -ForegroundColor Cyan
        $firestoreEnabled = gcloud services list --enabled --project=$ProjectId --filter="name:firestore.googleapis.com" 2>&1
        
        if ($firestoreEnabled -match "firestore") {
            Write-Host "✅ Firestore API is enabled" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Firestore API may not be enabled" -ForegroundColor Yellow
            Write-Host "   Enable it with: gcloud services enable firestore.googleapis.com --project=$ProjectId" -ForegroundColor Yellow
        }
        
        Write-Host ""
        Write-Host "Checking service account roles..." -ForegroundColor Cyan
        $roles = gcloud projects get-iam-policy $ProjectId --flatten="bindings[].members" --filter="bindings.members:serviceAccount:$serviceAccountEmail" --format="table(bindings.role)" 2>&1
        
        if ($roles -match "datastore" -or $roles -match "firestore") {
            Write-Host "✅ Service account has Firestore permissions" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Service account may not have Firestore permissions" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Grant permissions with:" -ForegroundColor Yellow
            Write-Host "  gcloud projects add-iam-policy-binding $ProjectId \`" -ForegroundColor White
            Write-Host "    --member=`"serviceAccount:$serviceAccountEmail`" \`" -ForegroundColor White
            Write-Host "    --role=`"roles/datastore.user`"" -ForegroundColor White
        }
        
    } catch {
        Write-Host "⚠️  Could not verify permissions (this is okay if you don't have gcloud CLI)" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  gcloud CLI not found" -ForegroundColor Yellow
    Write-Host "   Install it to verify permissions: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "✅ Credentials file: $credentialsPath" -ForegroundColor Green
Write-Host "✅ Project ID: $ProjectId" -ForegroundColor Green
Write-Host "✅ Service Account: $($credentials.client_email)" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Ensure Firestore API is enabled in GCP Console" -ForegroundColor White
Write-Host "2. Ensure service account has 'Cloud Datastore User' role" -ForegroundColor White
Write-Host "3. Restart Docker containers: docker-compose restart" -ForegroundColor White
Write-Host ""
