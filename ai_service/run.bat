@echo off
echo Starting FastAPI Backend...
if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
) else (
    echo Virtual environment (.venv) not found. Please ensure it is created.
    pause
    exit /b
)
uvicorn app:app --host 0.0.0.0 --port 8001
pause
