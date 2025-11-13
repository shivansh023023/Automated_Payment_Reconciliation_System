@echo off
echo ========================================
echo Payment Reconciliation System Setup
echo ========================================
echo.

echo Step 1: Starting PostgreSQL container...
docker compose -f docker-compose-postgres.yml up -d
timeout /t 5 /nobreak >nul

echo.
echo Step 2: Creating database schema...
Get-Content models.sql | docker exec -i payment_recon_db psql -U postgres -d payment_reconciliation
if errorlevel 1 (
    echo [ERROR] Failed to create schema
    exit /b 1
)

echo.
echo Step 3: Creating .env file...
if not exist .env (
    echo DATABASE_URL=postgresql://postgres:postgres@localhost:5432/payment_reconciliation > .env
    echo [OK] .env file created
) else (
    echo [INFO] .env file already exists
)

echo.
echo Step 4: Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    exit /b 1
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To start the server, run:
echo   uvicorn main:app --reload
echo.
echo Or use: start_server.bat
echo.
echo To test the system, run:
echo   python test_system.py
echo.
pause

