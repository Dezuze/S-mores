import os
import shutil
import uuid
import asyncio
import json
import logging
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# ML / Audio imports
# Note: In a real scenario, we would load these lazily or on startup.
# Attempting to import them. If optional models (like tts/asr) are missing, we might mock them or warn.
try:
    import torch
    import librosa
    import soundfile as sf
except ImportError:
    print("Warning: Audio libraries not found. Audio features may fail.")

# Placeholder for LLM integration
# from openai import OpenAI # Example

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration & HF LLM ---

LLM_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://127.0.0.1:8001") # Default port for local model server

import google.generativeai as genai

if LLM_API_KEY:
    genai.configure(api_key=LLM_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
else:
    gemini_model = None

async def generate_text(prompt: str) -> str:
    """
    Generate text using Hugging Face API.
    """
    logger.info(f"LLM Prompt: {prompt}")

    if not gemini_model:
         logger.warning("No GEMINI_API_KEY found. Using static backups.")
         # STRICT RULE: Local model is for ANALYSIS ONLY. Not generation.
         return ""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        # Fallback if safety filters block it or other error
        return ""

async def analyze_response(text: str, audio_path: str = None) -> dict:
    """
    Analyze a response using external API (primary) or local models (fallback).
    """
    # External API URL (LocalTunnel)
    EXTERNAL_API_URL = "https://happy-parks-wave.loca.lt"
    
    # 1. Try external API first
    transcription = ""
    flags = []
    features = {}
    external_analysis = None
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Helper to correctly hit the external API
            async def try_external(endpoint, form_data=None, files=None, json_payload=None):
                # Endpoint should be the relative path, e.g., "analyze/text"
                url = f"{EXTERNAL_API_URL}/{endpoint}"
                
                try:
                    kwargs = {"headers": {"Bypass-Tunnel-Reminder": "true"}}
                    if form_data:
                        kwargs["data"] = form_data
                    if files:
                        kwargs["files"] = files
                    if json_payload:
                        kwargs["json"] = json_payload
                    
                    # DEBUG: Print exact request details
                    print(f"--- TRY_EXTERNAL {endpoint} ---")
                    print(f"URL: {url}")
                    print(f"KWARGS: {kwargs}")
                    
                    resp = await client.post(url, **kwargs)
                    
                    if resp.status_code == 200:
                        return resp
                    else:
                        logger.warning(f"Error {resp.status_code} on {url}: {resp.text}")
                except Exception as ex:
                    logger.warning(f"Exception on {url}: {ex}")
                return None

            if audio_path and os.path.exists(audio_path):
                # Audio analysis via external API
                # CONTRACT: Input Format: UploadFile field named 'file' (from provided code)
                logger.info(f"Sending audio to external API (/analyze/audio)...")
                with open(audio_path, "rb") as f:
                    # 'file' is the key expected by the server's analyze_audio endpoint
                    upload_files = {"file": (os.path.basename(audio_path), f, "audio/webm")}
                    # Note: Endpoint is /analyze/audio (US spelling)
                    resp = await try_external("analyze/audio", files=upload_files)
                
                if resp and resp.status_code == 200:
                    external_analysis = resp.json()
                    print(f"\n[GOOGLE COLAB AUDIO RESPONSE]: {external_analysis}\n")
                    
                    # CONTRACT: Output Format: { "transcript": "...", "analysis": { "predicted_label": "...", "probability": ... } }
                    transcription = external_analysis.get("transcript", "")
                    
                    # Map analysis
                    analysis_data = external_analysis.get("analysis", {})
                    label = analysis_data.get("predicted_label", "unknown")
                    prob = analysis_data.get("probability", 0.0)
                    
                    # Internal Mapping Logic
                    if str(label).lower() in ["label_1", "1", "dyslexia", "positive"]:
                         # It predicted dyslexia
                         external_analysis["dyslexic_prob"] = prob
                    else:
                         # It predicted normal/control
                         external_analysis["dyslexic_prob"] = 1.0 - prob if prob > 0.5 else 0.0
                    
                    logger.info(f"External API audio analysis successful")
            
            elif text:
                # Text analysis via external API
                # CONTRACT: Input Format: JSON {"text": "..."} (from provided code TextRequest)
                logger.info(f"Sending text to external API (/analyze/text)...")
                # Use json=payload, NOT form_data
                resp = await try_external("analyze/text", json_payload={"text": text})

                if resp and resp.status_code == 200:
                    external_analysis = resp.json()
                    print(f"\n[GOOGLE COLAB TEXT RESPONSE]: {external_analysis}\n")
                    
                    # CONTRACT: Output Format: { "predicted_label": "...", "probability": ... }
                    label = external_analysis.get("predicted_label", "unknown")
                    prob = external_analysis.get("probability", 0.0)
                    
                    if str(label).lower() in ["label_1", "1", "dyslexia", "positive"]:
                         external_analysis["dyslexic_prob"] = prob
                    else:
                         external_analysis["dyslexic_prob"] = 1.0 - prob if prob > 0.5 else 0.0

                    logger.info(f"External API text analysis successful")
    
    except Exception as e:
        logger.warning(f"External API failed (all attempts), falling back to local model: {e}")
        external_analysis = None


    
    # 2. Fallback to local model server if external API failed
    if not external_analysis:
        if audio_path and os.path.exists(audio_path):
            logger.info(f"Using local model server for audio: {MODEL_SERVER_URL}/analyze/audio")
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    with open(audio_path, "rb") as f:
                        files = {"file": (os.path.basename(audio_path), f, "audio/webm")}
                        resp = await client.post(f"{MODEL_SERVER_URL}/analyze/audio", files=files)
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            transcription = data.get("transcription", "")
                            flags = data.get("analysis", {}).get("flags", [])
                            features = data.get("features", {})
                            logger.info(f"Local model audio analysis successful")
                        else:
                            logger.error(f"Local model error: {resp.status_code} - {resp.text}")
                            transcription = "[Error in local audio processing]"
            except Exception as e:
                logger.error(f"Failed to connect to local model server: {e}")
                transcription = "[Local model server unreachable]"
    
    content_to_analyze = text if text else transcription
    
    # 3. Generate comprehensive analysis using Gemini OR Derived from External Data
    analysis_text = "Assessment completed."
    score = 0  # Initialize to 0 to track if it gets updated
    
    # CALCULATE SCORE FROM EXTERNAL DATA IF AVAILABLE
    if external_analysis:
        # Text Logic
        if "dyslexic_prob" in external_analysis:
            dyslexic_risk = external_analysis.get("dyslexic_prob", 0)
            # Inverse score: High risk = Low score
            score = int((1.0 - dyslexic_risk) * 100)
            if score < 60: 
                flags.append("High Dyslexia Risk")
                analysis_text = f"We detected patterns common in dyslexia (Risk: {int(dyslexic_risk*100)}%)."
            elif score < 80:
                analysis_text = "Reading patterns are mostly normal with slight deviations."
            else:
                analysis_text = "Reading patterns indicate standard development."

        # Audio Logic
        if "audio_features" in external_analysis:
             if "Potential Hyperactivity" in flags or "Potential Inattention" in flags:
                 score = min(score if score > 0 else 85, 70) 
                 analysis_text += " Signs of attention variance detected."
    
    # If score is still 0 (no external data or it didn't set score), use Gemini
    if score == 0 and LLM_API_KEY and content_to_analyze:
        try:
            prompt = (
                f"Analyze this response for a child's language assessment.\n"
                f"Transcript: '{content_to_analyze}'\n"
                f"If the text is empty or nonsense, give a low score (10-30). "
                f"If it is a good sentence, give a high score (80-100).\n"
                f"Task: Provide a valid JSON with keys 'score' (integer 0-100) and 'feedback' (string)."
            )
            output = await generate_text(prompt)
            
            import json
            import re
            json_match = re.search(r'\{[^}]+\}', output)
            if json_match:
                parsed = json.loads(json_match.group())
                score = parsed.get('score', 75) # Default to 75 if parsing field fails
                analysis_text = parsed.get('feedback', output)
            else:
                # Fallback if no JSON found
                score = 75
                analysis_text = output
        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            score = 70 # Fallback on error

    # Final Failsafe if everything failed
    if score == 0:
        # Simple heuristic based on length
        word_count = len(content_to_analyze.split())
        if word_count > 3: score = 80
        else: score = 40
        analysis_text = "Basic analysis completed."
            
    return {
        "text": content_to_analyze,
        "transcription": transcription,
        "score": score,
        "feedback": analysis_text,
        "flags": flags,
        "features": features,
        "external_data": external_analysis  # Include full external API response
    }

# --- Database Setup ---
import sqlite3
from datetime import datetime

DB_NAME = "app.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER)''')
    # Sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions 
                 (id TEXT PRIMARY KEY, user_id INTEGER, type TEXT, 
                  timestamp DATETIME, category TEXT, summary TEXT, analysis TEXT)''')
    # Chat History (Persistence)
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(DB_NAME)

# --- CHATBOT LOGIC ---

# Global in-memory cache
SESSIONS = {}

class ChatStartRequest(BaseModel):
    session_id: str

class ChatResponseRequest(BaseModel):
    session_id: str
    answer: str

@app.post('/chat/start')
async def chat_start(req: ChatStartRequest):
    sid = req.session_id
    # SESSIONS is now just a cache for active state, ensure it exists
    if sid not in SESSIONS:
        # Try to recover from DB if needed, or fail
        return JSONResponse({"error": "session not found"}, 404)
    
    # Initialize Chat History in RAM
    SESSIONS[sid]['chat_history'] = []
    
    # Initial Question
    initial_q = "How often do you feel overwhelmed by your daily tasks?"
    
    # Save to DB
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)", (sid, 'bot', initial_q))
    conn.commit()
    conn.close()

    SESSIONS[sid]['chat_history'].append({"role": "bot", "content": initial_q})
    return {"message": initial_q}

@app.post('/chat/response')
async def chat_response(req: ChatResponseRequest):
    sid = req.session_id
    if sid not in SESSIONS:
        return JSONResponse({"error": "session not found"}, 404)
    
    history = SESSIONS[sid].get('chat_history', [])
    
    # 1. Save User Answer
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)", (sid, 'user', req.answer))
    conn.commit() # Commit user answer first
    
    history.append({"role": "user", "content": req.answer})
    
    # Check if we should end (Limit to 14 turns for ~10 questions)
    if len(history) >= 14: 
        SESSIONS[sid]['ready'] = False
        asyncio.create_task(analyze_chat_session(sid))
        conn.close()
        return {"done": True}

    # Generate Next Question
    context = "\n".join([f"{h['role']}: {h['content']}" for h in history])
    prompt = (
        f"You are an empathetic ai companion for a mental health screening with a child.\n"
        f"History:\n{context}\n\n"
        f"Task: Ask ONE simple, NEW follow-up question to the child based on their last answer. If the topic is exhausted, switch to a compatible new topic (school, friends, home, sleep).\n"
        f"Rules:\n"
        f"- Output ONLY the question text.\n"
        f"- Do NOT use JSON or lists like [].\n"
        f"- Do NOT prefix with 'Bot:'.\n"
        f"- STRICTLY Do NOT repeat any of these previous questions: {[h['content'] for h in history if h['role'] == 'bot']}\n"
    )
    
    # Fallback Pool
    fallbacks = [
        "Do you have trouble sleeping at night?",
        "Do you often feel worried about school?",
        "Is it easy for you to make new friends?",
        "Do you sometimes feel sad without a reason?",
        "Do you enjoy playing games with others?",
        "Do you get angry easily?",
        "Do you feel safe at home?"
    ]
    
    used_questions = [h['content'] for h in history if h['role'] == 'bot']
    available_fallbacks = [f for f in fallbacks if f not in used_questions]
    if not available_fallbacks:
         available_fallbacks = ["How are you feeling right now?"]

    try:
        next_q_raw = await generate_text(prompt)
        next_q = next_q_raw.strip()
        for bad in ["[]", "['", "']", "Bot:", "AI:"]:
            next_q = next_q.replace(bad, "")
        next_q = next_q.strip()
        
        if len(next_q) < 5 or next_q in used_questions:
            raise ValueError("Response invalid")
            
    except Exception as e:
        print(f"Chat Gen Error: {e}")
        import random
        next_q = random.choice(available_fallbacks)
        
    # 2. Save Bot Question
    c.execute("INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)", (sid, 'bot', next_q))
    conn.commit()
    conn.close()

    history.append({"role": "bot", "content": next_q})
    SESSIONS[sid]['chat_history'] = history
    
    return {"done": False, "message": next_q}

async def analyze_chat_session(sid):
    # Fetch History from DB to be safe
    conn = get_db()
    c = conn.cursor()
    
    # Identify User
    c.execute("SELECT user_id FROM sessions WHERE id=?", (sid,))
    row = c.fetchone()
    user_id = row[0] if row else None
    
    # Fetch Historical Context (Last 3 sessions)
    history_context = ""
    if user_id:
        c.execute('''SELECT timestamp, category, summary FROM sessions 
                     WHERE user_id=? AND id != ? AND category IS NOT NULL 
                     ORDER BY timestamp DESC LIMIT 3''', (user_id, sid))
        rows = c.fetchall()
        if rows:
            history_context = "PREVIOUS SESSIONS:\n"
            for r in rows:
                history_context += f"- {r[0]}: {r[1]} ({r[2]})\n"
    
    # Current Conversation
    history = SESSIONS[sid].get('chat_history', [])
    full_conversation = "\n".join([f"{h['role']}: {h['content']}" for h in history])
    
    prompt = (
        f"Analyze this mental health screening conversation with a child:\n{full_conversation}\n\n"
        f"{history_context}\n"
        f"Context: The child answered questions using a Likert scale (Least Likely to Most Likely).\n"
        f"Task: Evaluate their responses for signs of Anxiety or Depression.\n"
        f"If 'PREVIOUS SESSIONS' are provided, specifically compare the current state to the past. Are they improving or declining?\n"
        f"Provide a JSON output with:\n"
        f"1. 'category': One of ['Good', 'Moderate', 'Needs Attention']\n"
        f"2. 'summary': A short, encouraging message for the child.\n"
        f"3. 'analysis': A 2-3 sentence professional observation for the parent. Mention trend if applicable.\n"
        f"Return ONLY the raw JSON."
    )
    
    cat = "Moderate"
    summary = "We have recorded your responses."
    analysis = "Assessment complete."

    try:
        raw = await generate_text(prompt)
        # Parse JSON
        clean_json = raw.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        import json
        data = json.loads(clean_json)
        cat = data.get("category", "Moderate")
        summary = data.get("summary", summary)
        analysis = data.get("analysis", analysis)
    except Exception as e:
        print(f"Analysis Error: {e}")
        # Fallback
        if "Attention" in raw: cat = "Needs Attention"
        elif "Good" in raw: cat = "Good"

    # Save Result to DB
    c.execute('''UPDATE sessions SET category=?, summary=?, analysis=? WHERE id=?''', 
              (cat, summary, analysis, sid))
    conn.commit()
    conn.close()

    SESSIONS[sid]['result'] = {
        "name": SESSIONS[sid]['info'].get('name'),
        "age": SESSIONS[sid]['info'].get('age'),
        "category": cat,
        "summary": summary,
        "analysis": analysis
    }
    SESSIONS[sid]['ready'] = True
    print(f"DB Analysis Ready for {sid}: {cat}")

# --- END CHATBOT LOGIC ---

class StartRequest(BaseModel):
    name: Optional[str]
    age: Optional[int]
    role: Optional[str]
    test_type: Optional[str] = "language" # 'language' or 'mental'

# --- Endpoints ---

@app.post('/start')
async def start(req: StartRequest):
    session_id = str(uuid.uuid4())
    
    # 1. DB: Find or Create User
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name=? AND age=?", (req.name, req.age))
        row = c.fetchone()
        
        if row:
            user_id = row[0]
            # logging.info(f"Welcome back user {user_id}")
        else:
            c.execute("INSERT INTO users (name, age) VALUES (?, ?)", (req.name, req.age))
            user_id = c.lastrowid
            
        # 2. DB: Create Session
        c.execute("INSERT INTO sessions (id, user_id, type, timestamp) VALUES (?, ?, ?, ?)", 
                  (session_id, user_id, req.test_type, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error in /start: {e}")
        return JSONResponse({"error": f"Database error: {str(e)}"}, status_code=500)

    # 3. Memory Cache (Active Session)
    SESSIONS[session_id] = {
        "info": req.dict(),
        "answers": [],
        "ready": False,
        "type": req.test_type
    }

    if req.test_type == 'mental':
        return {"session_id": session_id, "questions": [], "redirect": "chat.html"}

    # Language Assessment Logic
    # Generate 10 questions with mixed types (Audio for Reading, Text for Writing/Comprehension)
    prompt = (
        f"Generate exactly 10 tasks for a {req.age or 7}-year-old child's language assessment. "
        f"Mix 5 'read aloud' tasks (sentences to read) and 5 'writing' tasks (simple questions to answer). "
        f"Return a strict JSON list of objects. Each object must have:\n"
        f"- 'text': The sentence or question.\n"
        f"- 'type': 'audio' (for reading tasks) or 'text' (for writing tasks).\n"
        f"Example output: [{{'text': 'Read this.', 'type': 'audio'}}, {{'text': 'What is this?', 'type': 'text'}}]"
    )
    
    questions = []
    try:
        # 1. Attempt LLM generation
        raw_text = await generate_text(prompt)
        # Clean potential markdown
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        import json
        questions = json.loads(clean_json)
        
        # Validate structure
        if not isinstance(questions, list): raise ValueError("Not a list")
    except Exception as e:
        print(f"LLM Generation failed: {e}")
        questions = []
    
    # Robust Fallback to ensure 10 questions
    if len(questions) < 10:
        backups = [
            {"text": "The quick brown fox jumps over the dog.", "type": "audio"},
            {"text": "What is your favorite color and why?", "type": "text"},
            {"text": "Reading books helps me learn new words.", "type": "audio"},
            {"text": "Write a sentence about a cat.", "type": "text"},
            {"text": "The sun shines brightly in the blue sky.", "type": "audio"},
            {"text": "Describe your best friend.", "type": "text"},
            {"text": "I like to play games with my friends.", "type": "audio"},
            {"text": "What do you do after school?", "type": "text"},
            {"text": "Eating vegetables is good for my health.", "type": "audio"},
            {"text": "Name three animals you see at the zoo.", "type": "text"}
        ]
        # Fill strictly up to 10
        questions.extend(backups[len(questions):10])

    # Truncate if too many
    structured_questions = questions[:10]
    SESSIONS[session_id]['questions'] = structured_questions
    return {"session_id": session_id, "questions": structured_questions}

@app.post('/response')
async def response(
    session_id: str = Form(...),
    question_index: int = Form(...),
    question: str = Form(...),
    question_type: str = Form(...),
    answer_text: Optional[str] = Form(None),
    answer_audio: Optional[UploadFile] = File(None)
):
    """Accept a single question response."""
    if session_id not in SESSIONS:
        return JSONResponse({"error": "invalid session_id"}, status_code=400)

    # Save audio if present
    audio_path = None
    if answer_audio:
        os.makedirs("uploads", exist_ok=True)
        filename = f"{session_id}_{question_index}.webm"
        audio_path = os.path.join("uploads", filename)
        with open(audio_path, "wb") as f:
            f.write(await answer_audio.read())

    # Analyze immediately
    analysis = await analyze_response(answer_text, audio_path)

    # Store raw data AND analysis result
    item = {
        "question_index": question_index,
        "question": question,
        "question_type": question_type,
        "answer_text": answer_text,
        "audio_path": audio_path,
        "analysis": analysis # Store the result immediately
    }
    SESSIONS[session_id]['answers'].append(item)
    return {"status": "ok", "partial_analysis": analysis}

class SubmitPayload(BaseModel):
    session_id: str
    answers: List[dict] # This might just be client-side echo; we rely on server store primarily if we saved incrementally.

@app.post('/submit')
async def submit(payload: SubmitPayload):
    """Trigger final analysis."""
    sid = payload.session_id
    if sid not in SESSIONS:
        return JSONResponse({"error": "invalid session_id"}, status_code=400)

    # In a real app, we might use payload.answers if we didn't store incrementally. 
    # But since /response saves files, we should use server state for files.
    # We'll merge or just trust server state for audio files.
    
    answers = SESSIONS[sid]['answers']
    
    # Process all answers
    processed_results = []
    total_score = 0
    all_flags = []
    
    for ans in answers:
        # Check if analysis was already done (incremental)
        if 'analysis' in ans:
            analysis = ans['analysis']
        else:
            # Fallback for old items or if immediate analysis failed quietly
            analysis = await analyze_response(ans.get('answer_text'), ans.get('audio_path'))
            ans['analysis'] = analysis # Store it back to avoid re-analysis

        processed_results.append({
            "question": ans['question'],
            "analysis": analysis
        })
        total_score += analysis.get('score', 0)
        if 'flags' in analysis:
            all_flags.extend(analysis['flags'])
    
    avg_score = total_score / len(answers) if answers else 0
    
    # --- REVAMPED AGGREGATION LOGIC ---
    # Compile a Master Transcript of all responses to get "Actual Results"
    master_transcript = ""
    for i, res in enumerate(processed_results):
        q_text = res['question']
        a_analysis = res['analysis']
        transcription = a_analysis.get('transcription', '') or a_analysis.get('text', '')
        score = a_analysis.get('score', 0)
        feedback = a_analysis.get('feedback', '')
        
        master_transcript += f"Q{i+1}: {q_text}\nResponse: {transcription}\nScore: {score}\nNotes: {feedback}\n\n"

    # Default values
    category = "Pending"
    summary = "Analysis in progress..."
    analysis_text = "Integrating results..."
    
    if LLM_API_KEY:
        try:
            # Ask Gemini to Aggregate into a Single Final Result
            prompt = (
                f"You are a professional language therapist. Review this full assessment transcript for a {SESSIONS[sid]['info'].get('age', 7)}-year-old child.\n\n"
                f"{master_transcript}\n"
                f"Task: Provide a FINAL JSON output with these exact keys:\n"
                f"- 'category': One of ['Excellent', 'Good', 'Needs Attention'] based on overall performance.\n"
                f"- 'summary': A one-line summary of the child's performance (start with '✔' or '⚠').\n"
                f"- 'analysis': A detailed 3-4 sentence professional evaluation citing specific strengths/weaknesses from the transcript. Do NOT mention 'random' or 'simulated'. Be direct and helpful.\n"
            )
            
            raw_output = await generate_text(prompt)
            
            # Robust JSON parsing
            import json
            import re
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                category = parsed.get('category', "Good")
                summary = parsed.get('summary', "✔ Good effort shown.")
                analysis_text = parsed.get('analysis', raw_output)
            else:
                # Fallback if JSON fails but text is generated
                analysis_text = raw_output
                if avg_score > 80: category = "Excellent"
                elif avg_score > 60: category = "Good"
                else: category = "Needs Attention"
                summary = "✔ Assessment completed."

        except Exception as e:
            logger.error(f"Aggregated analysis generation failed: {e}")
            analysis_text = "Automated analysis aggregation failed, but individual scores are recorded."
            if avg_score > 60: category = "Good"
            else: category = "Needs Attention"
    
    # Save Language Result to DB
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE sessions SET category=?, summary=?, analysis=? WHERE id=?", 
                  (category, summary, analysis_text, sid))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Update failed: {e}")

    result = {
        "name": SESSIONS[sid]['info'].get('name'),
        "age": SESSIONS[sid]['info'].get('age'),
        "category": category,
        "summary": summary,
        "analysis": analysis_text,
        "detail": {
            "score": avg_score,
            "breakdown": processed_results
        }
    }
    SESSIONS[sid]['result'] = result
    SESSIONS[sid]['ready'] = True

    return {"status": "processing_started"}

@app.get('/result')
async def result(session_id: str):
    if session_id not in SESSIONS:
        return JSONResponse({"error": "invalid session_id"}, status_code=400)
    if not SESSIONS[session_id]['ready']:
        return JSONResponse({"status": "pending"}, status_code=202)
    return SESSIONS[session_id]['result']

@app.get('/teacher/all_results')
async def get_all_results():
    conn = get_db()
    c = conn.cursor()
    
    # Fetch all users
    c.execute("SELECT id, name, age FROM users ORDER BY name")
    users = c.fetchall()
    
    data = []
    for u in users:
        uid, name, age = u
        
        # Fetch sessions for this user
        c.execute('''SELECT id, type, timestamp, category, summary, analysis 
                     FROM sessions WHERE user_id=? ORDER BY timestamp DESC''', (uid,))
        sessions = []
        rows = c.fetchall()
        
        latest_risk = "Good" # Default
        
        for r in rows:
            sid, stype, ts, cat, summ, anal = r
            sessions.append({
                "session_id": sid,
                "type": stype,
                "timestamp": ts,
                "category": cat,
                "summary": summ,
                "analysis": anal
            })
            # Determine risk based on latest mental health session
            if stype == "mental" and cat and sessions[0]['session_id'] == sid:
                latest_risk = cat
                
        data.append({
            "user_id": uid,
            "name": name,
            "age": age,
            "latest_risk": latest_risk,
            "sessions": sessions
        })
        
    conn.close()
    return data

@app.get('/')
async def root():
    return {"status": "backend up (AI Integrated)"}
