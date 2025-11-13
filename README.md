# Automated Payment Reconciliation System

Built an Automated Payment Reconciliation System (FastAPI, Postgres, RapidFuzz) that ingests ledger and bank CSVs, streams rows with server-side DB cursors, auto-matches transactions via exact and fuzzy rules, and exposes a reviewer API.

## Features

- **Memory-efficient processing**: Uses PostgreSQL server-side cursors to stream large datasets without loading entire tables into memory
- **Multi-strategy matching**: Exact matching, fuzzy reference matching, and fuzzy payee matching with configurable thresholds
- **RESTful API**: FastAPI endpoints for uploading data, running reconciliation, and managing matches
- **Manual review workflow**: Confirm or unmatch reconciliation results with reviewer tracking

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- pip

### Installation

1. Clone or navigate to the project directory

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a PostgreSQL database:
```bash
createdb payment_reconciliation
```

4. Set up the database schema:
```bash
psql -d payment_reconciliation -f models.sql
```

5. Create a `.env` file in the project root:
```
DATABASE_URL=postgresql://username:password@localhost:5432/payment_reconciliation
```

Replace `username`, `password`, and database name as needed.

### Running the Application

**Quick Start (Windows):**
```bash
# 1. Start PostgreSQL
docker compose -f docker-compose-postgres.yml up -d

# 2. Create schema (one-time setup)
Get-Content models.sql | docker exec -i payment_recon_db psql -U postgres -d payment_reconciliation

# 3. Create .env file (if not exists)
echo DATABASE_URL=postgresql://postgres:postgres@localhost:5432/payment_reconciliation > .env

# 4. Start the server
uvicorn main:app --reload
```

Or use the provided batch files:
```bash
# Run setup (one-time)
setup_and_test.bat

# Start server
start_server.bat
```

The API will be available at `http://localhost:8000`

## CSV Format

Both payment and bank CSV files should have the following header:
```
id,amount,date,reference,payee
```

Example row:
```
1,1234.56,2025-01-15,Invoice #INV-1023,Acme Corp.
```

Sample CSV files are provided in `sample_data/` directory.

## API Endpoints

### Upload Payments
```bash
curl -F "file=@sample_data/payments.csv" http://localhost:8000/upload/payments
```

### Upload Bank Transactions
```bash
curl -F "file=@sample_data/bank.csv" http://localhost:8000/upload/bank
```

### Run Reconciliation
```bash
curl -X POST http://localhost:8000/reconcile
```

### Get Matches
```bash
# Get all recent matches
curl http://localhost:8000/matches

# Get only confirmed matches
curl http://localhost:8000/matches?status=confirmed

# Get only pending matches
curl http://localhost:8000/matches?status=pending

# Limit results
curl http://localhost:8000/matches?limit=50
```

### Confirm Match
```bash
curl -X POST http://localhost:8000/matches/1/confirm \
  -H "Content-Type: application/json" \
  -d '{"reviewer":"Shivansh","action":"confirm"}'
```

### Unmatch
```bash
curl -X POST http://localhost:8000/matches/1/confirm \
  -H "Content-Type: application/json" \
  -d '{"reviewer":"Shivansh","action":"unmatch"}'
```

## Demo Script

Quick test workflow:

```bash
# 1. Upload sample data
curl -F "file=@sample_data/payments.csv" http://localhost:8000/upload/payments
curl -F "file=@sample_data/bank.csv" http://localhost:8000/upload/bank

# 2. Run reconciliation
curl -X POST http://localhost:8000/reconcile

# 3. View matches
curl http://localhost:8000/matches

# 4. Confirm a match (replace 1 with actual match ID)
curl -X POST http://localhost:8000/matches/1/confirm \
  -H "Content-Type: application/json" \
  -d '{"reviewer":"Shivansh","action":"confirm"}'
```

## Matching Rules

The reconciliation engine uses three matching strategies:

1. **Exact Match (Score: 100)**: Amount matches exactly, date within ±1 day, and normalized reference is identical
2. **Fuzzy Reference Match (Score: 90)**: Amount matches exactly and reference similarity ≥ 90%
3. **Fuzzy Payee Match (Score: 80)**: Amount within ±0.5% tolerance and payee similarity ≥ 85%

Configuration thresholds can be adjusted in `matcher.py` (CONFIG dictionary).

## Testing

Run unit tests:
```bash
pytest tests/test_matcher.py -v
```

## Architecture

- **main.py**: FastAPI application with REST endpoints
- **db.py**: Database connection management and server-side cursor streaming
- **matcher.py**: Matching engine with normalization and scoring logic
- **models.sql**: PostgreSQL schema definitions

The system uses PostgreSQL named cursors (`cursor(name=...)`) to stream rows in batches (default 500 rows), ensuring memory efficiency even with large datasets.

## License

MIT

