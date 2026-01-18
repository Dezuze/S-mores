# LingoSight - Technical Documentation

## Project Overview

**LingoSight** is an AI-powered educational assessment platform designed to evaluate children's language development and mental health through interactive questionnaires and conversational AI. The system uses machine learning models for speech analysis, text classification, and natural language understanding to provide comprehensive assessments.

### Key Features
- **Language Assessment**: Mixed text and audio response questionnaires for evaluating reading, pronunciation, and speech patterns
- **Mental Health Screening**: Conversational AI chatbot using Likert scale responses to assess emotional well-being
- **AI-Powered Analysis**: Integration with local ML models (ASR, text classification) and Gemini AI for comprehensive evaluation
- **Role-Based Access**: Separate interfaces for students and teachers with password-protected teacher dashboard
- **Real-time Processing**: Asynchronous analysis with loading states and result visualization

---

## System Architecture

### Three-Tier Architecture

```
┌─────────────────┐
│   Frontend      │  Port 3000 (HTTP Server)
│   HTML/CSS/JS   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Main Backend   │  Port 8000 (FastAPI)
│  - Gemini AI    │
│  - Session Mgmt │
│  - SQLite DB    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ML Model Server│  Port 8001 (FastAPI)
│  - ASR (Whisper)│
│  - Text Classify│
│  - TTS Models   │
└─────────────────┘
```

### Technology Stack

**Frontend:**
- Pure HTML5, CSS3, JavaScript (ES6+)
- No frameworks (vanilla JS for lightweight performance)
- Apple-inspired design system with glassmorphism
- LocalStorage for session management

**Backend (Main - Port 8000):**
- FastAPI (Python 3.9+)
- Google Gemini AI (gemini-pro model)
- SQLite database for persistence
- HTTPX for async HTTP requests
- CORS enabled for cross-origin requests

**ML Model Server (Port 8001):**
- FastAPI (Python 3.9+)
- Transformers (Hugging Face)
- PyTorch
- OpenAI Whisper (ASR)
- Librosa (audio processing)
- SoundFile (audio I/O)

---

## Directory Structure

```
hacka/
├── backend/                      # Main application backend
│   ├── main.py                   # FastAPI app with all endpoints
│   ├── .env                      # Environment variables (Gemini API key)
│   ├── requirements.txt          # Python dependencies
│   ├── app.db                    # SQLite database
│   ├── uploads/                  # Audio file storage
│   ├── test_api_status.py        # Gemini API verification script
│   └── test_endpoints.py         # API testing utilities
│
├── fastapi_backend_package/      # ML Model Server
│   ├── app.py                    # FastAPI ML endpoints
│   ├── requirements.txt          # ML dependencies
│   ├── Dockerfile                # Docker configuration
│   ├── run.bat                   # Windows startup script (port 8001)
│   ├── asr_model/                # Whisper ASR model files
│   ├── text_classification_model/# Dyslexia detection model
│   └── tts_model/                # Text-to-speech model
│
├── index.html                    # Landing page (role selection)
├── qn.html                       # Questionnaire page
├── chat.html                     # Mental health chat interface
├── loading.html                  # Processing/loading page
├── result.html                   # Results display page
├── teacher.html                  # Teacher dashboard
│
├── script.js                     # Main app logic
├── qn.js                         # Questionnaire logic
├── chat.js                       # Chat interface logic
├── config.js                     # API configuration
│
├── style.css                     # Main stylesheet
├── qn.css                        # Questionnaire styles
├── resultloading.css             # Loading/result styles
├── result_styles.css             # Result page specific styles
│
├── run_frontend.bat              # Frontend server launcher
├── run_backend.bat               # Backend launcher (legacy)
├── TESTING_GUIDE.md              # Manual testing instructions
└── test_external_api.py          # External API testing script
```

---

## Database Schema

### SQLite Tables

**users**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    age INTEGER
)
```

**sessions**
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,              -- UUID
    user_id INTEGER,                  -- Foreign key to users
    type TEXT,                        -- 'language' or 'mental'
    timestamp DATETIME,
    category TEXT,                    -- Result category
    summary TEXT,                     -- Result summary
    analysis TEXT                     -- Detailed analysis
)
```

**chat_history**
```sql
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,                  -- Foreign key to sessions
    role TEXT,                        -- 'bot' or 'user'
    content TEXT                      -- Message content
)
```

---

## API Endpoints

### Main Backend (Port 8000)

#### Session Management

**POST /start**
- **Purpose**: Initialize new assessment session
- **Request Body**:
  ```json
  {
    "name": "string",
    "age": integer,
    "role": "child",
    "test_type": "language" | "mental"
  }
  ```
- **Response**:
  ```json
  {
    "session_id": "uuid",
    "questions": [
      {"text": "question text", "type": "text" | "audio"}
    ],
    "redirect": "chat.html" (if mental health)
  }
  ```
- **Logic**: 
  - Creates user in DB if new
  - Generates 5 questions (positions 2 & 4 are audio type)
  - Uses Gemini AI for question generation with fallback

**POST /response**
- **Purpose**: Submit individual question response
- **Request**: FormData with:
  - `session_id`: string
  - `question_index`: integer
  - `question`: string
  - `question_type`: "text" | "audio"
  - `answer_text`: string (optional)
  - `answer_audio`: file (optional)
- **Response**: `{"status": "ok"}`
- **Logic**: Stores response in session, saves audio files to uploads/

**POST /submit**
- **Purpose**: Finalize assessment and trigger analysis
- **Request Body**:
  ```json
  {
    "session_id": "uuid",
    "answers": []
  }
  ```
- **Response**: `{"status": "processing_started"}`
- **Logic**:
  - Calls ML Model Server (port 8001) for each audio/text response
  - Aggregates scores and flags
  - Generates detailed analysis using Gemini AI
  - Stores result in session

**GET /result**
- **Purpose**: Retrieve assessment results
- **Query Params**: `session_id`
- **Response**:
  ```json
  {
    "name": "string",
    "age": integer,
    "category": "Excellent" | "Good" | "Needs Attention",
    "summary": "string",
    "analysis": "string",
    "detail": {
      "score": float,
      "breakdown": []
    }
  }
  ```
- **Status Codes**:
  - 200: Results ready
  - 202: Still processing

#### Mental Health Chat

**POST /chat/start**
- **Request**: `{"session_id": "uuid"}`
- **Response**: `{"message": "initial question"}`
- **Logic**: Initializes chat history with first question

**POST /chat/response**
- **Request**: `{"session_id": "uuid", "answer": "Likert scale value"}`
- **Response**: 
  ```json
  {
    "done": false,
    "message": "next question"
  }
  ```
- **Logic**:
  - Saves user response to DB
  - Generates next question using Gemini AI
  - After 8 turns, triggers async analysis
  - Compares with previous sessions for trend analysis

#### Teacher Dashboard

**GET /teacher/all_results**
- **Purpose**: Retrieve all student assessments
- **Response**:
  ```json
  [
    {
      "user_id": integer,
      "name": "string",
      "age": integer,
      "latest_risk": "Good" | "Moderate" | "Needs Attention",
      "sessions": [
        {
          "session_id": "uuid",
          "type": "language" | "mental",
          "timestamp": "datetime",
          "category": "string",
          "summary": "string",
          "analysis": "string"
        }
      ]
    }
  ]
  ```

### ML Model Server (Port 8001)

**GET /**
- **Response**: `{"status": "AI Model Server Running"}`

**POST /analyze/text**
- **Purpose**: Classify text for dyslexia indicators
- **Request**:
  ```json
  {
    "text": "string"
  }
  ```
- **Response**:
  ```json
  {
    "classification": [
      {"label": "LABEL_0", "score": 0.95}
    ],
    "summary": "Analysis complete",
    "scores": {}
  }
  ```
- **Model**: Transformers text classification pipeline

**POST /analyze/audio**
- **Purpose**: Transcribe audio and extract speech features
- **Request**: Multipart form with audio file
- **Response**:
  ```json
  {
    "transcription": "string",
    "features": {
      "duration_seconds": float,
      "speech_rate_wps": float,
      "pause_ratio": float
    },
    "analysis": {
      "flags": ["slow_reader", "high_pause", etc.],
      "is_adhd_risk": boolean
    }
  }
  ```
- **Processing**:
  - Whisper ASR for transcription
  - Librosa for audio feature extraction
  - Heuristic analysis for ADHD/speech pattern flags

---

## AI Integration

### Gemini AI (Google)

**Configuration:**
- API Key stored in `backend/.env`
- Model: `gemini-pro`
- Used for:
  - Question generation
  - Chat conversation flow
  - Result analysis and summarization
  - Trend comparison across sessions

**Key Functions:**

```python
async def generate_text(prompt: str) -> str:
    """Generate text using Gemini API with fallback"""
    if not gemini_model:
        return mock_response()
    
    response = gemini_model.generate_content(prompt)
    return response.text
```

**Prompts:**
- Question generation: Age-appropriate sentences for reading
- Chat flow: Empathetic follow-up questions
- Analysis: Professional assessment summaries

### Local ML Models

**ASR (Automatic Speech Recognition):**
- Model: OpenAI Whisper (local)
- Purpose: Transcribe audio responses
- Input: Audio file (webm format)
- Output: Text transcription

**Text Classification:**
- Purpose: Detect dyslexia indicators
- Input: Text string
- Output: Classification scores

**Feature Extraction:**
- Library: Librosa
- Metrics:
  - Speech rate (words per second)
  - Pause ratio (silence duration / total duration)
  - Non-silent intervals
- Thresholds:
  - Slow reader: < 1.0 wps
  - Hyperactivity: > 3.0 wps
  - High pause: > 0.4 ratio

---

## Frontend Architecture

### State Management

**LocalStorage Keys:**
- `session_id`: Current session UUID
- `user_name`: Student name
- `user_age`: Student age
- `test_type`: "language" | "mental"
- `questions`: JSON array of questions
- `answers`: JSON array of responses
- `result`: Final assessment result
- `API_BASE`: Backend URL (default: http://localhost:8000)

### Page Flow

```
index.html (Role Selection)
    ↓
    ├─→ Student Flow
    │   ├─→ User Info (name/age)
    │   ├─→ Test Selection (language/mental)
    │   │   ├─→ qn.html (Language Assessment)
    │   │   └─→ chat.html (Mental Health)
    │   ├─→ loading.html (Processing)
    │   └─→ result.html (Results)
    │
    └─→ Teacher Flow
        └─→ teacher.html (Dashboard)
```

### Key JavaScript Modules

**script.js:**
- Role selection logic
- User info collection
- Test type selection
- API calls to `/start`

**qn.js:**
- Question rendering with type detection
- Audio recording (MediaRecorder API)
- Text input handling
- Progress tracking
- Submission to `/response` and `/submit`

**chat.js:**
- Chat bubble rendering
- Likert scale button handling
- Message streaming
- API calls to `/chat/start` and `/chat/response`

**config.js:**
- Global API_BASE configuration
- LocalStorage management for API URL

### UI Design System

**CSS Variables:**
```css
--bg-color: #f5f5f7;
--card-bg: rgba(255, 255, 255, 0.8);
--text-primary: #1d1d1f;
--accent-blue: #0071e3;
--shadow-soft: 0 10px 30px rgba(0, 0, 0, 0.05);
--radius-large: 24px;
--ease-apple: cubic-bezier(0.25, 0.1, 0.25, 1.0);
```

**Design Principles:**
- Glassmorphism with backdrop-filter blur
- Smooth animations (fadeInUp, slideIn)
- Apple-inspired typography and spacing
- Responsive design with mobile-first approach
- Accessibility focus states

---

## Deployment

### Local Development

**Prerequisites:**
- Python 3.9+
- Node.js (optional, for npm packages)
- FFmpeg (for audio processing)

**Setup Steps:**

1. **Install Backend Dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Install ML Server Dependencies:**
   ```bash
   cd fastapi_backend_package
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   # backend/.env
   GEMINI_API_KEY=your_api_key_here
   ```

4. **Start Services:**
   ```bash
   # Terminal 1: Frontend
   python -m http.server 3000

   # Terminal 2: Main Backend
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload

   # Terminal 3: ML Model Server
   cd fastapi_backend_package
   .venv\Scripts\activate
   uvicorn app:app --host 0.0.0.0 --port 8001
   ```

5. **Access Application:**
   - Frontend: http://localhost:3000
   - Main Backend API: http://localhost:8000/docs
   - ML Server API: http://localhost:8001/docs

### Docker Deployment (ML Server)

**Dockerfile:**
```dockerfile
FROM python:3.9-slim-buster
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY text_classification_model ./text_classification_model
COPY asr_model ./asr_model
COPY tts_model ./tts_model
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build & Run:**
```bash
cd fastapi_backend_package
docker build -t lingosight-ml .
docker run -p 8001:8000 lingosight-ml
```

### Production Considerations

**Security:**
- Add authentication/authorization
- Implement rate limiting
- Use HTTPS with SSL certificates
- Sanitize user inputs
- Secure API keys with secrets management

**Performance:**
- Use production ASGI server (Gunicorn + Uvicorn)
- Implement caching (Redis)
- Database connection pooling
- CDN for static assets
- Load balancing for multiple instances

**Monitoring:**
- Application logging (structured logs)
- Error tracking (Sentry)
- Performance monitoring (APM)
- Health check endpoints

---

## Testing

### Manual Testing

See `TESTING_GUIDE.md` for comprehensive manual testing procedures.

### API Testing

**Test Scripts:**
- `backend/test_api_status.py`: Verify Gemini AI connectivity
- `backend/test_endpoints.py`: Test backend endpoints
- `test_external_api.py`: Test external tunnel URLs

**Example Test:**
```python
import httpx

# Test backend health
response = httpx.get("http://localhost:8000/")
assert response.status_code == 200
assert response.json()["status"] == "backend up (AI Integrated)"

# Test ML server
response = httpx.get("http://localhost:8001/")
assert response.json()["status"] == "AI Model Server Running"
```

---

## Known Issues & Limitations

1. **Docker Availability**: Docker command not in PATH on current development machine
2. **LocalTunnel**: External URL requires tunnel password (public IP)
3. **Browser Automation**: Rate limiting on browser subagent for testing
4. **Audio Format**: Limited to WebM format (browser MediaRecorder default)
5. **Model Size**: Large ML models (~800MB) not suitable for edge deployment
6. **Session Persistence**: In-memory sessions lost on server restart (use DB for production)

---

## Future Enhancements

1. **Real-time Collaboration**: WebSocket for live teacher monitoring
2. **Advanced Analytics**: Trend visualization, progress tracking
3. **Multi-language Support**: i18n for global accessibility
4. **Mobile Apps**: Native iOS/Android applications
5. **Enhanced ML Models**: Fine-tuned models for better accuracy
6. **Parent Portal**: Separate dashboard for parents
7. **Gamification**: Rewards and achievements for students
8. **Export Reports**: PDF generation for assessment results

---

## Dependencies

### Backend (Main)
```
fastapi
uvicorn[standard]
python-multipart
transformers
torch
librosa
soundfile
nest-asyncio
httpx
numpy
openai-whisper
ffmpeg-python
python-dotenv
openai
huggingface_hub
google-generativeai
```

### ML Model Server
```
fastapi
uvicorn
transformers
torch
librosa
soundfile
python-multipart
nest-asyncio
httpx
numpy
openai-whisper
ffmpeg-python
```

---

## Contact & Support

**Project Repository**: Local development environment
**Documentation**: This file + TESTING_GUIDE.md + walkthrough.md
**API Documentation**: Available at /docs endpoints (FastAPI Swagger UI)

---

## License

[Specify license if applicable]

---

**Last Updated**: 2026-01-17
**Version**: 1.0.0
**Status**: Development/Testing Phase
