const roleSelection = document.getElementById('roleSelection');
const userInfo = document.getElementById('userInfo');
const teacherLoginSection = document.getElementById('teacherLoginSection');
const testSelection = document.getElementById('testSelection');
const finalActionContainer = document.getElementById('finalActionContainer');

let selectedTest = null;

// Navigation Helper with Animations
function transitionTo(fromId, toId) {
    const fromEl = document.getElementById(fromId);
    const toEl = document.getElementById(toId);

    if (fromEl) {
        fromEl.classList.remove('anim-enter');
        fromEl.classList.add('anim-exit');
        
        // Wait for exit animation
        setTimeout(() => {
            fromEl.classList.add('hidden');
            fromEl.classList.remove('anim-exit');
            
            if (toEl) {
                toEl.classList.remove('hidden');
                toEl.classList.add('anim-enter');
            }
        }, 350); // Match CSS animation duration approx
    } else {
        // Initial load or direct show
        if (toEl) {
            toEl.classList.remove('hidden');
            toEl.classList.add('anim-enter');
        }
    }
}

// Update Global Functions to use transition
window.selectRole = function(role) {
    if (role === 'student') {
        transitionTo('roleSelection', 'userInfo');
    } else {
        transitionTo('roleSelection', 'teacherLoginSection');
    }
}

window.goBack = function(toId) {
    // Find current visible section to animate out
    const current = document.querySelector('section:not(.hidden), div.step-container:not(.hidden)');
    transitionTo(current ? current.id : null, toId);
}

window.handleTeacherLogin = function() {
    const pwd = document.getElementById('teacherPass').value;
    if (pwd === 'admin') {
        window.location.href = 'teacher.html';
    } else {
        alert('Incorrect Password');
    }
}

// Student Flow: Name/Age -> Test Selection
document.getElementById('continueToTestBtn').addEventListener('click', () => {
    const name = document.getElementById('childName').value;
    const age = document.getElementById('childAge').value;
    
    if (!name || !age) {
        alert("Please enter name and age");
        return;
    }
    
    // Transition: UserInfo -> TestSelection
    // Show cards first
    transitionTo('userInfo', 'testSelection');
    
    // Also show the final action button container
    // We can just query it and show it since it's part of the next step
    if (finalActionContainer) {
        finalActionContainer.classList.remove('hidden');
        finalActionContainer.classList.add('anim-enter');
    }
});

// Test Card Selection
document.querySelectorAll('.test-card').forEach(card => {
    // Exclude the role cards (which use onclick)
    if (card.closest('#testSelection')) {
        card.addEventListener('click', () => {
            document.querySelectorAll('#testSelection .test-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedTest = card.getAttribute('data-type');
            
            const btn = document.getElementById('startTestBtn');
            btn.textContent = "Start " + (selectedTest === 'language' ? "Assessment" : "Check");
        });
    }
});

// Start Test Logic
document.getElementById('startTestBtn').addEventListener('click', async () => {
    if (!selectedTest) {
        alert("Please select a test type");
        return;
    }
    
    const btn = document.getElementById('startTestBtn');
    const name = document.getElementById('childName').value;
    const age = document.getElementById('childAge').value;
    
    btn.disabled = true;
    btn.textContent = "Loading...";
    
    const payload = {
        name: name,
        age: parseInt(age),
        role: "child",
        test_type: selectedTest
    };
    
    try {
        // Use backend port from config
        const response = await fetch(`${window.API_BASE || 'http://localhost:8000'}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error("Backend Error");
        
        const data = await response.json();
        
        localStorage.setItem('session_id', data.session_id);
        localStorage.setItem('user_name', name);
        localStorage.setItem('user_age', age);
        localStorage.setItem('test_type', selectedTest);
        
        if (data.redirect) {
            window.location.href = data.redirect;
        } else {
            localStorage.setItem('questions', JSON.stringify(data.questions || []));
            window.location.href = 'assessment.html';
        }
        
    } catch (e) {
        console.error(e);
        alert("Connection Failed. Try again.");
        btn.disabled = false;
        btn.textContent = "Try Again";
    }
});
