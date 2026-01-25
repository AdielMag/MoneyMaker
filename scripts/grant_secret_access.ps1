# Quick script to grant Secret Manager access to service account
# Usage: .\scripts\grant_secret_access.ps1

$ErrorActionPreference = "Stop"

if (-not $env:PROJECT_ID) {
    Write-Host "ERROR: PROJECT_ID environment variable not set" -ForegroundColor Red
    Write-Host 'Run: $env:PROJECT_ID = "money-maker-484006"' -ForegroundColor Yellow
    exit 1
}

$PROJECT_ID = $env:PROJECT_ID
$SA_EMAIL = "moneymaker-service@${PROJECT_ID}.iam.gserviceaccount.com"

Write-Host "Granting Secret Manager access to: $SA_EMAIL" -ForegroundColor Cyan
Write-Host ""

$SECRETS = @(
    "polymarket-api-key",
    "polymarket-api-secret",
    "gemini-api-key"
)

foreach ($secretName in $SECRETS) {
    Write-Host "Granting access to: $secretName..." -ForegroundColor Yellow
    gcloud secrets add-iam-policy-binding $secretName `
        --member="serviceAccount:${SA_EMAIL}" `
        --role="roles/secretmanager.secretAccessor" `
        --project=$PROJECT_ID

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Access granted" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to grant access" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Done! You can now redeploy the orchestrator." -ForegroundColor Green
