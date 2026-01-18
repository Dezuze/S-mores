@echo off
cd ai_service
echo Starting AI Service (Model Server)...
uvicorn app:app --reload --port 8001
pause
