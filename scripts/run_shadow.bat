@echo off
cd /d "C:\test\stock prediction"
if not exist "logs" mkdir "logs"
".venv\Scripts\python.exe" scripts\run_shadow_pipeline.py >> "logs\shadow_run.log" 2>&1
