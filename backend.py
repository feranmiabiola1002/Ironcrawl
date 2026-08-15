#!/usr/bin/env python3
# backend.py - IronClaw Backend Engine
# Deploy on Render as Web Service

import os
import json
import time
import sqlite3
import threading
import logging
import smtplib
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import requests

# ─── CONFIG ──────────────────────────────────────────────────
PORT = int(os.environ.get('PORT', 5000))
DB_FILE = "ironclaw.db"
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# ─── SETUP ──────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
log = logging.getLogger(__name__)

# ─── DATABASE ──────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Events table
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  title TEXT,
                  message TEXT,
                  type TEXT,
                  severity TEXT,
                  data TEXT)''')
    
    # Campaigns table
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  type TEXT,
                  status TEXT,
                  progress INTEGER,
                  target TEXT,
                  created TEXT,
                  updated TEXT)''')
    
    # Alerts table
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  type TEXT,
                  severity TEXT,
                  message TEXT,
                  source TEXT,
                  resolved INTEGER DEFAULT 0)''')
    
    # Config table
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchall()
    conn.commit()
    conn.close()
    return result

def db_execute(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

# ─── HELPERS ──────────────────────────────────────────────────

def get_config():
    result = db_query("SELECT key, value FROM config")
    return {row[0]: row[1] for row in result}

def set_config(key, value):
    db_execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))

# ─── EVENT & ALERT FUNCTIONS ──────────────────────────────

def add_event(title, message, event_type, severity='info', data=None):
    timestamp = datetime.now().isoformat()
    db_execute(
        "INSERT INTO events (timestamp, title, message, type, severity, data) VALUES (?, ?, ?, ?, ?, ?)",
        (timestamp, title, message, event_type, severity, json.dumps(data) if data else None)
    )
    
    event_data = {
        'timestamp': timestamp,
        'title': title,
        'message': message,
        'type': event_type,
        'severity': severity,
        'data': data
    }
    socketio.emit('event', event_data)
    log.info(f"[{event_type.upper()}] {title}: {message}")
    return event_data

def add_alert(alert_type, severity, message, source=None):
    timestamp = datetime.now().isoformat()
    db_execute(
        "INSERT INTO alerts (timestamp, type, severity, message, source, resolved) VALUES (?, ?, ?, ?, ?, ?)",
        (timestamp, alert_type, severity, message, source, 0)
    )
    
    alert_data = {
        'timestamp': timestamp,
        'type': alert_type,
        'severity': severity,
        'message': message,
        'source': source
    }
    socketio.emit('alert', alert_data)
    
    # Send notifications
    send_telegram_alert(message, severity)
    send_email_alert(message, severity)
    return alert_data

# ─── NOTIFICATIONS ──────────────────────────────────────────

def send_telegram_alert(message, severity):
    config = get_config()
    token = config.get('telegram_token')
    chat_id = config.get('telegram_chat_id')
    
    if token and chat_id:
        try:
            emoji = {'critical': '🚨', 'high': '⚠️', 'medium': '🔔', 'low': '📢'}.get(severity, '📢')
            text = f"{emoji} *IronClaw Alert*\nSeverity: *{severity.upper()}*\n{message}"
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=5)
        except Exception as e:
            log.error(f"Telegram alert failed: {e}")

def send_email_alert(message, severity):
    config = get_config()
    smtp_server = config.get('smtp_server')
    smtp_user = config.get('smtp_user')
    smtp_pass = config.get('smtp_pass')
    alert_email = config.get('alert_email')
    
    if smtp_server and smtp_user and alert_email:
        try:
            subject = f"[IronClaw] {severity.upper()} Alert"
            body = f"Timestamp: {datetime.now()}\nSeverity: {severity}\n\n{message}"
            msg = f"Subject: {subject}\n\n{body}"
            with smtplib.SMTP(smtp_server, 587) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [alert_email], msg)
        except Exception as e:
            log.error(f"Email alert failed: {e}")

# ─── SIMULATION ENGINE ──────────────────────────────────────

def simulate_phishing(target, template):
    time.sleep(2)
    if target and '@' in target and hash(target) % 10 < 3:
        add_event(
            "Phishing Click Detected",
            f"Target clicked: {target}",
            'detection',
            'critical',
            {'target': target, 'template': template}
        )
        add_alert('phishing', 'critical', f"Phishing click from {target}", target)

def simulate_ransomware(target):
    add_event("Ransomware Simulation", f"Encrypting test files on {target}", 'attack', 'critical')
    time.sleep(3)
    add_event("Ransomware Blocked", f"EDR detected and blocked ransomware on {target}", 'defense', 'high')
    add_alert('ransomware', 'high', f"Ransomware simulation completed on {target}", target)

def simulate_honeypot(service, port):
    time.sleep(5)
    if hash(str(time.time())) % 5 == 0:
        source_ip = f"192.168.1.{hash(str(time.time())) % 255}"
        add_event("Honeypot Triggered", f"Attacker connected to {service} on port {port}", 'detection', 'critical', {'source_ip': source_ip})
        add_alert('honeypot', 'critical', f"Honeypot triggered on {service}:{port} from {source_ip}", source_ip)

def run_vulnerability_scan(target):
    add_event("Vulnerability Scan Started", f"Scanning {target} for vulnerabilities", 'defense', 'low')
    time.sleep(4)
    findings = {'critical': hash(target) % 3, 'high': hash(target) % 5, 'medium': hash(target) % 7, 'low': hash(target) % 10}
    add_event("Scan Complete", f"Found {sum(findings.values())} vulnerabilities", 'defense', 'medium', findings)
    if findings['critical'] > 0:
        add_alert('vulnerability', 'high', f"Critical vulnerabilities found on {target}", target)
    return findings

# ─── ATTACK & DEFENSE API ───────────────────────────────────

def deploy_phishing(target, template='generic'):
    add_event(f"Phishing Campaign: {target}", f"Deploying {template} template to target", 'attack', 'high')
    threading.Thread(target=simulate_phishing, args=(target, template)).start()
    return {'status': 'deployed', 'target': target, 'template': template}

def deploy_ransomware(target):
    threading.Thread(target=simulate_ransomware, args=(target,)).start()
    return {'status': 'deployed', 'target': target}

def deploy_honeypot(service='ssh', port=22):
    add_event(f"Honeypot Deployed: {service}", f"Fake {service.upper()} service on port {port}", 'defense', 'medium')
    threading.Thread(target=simulate_honeypot, args=(service, port)).start()
    return {'status': 'deployed', 'service': service, 'port': port}

def deploy_deception(target):
    add_event("Deception Technology Active", f"Fake credentials and shares deployed for {target}", 'defense', 'high')
    return {'status': 'deployed', 'target': target}

def auto_respond(alert_type, severity, source):
    config = get_config()
    response_mode = config.get('auto_response', 'notify')
    add_event("Auto-Response Triggered", f"Responding to {alert_type} with {response_mode} mode", 'defense', 'high')
    
    if response_mode == 'block':
        add_event("IP Blocked", f"Blocked {source} in firewall", 'defense', 'high')
        add_alert('block', 'high', f"Blocked {source} via auto-response", source)
    elif response_mode == 'isolate':
        add_event("Host Isolated", f"Isolated host {source} from network", 'defense', 'critical')
        add_alert('isolation', 'critical', f"Isolated {source}", source)
    elif response_mode == 'neutralize':
        add_event("Threat Neutralized", f"Removed threat from {source}", 'defense', 'critical')
        add_alert('neutralized', 'critical', f"Neutralized threat on {source}", source)
    return {'status': 'responded', 'mode': response_mode, 'source': source}

# ─── FLASK ROUTES ────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({'status': 'IronClaw Engine Online', 'version': '3.0', 'mode': 'combat'})

@app.route('/api/events')
def get_events():
    limit = request.args.get('limit', 50, type=int)
    events = db_query("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
    return jsonify([{
        'id': e[0], 'timestamp': e[1], 'title': e[2], 'message': e[3],
        'type': e[4], 'severity': e[5], 'data': json.loads(e[6]) if e[6] else None
    } for e in events])

@app.route('/api/campaigns')
def get_campaigns():
    campaigns = db_query("SELECT * FROM campaigns ORDER BY created DESC")
    return jsonify([{
        'id': c[0], 'name': c[1], 'type': c[2], 'status': c[3],
        'progress': c[4], 'target': c[5], 'created': c[6]
    } for c in campaigns])

@app.route('/api/alerts')
def get_alerts():
    resolved = request.args.get('resolved', '0')
    alerts = db_query("SELECT * FROM alerts WHERE resolved = ? ORDER BY id DESC LIMIT 50", (resolved,))
    return jsonify([{
        'id': a[0], 'timestamp': a[1], 'type': a[2], 'severity': a[3],
        'message': a[4], 'source': a[5], 'resolved': a[6]
    } for a in alerts])

@app.route('/api/stats')
def get_stats():
    total = db_query("SELECT COUNT(*) FROM events")[0][0]
    attacks = db_query("SELECT COUNT(*) FROM events WHERE type = 'attack'")[0][0]
    defenses = db_query("SELECT COUNT(*) FROM events WHERE type = 'defense'")[0][0]
    detections = db_query("SELECT COUNT(*) FROM events WHERE type = 'detection'")[0][0]
    alerts = db_query("SELECT COUNT(*) FROM alerts WHERE resolved = 0")[0][0]
    
    return jsonify({
        'total_events': total,
        'attacks': attacks,
        'defenses': defenses,
        'detections': detections,
        'active_alerts': alerts,
        'honeypots': db_query("SELECT COUNT(*) FROM events WHERE title LIKE '%Honeypot%'")[0][0]
    })

@app.route('/api/deploy/attack', methods=['POST'])
def deploy_attack():
    data = request.json
    attack_type = data.get('type', 'phishing')
    target = data.get('target', 'unknown')
    
    if attack_type == 'phishing':
        result = deploy_phishing(target, data.get('template', 'generic'))
    elif attack_type == 'ransomware':
        result = deploy_ransomware(target)
    else:
        result = {'status': 'unknown_attack'}
    
    # Add to campaigns
    campaign_id = f"{attack_type}_{int(time.time())}"
    db_execute(
        "INSERT OR REPLACE INTO campaigns (id, name, type, status, progress, target, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (campaign_id, f"{attack_type.capitalize()} Campaign", 'red', 'active', 10, target, datetime.now().isoformat(), datetime.now().isoformat())
    )
    
    return jsonify(result)

@app.route('/api/deploy/defense', methods=['POST'])
def deploy_defense():
    data = request.json
    defense_type = data.get('type', 'honeypot')
    target = data.get('target', 'local')
    
    if defense_type == 'honeypot':
        result = deploy_honeypot(data.get('service', 'ssh'), data.get('port', 22))
    elif defense_type == 'scan':
        result = run_vulnerability_scan(target)
    elif defense_type == 'deception':
        result = deploy_deception(target)
    else:
        result = {'status': 'unknown_defense'}
    
    campaign_id = f"{defense_type}_{int(time.time())}"
    db_execute(
        "INSERT OR REPLACE INTO campaigns (id, name, type, status, progress, target, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (campaign_id, f"{defense_type.capitalize()} Defense", 'blue', 'active', 10, target, datetime.now().isoformat(), datetime.now().isoformat())
    )
    
    return jsonify(result)

@app.route('/api/respond', methods=['POST'])
def trigger_response():
    data = request.json
    result = auto_respond(data.get('type', 'unknown'), data.get('severity', 'medium'), data.get('source', 'unknown'))
    return jsonify(result)

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        data = request.json
        for key, value in data.items():
            set_config(key, value)
        return jsonify({'status': 'saved'})
    return jsonify(get_config())

@app.route('/api/resolve/<int:alert_id>', methods=['POST'])
def resolve_alert(alert_id):
    db_execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))
    return jsonify({'status': 'resolved'})

# ─── WEBSOCKET EVENTS ──────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    log.info(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to IronClaw Engine', 'mode': 'combat'})
    # Send recent events
    events = db_query("SELECT * FROM events ORDER BY id DESC LIMIT 10")
    for e in events:
        emit('event', {
            'timestamp': e[1],
            'title': e[2],
            'message': e[3],
            'type': e[4],
            'severity': e[5],
            'data': json.loads(e[6]) if e[6] else None
        })

@socketio.on('ping')
def handle_ping():
    emit('pong', {'timestamp': datetime.now().isoformat()})

@socketio.on('subscribe')
def handle_subscribe(data):
    log.info(f"Client subscribed to: {data.get('channel', 'all')}")

# ─── MAIN ──────────────────────────────────────────────────

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                    IRONCLAW ENGINE                       ║
    ║  ⚔️ Adversary Emulation & Active Defense Platform       ║
    ║                                                          ║
    ║  API:   https://ironclaw-backend.onrender.com           ║
    ║  WS:    wss://ironclaw-backend.onrender.com             ║
    ║  Status: Online                                         ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
