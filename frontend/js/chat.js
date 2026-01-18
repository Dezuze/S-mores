const chatStream = document.getElementById('chatStream');
const likertBtns = document.querySelectorAll('.likert-btn');
const typingIndicator = document.getElementById('typingIndicator');
const API_BASE_CHAT = window.API_BASE || "http://localhost:8000";

let session_id = localStorage.getItem('session_id');

async function initChat() {
    if(!session_id) {
        alert("Session invalid. returning home.");
        window.location.href = 'index.html';
        return;
    }

    // Start Chat
    showTyping();
    try {
        const resp = await fetch(`${API_BASE_CHAT}/chat/start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ session_id })
        });
        const data = await resp.json();
        hideTyping();
        addMessage('bot', data.message);
    } catch(e) {
        console.error(e);
        hideTyping();
        addMessage('bot', "Hello. I'm here to listen. How are you feeling today?");
    }
}

function addMessage(role, text) {
    const bubble = document.createElement('div');
    bubble.className = `message ${role}`;
    bubble.textContent = text;
    
    // Insert before typing indicator
    chatStream.insertBefore(bubble, typingIndicator);
    
    // Auto scroll
    chatStream.scrollTop = chatStream.scrollHeight;
}

function showTyping() {
    typingIndicator.style.display = 'flex';
    chatStream.scrollTop = chatStream.scrollHeight;
}

function hideTyping() {
    typingIndicator.style.display = 'none';
}

const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

// Helper to disable all controls
function setControlsDisabled(disabled) {
    likertBtns.forEach(b => b.disabled = disabled);
    chatInput.disabled = disabled;
    sendBtn.disabled = disabled;
}

// Core Submission Logic
async function submitAnswer(val) {
    if (!val) return;
    
    // Add User Bubble
    addMessage('user', val);
    chatInput.value = ''; // clear input
    
    setControlsDisabled(true);
    showTyping();

    try {
        const resp = await fetch(`${API_BASE_CHAT}/chat/response`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ session_id, answer: val })
        });
        const data = await resp.json();

        if (data.done) {
            window.location.href = 'loading.html';
        } else {
            setTimeout(() => {
                hideTyping();
                addMessage('bot', data.message);
                setControlsDisabled(false);
                chatInput.focus();
            }, 800);
        }
    } catch(e) {
        console.error(e);
        hideTyping();
        setControlsDisabled(false);
    }
}

// Event Listeners
likertBtns.forEach(btn => {
    btn.addEventListener('click', () => submitAnswer(btn.getAttribute('data-value')));
});

sendBtn.addEventListener('click', () => submitAnswer(chatInput.value.trim()));

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') submitAnswer(chatInput.value.trim());
});

initChat();
