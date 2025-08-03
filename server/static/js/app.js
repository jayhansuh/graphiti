// API Playground functionality

// Authentication handling
function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    
    // Check for JWT token first
    const token = localStorage.getItem('graphiti_token');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        return headers;
    }
    
    // Fall back to API key
    const apiKey = localStorage.getItem('graphiti_api_key');
    if (apiKey) {
        headers['X-API-Key'] = apiKey;
        return headers;
    }
    
    return headers;
}

// Check if user is authenticated
function checkAuth() {
    const token = localStorage.getItem('graphiti_token');
    const apiKey = localStorage.getItem('graphiti_api_key');
    
    if (!token && !apiKey) {
        // Redirect to login page
        window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
        return false;
    }
    return true;
}

// Logout function
function logout() {
    localStorage.removeItem('graphiti_token');
    localStorage.removeItem('graphiti_api_key');
    window.location.href = '/login';
}

// Switch between tabs
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

// Execute API request based on tab
async function executeRequest(endpoint) {
    const responseOutput = document.getElementById('response-output');
    responseOutput.innerHTML = '<code class="language-json">Loading...</code>';
    
    try {
        let response;
        
        switch(endpoint) {
            case 'messages':
                const messagesData = JSON.parse(document.getElementById('messages-input').value);
                response = await fetch('/messages', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(messagesData)
                });
                // Refresh graph after adding messages
                setTimeout(() => {
                    const groupId = messagesData.group_id;
                    document.getElementById('group-filter').value = groupId;
                    loadGraphData(groupId);
                    updateStats();
                }, 2000);
                break;
                
            case 'search':
                const searchData = JSON.parse(document.getElementById('search-input').value);
                response = await fetch('/search', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(searchData)
                });
                break;
                
            case 'episodes':
                const groupId = document.getElementById('episodes-group-id').value;
                const lastN = document.getElementById('episodes-last-n').value;
                response = await fetch(`/episodes/${groupId}?last_n=${lastN}`, {
                    headers: getAuthHeaders()
                });
                break;
                
            case 'entity':
                const entityData = JSON.parse(document.getElementById('entity-input').value);
                response = await fetch('/entity-node', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(entityData)
                });
                // Refresh graph after adding entity
                setTimeout(() => {
                    loadGraphData(entityData.group_id);
                    updateStats();
                }, 1000);
                break;
                
            case 'memory':
                const memoryData = JSON.parse(document.getElementById('memory-input').value);
                response = await fetch('/get-memory', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(memoryData)
                });
                break;
        }
        
        const data = await response.json();
        displayResponse(data, response.ok);
        
    } catch (error) {
        displayResponse({ error: error.message }, false);
    }
}

// Management operations
async function deleteGroup() {
    const groupId = document.getElementById('delete-group-id').value.trim();
    if (!groupId) {
        alert('Please enter a group ID');
        return;
    }
    
    if (!confirm(`Are you sure you want to delete group: ${groupId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/group/${groupId}`, { 
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const data = await response.json();
        displayResponse(data, response.ok);
        
        if (response.ok) {
            refreshGraph();
        }
    } catch (error) {
        displayResponse({ error: error.message }, false);
    }
}

async function deleteEpisode() {
    const uuid = document.getElementById('delete-episode-uuid').value.trim();
    if (!uuid) {
        alert('Please enter an episode UUID');
        return;
    }
    
    try {
        const response = await fetch(`/episode/${uuid}`, { 
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const data = await response.json();
        displayResponse(data, response.ok);
        
        if (response.ok) {
            refreshGraph();
        }
    } catch (error) {
        displayResponse({ error: error.message }, false);
    }
}

async function deleteEdge() {
    const uuid = document.getElementById('delete-edge-uuid').value.trim();
    if (!uuid) {
        alert('Please enter an edge UUID');
        return;
    }
    
    try {
        const response = await fetch(`/entity-edge/${uuid}`, { 
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const data = await response.json();
        displayResponse(data, response.ok);
        
        if (response.ok) {
            refreshGraph();
        }
    } catch (error) {
        displayResponse({ error: error.message }, false);
    }
}

async function clearAllData() {
    if (!confirm('⚠️ This will delete ALL data in the graph. Are you sure?')) {
        return;
    }
    
    if (!confirm('This action cannot be undone. Are you REALLY sure?')) {
        return;
    }
    
    try {
        const response = await fetch('/clear', { 
            method: 'POST',
            headers: getAuthHeaders()
        });
        const data = await response.json();
        displayResponse(data, response.ok);
        
        if (response.ok) {
            refreshGraph();
        }
    } catch (error) {
        displayResponse({ error: error.message }, false);
    }
}

// Display response with syntax highlighting
function displayResponse(data, isSuccess) {
    const responseOutput = document.getElementById('response-output');
    const jsonString = JSON.stringify(data, null, 2);
    
    responseOutput.innerHTML = `<code class="language-json ${isSuccess ? 'success' : 'error'}">${jsonString}</code>`;
    Prism.highlightElement(responseOutput.querySelector('code'));
    
    // Scroll to response
    responseOutput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Format JSON in textareas
function formatJSON(textareaId) {
    try {
        const textarea = document.getElementById(textareaId);
        const json = JSON.parse(textarea.value);
        textarea.value = JSON.stringify(json, null, 2);
    } catch (e) {
        // Invalid JSON, leave as is
    }
}

// Add event listeners for JSON formatting
document.addEventListener('DOMContentLoaded', () => {
    // Check authentication first
    if (!checkAuth()) {
        return; // checkAuth will redirect to login page
    }
    
    // Format JSON on blur
    document.querySelectorAll('.json-input').forEach(textarea => {
        textarea.addEventListener('blur', () => {
            formatJSON(textarea.id);
        });
    });
    
    // Handle Enter key in input fields
    document.querySelectorAll('input[type="text"], input[type="number"]').forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const button = input.closest('.tab-pane').querySelector('.execute-btn, button');
                if (button) button.click();
            }
        });
    });
});