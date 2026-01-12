# Script to update Cloud Run service timeout
# Usage: .\scripts\update_timeout.ps1 [-Service <name>]
# Example: .\scripts\update_timeout.ps1 -Service orchestrator

param(
    [string]$Service = "orchestrator"
)

if (-not $env:PROJECT_ID) {
    Write-Host "ERROR: PROJECT_ID environment variable not set" -ForegroundColor Red
    Write-Host 'Run: $env:PROJECT_ID = "your-project-id"'
    exit 1
}

if (-not $env:REGION) {
    $env:REGION = "us-central1"
}

$cloudRunName = "moneymaker-$($Service -replace '_', '-')"

Write-Host "Updating timeout for $cloudRunName..." -ForegroundColor Yellow
Write-Host "Project: $($env:PROJECT_ID)" -ForegroundColor White
Write-Host "Region:  $($env:REGION)" -ForegroundColor White
Write-Host ""

gcloud run services update $cloudRunName `
    --region=$env:REGION `
    --project=$env:PROJECT_ID `
    --timeout=900 `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Timeout updated to 900 seconds (15 minutes)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Verify with:" -ForegroundColor Yellow
    Write-Host "  gcloud run services describe $cloudRunName --region=$($env:REGION) --format='value(spec.template.spec.timeoutSeconds)'"
} else {
    Write-Host ""
    Write-Host "❌ Failed to update timeout" -ForegroundColor Red
    exit 1
}
