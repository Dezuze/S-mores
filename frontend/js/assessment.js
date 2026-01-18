let questions = [];
let currentIndex = 0;

const questionText = document.getElementById("questionText");
const answerInput = document.getElementById("answerInput");
const submitBtn = document.getElementById("submitBtn");
const progressFill = document.getElementById("progressFill");
const currentQ = document.getElementById("currentQ");

// Audio elements
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const playback = document.getElementById("playback");
const audioControls = document.getElementById('audioControls');
const playQBtn = document.getElementById('playQBtn');
const answerSection = document.querySelector('.answer-section');
const answerLabel = answerSection ? answerSection.querySelector('label') : null;

let mediaRecorder = null;
let audioChunks = [];
let lastAudioBlob = null;

function loadQuestions() {
  const stored = localStorage.getItem("questions");
  if (stored) {
    try {
      questions = JSON.parse(stored);
    } catch (e) {
      console.error("Failed to parse questions", e);
    }
  }

  if (!questions || questions.length === 0) {
    questionText.textContent = "No questions available. Please restart the test.";
    submitBtn.disabled = true;
    return;
  }

  loadQuestion();
}

function loadQuestion() {
  const container = document.querySelector('.question-box');
  const answerSection = document.querySelector('.answer-section');
  
  // ANIMATED TRANSITION
  const mainStream = document.querySelector('.question-stream');
  
  // Exit Animation
  mainStream.classList.remove('anim-enter');
  mainStream.classList.add('anim-exit');

  setTimeout(() => {
    // Logic to update content
    const raw = questions[currentIndex];
    let qText = '';
    let qType = 'text';
    if (typeof raw === 'string') {
      qText = raw;
    } else if (raw && typeof raw === 'object') {
      qText = raw.text || raw.question || '';
      qType = raw.type || raw.response_type || 'text';
    }

    questionText.textContent = qText;
    currentQ.textContent = currentIndex + 1;
    
    // Update Progress
    if (document.getElementById('totalQ')) {
        document.getElementById('totalQ').textContent = questions.length;
    }
    const pct = ((currentIndex + 1) / questions.length) * 100;
    progressFill.style.width = `${pct}%`;

    answerInput.value = "";
    playback.style.display = "none";
    lastAudioBlob = null;

    // Update UI based on type
    // Explicitly toggle visibility
    const ansSection = document.querySelector('.answer-section');
    if (ansSection) ansSection.style.display = 'block';

    if (qType === 'audio') {
      answerInput.style.display = 'none';
      audioControls.style.display = 'flex';
      submitBtn.disabled = true;
    } else {
      answerInput.style.display = 'block';
      audioControls.style.display = 'none';
      submitBtn.disabled = !answerInput.value.trim();
    }

    // Reset Buttons
    if (recordBtn) {
      recordBtn.classList.remove('recording');
      recordBtn.disabled = false;
    }
    if (stopBtn) stopBtn.disabled = true;

    // Enter Animation
    mainStream.classList.remove('anim-exit');
    mainStream.classList.add('anim-enter');

  }, 500); // Wait for exit animation
}

// Media recording
recordBtn.addEventListener("click", async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Audio recording not supported in this browser.");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = () => {
      lastAudioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      playback.src = URL.createObjectURL(lastAudioBlob);
      playback.style.display = "block";
    };

    mediaRecorder.start();
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    recordBtn.classList.add('recording');
  } catch (err) {
    console.error(err);
    alert("Failed to start microphone.");
  }
});

stopBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    recordBtn.disabled = false;
    stopBtn.disabled = true;
    recordBtn.classList.remove('recording');
  }
});

// When playback (audio) becomes available, enable submit
const obs = new MutationObserver(() => {
  if (lastAudioBlob) submitBtn.disabled = false;
});
obs.observe(playback, { attributes: true, attributeFilter: ['src'] });

// Enable/disable submit for text input
answerInput.addEventListener('input', () => {
  // only applicable for text questions
  const raw = questions[currentIndex];
  let qType = 'text';
  if (raw && typeof raw === 'object') qType = raw.type || raw.response_type || 'text';
  if (qType !== 'audio') {
    submitBtn.disabled = !answerInput.value.trim();
  }
});

// Play question text using SpeechSynthesis for accessibility
if (playQBtn) {
  playQBtn.addEventListener('click', () => {
    try {
      const raw = questions[currentIndex];
      const questionTextValue = (typeof raw === 'string') ? raw : (raw.text || raw.question || '');
      if (!questionTextValue) return;
      const u = new SpeechSynthesisUtterance(questionTextValue);
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.error('TTS failed', e);
    }
  });
}

    submitBtn.addEventListener("click", async () => {
      // Prevent multiple clicks
      submitBtn.disabled = true;
      submitBtn.textContent = "Processing...";
  const raw = questions[currentIndex];
  let qType = 'text';
  if (raw && typeof raw === 'object') qType = raw.type || raw.response_type || 'text';

  if (qType === 'audio' && !lastAudioBlob) {
    alert('This question requires an audio response. Please record your answer.');
    return;
  }

  if (qType !== 'audio' && !answerInput.value.trim() && !lastAudioBlob) {
    alert("Please provide a text answer or record audio.");
    return;
  }

  const session_id = localStorage.getItem("session_id");
  if (!session_id) {
      alert("Session expired or missing. Please restart the assessment.");
      window.location.href = 'index.html';
      return;
  }

  // send this answer to backend
  try {
    const form = new FormData();
    form.append('session_id', session_id);
    form.append('question_index', String(currentIndex));
    // include question text and type
    const questionTextValue = (typeof raw === 'string') ? raw : (raw.text || raw.question || '');
    form.append('question', questionTextValue);
    form.append('question_type', qType);
    form.append('answer_text', qType === 'audio' ? '' : answerInput.value.trim());
    if (lastAudioBlob) {
      form.append('answer_audio', lastAudioBlob, `answer-${currentIndex}.webm`);
    }

    // Retry logic helper
    const fetchWithRetry = async (url, options, retries = 3) => {
        try {
            const res = await fetch(url, options);
            if (!res.ok) {
                 // If 4xx error (client side), do not retry (except 429)
                 if (res.status >= 400 && res.status < 500 && res.status !== 429) {
                     return res; // Return to let main logic handle error
                 }
                 throw new Error(`Server returned ${res.status}`);
            }
            return res;
        } catch (err) {
            if (retries > 0) {
                console.warn(`Retrying... attempts left: ${retries}. Error: ${err.message}`);
                await new Promise(r => setTimeout(r, 1500)); // Wait 1.5s
                return fetchWithRetry(url, options, retries - 1);
            }
            throw err;
        }
    };

    const resp = await fetchWithRetry(`${window.API_BASE}/response`, {
      method: 'POST',
      body: form
    });
    
    if (!resp.ok) {
        let msg = 'Server Error';
        try {
            const errJson = await resp.json(); 
            msg = errJson.error || errJson.detail || JSON.stringify(errJson);
        } catch(e) {
            msg = `Status ${resp.status}`;
        }
        throw new Error(msg);
    }

    // store locally as well
    let answers = JSON.parse(localStorage.getItem('answers') || '[]');
    answers.push({ question: questions[currentIndex], answer: answerInput.value.trim(), audio: lastAudioBlob ? true : false });
    localStorage.setItem('answers', JSON.stringify(answers));

    currentIndex++;

    if (currentIndex < questions.length) {
      loadQuestion();
    } else {
      // submit all answers to backend for processing
      await fetch(`${API_BASE}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id, answers: JSON.parse(localStorage.getItem('answers') || '[]') })
      });

      // navigate to loading page where we'll poll for results
      window.location.href = 'loading.html';
    }
  } catch (err) {
    console.error(err);
    alert('Failed to send answer: ' + (err.message || err));
  }
});

loadQuestions();
