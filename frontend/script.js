const API_BASE = "http://localhost:8000/api";

// UI Elements
const els = {
    prompt: document.getElementById('prompt'),
    genre: document.getElementById('genre'),
    audience: document.getElementById('audience'),
    tone: document.getElementById('tone'),
    btn: document.getElementById('generateBtn'),
    status: document.getElementById('statusIndicator'),
    statusText: document.getElementById('statusText'),
    accordion: document.getElementById('thinking-accordion'),
    log: document.getElementById('thinking-log'),
    story: document.getElementById('story-output')
};

// Global State
let currentTaskId = null;
let pollInterval = null;

// Event Listeners
els.btn.addEventListener('click', startGeneration);

function toggleAccordion() {
    els.accordion.classList.toggle('open');
}

async function startGeneration() {
    const text = els.prompt.value.trim();
    const genre = els.genre.value.trim();
    const audience = els.audience.value;
    const tone = els.tone.value.trim();
    
    if (!text) return alert("Please enter a story prompt!");

    // UI Reset
    setLoading(true);
    els.log.innerHTML = "";
    els.story.innerHTML = "";
    els.accordion.classList.remove('hidden');
    els.accordion.classList.add('open');
    addLog("Initializing request...", true);

    try {
        const res = await fetch(`${API_BASE}/narrative/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                input_text: text, 
                target_genre: genre,
                target_audience: audience,
                tone: tone,
                words_per_scene: parseInt(document.getElementById('wordsPerScene').value),
                safety_level: document.getElementById('safetyLevel').value
            })
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error("API Error Response:", res.status, errorText);
            throw new Error(`API Connection Failed: ${res.status} ${res.statusText}`);
        }
        
        const data = await res.json();
        currentTaskId = data.task_id;
        addLog(`Task ID: ${currentTaskId} created.`, true);
        
        // NEW: Connect to SSE stream for real-time thinking updates
        connectThinkingStream(currentTaskId);
        
        // Start Polling (keep for final status check)
        pollInterval = setInterval(checkStatus, 2000);

    } catch (e) {
        handleError(e);
    }
}

// NEW: Real-time thinking stream via Server-Sent Events
let currentEventSource = null;

function connectThinkingStream(taskId) {
    console.log(`🌊 Connecting to SSE stream for task: ${taskId}`);
    
    // Close any existing stream
    if (currentEventSource) {
        currentEventSource.close();
    }
    
    // Create EventSource
    currentEventSource = new EventSource(`${API_BASE}/narrative/stream/${taskId}`);
    
    currentEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleThinkingEvent(data);
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };
    
    currentEventSource.onerror = (error) => {
        console.error('SSE Error:', error);
        currentEventSource.close();
        currentEventSource = null;
    };
}

function handleThinkingEvent(event) {
    const log = document.getElementById('thinking-log');
    const timestamp = new Date(event.timestamp || Date.now()).toLocaleTimeString();
    
    console.log(`📡 Received event: ${event.type}`, event.data);
    
    switch (event.type) {
        case 'workflow_start':
            clearThinkingLog();
            addThinkingEntry(timestamp, `🚀 Starting generation...`);
            addThinkingEntry(timestamp, `📏 Words/scene: ${event.data.words_per_scene}`);
            addThinkingEntry(timestamp, `🛡️ Safety: ${event.data.safety_level}`);
            break;
        
        case 'chunk_start':
            addThinkingEntry(timestamp, `📝 Rendering scene ${event.data.node_index}/${event.data.total_nodes}: ${event.data.action}`);
            break;
            
        case 'chunk_reasoning':
            addThinkingEntry(timestamp, `💭 Current Reasoning: ${event.data.reasoning}`, 'reasoning');
            break;
            
        case 'chunk_complete':
            addThinkingEntry(timestamp, `✅ Scene ${event.data.chunks_rendered}/${event.data.total_chunks} complete (${event.data.word_count} words)`);
            updateMetric('metricChunksRendered', event.data.chunks_rendered);
            break;
            
        case 'workflow_complete':
            addThinkingEntry(timestamp, `✅ Generation Complete!`, 'complete');
            addThinkingEntry(timestamp, `📊 Total: ${event.data.total_nodes} scenes, ${event.data.total_words} words`);
            updateMetric('metricGraphNodes', event.data.total_nodes);
            updateMetric('metricChunksRendered', event.data.total_chunks);
            
            // Close stream
            if (currentEventSource) {
                currentEventSource.close();
                currentEventSource = null;
            }
            break;
            
        case 'error':
            addThinkingEntry(timestamp, `❌ Error: ${event.data.message}`, 'error');
            if (currentEventSource) {
                currentEventSource.close();
                currentEventSource = null;
            }
            break;
            
        case 'heartbeat':
            // Ignore heartbeats
            break;
            
        default:
            // Log other events
            addThinkingEntry(timestamp, `${event.type}: ${JSON.stringify(event.data)}`);
    }
}

function addThinkingEntry(timestamp, text, className = '') {
    const log = document.getElementById('thinking-log');
    const entry = document.createElement('div');
    entry.className = `thinking-entry ${className}`;
    entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${text}`;
    log.appendChild(entry);
    
    // Auto-scroll to bottom
    log.scrollTop = log.scrollHeight;
}

function clearThinkingLog() {
    const log = document.getElementById('thinking-log');
    log.innerHTML = '';
}

function updateMetric(elementId, value) {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = value;
    }
}

async function checkStatus() {
    try {
        const res = await fetch(`${API_BASE}/narrative/status/${currentTaskId}`);
        const data = await res.json();
        
        updateProgress(data);

        if (data.status === 'completed') {
            finishGeneration(data.result);
        } else if (data.status === 'failed') {
            throw new Error(data.error || "Generation Failed");
        }
        
    } catch (e) {
        handleError(e);
    }
}

async function updateProgress(data) {
    els.statusText.innerText = `Status: ${data.status.toUpperCase()}`;
    
    // In Phase 1, we don't have granular progress streams yet,
    // so we just log the status. In Phase 3, we'll stream logs.
    if (data.status === 'processing') {
        // We can fetch intermediate state to show "Thinking"
        // This is a "pull" based update for now.
        try {
            const stateRes = await fetch(`${API_BASE}/narrative/state/${currentTaskId}`);
            if (stateRes.ok) {
                const state = await stateRes.json();
                renderThinking(state);
            }
        } catch (ignored) {
            // State might not be ready
        }
    }
}

function renderThinking(state) {
    // Extract Reasoning from graph if available
    // Note: This logic assumes we can see the graph nodes in the state
    if (!state.story_state) return;
    
    const story = state.story_state;
    const nodes = story.graph?.nodes || [];
    const renderedCount = Object.keys(story.rendered_chunks || {}).length;

    // Clear and rebuild logs to avoid duplicates (naive approach for Phase 1)
    let logHTML = `<div class="log-entry">Graph Nodes: ${nodes.length}</div>`;
    logHTML += `<div class="log-entry">Chunks Rendered: ${renderedCount}</div>`;

    // Show reasoning of the last processed node
    if (nodes.length > 0) {
        const lastNode = nodes[renderedCount > 0 ? renderedCount - 1 : 0];
        if (lastNode && lastNode.reasoning) {
             const shortReasoning = lastNode.reasoning.substring(0, 100) + "...";
             logHTML += `<div class="log-entry highlight">Current Reasoning: ${shortReasoning}</div>`;
        }
    }

    els.log.innerHTML = logHTML;
}

function finishGeneration(result) {
    clearInterval(pollInterval);
    setLoading(false);
    
    addLog("Generation Complete!", true);
    
    // Render Story
    const chunks = Object.values(result.chunks);
    els.story.innerHTML = chunks.map(text => 
        `<p>${text.replace(/\n/g, '<br>')}</p>`
    ).join('');
}

function handleError(e) {
    clearInterval(pollInterval);
    setLoading(false);
    alert(`Error: ${e.message}`);
    addLog(`Error: ${e.message}`, true);
}

function setLoading(isLoading) {
    if (isLoading) {
        els.btn.disabled = true;
        els.btn.style.opacity = "0.7";
        els.status.classList.remove('hidden');
    } else {
        els.btn.disabled = false;
        els.btn.style.opacity = "1";
    }
}

function addLog(msg, highlight = false) {
    const div = document.createElement('div');
    div.className = `log-entry ${highlight ? 'highlight' : ''}`;
    div.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
    els.log.appendChild(div);
    els.log.scrollTop = els.log.scrollHeight;
}
