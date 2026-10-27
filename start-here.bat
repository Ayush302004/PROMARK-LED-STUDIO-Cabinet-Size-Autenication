@echo off
cd /d "%~dp0av_wall_designer"

if not exist "app.py" (
    echo ERROR: av_wall_designer\app.py was not found.
    pause
    exit /b 1
)

if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" app.py
) else (
    py app.py
)

pause
