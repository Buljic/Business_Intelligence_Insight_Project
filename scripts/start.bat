@echo off
echo ============================================
echo E-Commerce BI Platform - Startup Script
echo ============================================
echo.

echo Checking Docker...
docker --version
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not running.
    echo Please install Docker Desktop and try again.
    pause
    exit /b 1
)

echo.
echo Starting all services...
docker-compose up -d

echo.
echo Waiting for services to initialize (60 seconds)...
timeout /t 60 /nobreak

echo.
echo ============================================
echo Services Status:
echo ============================================
docker-compose ps

echo.
echo ============================================
echo Access URLs:
echo ============================================
echo   n8n (ETL):       http://localhost:5678
echo                    Username: admin
echo                    Password: admin123
echo.
echo   Superset (BI):   http://localhost:8088
echo                    Username: admin
echo                    Password: admin123
echo.
echo   ML Service:      http://localhost:8000
echo                    API Docs: http://localhost:8000/docs
echo.
echo   PostgreSQL:      localhost:5432
echo                    Database: ecommerce_dw
echo                    Username: postgres
echo                    Password: postgres123
echo.
echo ============================================
echo Next Steps:
echo ============================================
echo 1. Open n8n at http://localhost:5678
echo 2. Create PostgreSQL credentials:
echo    - Host: postgres
echo    - Port: 5432
echo    - Database: ecommerce_dw
echo    - User: postgres
echo    - Password: postgres123
echo 3. Import and run Workflow A (CSV Ingestion)
echo 4. Import and run Workflow B (ETL Transforms)
echo 5. Import and run Workflow C (ML Pipeline)
echo 6. Open Superset and create dashboards
echo.
echo ============================================
pause
