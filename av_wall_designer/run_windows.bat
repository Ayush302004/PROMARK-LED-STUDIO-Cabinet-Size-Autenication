@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -m venv .venv
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Open http://127.0.0.1:5000 in your browser after the server starts.
echo Keep this window open. Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" app.py
pause
exit /b
:failed
echo Setup failed. Confirm Python is installed and read README.md.
pause
exit /b 1
