// Login functionality for Graphiti

const API_BASE_URL = window.location.origin;

// Show message box
function showMessage(message, type = 'info') {
    const messageBox = document.getElementById('messageBox');
    messageBox.className = `message-box ${type}`;
    messageBox.textContent = message;
    messageBox.style.display = 'flex';
    
    setTimeout(() => {
        messageBox.style.display = 'none';
    }, 5000);
}

// Show/hide loading overlay
function setLoading(isLoading) {
    const overlay = document.getElementById('loadingOverlay');
    if (isLoading) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

// Store token and redirect
function handleAuthSuccess(token) {
    // Store token in localStorage
    localStorage.setItem('graphiti_token', token);
    
    // Redirect to main app or dashboard
    const redirectUrl = new URLSearchParams(window.location.search).get('redirect') || '/';
    window.location.href = redirectUrl;
}

// OAuth login functions
async function loginWithGoogle() {
    try {
        setLoading(true);
        const response = await fetch(`${API_BASE_URL}/auth/google/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            // Redirect to Google OAuth
            window.location.href = data.authorization_url;
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Google login is not configured', 'error');
            setLoading(false);
        }
    } catch (error) {
        console.error('Google login error:', error);
        showMessage('Failed to initiate Google login', 'error');
        setLoading(false);
    }
}

async function loginWithGitHub() {
    try {
        setLoading(true);
        const response = await fetch(`${API_BASE_URL}/auth/github/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            // Redirect to GitHub OAuth
            window.location.href = data.authorization_url;
        } else {
            const error = await response.json();
            showMessage(error.detail || 'GitHub login is not configured', 'error');
            setLoading(false);
        }
    } catch (error) {
        console.error('GitHub login error:', error);
        showMessage('Failed to initiate GitHub login', 'error');
        setLoading(false);
    }
}

// API Key login
async function loginWithApiKey(event) {
    event.preventDefault();
    
    const apiKey = document.getElementById('apiKey').value;
    
    if (!apiKey) {
        showMessage('Please enter your API key', 'error');
        return;
    }
    
    try {
        setLoading(true);
        
        // Test the API key by calling a protected endpoint
        const response = await fetch(`${API_BASE_URL}/stats`, {
            headers: {
                'X-API-Key': apiKey
            }
        });
        
        if (response.ok) {
            // Store API key as token
            localStorage.setItem('graphiti_api_key', apiKey);
            showMessage('Login successful!', 'success');
            
            // Redirect after a short delay
            setTimeout(() => {
                const redirectUrl = new URLSearchParams(window.location.search).get('redirect') || '/';
                window.location.href = redirectUrl;
            }, 1000);
        } else {
            showMessage('Invalid API key', 'error');
            setLoading(false);
        }
    } catch (error) {
        console.error('API key login error:', error);
        showMessage('Failed to verify API key', 'error');
        setLoading(false);
    }
}

// Show signup information
function showSignupInfo() {
    showMessage('OAuth signup will be available once OAuth providers are configured. For now, use the API key.', 'info');
}

// Check for OAuth callback token
function checkOAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('error');
    
    if (token) {
        handleAuthSuccess(token);
    } else if (error) {
        if (error === 'authentication_failed') {
            showMessage('Authentication failed. Please try again.', 'error');
        } else {
            showMessage('An error occurred during authentication.', 'error');
        }
        // Clean up URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

// Check if user is already logged in
function checkExistingAuth() {
    const token = localStorage.getItem('graphiti_token');
    const apiKey = localStorage.getItem('graphiti_api_key');
    
    if (token || apiKey) {
        // User is already logged in, redirect to main app
        const redirectUrl = new URLSearchParams(window.location.search).get('redirect') || '/';
        window.location.href = redirectUrl;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkOAuthCallback();
    checkExistingAuth();
});