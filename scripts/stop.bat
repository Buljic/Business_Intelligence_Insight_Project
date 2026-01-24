@echo off
echo ============================================
echo E-Commerce BI Platform - Shutdown Script
echo ============================================
echo.

echo Stopping all services...
docker-compose down

echo.
echo All services stopped.
echo.
echo To remove all data volumes, run:
echo   docker-compose down -v
echo.
pause
