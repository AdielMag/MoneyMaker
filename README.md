<div align="center">

# 💰 MoneyMaker

### AI-Powered Polymarket Trading System

<p>
  <strong>Automated prediction market trading with Gemini AI analysis</strong>
</p>

<p>
  <a href="https://github.com/AdielMag/MoneyMaker/actions/workflows/test.yml">
    <img src="https://github.com/AdielMag/MoneyMaker/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://codecov.io/gh/AdielMag/MoneyMaker">
    <img src="https://codecov.io/gh/AdielMag/MoneyMaker/branch/main/graph/badge.svg" alt="codecov">
  </a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/GCP-Cloud%20Run-4285F4?logo=google-cloud" alt="GCP Cloud Run">
  <img src="https://img.shields.io/badge/AI-Gemini%201.5-8E75B2?logo=google" alt="Gemini AI">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT">
</p>

<p>
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#running-locally-with-docker">Docker</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#api-reference">API</a> •
  <a href="#deployment">Deployment</a>
</p>

</div>

---

## Overview

MoneyMaker is an automated trading system for [Polymarket](https://polymarket.com) prediction markets. It uses **Google Gemini AI** to analyze markets and identify profitable short-term trading opportunities.

The system supports both **real money** and **simulated (paper) trading** modes, with automatic position monitoring, stop-loss, and take-profit execution. All services can run locally with Docker or be deployed to GCP Cloud Run.

---

## Features

- **Smart Market Filtering** - Filter by volume, liquidity, time-to-resolution, and categories
- **AI-Powered Suggestions** - Gemini analyzes market data for profitable opportunities
- **Paper Trading Mode** - Test strategies with simulated money stored in Firestore
- **Real Trading Mode** - Execute actual trades on Polymarket (when enabled)
- **Risk Management** - Configurable stop-loss and take-profit thresholds
- **RESTful API** - Query markets, positions, and trigger workflows on demand
- **Microservices Architecture** - 6 independent services
- **CI/CD Pipeline** - Automated testing and deployment via GitHub Actions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Cloud Scheduler                              │
│              (Discovery: */30 min, Monitor: */5 min)                 │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Orchestrator Service                            │
│                   (Coordinates all workflows)                        │
└────────┬──────────────┬──────────────┬──────────────┬───────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│  Scraper   │  │     AI     │  │   Trader   │  │  Monitor   │
│  Service   │  │  Suggester │  │  Service   │  │  Service   │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │               │
      ▼               ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌─────────────────────────────┐
│ Polymarket │  │  Gemini    │  │         Firestore           │
│    API     │  │  1.5 Pro   │  │  (Positions, Wallets, etc)  │
└────────────┘  └────────────┘  └─────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Service                               │
│         (Web UI - fetches data from Orchestrator API)                │
└─────────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Description |
|---------|-------------|
| **Orchestrator** | Main API gateway, coordinates all workflows |
| **Scraper** | Fetches and filters Polymarket markets |
| **AI Suggester** | Gemini-powered market analysis and suggestions |
| **Trader** | Order execution for real/fake trading |
| **Monitor** | Position monitoring and automatic sell triggers |
| **Dashboard** | Web UI for viewing fake trading data and metrics |

---

## Quick Start

### Prerequisites

- **Docker Desktop** (recommended) or **Python 3.11+**
- **GCP Account** with billing enabled
- **Polymarket API credentials**
- **Gemini API key**

### Recommended: Run with Docker

The easiest way to run all services locally is using Docker Compose. See the [Running Locally with Docker](#running-locally-with-docker) section for complete setup instructions.

**Quick Docker start:**
```bash
# 1. Clone and setup
git clone https://github.com/AdielMag/MoneyMaker.git
cd MoneyMaker
cp config/env.example .env
# Edit .env with your credentials

# 2. Add GCP credentials
# Place your service account JSON as: gcp-credentials.json

# 3. Start all services
docker compose up -d

# 4. Access services
# Orchestrator API: http://localhost:8000/docs
# Dashboard: http://localhost:8080
```

### Alternative: Run Locally (Python)

```bash
# Clone and setup
git clone https://github.com/AdielMag/MoneyMaker.git
cd MoneyMaker
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure
cp config/env.example .env
# Edit .env with your credentials

# Run tests
pytest

# Start orchestrator
uvicorn services.orchestrator.main:app --reload --port 8000
```

---

## Running Locally with Docker

Run all services locally using Docker Compose. All services will connect to Firestore and Polymarket APIs (external), but run in Docker containers on your local machine.

### Prerequisites

- **Docker Desktop** installed and running
  - Ensure Docker is in your PATH (restart Docker Desktop if needed)
  - Verify with: `docker --version`
- **GCP Service Account JSON** file for Firestore authentication
- **API Credentials** (Polymarket, Gemini)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AdielMag/MoneyMaker.git
   cd MoneyMaker
   ```

2. **Create environment file:**
   ```bash
   # Copy the example file
   cp config/env.example .env
   
   # Edit .env with your credentials
   # Required: GCP_PROJECT_ID, POLYMARKET_API_KEY, POLYMARKET_API_SECRET,
   #           POLYMARKET_WALLET_ADDRESS, GEMINI_API_KEY
   ```

3. **Add GCP credentials:**
   ```bash
   # Place your GCP service account JSON file in the project root
   # Name it: gcp-credentials.json
   # 
   # To create a service account key:
   # gcloud iam service-accounts keys create gcp-credentials.json \
   #   --iam-account=YOUR_SERVICE_ACCOUNT_EMAIL
   ```

4. **Start all services:**
   ```bash
   docker compose up -d
   ```

### Accessing Services

Once started, services are available at:

| Service | URL | Description |
|---------|-----|-------------|
| **Orchestrator** | http://localhost:8000 | Main API (Swagger docs at `/docs`) |
| **Dashboard** | http://localhost:8080 | Web UI dashboard |
| **Scraper** | http://localhost:8001 | Scraper service API |
| **Trader** | http://localhost:8002 | Trader service API |
| **Monitor** | http://localhost:8003 | Monitor service API |
| **AI Suggester** | http://localhost:8004 | AI Suggester service API |

### Common Commands

```bash
# Start all services
docker compose up -d

# View logs (all services)
docker compose logs -f

# View logs for specific service
docker compose logs -f orchestrator

# Stop all services
docker compose down

# Rebuild and restart (after code changes)
docker compose up -d --build

# Restart a specific service
docker compose restart orchestrator

# Check service status
docker compose ps
```

> **Note:** If you're using Docker Desktop, use `docker compose` (with space). For older standalone installations, use `docker-compose` (with hyphen).

### Debugging with VS Code/Cursor

You can debug the services running in Docker containers directly from your IDE:

1. **Enable debug mode** by setting environment variables in `.env`:
   ```bash
   DEBUGPY_ENABLED=true
   DEBUGPY_WAIT_FOR_ATTACH=false  # Set to true to wait for debugger before starting
   ```

2. **Restart the orchestrator service** with debug enabled:
   ```bash
   docker compose restart orchestrator
   ```

3. **Attach debugger** in VS Code/Cursor:
   - Open the Run and Debug panel (F5)
   - Select "Python: Attach to Orchestrator (Docker)"
   - Click the play button or press F5
   - Set breakpoints in your code and they'll be hit!

**Alternative:** Use the debug override file:
```bash
docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d
```

**Note:** The debug port (5678) is already exposed in `docker-compose.yml`. Code changes are reflected immediately via volume mounts, so you can set breakpoints and debug live code.

### Troubleshooting

**Services won't start:**
- Check that Docker Desktop is running
- Verify `.env` file exists and has all required variables
- Ensure `gcp-credentials.json` exists in project root
- Check logs: `docker compose logs <service-name>`

**Connection errors to Firestore:**
- Verify `GCP_PROJECT_ID` in `.env` matches your GCP project
- Ensure `gcp-credentials.json` has proper permissions
- Check that Firestore API is enabled in your GCP project

**Dashboard can't connect to Orchestrator:**
- Ensure orchestrator service is running: `docker compose ps`
- Check orchestrator logs: `docker compose logs orchestrator`
- Verify network connectivity: `docker compose exec dashboard ping orchestrator`

**Port already in use:**
- Stop conflicting services on ports 8000-8004, 8080
- Or modify port mappings in `docker-compose.yml`

**Code changes not reflecting:**
- Volumes are mounted, so code changes should be immediate
- If not, restart the service: `docker compose restart <service-name>`
- For dependency changes, rebuild: `docker compose up -d --build <service-name>`

**`docker` command not found:**
- Docker Desktop may not be in your PATH. Add it temporarily:
  ```powershell
  $env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"
  ```
- To make it permanent, add Docker to your system PATH:
  1. Open System Properties → Environment Variables
  2. Edit "Path" under "User variables" or "System variables"
  3. Add: `C:\Program Files\Docker\Docker\resources\bin`
  4. Restart PowerShell
- Or restart Docker Desktop, which usually adds itself to PATH

**`docker-compose` command not found:**
- Docker Desktop uses `docker compose` (with space) instead of `docker-compose` (with hyphen)
- Use `docker compose` for all commands, or create an alias: `Set-Alias docker-compose docker compose`

---

## Configuration

Configuration is managed through environment variables (`.env` file) and `config/config.yaml`. Environment variables take precedence over YAML values.

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `POLYMARKET_API_KEY` | Polymarket API key |
| `POLYMARKET_API_SECRET` | Polymarket API secret |
| `POLYMARKET_WALLET_ADDRESS` | Your Polymarket wallet address |
| `GEMINI_API_KEY` | Google Gemini API key |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REAL_MONEY_ENABLED` | `false` | Enable real money trading |
| `FAKE_MONEY_ENABLED` | `true` | Enable paper trading |
| `MAX_BET_AMOUNT` | `20.0` | Maximum bet per trade |
| `MAX_POSITIONS` | `5` | Maximum concurrent positions |
| `STOP_LOSS_PERCENT` | `-10` | Stop-loss threshold (%) |
| `TAKE_PROFIT_PERCENT` | `20` | Take-profit threshold (%) |

### config/config.yaml

Main configuration file with trading parameters, market filters, and AI settings. See `config/config.yaml` for all available options. Key settings:

- **Workflows**: Enable/disable real or fake money trading
- **Trading**: Bet amounts, position limits, stop-loss/take-profit thresholds
- **Market Filters**: Volume, liquidity, time-to-resolution, excluded categories
- **AI**: Model selection, confidence thresholds, max suggestions

---

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/status` | System status with balances and config |
| `POST` | `/workflow/discover` | Trigger market discovery and betting |
| `POST` | `/workflow/monitor` | Check positions and execute sells |
| `POST` | `/workflow/toggle` | Enable/disable workflows |
| `GET` | `/markets` | Query filtered markets |
| `GET` | `/positions/{mode}` | Get open positions (fake/real) |
| `GET` | `/balance/{mode}` | Get current balance (fake/real) |
| `GET` | `/config` | Get system configuration |
| `GET` | `/docs` | Interactive API documentation (Swagger) |

### Dashboard

The dashboard service provides a web interface for monitoring fake trading activity.

**URL:** http://localhost:8080 (when running locally with Docker)

**Features:**
- Real-time wallet balance display
- Open positions with P&L tracking
- Filtered markets overview
- AI suggestions with confidence scores
- Auto-refresh every 30 seconds
- Responsive design with dark theme

### Example Requests

**Examples:**

```bash
# Check system health
curl http://localhost:8000/health

# Trigger discovery workflow (fake money mode)
curl -X POST http://localhost:8000/workflow/discover \
  -H "Content-Type: application/json" \
  -d '{"mode": "fake"}'

# Get fake money balance
curl http://localhost:8000/balance/fake

# Get open positions
curl http://localhost:8000/positions/fake

# Get system status
curl http://localhost:8000/status
```

**PowerShell:**
```powershell
# Trigger discovery workflow
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/workflow/discover" `
  -ContentType "application/json" `
  -Body '{"mode": "fake"}'
```

---

## Deployment

📖 **For detailed deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

> **Note:** For local development, use [Docker Compose](#running-locally-with-docker) instead of deploying to GCP.

### Quick Deploy to GCP Cloud Run

**Windows (PowerShell):**
```powershell
# Set environment variables
$env:PROJECT_ID = "your-gcp-project-id"
$env:REGION = "us-central1"
$env:GCP_PROJECT_ID = $env:PROJECT_ID

# Authenticate with GCP
gcloud auth login
gcloud config set project $env:PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com firestore.googleapis.com `
  secretmanager.googleapis.com artifactregistry.googleapis.com

# Set up secrets (interactive prompts)
.\scripts\setup_secrets.ps1

# Create Firestore database
gcloud firestore databases create --location=us-central1

# Initialize Firestore data
python scripts/init_firestore.py

# Deploy all services
.\scripts\deploy.ps1 -Service all -Tag v1.0.0
```

**macOS/Linux:**
```bash
# Set environment variables
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export GCP_PROJECT_ID="$PROJECT_ID"

# Authenticate with GCP
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com firestore.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com

# Set up secrets (interactive prompts)
./scripts/setup_secrets.sh

# Create Firestore database
gcloud firestore databases create --location=us-central1

# Initialize Firestore data
python scripts/init_firestore.py

# Deploy all services
./scripts/deploy.sh all v1.0.0
```

### Set Up Cloud Scheduler

After deployment, set up automated workflow triggers:

```powershell
$ORCH_URL = gcloud run services describe moneymaker-orchestrator `
  --region=us-central1 --format='value(status.url)'

# Discovery workflow - every 30 minutes
gcloud scheduler jobs create http discovery-fake `
  --location=us-central1 `
  --schedule="*/30 * * * *" `
  --uri="$ORCH_URL/workflow/discover" `
  --http-method=POST `
  --headers="Content-Type=application/json" `
  --message-body='{"mode":"fake"}'

# Monitor workflow - every 5 minutes  
gcloud scheduler jobs create http monitor-fake `
  --location=us-central1 `
  --schedule="*/5 * * * *" `
  --uri="$ORCH_URL/workflow/monitor" `
  --http-method=POST `
  --headers="Content-Type=application/json" `
  --message-body='{"mode":"fake"}'
```

---

## Project Structure

```
MoneyMaker/
├── services/
│   ├── orchestrator/     # Main API and workflow coordinator
│   ├── scraper/          # Market data scraping
│   ├── ai_suggester/     # Gemini AI integration
│   ├── trader/           # Order execution
│   ├── monitor/          # Position monitoring
│   └── dashboard/        # Web UI dashboard
├── shared/               # Shared utilities and clients
│   ├── config.py         # Configuration management
│   ├── models.py         # Pydantic data models
│   ├── polymarket_client.py
│   ├── firestore_client.py
│   └── gemini_client.py
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── e2e/              # End-to-end tests
│   └── fixtures/         # Test data
├── config/
│   ├── config.yaml       # Main configuration
│   └── env.example       # Environment template
├── scripts/
│   ├── deploy.ps1        # Windows deployment
│   ├── deploy.sh         # Linux/macOS deployment
│   ├── setup_secrets.ps1 # Windows secrets setup
│   ├── setup_secrets.sh  # Linux/macOS secrets setup
│   └── init_firestore.py # Database initialization
├── infra/                # Terraform infrastructure
├── docs/                 # Documentation
├── docker-compose.yml    # Local Docker setup
└── .github/workflows/    # CI/CD pipelines
```

---

## Testing

| Test Type | Command | Description |
|-----------|---------|-------------|
| All | `pytest` | Run all tests with coverage |
| Unit | `pytest tests/unit -v` | Fast, isolated tests |
| Integration | `pytest tests/integration -m integration` | Service integration |
| E2E | `pytest tests/e2e -m e2e` | Full workflow tests |
| Coverage | `pytest --cov --cov-report=html` | Generate HTML report |

---

## Workflows

### Discovery Workflow
1. Check available balance
2. Scrape live Polymarket markets
3. Apply filters (volume, liquidity, time, categories)
4. Send to Gemini AI for analysis
5. Place buy orders on top suggestions

### Monitor Workflow
1. Get all open positions
2. Fetch current market prices
3. Calculate profit/loss percentage
4. Execute sell if stop-loss or take-profit triggered

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure tests pass (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**Trading involves significant risk of loss.** This software is provided for educational and experimental purposes only. 

- Always start with **fake money mode** to test strategies
- Never invest more than you can afford to lose
- The authors are not responsible for any financial losses
- Past performance does not guarantee future results

---

<div align="center">
  <sub>Built with ❤️ using Python, FastAPI, GCP Cloud Run, and Gemini AI</sub>
</div>
