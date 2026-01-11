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
  <a href="#configuration">Configuration</a> •
  <a href="#api-reference">API</a> •
  <a href="#deployment">Deployment</a>
</p>

</div>

---

## Overview

MoneyMaker is an automated trading system for [Polymarket](https://polymarket.com) prediction markets. It uses **Google Gemini AI** to analyze markets and identify profitable short-term trading opportunities.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| 🔍 **Market Discovery** | Scrapes and filters live Polymarket markets based on configurable criteria |
| 🤖 **AI Analysis** | Uses Gemini 1.5 Pro to identify markets with high profit potential |
| 💵 **Dual Mode Trading** | Supports both real money and simulated (paper) trading |
| 📊 **Position Monitoring** | Automatic stop-loss (-10%) and take-profit (+20%) order execution |
| ⏰ **Scheduled Execution** | GCP Cloud Scheduler triggers workflows at configurable intervals |

---

## Features

- **Smart Market Filtering** - Filter by volume, liquidity, time-to-resolution, and categories
- **AI-Powered Suggestions** - Gemini analyzes market data for profitable opportunities
- **Paper Trading Mode** - Test strategies with simulated money stored in Firestore
- **Real Trading Mode** - Execute actual trades on Polymarket (when enabled)
- **Risk Management** - Configurable stop-loss and take-profit thresholds
- **RESTful API** - Query markets, positions, and trigger workflows on demand
- **Microservices Architecture** - 5 independent services deployed on Cloud Run
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
```

### Services

| Service | Description |
|---------|-------------|
| **Orchestrator** | Main API gateway, coordinates all workflows |
| **Scraper** | Fetches and filters Polymarket markets |
| **AI Suggester** | Gemini-powered market analysis and suggestions |
| **Trader** | Order execution for real/fake trading |
| **Monitor** | Position monitoring and automatic sell triggers |

> All services run on Cloud Run with port 8080 and auto-scale to zero when idle.

---

## Quick Start

### Prerequisites

- Python 3.11+
- GCP Account with billing enabled
- Docker Desktop (for local builds)
- Polymarket API credentials
- Gemini API key

### Installation

**Windows (PowerShell):**
```powershell
# Clone the repository
git clone https://github.com/AdielMag/MoneyMaker.git
cd MoneyMaker

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development/testing

# Copy environment template
Copy-Item config\env.example .env
# Edit .env with your credentials
```

**macOS/Linux:**
```bash
# Clone the repository
git clone https://github.com/AdielMag/MoneyMaker.git
cd MoneyMaker

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development/testing

# Copy environment template
cp config/env.example .env
# Edit .env with your credentials
```

### Run Tests

```bash
# Run all tests with coverage
pytest

# Run only unit tests
pytest tests/unit -v

# Run with coverage report
pytest --cov --cov-report=html

# Open coverage report
open coverage_html/index.html  # macOS
start coverage_html/index.html  # Windows
```

### Local Development

```bash
# Set environment variables
export GCP_PROJECT_ID="your-project-id"  # Bash
$env:GCP_PROJECT_ID = "your-project-id"  # PowerShell

# Start the orchestrator service
uvicorn services.orchestrator.main:app --reload --port 8000

# Access API docs
# Open http://localhost:8000/docs
```

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GCP_PROJECT_ID` | Google Cloud project ID | Yes |
| `POLYMARKET_API_KEY` | Polymarket API key | Yes |
| `POLYMARKET_API_SECRET` | Polymarket API secret | Yes |
| `POLYMARKET_WALLET_ADDRESS` | Your Polymarket wallet address | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `REAL_MONEY_ENABLED` | Enable real money trading | No (default: false) |
| `FAKE_MONEY_ENABLED` | Enable paper trading | No (default: true) |

### config/config.yaml

```yaml
workflows:
  real_money:
    enabled: false                    # ⚠️ Keep false until ready!
  fake_money:
    enabled: true
    initial_balance: 1000.0           # Starting paper money

trading:
  max_bet_amount: 20.0                # Maximum per bet
  max_positions: 5                    # Max concurrent positions
  sell_thresholds:
    stop_loss_percent: -10            # Sell if down 10%
    take_profit_percent: 20           # Sell if up 20%

market_filters:
  min_volume: 500                     # Minimum trading volume
  max_time_to_resolution_hours: 2     # Markets resolving within 2 hrs
  min_liquidity: 500
  excluded_categories:
    - sports
    - entertainment
  min_price: 0.05                     # Skip < 5¢ prices
  max_price: 0.95                     # Skip > 95¢ prices

ai:
  model: "gemini-1.5-pro"
  max_suggestions: 3                  # Top 3 picks per run
  confidence_threshold: 0.75          # Require 75%+ confidence
```

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
| `GET` | `/docs` | Interactive API documentation |

### Example Requests

**PowerShell:**
```powershell
# Check system health
Invoke-RestMethod "https://YOUR-ORCHESTRATOR-URL/health"

# Trigger discovery workflow (fake money mode)
Invoke-RestMethod -Method POST `
  -Uri "https://YOUR-ORCHESTRATOR-URL/workflow/discover" `
  -ContentType "application/json" `
  -Body '{"mode": "fake"}'

# Get fake money balance
Invoke-RestMethod "https://YOUR-ORCHESTRATOR-URL/balance/fake"

# Get open positions
Invoke-RestMethod "https://YOUR-ORCHESTRATOR-URL/positions/fake"
```

**Bash/cURL:**
```bash
# Trigger discovery workflow
curl -X POST https://YOUR-ORCHESTRATOR-URL/workflow/discover \
  -H "Content-Type: application/json" \
  -d '{"mode": "fake"}'

# Get system status
curl https://YOUR-ORCHESTRATOR-URL/status
```

---

## Deployment

📖 **For detailed deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

### Quick Deploy (Windows PowerShell)

```powershell
# 1. Set environment variables
$env:PROJECT_ID = "your-gcp-project-id"
$env:REGION = "us-central1"
$env:GCP_PROJECT_ID = $env:PROJECT_ID

# 2. Authenticate with GCP
gcloud auth login
gcloud config set project $env:PROJECT_ID

# 3. Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# 4. Set up secrets (interactive prompts)
.\scripts\setup_secrets.ps1

# 5. Create Firestore database
gcloud firestore databases create --location=us-central1

# 6. Initialize Firestore data
python scripts/init_firestore.py

# 7. Deploy all services
.\scripts\deploy.ps1 -Service all -Tag v1.0.0
```

### Quick Deploy (macOS/Linux)

```bash
# 1. Set environment variables
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export GCP_PROJECT_ID="$PROJECT_ID"

# 2. Authenticate with GCP
gcloud auth login
gcloud config set project $PROJECT_ID

# 3. Enable required APIs
gcloud services enable run.googleapis.com firestore.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com

# 4. Set up secrets (interactive prompts)
./scripts/setup_secrets.sh

# 5. Create Firestore database
gcloud firestore databases create --location=us-central1

# 6. Initialize Firestore data
python scripts/init_firestore.py

# 7. Deploy all services
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
│   └── monitor/          # Position monitoring
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
