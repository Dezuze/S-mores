import os
import io
import torch
import librosa
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification, 
    WhisperProcessor, 
    WhisperForConditionalGeneration,
    pipeline
)

app = FastAPI()

# --- 1. Load Text Model (Dyslexia) ---
print("Loading Text Model...")
try:
    TEXT_MODEL_PATH = "./text_classification_model"
    text_tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL_PATH)
    text_model = AutoModelForSequenceClassification.from_pretrained(TEXT_MODEL_PATH)
    text_pipeline = pipeline("text-classification", model=text_model, tokenizer=text_tokenizer)
    print("Text Model Loaded.")
except Exception as e:
    print(f"Error loading text model: {e}")
    text_pipeline = None

# --- 2. Load Audio Model (Whisper ASR) ---
print("Loading Audio Model...")
try:
    ASR_MODEL_PATH = "./asr_model"
    # Using pipeline for easier ASR
    asr_pipeline = pipeline("automatic-speech-recognition", model=ASR_MODEL_PATH)
    print("Audio Model Loaded.")
except Exception as e:
    print(f"Error loading audio model: {e}")
    asr_pipeline = None

# --- Pydantic Models ---
class TextAnalysisRequest(BaseModel):
    text: str

# --- Endpoints ---

@app.get("/")
def health_check():
    return {"status": "AI Model Server Running"}

@app.post("/analyze/text")
async def analyze_text(req: TextAnalysisRequest):
    """
    Classify text as 'normal' or 'dyslexic'.
    """
    if not text_pipeline:
        raise HTTPException(status_code=503, detail="Text model not loaded")
    
    try:
        # Run classification
        results = text_pipeline(req.text, top_k=None) 
        # Results format: [{'label': 'LABEL_0', 'score': 0.9}, ...]
        # Assuming LABEL_0 = normal, LABEL_1 = dyslexic or similar. 
        # Ideally we map this based on config. But raw scores work for now.
        
        # Simple mapping heuristic if labels are generic
        scores = {res['label']: res['score'] for res in results}
        
        return {
            "classification": results,
            "summary": "Analysis complete",
            "scores": scores
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/audio")
async def analyze_audio(file: UploadFile = File(...)):
    """
    Transcribe audio + Extract Features (Speech Rate, Pause Ratio) -> Detect ADHD flags.
    """
    if not asr_pipeline:
        raise HTTPException(status_code=503, detail="Audio model not loaded")
    
    try:
        # Read file
        content = await file.read()
        
        # 1. Transcription (ASR)
        # Pipeline expects bytes or filepath. Passing bytes might need wrapping.
        # Ideally, save temp file for librosa stability too.
        temp_filename = f"temp_{file.filename}"
        with open(temp_filename, "wb") as f:
            f.write(content)
            
        transcription_result = asr_pipeline(temp_filename)
        transcribed_text = transcription_result.get("text", "")
        
        # 2. Audio Feature Extraction (Librosa)
        try:
            # We use librosa to load. It might need ffmpeg for webm.
            y, sr = librosa.load(temp_filename, sr=16000) # Whisper prefers 16kHz
        except Exception as e:
            logger.error(f"Librosa load failed: {e}. Attempting fallback with soundfile.")
            # Fallback for some formats
            y, sr = sf.read(temp_filename)
            if len(y.shape) > 1: y = y.mean(axis=1) # Mono
            if sr != 16000: y = librosa.resample(y, orig_sr=sr, target_sr=16000); sr = 16000
            
        duration = librosa.get_duration(y=y, sr=sr)
        
        # Remove silence to find pauses
        # top_db=20 is standard for speech
        non_silent_intervals = librosa.effects.split(y, top_db=20)
        non_silent_duration = sum([(end - start) / sr for start, end in non_silent_intervals])
        
        silence_duration = max(0, duration - non_silent_duration)
        pause_ratio = silence_duration / duration if duration > 0 else 0
        
        # Speech Rate (Words per second)
        word_count = len(transcribed_text.split())
        speech_rate = word_count / duration if duration > 0 else 0
        
        # Cleanup
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        # 3. ADHD / Analysis Logic (Thresholds)
        # Hypotheses:
        # - High Pause Ratio (> 0.4) -> Inattention?
        # - Very Fast Speech (> 3.5 wps) -> Hyperactivity?
        # - Very Slow Speech (< 1.0 wps) -> Slow Reader?
        
        flags = []
        if speech_rate < 1.0:
            flags.append("slow_reader")
        if speech_rate > 3.0: # Fast talker
            flags.append("hyperactivity_flag")
        
        if pause_ratio > 0.4:
            flags.append("high_pause")
            flags.append("inattention_flag")
            
        return {
            "transcription": transcribed_text,
            "features": {
                "duration_seconds": round(duration, 2),
                "speech_rate_wps": round(speech_rate, 2),
                "pause_ratio": round(pause_ratio, 2)
            },
            "analysis": {
                "flags": flags,
                "is_adhd_risk": ("hyperactivity_flag" in flags or "inattention_flag" in flags)
            }
        }

    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

# Run with: uvicorn app:app --port 8001
