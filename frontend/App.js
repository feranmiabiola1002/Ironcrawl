// app.js - IronClaw Frontend Logic

// ─── CONFIG ──────────────────────────────────────────────────
const WS_URL = window.location.hostname === 'localhost' 
    ? 'ws://localhost:5000' 
    : 'wss://ironclaw-backend.onrender.com';

const API_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:5000/api'
    : 'https://ironclaw-backend.onrender.com/api';

let ws = null;
let currentMode = 'purple';
let stats = { attacks: 0, defenses: 0, threats: 0, resolved: 0, honeypots: 0, compromised: 0 };
let reconnectAttempts = 0;
const MAX_RECONNECT = 10;

// ─── DOM ──────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const toast = $('toast');
const toastMessage = $('toastMessage');

// ─── TOAST ──────────────────────────────────────────────────
function showToast(message, type = 'info') {
    toastMessage.textContent = message;
    toast.className = `toast show ${type}`;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { toast.className = 'toast'; }, 4000);
}

// ─── WEBSOCKET ──────────────────────────────────────────────
function connectWS() {
    try {
        ws = new WebSocket(WS_URL);
        
        ws.onopen = () => {
            $('statusBadge').className = 'badge-status badge-green';
            $('statusBadge').textContent = '● Online';
            reconnectAttempts = 0;
            showToast('Connected to IronClaw Engine', 'success');
            console.log('🔗 WebSocket connected');
            
            // Send ping to keep alive
            setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping' }));
                }
            }, 30000);
        };
        
        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            handleWSMessage(data);
        };
        
        ws.onclose = () => {
            $('statusBadge').className = 'badge-status badge-red';
            $('statusBadge').textContent = '● Offline';
            reconnectAttempts++;
            if (reconnectAttempts < MAX_RECONNECT) {
                setTimeout(connectWS, 3000 * Math.min(reconnectAttempts, 5));
            }
            showToast('WebSocket disconnected', 'warning');
        };
        
        ws.onerror = () => {
            if (ws) ws.close();
        };
    } catch (e) {
        console.error('WebSocket error:', e);
        setTimeout(connectWS, 5000);
    }
}

function handleWSMessage(data) {
    switch (data.type) {
        case 'event':
            addEvent(data.title, data.message, data.type, data.severity);
            updateStats(data);
            break;
        case 'alert':
            addAlert(data);
            break;
        case 'status':
            console.log('Status:', data.message);
            break;
        case 'pong':
            // Keep alive response
            break;
        default:
            console.log('Unknown WS message:', data);
    }
}

// ─── EVENT FUNCTIONS ──────────────────────────────────────

function addEvent(title, message, type, severity = 'info') {
    const feed = $('eventList');
    const empty = feed.querySelector('.empty-state');
    if (empty) feed.innerHTML = '';
    
    const div = document.createElement('div');
    div.className = 'event-item';
    div.style.animation = 'slideIn 0.3s ease';
    
    const tagMap = {
        'red': 'tag-red', 'blue': 'tag-blue', 'green': 'tag-green',
        'purple': 'tag-purple', 'yellow': 'tag-yellow', 'gray': 'tag-gray'
    };
    
    const timestamp = new Date().toLocaleTimeString();
    div.innerHTML = `
        <div class="info">
            <div class="title">${title}</div>
            <div class="meta">${timestamp} • ${message}</div>
        </div>
        <span class="tag ${tagMap[type] || 'tag-gray'}">${type}</span>
    `;
    
    feed.insertBefore(div, feed.firstChild);
    
    // Keep only last 100
    while (feed.children.length > 100) {
        feed.removeChild(feed.lastChild);
    }
    
    // Toast for critical events
    if (severity === 'critical') showToast(`🚨 ${title}`, 'error');
    else if (severity === 'high') showToast(`⚠️ ${title}`, 'warning');
}

function addAlert(data) {
    // Add to alerts feed (can be expanded)
    console.log('🚨 Alert:', data);
    showToast(`🔔 ${data.message}`, 'warning');
}

// ─── UPDATE STATS ──────────────────────────────────────────

function updateStats(data) {
    // Track stats based on event type
    switch (data.type) {
        case 'attack':
            stats.attacks++;
            $('attacksDeployed').textContent = stats.attacks;
            stats.compromised++;
            $('compromisedAssets').textContent = stats.compromised;
            break;
        case 'defense':
            stats.defenses++;
            $('defensesActive').textContent = stats.defenses;
            break;
        case 'detection':
            stats.threats++;
            $('threatsDetected').textContent = stats.threats;
            break;
    }
    // Honeypot detection
    if (data.title && data.title.includes('Honeypot')) {
        stats.honeypots++;
        $('honeypotsActive').textContent = stats.honeypots;
    }
}

// ─── CLEAR EVENTS ──────────────────────────────────────────

function clearEvents() {
    $('eventList').innerHTML = `
        <div class="empty-state"><div class="icon">📡</div><div>Events cleared.</div></div>
    `;
    showToast('Events cleared', 'info');
}

// ─── SIMULATE EVENT ──────────────────────────────────────────

function simulateEvent() {
    const types = [
        { title: '🔴 Phishing Click Detected', message: 'User clicked malicious link', type: 'red', severity: 'high' },
        { title: '🔵 Anomalous Login Blocked', message: 'Suspicious IP address logged', type: 'blue', severity: 'medium' },
        { title: '🟣 Honeypot Triggered', message: 'Attacker interacted with decoy', type: 'purple', severity: 'critical' },
        { title: '🟡 Vulnerability Found', message: 'CVE-2024-xxxxx detected', type: 'yellow', severity: 'high' },
        { title: '🟢 Incident Resolved', message: 'Threat fully neutralized', type: 'green', severity: 'low' },
        { title: '🔴 Credential Dump Found', message: 'Employee credentials in breach', type: 'red', severity: 'critical' },
    ];
    const event = types[Math.floor(Math.random() * types.length)];
    addEvent(event.title, event.message, event.type, event.severity);
    updateStats({ type: event.type === 'red' ? 'attack' : event.type === 'blue' ? 'defense' : 'detection' });
}

// ─── MODE TOGGLE ──────────────────────────────────────────

document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
        const modeNames = { red: '🔴 RED TEAM MODE', blue: '🔵 BLUE TEAM MODE', purple: '🟣 COMBAT MODE' };
        const modeClasses = { red: 'mode-red', blue: 'mode-blue', purple: 'mode-purple' };
        const indicator = $('modeIndicator');
        indicator.textContent = modeNames[currentMode] || '⚡ COMBAT MODE';
        indicator.className = `mode-indicator ${modeClasses[currentMode]}`;
        showToast(`Switched to ${modeNames[currentMode]}`, 'info');
    });
});

// ─── API CALLS ──────────────────────────────────────────────

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (data) options.body = JSON.stringify(data);
        const response = await fetch(`${API_URL}${endpoint}`, options);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API error:', error);
        showToast(`API error: ${error.message}`, 'error');
        return null;
    }
}

// ─── DEPLOY ACTIONS ──────────────────────────────────────────

function deployAttack() {
    if (currentMode === 'blue') {
        showToast('Switch to Red or Combat mode', 'warning');
        return;
    }
    const target = $('targetDomain').value || 'target-company.com';
    apiCall('/deploy/attack', 'POST', { type: 'phishing', target });
    showToast(`⚔️ Attack deployed against ${target}`, 'warning');
    addEvent('⚔️ Attack Deployed', `Phishing campaign targeting ${target}`, 'red', 'high');
}

function deployDefense() {
    if (currentMode === 'red') {
        showToast('Switch to Blue or Combat mode', 'warning');
        return;
    }
    apiCall('/deploy/defense', 'POST', { type: 'honeypot' });
    showToast('🛡️ Defense deployed', 'success');
    addEvent('🛡️ Defense Deployed', 'Honeypot service activated', 'blue', 'medium');
}

function deployPhishing() {
    const target = $('targetDomain').value || 'target-company.com';
    apiCall('/deploy/attack', 'POST', { type: 'phishing', target });
    showToast(`📧 Phishing campaign deployed against ${target}`, 'warning');
    addEvent('📧 Phishing Deployed', `Targeting ${target} employees`, 'red', 'high');
}

function deployRansomware() {
    const target = $('targetDomain').value || 'target-company.com';
    apiCall('/deploy/attack', 'POST', { type: 'ransomware', target });
    showToast('💀 Ransomware simulation started', 'error');
    addEvent('💀 Ransomware Simulation', `Encrypting test files on ${target}`, 'red', 'critical');
}

function deployHoneypot() {
    apiCall('/deploy/defense', 'POST', { type: 'honeypot', service: 'ssh', port: 22 });
    showToast('🍯 Honeypot deployed', 'success');
    addEvent('🍯 Honeypot Deployed', 'Fake SSH service on port 22', 'purple', 'medium');
}

function deployDeception() {
    const target = $('targetDomain').value || 'target-company.com';
    apiCall('/deploy/defense', 'POST', { type: 'deception', target });
    showToast('🎭 Deception layer activated', 'info');
    addEvent('🎭 Deception Technology', `Fake assets deployed for ${target}`, 'purple', 'high');
}

function runScanner() {
    const target = $('targetDomain').value || 'target-company.com';
    apiCall('/deploy/defense', 'POST', { type: 'scan', target });
    showToast('🔍 Vulnerability scan started', 'info');
    addEvent('🔍 Scan Started', `Scanning ${target} for vulnerabilities`, 'blue', 'low');
}

function autoRespond() {
    apiCall('/respond', 'POST', { type: 'simulated_threat', severity: 'high', source: 'unknown' });
    showToast('⚡ Auto-response triggered', 'success');
    addEvent('⚡ Auto-Response', 'Neutralizing threats', 'green', 'high');
}

// ─── CONFIG ──────────────────────────────────────────────────

function saveConfig() {
    const config = {
        target_domain: $('targetDomain').value,
        auto_response: $('autoResponse').value,
        telegram_token: $('telegramToken').value,
        telegram_chat_id: $('telegramChatId').value,
        alert_email: $('alertEmail').value,
        smtp_server: $('smtpServer').value
    };
    apiCall('/config', 'POST', config);
    showToast('✅ Configuration saved', 'success');
}

function loadConfig() {
    apiCall('/config').then(config => {
        if (config) {
            if (config.target_domain) $('targetDomain').value = config.target_domain;
            if (config.auto_response) $('autoResponse').value = config.auto_response;
            if (config.telegram_token) $('telegramToken').value = config.telegram_token;
            if (config.telegram_chat_id) $('telegramChatId').value = config.telegram_chat_id;
            if (config.alert_email) $('alertEmail').value = config.alert_email;
            if (config.smtp_server) $('smtpServer').value = config.smtp_server;
        }
    });
}

// ─── LOAD STATS ──────────────────────────────────────────

function loadStats() {
    apiCall('/stats').then(data => {
        if (data) {
            $('attacksDeployed').textContent = data.attacks || 0;
            $('defensesActive').textContent = data.defenses || 0;
            $('threatsDetected').textContent = data.detections || 0;
            $('incidentsResolved').textContent = data.active_alerts || 0;
            $('honeypotsActive').textContent = data.honeypots || 0;
            stats.attacks = data.attacks || 0;
            stats.defenses = data.defenses || 0;
            stats.threats = data.detections || 0;
            stats.resolved = data.active_alerts || 0;
            stats.honeypots = data.honeypots || 0;
        }
    });
}

// ─── EXPOSE GLOBALLY ──────────────────────────────────────

window.deployAttack = deployAttack;
window.deployDefense = deployDefense;
window.deployPhishing = deployPhishing;
window.deployRansomware = deployRansomware;
window.deployHoneypot = deployHoneypot;
window.deployDeception = deployDeception;
window.runScanner = runScanner;
window.autoRespond = autoRespond;
window.simulateEvent = simulateEvent;
window.clearEvents = clearEvents;
window.saveConfig = saveConfig;

// ─── INIT ──────────────────────────────────────────────────

connectWS();
loadConfig();
loadStats();

// Seed initial events
setTimeout(() => {
    addEvent('⚔️ IronClaw Initialized', 'Combat mode engaged. System ready.', 'gray', 'low');
    addEvent('🛡️ Active Defense Engaged', 'Monitoring for threats', 'blue', 'low');
    addEvent('🔍 Threat Intelligence Active', 'Multiple sources online', 'gray', 'low');
}, 500);

// Auto-simulate
setInterval(() => {
    if (Math.random() > 0.6) {
        simulateEvent();
    }
}, 15000);

console.log('⚔️ IronClaw initialized');
