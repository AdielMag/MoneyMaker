<div align="center">

# MoneyMaker

### AI-Powered Polymarket Trading System

<p>
  <strong>Automated prediction market trading with Gemini AI analysis</strong>
</p>

<p>
  <a href="https://github.com/YOUR_USERNAME/MoneyMaker/actions/workflows/test.yml">
    <img src="https://github.com/YOUR_USERNAME/MoneyMaker/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://codecov.io/gh/YOUR_USERNAME/MoneyMaker">
    <img src="https://codecov.io/gh/YOUR_USERNAME/MoneyMaker/branch/main/graph/badge.svg" alt="Coverage">
  </a>
  <a href="https://github.com/YOUR_USERNAME/MoneyMaker/actions/workflows/deploy.yml">
    <img src="https://github.com/YOUR_USERNAME/MoneyMaker/actions/workflows/deploy.yml/badge.svg" alt="Deploy">
  </a>
</p>

<p>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/GCP-Cloud%20Run-4285F4?logo=google-cloud" alt="GCP Cloud Run">
  <img src="https://img.shields.io/badge/AI-Gemini-8E75B2?logo=google" alt="Gemini AI">
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
| **Market Discovery** | Scrapes and filters live Polymarket markets based on configurable criteria |
| **AI Analysis** | Uses Gemini to identify markets with high profit potential within 1 hour |
| **Dual Mode Trading** | Supports both real money and simulated (paper) trading |
| **Position Monitoring** | Automatic stop-loss (-15%) and take-profit (+30%) order execution |
| **Scheduled Execution** | GCP Cloud Scheduler triggers workflows at configurable intervals |

---

## Features

- **Smart Market Filtering** - Filter by volume, liquidity, time-to-resolution, and categories
- **AI-Powered Suggestions** - Gemini analyzes market data for profitable opportunities
- **Paper Trading Mode** - Test strategies with simulated money stored in Firestore
- **Real Trading Mode** - Execute actual trades on Polymarket
- **Risk Management** - Configurable stop-loss and take-profit thresholds
- **RESTful API** - Query markets, positions, and trigger workflows on demand
- **Full Test Coverage** - 80%+ code coverage with unit, integration, and e2e tests
- **CI/CD Pipeline** - Automated testing and deployment via GitHub Actions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Cloud Scheduler                              │
│                    (Triggers every X minutes)                        │
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
│    API     │  │    AI      │  │  (Positions, Wallets, etc)  │
└────────────┘  └────────────┘  └─────────────────────────────┘
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **Orchestrator** | 8000 | Main API, coordinates all workflows |
| **Scraper** | 8001 | Fetches and filters Polymarket markets |
| **AI Suggester** | 8002 | Gemini-powered market analysis |
| **Trader** | 8003 | Order execution for real/fake trading |
| **Monitor** | 8004 | Position monitoring and sell triggers |

---

## Quick Start

### Prerequisites

- Python 3.11+
- GCP Account with Firestore enabled
- Polymarket API credentials
- Gemini API key

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/MoneyMaker.git
cd MoneyMaker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development

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
open coverage_html/index.html
```

### Local Development

```bash
# Start the orchestrator service
uvicorn services.orchestrator.main:app --reload --port 8000

# Access API docs
open http://localhost:8000/docs
```

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GCP_PROJECT_ID` | Google Cloud project ID | Yes |
| `POLYMARKET_API_KEY` | Polymarket API key | Yes |
| `POLYMARKET_API_SECRET` | Polymarket API secret | Yes |
| `POLYMARKET_WALLET_ADDRESS` | Your wallet address | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `REAL_MONEY_ENABLED` | Enable real money trading | No (default: false) |
| `FAKE_MONEY_ENABLED` | Enable paper trading | No (default: true) |

### config.yaml

```yaml
workflows:
  real_money:
    enabled: false
    scheduler_cron: "0 */2 * * *"  # Every 2 hours
  fake_money:
    enabled: true
    scheduler_cron: "*/30 * * * *"  # Every 30 minutes
    initial_balance: 1000.0

trading:
  min_balance_to_trade: 10.0
  max_bet_amount: 50.0
  max_positions: 10
  sell_thresholds:
    stop_loss_percent: -15
    take_profit_percent: 30

market_filters:
  min_volume: 1000
  max_time_to_resolution_hours: 1
  min_liquidity: 500
  excluded_categories: ["sports", "entertainment"]

ai:
  model: "gemini-1.5-pro"
  max_suggestions: 5
  confidence_threshold: 0.7
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
| `GET` | `/positions/{mode}` | Get open positions |
| `GET` | `/balance/{mode}` | Get current balance |
| `GET` | `/config` | Get system configuration |

### Example Requests

```bash
# Trigger discovery workflow (fake money mode)
curl -X POST http://localhost:8000/workflow/discover \
  -H "Content-Type: application/json" \
  -d '{"mode": "fake"}'

# Get system status
curl http://localhost:8000/status

# Get fake money balance
curl http://localhost:8000/balance/fake

# Get open positions
curl http://localhost:8000/positions/fake
```

---

## Deployment

📖 **For detailed deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

### Quick Deploy

**Windows (PowerShell):**
```powershell
# 1. Set up environment
$env:PROJECT_ID = "your-gcp-project-id"
$env:REGION = "us-central1"

# 2. Set up secrets (interactive)
.\scripts\setup_secrets.ps1

# 3. Initialize Firestore
python scripts/init_firestore.py

# 4. Deploy all services
.\scripts\deploy.ps1 -Service all -Tag v1.0.0
```

**macOS/Linux (Bash):**
```bash
# 1. Set up environment
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# 2. Set up secrets (interactive)
./scripts/setup_secrets.sh

# 3. Initialize Firestore
python scripts/init_firestore.py

# 4. Deploy all services
./scripts/deploy.sh all v1.0.0
```

**Then set up Cloud Scheduler:**
```bash
cd infra && terraform init && terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="orchestrator_url=$(gcloud run services describe moneymaker-orchestrator --region=$REGION --format='value(status.url)')"
```

### Manual Deployment

```bash
# Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push Docker images
gcloud builds submit --config cloudbuild.yaml --substitutions=_TAG=v1.0.0

# Or deploy individually
docker build -t gcr.io/YOUR_PROJECT/orchestrator -f services/orchestrator/Dockerfile .
docker push gcr.io/YOUR_PROJECT/orchestrator

gcloud run deploy moneymaker-orchestrator \
  --image gcr.io/YOUR_PROJECT/orchestrator \
  --region us-central1 \
  --allow-unauthenticated
```

### CI/CD Pipeline

The project uses GitHub Actions for automated testing and deployment:

| Trigger | Action |
|---------|--------|
| Push to any branch | Run linting and tests |
| PR to main | Run tests with coverage report |
| Push to main | Run e2e tests, build images |
| Tag `v*` | Full deploy to Cloud Run |

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
│   ├── models.py         # Pydantic models
│   ├── polymarket_client.py
│   ├── firestore_client.py
│   └── gemini_client.py
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── config/               # Configuration files
├── infra/                # Terraform infrastructure
└── .github/workflows/    # CI/CD pipelines
```

---

## Testing

| Test Type | Command | Coverage Target |
|-----------|---------|-----------------|
| Unit | `pytest tests/unit` | 80% |
| Integration | `pytest tests/integration -m integration` | 70% |
| E2E | `pytest tests/e2e -m e2e` | - |
| All | `pytest` | 80% |

Coverage reports are automatically uploaded to [Codecov](https://codecov.io).

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure tests pass and coverage doesn't decrease
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Disclaimer

⚠️ **Trading involves risk.** This software is for educational purposes. Use real money mode at your own risk. The authors are not responsible for any financial losses.

---

<div align="center">
  <sub>Built with Python, FastAPI, GCP, and Gemini AI</sub>
</div>
