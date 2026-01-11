# MoneyMaker Deployment Script for Windows PowerShell
# Usage: .\scripts\deploy.ps1 [-Service <name>] [-Tag <version>]
# Example: .\scripts\deploy.ps1 -Service orchestrator -Tag v1.0.0
# Example: .\scripts\deploy.ps1 -Service all -Tag latest

param(
    [string]$Service = "all",
    [string]$Tag = "latest"
)

# Find Docker executable and add to PATH if needed
$DockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $DockerCmd) {
    # Check common Docker locations
    $dockerPaths = @(
        "C:\Program Files\Docker\Docker\resources\bin",
        "$env:ProgramFiles\Docker\Docker\resources\bin",
        "$env:LOCALAPPDATA\Docker\wsl"
    )
    foreach ($dockerDir in $dockerPaths) {
        $dockerExe = Join-Path $dockerDir "docker.exe"
        if (Test-Path $dockerExe) {
            # Add to PATH for this session (needed for credential helpers)
            $env:PATH = "$dockerDir;$env:PATH"
            $DockerCmd = $dockerExe
            Write-Host "Found Docker at: $dockerExe" -ForegroundColor Green
            Write-Host "Added to PATH for this session." -ForegroundColor Gray
            break
        }
    }
}

if (-not $DockerCmd) {
    Write-Host "ERROR: Docker not found. Please install Docker Desktop or add Docker to PATH." -ForegroundColor Red
    exit 1
}

# Use the docker path
if ($DockerCmd -is [System.Management.Automation.ApplicationInfo]) {
    $Docker = $DockerCmd.Source
} else {
    $Docker = $DockerCmd
}

Write-Host "Using Docker: $Docker" -ForegroundColor Gray

# Check required environment variables
if (-not $env:PROJECT_ID) {
    Write-Host "ERROR: PROJECT_ID environment variable not set" -ForegroundColor Red
    Write-Host 'Run: $env:PROJECT_ID = "your-project-id"'
    exit 1
}

if (-not $env:REGION) {
    $env:REGION = "us-central1"
}

$REGISTRY = "$($env:REGION)-docker.pkg.dev/$($env:PROJECT_ID)/moneymaker"
$SA_EMAIL = "moneymaker-service@$($env:PROJECT_ID).iam.gserviceaccount.com"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   MoneyMaker Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project: $($env:PROJECT_ID)" -ForegroundColor White
Write-Host "Region:  $($env:REGION)" -ForegroundColor White
Write-Host "Service: $Service" -ForegroundColor White
Write-Host "Tag:     $Tag" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configure Docker for Artifact Registry
Write-Host "Configuring Docker for Artifact Registry..." -ForegroundColor Yellow
gcloud auth configure-docker "$($env:REGION)-docker.pkg.dev" --quiet 2>$null
Write-Host "  Done." -ForegroundColor Green

# Enable required APIs first
Write-Host "Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable artifactregistry.googleapis.com --project=$env:PROJECT_ID --quiet 2>$null
gcloud services enable run.googleapis.com --project=$env:PROJECT_ID --quiet 2>$null
Write-Host "  Done." -ForegroundColor Green

# Create Artifact Registry repository if it doesn't exist
Write-Host "Checking Artifact Registry..." -ForegroundColor Yellow
$repoList = gcloud artifacts repositories list --location=$env:REGION --project=$env:PROJECT_ID --format="value(name)" --quiet 2>$null
if ($repoList -notmatch "moneymaker") {
    Write-Host "  Creating Artifact Registry repository..." -ForegroundColor Yellow
    gcloud artifacts repositories create moneymaker `
        --repository-format=docker `
        --location=$env:REGION `
        --project=$env:PROJECT_ID `
        --description="MoneyMaker Docker images" `
        --quiet 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Repository created." -ForegroundColor Green
    } else {
        Write-Host "  Repository may already exist, continuing..." -ForegroundColor Yellow
    }
} else {
    Write-Host "  Repository exists." -ForegroundColor Green
}

function Deploy-Service {
    param(
        [string]$ServiceName
    )
    
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host "Deploying: $ServiceName" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    $imageName = "$REGISTRY/${ServiceName}:$Tag"
    
    # Build Docker image
    Write-Host "  Building Docker image..." -ForegroundColor White
    & $Docker build -t $imageName -f "services/$ServiceName/Dockerfile" .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to build Docker image" -ForegroundColor Red
        return $false
    }
    Write-Host "  Image built." -ForegroundColor Green
    
    # Push to Artifact Registry
    Write-Host "  Pushing to Artifact Registry..." -ForegroundColor White
    & $Docker push $imageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to push Docker image" -ForegroundColor Red
        return $false
    }
    Write-Host "  Image pushed." -ForegroundColor Green
    
    # Deploy to Cloud Run (replace underscores with dashes for valid service name)
    $cloudRunName = "moneymaker-$($ServiceName -replace '_', '-')"
    Write-Host "  Deploying to Cloud Run as $cloudRunName..." -ForegroundColor White
    gcloud run deploy $cloudRunName `
        --image=$imageName `
        --region=$env:REGION `
        --project=$env:PROJECT_ID `
        --platform=managed `
        --allow-unauthenticated `
        --memory=512Mi `
        --cpu=1 `
        --min-instances=0 `
        --max-instances=3 `
        --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=$($env:PROJECT_ID),GCP_REGION=$($env:REGION)" `
        --quiet
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to deploy to Cloud Run" -ForegroundColor Red
        return $false
    }
    
    # Get service URL
    $url = gcloud run services describe $cloudRunName `
        --region=$env:REGION `
        --project=$env:PROJECT_ID `
        --format='value(status.url)' 2>$null
    
    Write-Host "  Deployed: $url" -ForegroundColor Green
    return $true
}

$deployedCount = 0
$failedCount = 0

switch ($Service.ToLower()) {
    "orchestrator" { 
        if (Deploy-Service -ServiceName "orchestrator") { $deployedCount++ } else { $failedCount++ }
    }
    "scraper" { 
        if (Deploy-Service -ServiceName "scraper") { $deployedCount++ } else { $failedCount++ }
    }
    "ai_suggester" { 
        if (Deploy-Service -ServiceName "ai_suggester") { $deployedCount++ } else { $failedCount++ }
    }
    "ai-suggester" { 
        if (Deploy-Service -ServiceName "ai_suggester") { $deployedCount++ } else { $failedCount++ }
    }
    "trader" { 
        if (Deploy-Service -ServiceName "trader") { $deployedCount++ } else { $failedCount++ }
    }
    "monitor" { 
        if (Deploy-Service -ServiceName "monitor") { $deployedCount++ } else { $failedCount++ }
    }
    "dashboard" { 
        if (Deploy-Service -ServiceName "dashboard") { $deployedCount++ } else { $failedCount++ }
    }
    "all" {
        foreach ($svc in @("orchestrator", "scraper", "ai_suggester", "trader", "monitor", "dashboard")) {
            if (Deploy-Service -ServiceName $svc) { $deployedCount++ } else { $failedCount++ }
        }
    }
    default {
        Write-Host "Unknown service: $Service" -ForegroundColor Red
        Write-Host "Available: orchestrator, scraper, ai_suggester, trader, monitor, dashboard, all"
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($failedCount -eq 0) {
    Write-Host "   Deployment Complete!" -ForegroundColor Green
} else {
    Write-Host "   Deployment Finished with Errors" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployed: $deployedCount" -ForegroundColor Green
if ($failedCount -gt 0) {
    Write-Host "  Failed:   $failedCount" -ForegroundColor Red
}
Write-Host ""

# Show deployed services
Write-Host "Deployed Services:" -ForegroundColor Yellow
gcloud run services list --project=$env:PROJECT_ID --region=$env:REGION --filter="metadata.name~moneymaker" --format="table(metadata.name,status.url)" 2>$null

Write-Host ""
