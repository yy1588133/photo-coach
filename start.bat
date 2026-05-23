@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo.
echo ==========================================
echo      Photo Coach - AI Photography Coach
echo ==========================================
echo.

:: --- Check .env config ---
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        echo [!] backend\.env not found, copying from .env.example...
        copy "backend\.env.example" "backend\.env" >nul
        echo.
        echo [WARNING] Please edit backend\.env and set your DEFAULT_API_KEY
        echo           File: %~dp0backend\.env
        echo.
        start notepad "backend\.env"
        echo Press any key after editing...
        pause >nul
    ) else (
        echo [ERROR] backend\.env.example not found!
        pause
        exit /b 1
    )
)

:: --- Install Python deps ---
echo [*] Checking Python dependencies...
cd backend
pip install -r requirements.txt -q 2>nul
cd ..

:: --- Install Node deps ---
echo [*] Checking Node dependencies...
cd frontend
if not exist "node_modules" (
    echo [*] First run, installing frontend dependencies...
    call npm install
)
cd ..

:: --- Start Backend ---
echo.
echo [OK] Starting backend (port 8000)...
start "Photo Coach - Backend" cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0"

:: Wait for backend
echo [*] Waiting for backend...
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 goto wait_backend
echo [OK] Backend is ready

:: --- Start Frontend ---
echo [OK] Starting frontend (port 5173)...
start "Photo Coach - Frontend" cmd /c "cd /d %~dp0frontend && npx vite --host"

:: --- Open Browser ---
timeout /t 2 /nobreak >nul
echo [OK] Opening browser...
start http://localhost:5173

echo.
echo ==========================================
echo   Photo Coach is running!
echo.
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo.
echo   Closing this window will NOT stop services.
echo ==========================================
echo.
pause
