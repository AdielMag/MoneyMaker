# MoneyMaker Secrets Setup Script for Windows PowerShell
# Usage: .\scripts\setup_secrets.ps1
# This script helps you set up secrets in Google Secret Manager

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   MoneyMaker Secrets Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
Write-Host "Checking gcloud CLI..." -ForegroundColor Yellow
$gcloudCmd = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $gcloudCmd) {
    Write-Host "ERROR: gcloud CLI not found. Please install it first." -ForegroundColor Red
    Write-Host "https://cloud.google.com/sdk/docs/install" -ForegroundColor Gray
    exit 1
}
Write-Host "  Found gcloud at: $($gcloudCmd.Source)" -ForegroundColor Green
Write-Host ""

# Check PROJECT_ID
if (-not $env:PROJECT_ID) {
    Write-Host "ERROR: PROJECT_ID environment variable not set" -ForegroundColor Red
    Write-Host ""
    Write-Host 'Run this first:' -ForegroundColor Yellow
    Write-Host '  $env:PROJECT_ID = "your-project-id"' -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "Project: $($env:PROJECT_ID)" -ForegroundColor Green
Write-Host ""

# Verify gcloud is authenticated
Write-Host "Checking gcloud authentication..." -ForegroundColor Yellow
$account = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>&1
if ([string]::IsNullOrEmpty($account)) {
    Write-Host "ERROR: Not authenticated with gcloud" -ForegroundColor Red
    Write-Host "Run: gcloud auth login" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Authenticated as: $account" -ForegroundColor Green
Write-Host ""

function New-Secret {
    param(
        [string]$SecretName,
        [string]$PromptText
    )
    
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host "Setting up: $SecretName" -ForegroundColor Yellow
    
    # Check if secret exists using list and filter
    Write-Host "  Checking if secret exists..." -ForegroundColor Gray
    $existingSecrets = gcloud secrets list --project=$env:PROJECT_ID --format="value(name)" 2>&1
    $exists = $existingSecrets -match "^$SecretName$"
    
    if ($exists) {
        Write-Host "  Secret already exists." -ForegroundColor Cyan
        $update = Read-Host "  Update with new value? (y/N)"
        if ($update.ToLower() -ne "y") {
            Write-Host "  Skipping..." -ForegroundColor Gray
            return
        }
    }
    
    # Prompt for value
    Write-Host ""
    $secretValue = Read-Host "  Enter $PromptText"
    
    if ([string]::IsNullOrEmpty($secretValue)) {
        Write-Host "  Empty value, skipping..." -ForegroundColor Yellow
        return
    }
    
    # Create a temporary file for the secret
    $tempFile = [System.IO.Path]::GetTempFileName()
    
    try {
        # Write secret to temp file
        [System.IO.File]::WriteAllText($tempFile, $secretValue)
        
        if ($exists) {
            Write-Host "  Adding new version..." -ForegroundColor Gray
            $result = gcloud secrets versions add $SecretName `
                --project=$env:PROJECT_ID `
                --data-file="$tempFile" 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Secret updated!" -ForegroundColor Green
            } else {
                Write-Host "  ERROR: $result" -ForegroundColor Red
            }
        } else {
            Write-Host "  Creating secret..." -ForegroundColor Gray
            $result = gcloud secrets create $SecretName `
                --project=$env:PROJECT_ID `
                --data-file="$tempFile" 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Secret created!" -ForegroundColor Green
            } else {
                Write-Host "  ERROR: $result" -ForegroundColor Red
            }
        }
    }
    finally {
        # Securely delete temp file
        if (Test-Path $tempFile) {
            # Overwrite with zeros before deleting
            [System.IO.File]::WriteAllBytes($tempFile, (New-Object byte[] 1024))
            Remove-Item $tempFile -Force
        }
    }
    
    Write-Host ""
}

# Enable Secret Manager API if needed
Write-Host "Ensuring Secret Manager API is enabled..." -ForegroundColor Yellow
gcloud services enable secretmanager.googleapis.com --project=$env:PROJECT_ID 2>&1 | Out-Null
Write-Host "  API enabled." -ForegroundColor Green
Write-Host ""

# Set up each secret
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Polymarket Credentials" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "(Get these from your Polymarket account)" -ForegroundColor Gray
Write-Host ""

New-Secret -SecretName "polymarket-api-key" -PromptText "Polymarket API Key"
New-Secret -SecretName "polymarket-api-secret" -PromptText "Polymarket API Secret"
New-Secret -SecretName "polymarket-wallet-address" -PromptText "Polymarket Wallet Address (0x...)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Gemini AI Credentials" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "(Get this from https://makersuite.google.com/app/apikey)" -ForegroundColor Gray
Write-Host ""

New-Secret -SecretName "gemini-api-key" -PromptText "Gemini API Key"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Verify your secrets with:" -ForegroundColor Yellow
Write-Host "  gcloud secrets list --project=$($env:PROJECT_ID)" -ForegroundColor White
Write-Host ""
Write-Host "To view a secret value:" -ForegroundColor Yellow
Write-Host '  gcloud secrets versions access latest --secret="SECRET_NAME" --project=$env:PROJECT_ID' -ForegroundColor White
Write-Host ""
