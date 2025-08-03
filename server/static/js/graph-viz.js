// Graph Visualization with vis.js
let network = null;
let nodes = null;
let edges = null;

// Import auth headers function from app.js (it's loaded before this script)
// If getAuthHeaders is not defined, create a fallback
if (typeof getAuthHeaders === 'undefined') {
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
}

// Initialize the graph
function initializeGraph() {
    const container = document.getElementById('graph-container');
    
    // Create initial empty datasets
    nodes = new vis.DataSet([]);
    edges = new vis.DataSet([]);
    
    // Create network
    const data = { nodes, edges };
    
    const options = {
        nodes: {
            shape: 'dot',
            size: 20,
            font: {
                size: 14,
                color: '#c9d1d9'
            },
            borderWidth: 2,
            shadow: true,
            color: {
                background: '#58a6ff',
                border: '#1f6feb',
                highlight: {
                    background: '#79c0ff',
                    border: '#58a6ff'
                }
            }
        },
        edges: {
            width: 2,
            color: {
                color: '#30363d',
                highlight: '#58a6ff',
                hover: '#58a6ff'
            },
            font: {
                size: 12,
                color: '#8b949e',
                strokeWidth: 3,
                strokeColor: '#0d1117'
            },
            smooth: {
                type: 'continuous',
                roundness: 0.5
            },
            arrows: {
                to: {
                    enabled: true,
                    scaleFactor: 0.5
                }
            }
        },
        physics: {
            barnesHut: {
                gravitationalConstant: -8000,
                centralGravity: 0.3,
                springLength: 120,
                springConstant: 0.04,
                damping: 0.09
            },
            stabilization: {
                iterations: 150
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            hideEdgesOnDrag: true
        }
    };
    
    network = new vis.Network(container, data, options);
    
    // Add click event listener
    network.on("click", function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const node = nodes.get(nodeId);
            showNodeDetails(node);
        }
    });
    
    // Add double click event for centering
    network.on("doubleClick", function(params) {
        if (params.nodes.length > 0) {
            network.focus(params.nodes[0], {
                scale: 1.5,
                animation: true
            });
        }
    });
}

// Load graph data from server
async function loadGraphData(groupId = null) {
    try {
        const url = groupId ? `/graph-data?group_id=${groupId}` : '/graph-data';
        const response = await fetch(url, {
            headers: getAuthHeaders()
        });
        const data = await response.json();
        
        // Clear existing data
        nodes.clear();
        edges.clear();
        
        // Process nodes
        const nodeData = data.nodes.map(node => ({
            id: node.id,
            label: node.label || node.name || 'Unknown',
            title: `<b>${node.label}</b><br>${node.summary || 'No description'}`,
            group: node.group,
            size: 25,
            color: getNodeColor(node.labels)
        }));
        
        // Process edges
        const edgeData = data.edges.map(edge => ({
            from: edge.source,
            to: edge.target,
            label: edge.label || edge.type,
            title: edge.label,
            arrows: 'to'
        }));
        
        // Add to datasets
        nodes.add(nodeData);
        edges.add(edgeData);
        
        // Fit network to show all nodes
        setTimeout(() => {
            network.fit({
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }, 500);
        
    } catch (error) {
        console.error('Error loading graph data:', error);
        showError('Failed to load graph data');
    }
}

// Get node color based on type
function getNodeColor(labels) {
    if (!labels || labels.length === 0) {
        return {
            background: '#58a6ff',
            border: '#1f6feb'
        };
    }
    
    // Different colors for different entity types
    const colorMap = {
        'Person': { background: '#3fb950', border: '#238636' },
        'Organization': { background: '#f85149', border: '#da3633' },
        'Technology': { background: '#a371f7', border: '#8957e5' },
        'Project': { background: '#ffd33d', border: '#f9c513' },
        'Concept': { background: '#79c0ff', border: '#58a6ff' }
    };
    
    // Try to match known types
    for (const label of labels) {
        if (colorMap[label]) {
            return colorMap[label];
        }
    }
    
    // Default color
    return {
        background: '#58a6ff',
        border: '#1f6feb'
    };
}

// Show node details
function showNodeDetails(node) {
    alert(`Node: ${node.label}\nID: ${node.id}\nGroup: ${node.group}\n${node.title.replace(/<[^>]*>/g, '')}`);
}

// Refresh graph
async function refreshGraph() {
    const groupId = document.getElementById('group-filter').value.trim();
    const button = event.target;
    button.classList.add('loading');
    button.disabled = true;
    
    await loadGraphData(groupId || null);
    await updateStats();
    
    button.classList.remove('loading');
    button.disabled = false;
}

// Update statistics
async function updateStats() {
    try {
        const response = await fetch('/stats', {
            headers: getAuthHeaders()
        });
        const stats = await response.json();
        
        document.getElementById('entity-count').textContent = stats.entity_count || 0;
        document.getElementById('episode-count').textContent = stats.episode_count || 0;
        document.getElementById('relation-count').textContent = stats.relation_count || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Show error message
function showError(message) {
    const response = document.getElementById('response-output');
    response.innerHTML = `<code class="language-json error">${JSON.stringify({ error: message }, null, 2)}</code>`;
    Prism.highlightElement(response.querySelector('code'));
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check authentication first
    const token = localStorage.getItem('graphiti_token');
    const apiKey = localStorage.getItem('graphiti_api_key');
    
    if (!token && !apiKey) {
        // Don't initialize if not authenticated
        // app.js will handle the redirect
        return;
    }
    
    initializeGraph();
    loadGraphData();
    updateStats();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        const groupId = document.getElementById('group-filter').value.trim();
        loadGraphData(groupId || null);
        updateStats();
    }, 30000);
});