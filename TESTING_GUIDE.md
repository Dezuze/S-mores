# Manual Testing Guide

## Prerequisites
All three services should be running:
- Frontend: `http://localhost:3000`
- Main Backend: `http://localhost:8000`
- ML Model Server: `http://localhost:8001`

## Test 1: Language Assessment (Mixed Question Types)

### Steps:
1. Open `http://localhost:3000` in your browser
2. Click the **Student** card
3. Enter:
   - Name: `Test Student`
   - Age: `8`
4. Click **Continue**
5. Select **Language Assessment** card
6. Click **Start Assessment**

### Expected Behavior:
- **Question 1** (Text): You should see a text input field
- **Question 2** (Audio): You should see the microphone recording interface
- **Question 3** (Text): Text input field returns
- **Question 4** (Audio): Recording interface again
- **Question 5** (Text): Final text input

### For Each Question:
- **Text questions**: Type any simple answer (e.g., "The sky is blue")
- **Audio questions**: 
  - Click the microphone button to start recording
  - Speak for 2-3 seconds
  - Click the stop button
  - Click the checkmark to submit

### After All Questions:
1. You'll see the **Loading** page with a spinning animation
2. Wait 5-10 seconds for AI analysis
3. The **Result** page should display with:
   - Student name and age
   - Category indicator (green/yellow/red dot)
   - Summary message
   - Detailed analysis box (if available)

---

## Test 2: Mental Health Check

### Steps:
1. Go back to `http://localhost:3000`
2. Click **Student** card
3. Enter:
   - Name: `Test Child`
   - Age: `7`
4. Click **Continue**
5. Select **Mental Health Check** card
6. Click **Start Check**

### Expected Behavior:
- Chat interface appears with AI Companion header
- Bot asks first question
- Five Likert scale buttons appear at bottom

### During Chat:
1. Answer each question by clicking one of the five buttons:
   - Least Likely
   - Unlikely
   - Neutral
   - Likely
   - Most Likely
2. Bot will ask follow-up questions (4-8 total)
3. After final question, you'll be redirected to loading page

### After Chat:
1. Loading page appears
2. Wait for analysis (5-10 seconds)
3. Result page displays with mental health assessment

---

## Test 3: UI Verification

### Loading Page (`/loading.html`):
- Navigate directly to `http://localhost:3000/loading.html`
- **Expected**: Blue spinning circle with "Analyzing" text

### Chat Interface (`/chat.html`):
- Navigate to `http://localhost:3000/chat.html`
- **Expected**: 
  - Clean header with "AI Companion"
  - Chat message area
  - Five styled Likert buttons at bottom
  - Buttons should have hover effects (blue background on hover)

### Result Page (`/result.html`):
- After completing any assessment
- **Expected**:
  - Clean card design with glassmorphism effect
  - Student info in rounded box
  - Three colored dots (green/yellow/red)
  - Active dot should be larger and glowing
  - Summary text below dots
  - Analysis box (if available)
  - "Done" button at bottom

---

## Troubleshooting

### If Questions Don't Load:
- Check browser console (F12) for errors
- Verify backend is running on port 8000
- Check that session_id is stored in localStorage

### If Audio Recording Doesn't Work:
- Grant microphone permissions when prompted
- Check browser console for errors
- Try a different browser (Chrome/Edge recommended)

### If Results Don't Display:
- Check browser console for errors
- Verify the loading page polling is working
- Check backend logs for processing errors
- Ensure localStorage has 'result' key after loading completes

### If AI Analysis is Missing:
- Verify Gemini API key is set in `backend/.env`
- Check backend logs for API errors
- ML Model Server should be running on port 8001
