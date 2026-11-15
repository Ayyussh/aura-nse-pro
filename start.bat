@echo off
title AURA-NSE Pro Decision-Support Platform
color 0A

echo ========================================================
echo   AURA-NSE Pro - Indian Equities Decision Support
echo ========================================================
echo.
echo [1/3] Activating Python Virtual Environment...
call .venv\Scripts\activate.bat

echo [2/3] Checking SQLite Database & Schema...
python -m backend.db.init_db

echo [3/3] Launching AURA-NSE Pro Backend + Frontend Server...
echo.
echo Local Server starting on http://127.0.0.1:8000
echo Serving:
echo   - FastAPI Backend API at: http://127.0.0.1:8000/api
echo   - React 19 Frontend UI at: http://127.0.0.1:8000
echo   - WebSocket Feed at: ws://127.0.0.1:8000/ws
echo.
echo Opening default web browser to http://127.0.0.1:8000 ...
start http://127.0.0.1:8000

python -m backend.main
pause
