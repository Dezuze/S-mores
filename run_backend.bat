@echo off
cd backend
echo Starting Backend (FastAPI)...
echo Ensure your AI Service is running on Port 8001 first!
uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
