# Audio Question Flow Guide

## Overview
The language assessment includes **mixed question types**: some require text responses, others require audio recordings. Audio responses are automatically sent to the external API for advanced analysis.

---

## Question Distribution

### Language Assessment (5 Questions Total)
- **Question 1**: Text response
- **Question 2**: 🎤 **Audio response** (record and speak)
- **Question 3**: Text response
- **Question 4**: 🎤 **Audio response** (record and speak)
- **Question 5**: Text response

**Configuration**: Set in `backend/main.py` lines 500-510

---

## How Audio Questions Work

### 1. **Question Display**
When an audio question appears:
- Large question text displayed
- Audio recording interface shown
- Microphone button (red gradient)
- Recording status indicator

### 2. **Recording Process**
```
User clicks microphone → Browser requests permission
    ↓
Recording starts → Pulse animation on button
    ↓
User speaks (2-10 seconds recommended)
    ↓
User clicks stop → Recording saved as WebM
    ↓
User clicks submit → File uploaded to backend
```

### 3. **Backend Processing**
```python
# File: backend/main.py, Function: analyze_response()

1. Receive audio file (WebM format)
2. Try External API first:
   POST https://tender-onions-smoke.loca.lt/analyze/audio
   - Timeout: 15 seconds
   - Headers: Bypass-Tunnel-Reminder: true
   
3. If external fails, fallback to Local Model:
   POST http://localhost:8001/analyze/audio
   
4. Parse response:
   - Transcription (what was said)
   - Flags (slow_reader, high_pause, etc.)
   - Features (speech rate, duration, etc.)
   - Classification scores
```

### 4. **External API Request**
```python
async with httpx.AsyncClient(timeout=15.0) as client:
    with open(audio_path, "rb") as f:
        files = {"file": (filename, f, "audio/webm")}
        resp = await client.post(
            "https://tender-onions-smoke.loca.lt/analyze/audio",
            files=files,
            headers={"Bypass-Tunnel-Reminder": "true"}
        )
```

### 5. **Response Processing**
External API returns:
```json
{
  "transcription": "The quick brown fox...",
  "analysis": {
    "flags": ["slow_reader", "high_pause"]
  },
  "features": {
    "duration_seconds": 5.2,
    "speech_rate_wps": 1.8,
    "pause_ratio": 0.35
  },
  "classification": [
    {"label": "LABEL_0", "score": 0.95}
  ]
}
```

---

## Results Display

### Overall Results Page
Shows aggregated analysis:
- Overall score (0-100)
- Category (Excellent/Good/Needs Attention)
- Summary message
- Detailed analysis from Gemini AI

### Detailed Breakdown
For each question (including audio):
```
┌─────────────────────────────────┐
│ Question 2              85/100  │ ← Score color-coded
├─────────────────────────────────┤
│ Good pronunciation and clarity. │ ← AI feedback
│ Speech rate is appropriate.     │
│                                 │
│ Flags: None                     │ ← Detected issues
│ External Analysis: LABEL_0 95%  │ ← External API result
└─────────────────────────────────┘
```

---

## File Storage

### Audio Files Location
- **Path**: `backend/uploads/`
- **Format**: `audio_{session_id}_{question_index}.webm`
- **Example**: `audio_abc123_1.webm`

### Cleanup
Audio files are stored for the session duration. Consider implementing cleanup:
```python
# Optional: Add to backend/main.py
import os
from datetime import datetime, timedelta

def cleanup_old_audio():
    upload_dir = "uploads"
    for file in os.listdir(upload_dir):
        file_path = os.path.join(upload_dir, file)
        if os.path.getmtime(file_path) < (datetime.now() - timedelta(days=7)).timestamp():
            os.remove(file_path)
```

---

## Testing Audio Flow

### Manual Test
1. Open `http://localhost:3000`
2. Select **Student** → Enter name/age
3. Choose **Language Assessment**
4. Complete questions:
   - Q1: Type text answer
   - Q2: Click mic → Speak → Stop → Submit
   - Q3: Type text answer
   - Q4: Click mic → Speak → Stop → Submit
   - Q5: Type text answer
5. Wait for loading page
6. View results with detailed breakdown

### Check Backend Logs
```bash
# Terminal running backend (port 8000)
# Look for these messages:

INFO: Sending audio to external API: https://tender-onions-smoke.loca.lt/analyze/audio
INFO: External API audio analysis successful

# OR if fallback:

WARNING: External API failed, falling back to local model: ...
INFO: Using local model server for audio: http://localhost:8001/analyze/audio
INFO: Local model audio analysis successful
```

---

## Troubleshooting

### Microphone Not Working
- **Check browser permissions**: Allow microphone access
- **Try different browser**: Chrome/Edge recommended
- **Check console**: F12 → Console for errors

### Audio Not Uploading
- **Check file size**: WebM should be < 10MB
- **Verify backend running**: `http://localhost:8000/` should respond
- **Check uploads folder**: Should exist in `backend/uploads/`

### External API Timeout
- **Normal behavior**: System automatically falls back to local model
- **Check logs**: Backend will show "falling back to local model"
- **Results still work**: Local model provides analysis

### No Results Displayed
- **Check localStorage**: F12 → Application → Local Storage → `result`
- **Verify loading page**: Should poll `/result` endpoint
- **Check backend logs**: Look for "processing_started" message

---

## Configuration

### Change Audio Question Positions
Edit `backend/main.py` around line 505:
```python
# Current: Questions 2 and 4 are audio
question_type = "audio" if i in [1, 3] else "text"

# Example: Make questions 1, 3, 5 audio
question_type = "audio" if i in [0, 2, 4] else "text"

# Example: All questions audio
question_type = "audio"
```

### Adjust External API Timeout
Edit `backend/main.py` line 95:
```python
# Current: 15 seconds
async with httpx.AsyncClient(timeout=15.0) as client:

# Increase to 30 seconds
async with httpx.AsyncClient(timeout=30.0) as client:
```

---

## Summary

✅ **Audio questions are fully implemented**  
✅ **External API integration working**  
✅ **Automatic fallback to local model**  
✅ **Results display detailed breakdown**  
✅ **Apple design DNA maintained**

The system is production-ready for audio-based language assessments!
