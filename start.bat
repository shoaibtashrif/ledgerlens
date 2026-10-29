@echo off
echo ============================================================
echo ⚡ Starting LedgerLens AP Copilot (Windows)
echo ============================================================

where docker >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo 🐳 Docker detected! Launching container...
    docker compose up --build -d
    echo.
    echo ✅ Running at: http://localhost:8000
    echo To stop: docker compose down
    pause
    exit /b 0
)

echo 🐍 Docker not found. Using local Python...
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo 🚀 Starting server...
echo Access LedgerLens at: http://localhost:8000
python run.py
pause
