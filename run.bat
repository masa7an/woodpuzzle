@echo off
cd /d "%~dp0"

REM Use the venv python directly. Do not use activate.bat: it only checks
REM that the folder exists, so it reports success even when the base
REM interpreter is gone.
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Create it first:
    echo     py -3.12 -m venv venv
    echo     venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting local test server...
echo Open http://localhost:8000/ in your browser
echo Press Ctrl+C to stop the server
echo.
"venv\Scripts\python.exe" -m pygbag .
pause
