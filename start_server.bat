@echo off
echo Starting Payment Reconciliation System...
echo.
echo Make sure PostgreSQL is running (docker compose -f docker-compose-postgres.yml up -d)
echo.
uvicorn main:app --reload --host 0.0.0.0 --port 8000

