from flask import Flask, request, jsonify, render_template_string, send_file, Response
from functools import wraps
import subprocess
import os
import threading
import signal
import time
import zipfile
import io

app = Flask(__name__)

def check_auth(username, password):
    """Check if a username / password combination is valid."""
    expected_username = os.environ.get('APP_USERNAME', 'admin')
    expected_password = os.environ.get('APP_PASSWORD', 'password')
    return username == expected_username and password == expected_password

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/login')
@requires_auth
def login():
    return '<script>window.location.href="/";</script>'

# Global to store the current process
current_process = None
current_prefix = None
start_time = None

def get_raw_estimate(prefix):
    length = len(prefix)
    if length < 2 or length > 10:
        return None

    trials = {
        2: 709,
        3: 22713,
        4: 726817,
        5: 23258160,
        6: 744261118,
        7: 23816355774,
        8: 762123384785,
        9: 24387948313146,
        10: 780414346020670
    }

    rate = 6700000 # Average hash rate for mkp224o on typical hardware
    if length in trials:
        return trials[length] / rate
    return None

def format_time(seconds):
    if seconds is None:
        return "Unknown"
    if seconds < 60:
        return f"~{seconds:.1f} seconds"
    elif seconds < 3600:
        return f"~{seconds/60:.1f} minutes"
    else:
        return f"~{seconds/3600:.1f} hours"

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="en" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Onion Address Generator</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e);
                background-size: 400% 400%;
                animation: gradientBG 15s ease infinite;
                color: #fff;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                overflow-x: hidden;
                margin: 0;
            }

            @keyframes gradientBG {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            .glass-card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                height: 100%;
            }

            .timer-display {
                font-family: 'Courier New', Courier, monospace;
                font-size: 2.2rem;
                font-weight: 900;
                background: -webkit-linear-gradient(#00f2fe, #4facfe);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-align: center;
                margin: 20px 0;
                text-shadow: 0px 5px 15px rgba(0,242,254,0.3);
            }

            .url-banner {
                background: rgba(0,0,0,0.6);
                backdrop-filter: blur(10px);
                padding: 12px 15px; /* Added horizontal padding */
                text-align: center;
                font-family: 'Courier New', monospace;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                position: sticky;
                top: 0;
                z-index: 1000;
                font-size: 1.1rem;
                color: #a8b2d1;
                box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
                
                /* Flexbox helps keep the "Live Demo:" text and link aligned */
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 5px;
                white-space: nowrap;
            }

            a.onion-link {
                color: #00f2fe;
                text-decoration: none;
                transition: all 0.3s ease;
                font-weight: bold;
                letter-spacing: 0.5px;
                
                /* Truncation Logic */
                display: inline-block;
                vertical-align: bottom;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 100%; /* Default for desktop */
            }

            /* Mobile Responsive Rule */
            @media (max-width: 576px) {
                a.onion-link {
                    /* Adjust width to show roughly the first 8-10 characters */
                    max-width: 130px; 
                }
                .url-banner {
                    font-size: 0.9rem;
                }
            }

            a.onion-link:hover {
                color: #ffffff;
                text-shadow: 0 0 15px #00f2fe;
            }

            .main-wrapper {
                flex: 1;
                padding: 40px 20px;
                display: flex;
                align-items: stretch;
                justify-content: center;
            }
            
            .grid-container {
                display: grid;
                grid-template-columns: 4fr 6fr;
                gap: 40px;
                width: 100%;
                max-width: 1800px;
            }

            @media (max-width: 1400px) {
                .grid-container {
                    grid-template-columns: 1fr 1.5fr;
                }
            }

            @media (max-width: 991px) {
                .grid-container {
                    grid-template-columns: 1fr;
                }
                .timer-display { font-size: 2rem; }
            }

            .list-group-item {
                background: rgba(0,0,0,0.3)!important;
                border-color: rgba(255,255,255,0.05)!important;
                color: #e2e8f0!important;
                font-family: 'Courier New', monospace;
                font-size: 1.1rem;
                padding: 15px;
                margin-bottom: 5px;
                border-radius: 8px!important;
            }
            
            .btn-primary {
                background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
                border: none;
                transition: all 0.3s ease;
                color: #1a1a2e;
            }

            .btn-primary:hover:not(:disabled) {
                transform: translateY(-3px);
                box-shadow: 0 10px 20px rgba(0,242,254,0.4);
                color: #1a1a2e;
            }
            
            .btn-info {
                background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
                border: none;
                color: #1a1a2e;
                transition: all 0.3s ease;
            }
            
            .btn-info:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 20px rgba(56,239,125,0.4);
                color: #1a1a2e;
            }

            .btn-danger {
                background: linear-gradient(90deg, #ff416c 0%, #ff4b2b 100%);
                border: none;
                transition: all 0.3s ease;
            }

            .btn-danger:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 20px rgba(255, 65, 108, 0.4);
            }

            .keys-scroll {
                max-height: 500px; 
                overflow-y: auto;
                padding-right: 10px;
            }
            
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 4px; }
            ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }

            .header-title {
                font-size: 3.5rem;
                font-weight: 900;
                background: -webkit-linear-gradient(#ffffff, #a8b2d1);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
                line-height: 1.2;
            }
            
            .form-control {
                background-color: rgba(0,0,0,0.2) !important;
                border: 1px solid rgba(255,255,255,0.1) !important;
                color: white !important;
                font-family: monospace;
                padding: 15px;
                border-radius: 10px;
            }
            
            .form-control:focus {
                box-shadow: 0 0 0 0.25rem rgba(0, 242, 254, 0.25) !important;
                border-color: #00f2fe !important;
            }
        </style>
    </head>
    <body>
        <div class="url-banner">
            <span>🌐 Live Demo:</span> 
            <a href="http://vanity3yyoibkcgj6xbsvr72oh2prmiky5bbe7ogxyq662ewhpdsaeqd.onion/" target="_blank" class="onion-link">
                http://vanity3yyoibkcgj6xbsvr72oh2prmiky5bbe7ogxyq662ewhpdsaeqd.onion/
            </a>
        </div>

        <div class="main-wrapper">
            <div class="grid-container">
                <!-- Left Column -->
                <div class="d-flex flex-column gap-4">
                    <div class="glass-card p-4 p-xl-5 d-flex flex-column">
                        <h2 class="header-title">Onion Vanity Generator</h2>
                        <p class="fs-5 text-white-50 mb-5">Create your custom Tor V3 hidden service address powerfully & securely.</p>
                        
                        <div id="alertContainer"></div>

                        <form id="generateForm" class="mt-auto">
                            <div class="mb-4">
                                <label for="prefix" class="form-label fs-5 text-white-50">Desired Prefix</label>
                                <input type="text" id="prefix" name="prefix" class="form-control form-control-lg" placeholder="e.g., vanity" required>
                                <div class="form-text text-white-50 mt-2">Only base32 characters allowed (a-z, 2-7).</div>
                            </div>
                            <div class="row g-3 mt-4">
                                <div class="col-sm-6">
                                    <button id="generateBtn" type="submit" class="btn btn-primary btn-lg w-100 py-3 fw-bolder fs-5">🚀 Generate Keys</button>
                                </div>
                                <div class="col-sm-6">
                                    <button id="downloadBtn" type="button" class="btn btn-info btn-lg w-100 py-3 fw-bolder fs-5">📥 Download ZIP</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Right Column -->
                <div class="d-flex flex-column gap-4 w-100 h-100" style="min-height: 0;">
                    <div id="statusCard" class="glass-card p-4 p-xl-5 d-none d-flex flex-column" style="flex: 1;">
                        <h3 class="card-title fw-bold mb-4 border-bottom border-secondary border-opacity-25 pb-3">Live Mining Status</h3>
                        <div class="text-center my-auto py-4">
                            <p class="fs-5 text-info mb-2 text-uppercase tracking-wide font-monospace">Estimated Time Remaining</p>
                            <div id="countdownDisplay" class="timer-display">00:00:00</div>
                            <p id="statusMessage" class="fs-4 mt-4 font-monospace text-white-50"></p>
                        </div>
                        <button id="stopButton" class="btn btn-danger btn-lg w-100 py-3 fw-bolder fs-5 mt-auto">🛑 Stop Process</button>
                    </div>

                    <div id="keysCard" class="glass-card p-4 p-xl-5 d-none flex-column" style="display: flex; flex: 1; min-height: 0; overflow: hidden;">
                        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 border-bottom border-secondary border-opacity-25 pb-3 gap-3">
                            <h3 class="card-title fw-bold mb-0 fs-4 fs-sm-3">Generated Keys</h3>
                            <div class="d-flex flex-wrap align-items-center gap-2">
                                <button type="button" class="btn btn-outline-info btn-sm rounded-pill px-3 fw-bold flex-shrink-0" data-bs-toggle="modal" data-bs-target="#keysModal" id="viewAllBtn">View All</button>
                                <span class="badge bg-success bg-opacity-25 text-success fs-6 fs-sm-5 px-3 py-2 rounded-pill border border-success border-opacity-50 text-wrap text-break" id="keysPrefixBadge" style="max-width: 100%; word-break: break-all;"></span>
                            </div>
                        </div>
                        <div class="keys-scroll mt-3 w-100" id="keysCardBody" style="flex: 1; min-height: 0; overflow-y: auto;">
                            <div id="generatedKeysContainer"></div>
                        </div>
                    </div>
                    
                    <!-- Empty State -->
                    <div id="emptyState" class="glass-card p-4 p-xl-5 d-flex flex-column align-items-center justify-content-center text-center opacity-50 h-100">
                        <svg xmlns="http://www.w3.org/-2000/svg" width="80" height="80" fill="currentColor" class="bi bi-cpu mb-4 text-white-50" viewBox="0 0 16 16">
                            <path d="M5 0a.5.5 0 0 1 .5.5V2h1V.5a.5.5 0 0 1 1 0V2h1V.5a.5.5 0 0 1 1 0V2h1V.5a.5.5 0 0 1 1 0V2A2.5 2.5 0 0 1 14 4.5h1.5a.5.5 0 0 1 0 1H14v1h1.5a.5.5 0 0 1 0 1H14v1h1.5a.5.5 0 0 1 0 1H14v1h1.5a.5.5 0 0 1 0 1H14a2.5 2.5 0 0 1-2.5 2.5v1.5a.5.5 0 0 1-1 0V14h-1v1.5a.5.5 0 0 1-1 0V14h-1v1.5a.5.5 0 0 1-1 0V14h-1v1.5a.5.5 0 0 1-1 0V14A2.5 2.5 0 0 1 2 11.5H.5a.5.5 0 0 1 0-1H2v-1H.5a.5.5 0 0 1 0-1H2v-1H.5a.5.5 0 0 1 0-1H2v-1H.5a.5.5 0 0 1 0-1H2A2.5 2.5 0 0 1 4.5 2V.5A.5.5 0 0 1 5 0m-.5 3A1.5 1.5 0 0 0 3 4.5v7A1.5 1.5 0 0 0 4.5 13h7a1.5 1.5 0 0 0 1.5-1.5v-7A1.5 1.5 0 0 0 11.5 3zM5 6.5A1.5 1.5 0 0 1 6.5 5h3A1.5 1.5 0 0 1 11 6.5v3A1.5 1.5 0 0 1 9.5 11h-3A1.5 1.5 0 0 1 5 9.5z"/>
                        </svg>
                        <h4 class="text-white fw-bold">System Idle</h4>
                        <p class="text-white-50 mb-0 fs-5">Enter a prefix to begin mining operations.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal for All Generated URLs -->
        <div class="modal fade" id="keysModal" tabindex="-1" aria-labelledby="keysModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content" style="background: rgba(30, 30, 50, 0.95); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); color: #fff;">
                    <div class="modal-header border-bottom border-secondary border-opacity-25">
                        <h5 class="modal-title font-monospace text-info fw-bold" id="keysModalLabel">All Generated Addresses</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body p-4" style="background: rgba(0, 0, 0, 0.2);">
                        <div id="modalKeysContainer" class="d-flex flex-column gap-2" style="font-family: 'Courier New', monospace; word-break: break-all;">
                            <div class="text-white-50 text-center py-3">No keys generated yet.</div>
                        </div>
                    </div>
                    <div class="modal-footer border-top border-secondary border-opacity-25">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const form = document.getElementById('generateForm');
            const alertContainer = document.getElementById('alertContainer');
            const statusCard = document.getElementById('statusCard');
            const keysCard = document.getElementById('keysCard');
            const emptyState = document.getElementById('emptyState');
            const statusMessage = document.getElementById('statusMessage');
            const countdownDisplay = document.getElementById('countdownDisplay');
            const stopButton = document.getElementById('stopButton');
            const generateButton = document.getElementById('generateBtn');
            const downloadButton = document.getElementById('downloadBtn');
            const keysPrefixBadge = document.getElementById('keysPrefixBadge');

            let pollInterval = null;
            let countdownInterval = null;
            let currentKnownKeysLength = -1;
            let currentPrefix = '';

            function formatDuration(seconds) {
                if (seconds <= 0) return "00:00:00";
                const h = Math.floor(seconds / 3600);
                const m = Math.floor((seconds % 3600) / 60);
                const s = Math.floor(seconds % 60);
                return [h, m, s].map(v => v < 10 ? "0" + v : v).join(":");
            }

            function startCountdown(totalSeconds, elapsedSeconds) {
                clearInterval(countdownInterval);
                let remaining = totalSeconds - elapsedSeconds;
                
                const updateUI = () => {
                    countdownDisplay.innerText = formatDuration(remaining);
                    if (remaining <= 0) {
                        countdownDisplay.style.background = "-webkit-linear-gradient(#f6d365, #fda085)";
                        countdownDisplay.style.webkitBackgroundClip = "text";
                        countdownDisplay.innerText = "Prob > 50%";
                    } else {
                        countdownDisplay.style.background = "-webkit-linear-gradient(#00f2fe, #4facfe)";
                        countdownDisplay.style.webkitBackgroundClip = "text";
                    }
                };

                updateUI();
                countdownInterval = setInterval(() => {
                    remaining -= 1;
                    updateUI();
                }, 1000);
            }

            function showAlert(message, type = 'info') {
                alertContainer.innerHTML = `
                    <div class="alert alert-${type} bg-${type} bg-opacity-25 text-white border-${type} alert-dismissible fade show shadow" role="alert">
                        ${message}
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                `;
            }

            async function fetchStatus() {
                try {
                    const response = await fetch('/status');
                    const data = await response.json();
                    
                    if (data.prefix) {
                        keysCard.classList.remove('d-none');
                        emptyState.classList.add('d-none');
                        if (data.prefix !== currentPrefix) {
                            currentPrefix = data.prefix;
                            currentKnownKeysLength = -1;
                            keysPrefixBadge.innerText = data.prefix;
                        }
                        
                        if (data.keys.length !== currentKnownKeysLength) {
                            currentKnownKeysLength = data.keys.length;
                            const container = document.getElementById('generatedKeysContainer');
                            const modalContainer = document.getElementById('modalKeysContainer');
                            if (data.keys.length === 0) {
                                container.innerHTML = '<div class="d-flex h-100 align-items-center justify-content-center pt-4 pb-4"><div class="spinner-grow text-info me-3" role="status"></div><span class="text-white-50 fs-5 font-monospace">Searching blocks...</span></div>';
                                modalContainer.innerHTML = '<div class="text-white-50 text-center py-3">No keys generated yet.</div>';
                                document.getElementById('viewAllBtn').innerHTML = 'View All';
                            } else {
                                container.innerHTML = '<div class="list-group list-group-flush gap-2"><div class="list-group-item d-flex flex-wrap justify-content-between align-items-center shadow-sm gap-2"><code style="word-break: break-all;">' + data.keys[0] + '</code> <span class="badge bg-success bg-opacity-75 rounded-pill flex-shrink-0">Latest</span></div></div>';
                                modalContainer.innerHTML = data.keys.map((key, index) => `
                                    <div class="list-group-item d-flex flex-wrap justify-content-between align-items-center shadow-sm p-3 rounded gap-2" style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); color: #e2e8f0;">
                                        <code style="word-break: break-all;">${key}</code>
                                        <div class="flex-shrink-0">
                                            ${index === 0 ? '<span class="badge bg-success bg-opacity-75 rounded-pill">Latest</span>' : '<span class="text-white-50 small">#' + (data.keys.length - index) + '</span>'}
                                        </div>
                                    </div>
                                `).join('');
                                document.getElementById('viewAllBtn').innerHTML = `View All <span class="badge bg-info text-dark ms-1 rounded-pill">#${data.keys.length}</span>`;
                            }
                            const keysCardBody = document.getElementById('keysCardBody');
                            keysCardBody.scrollTop = keysCardBody.scrollHeight;
                        }
                    }

                    if (data.generating) {
                        statusMessage.innerHTML = `Target Prefix: <span class="text-info fw-bold">${data.prefix}</span>`;
                        statusCard.classList.remove('d-none');
                        keysCard.style.gridColumn = "";
                        emptyState.classList.add('d-none');
                        document.getElementById('prefix').disabled = true;
                        generateButton.disabled = true;
                        
                        if (!countdownInterval && data.estimate_seconds) {
                            startCountdown(data.estimate_seconds, data.elapsed_seconds);
                        }
                    } else {
                        statusCard.classList.add('d-none');
                        keysCard.style.gridColumn = "1 / -1";
                        document.getElementById('prefix').disabled = false;
                        generateButton.disabled = false;
                        clearInterval(countdownInterval);
                        countdownInterval = null;
                        
                        if (keysCard.classList.contains('d-none')) {
                            emptyState.classList.remove('d-none');
                        }
                    }

                    return data.generating;
                } catch (e) {
                    console.error("Failed to fetch status:", e);
                    return false;
                }
            }

            function startPolling() {
                if (!pollInterval) {
                    pollInterval = setInterval(async () => {
                        const isGenerating = await fetchStatus();
                        if (!isGenerating) {
                            clearInterval(pollInterval);
                            pollInterval = null;
                        }
                    }, 2000);
                }
            }

            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const formData = new FormData(form);
                showAlert('Initializing mining operation...', 'info');

                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });

                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();
                if (!data.success) {
                    showAlert(`<strong>Error:</strong> ${data.error}`, 'danger');
                    return;
                }

                showAlert('<strong>Mining process initiated.</strong> Engine running.', 'success');
                currentKnownKeysLength = -1; 
                await fetchStatus();
                startPolling();
            });

            stopButton.addEventListener('click', async () => {
                const response = await fetch('/stop', { method: 'POST' });
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                const data = await response.json();
                if (data.success) {
                    showAlert(`<strong>Halted:</strong> ${data.message}`, 'warning');
                    await fetchStatus();
                }
            });

            document.getElementById('downloadBtn').addEventListener('click', () => {
                const prefix = document.getElementById('prefix').value || currentPrefix;
                if (!prefix) {
                    showAlert('Enter a prefix or generate one first', 'warning');
                    return;
                }
                window.location.href = `/download?prefix=${encodeURIComponent(prefix)}`;
            });

            window.addEventListener('load', async () => {
                const isGenerating = await fetchStatus();
                if (isGenerating) startPolling();
            });
        </script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/generate', methods=['POST'])
@requires_auth
def generate():
    global current_process, current_prefix, start_time
    prefix = request.form.get('prefix')
    if not prefix:
        return jsonify({'success': False, 'error': 'No prefix provided'}), 400

    if current_process and current_process.poll() is None:
        return jsonify({'success': False, 'error': 'Already generating.'}), 400

    current_prefix = prefix
    start_time = time.time()
    
    os.makedirs(f'mkp224o/onions/{prefix}', exist_ok=True)
    # Ensure mkp224o exists or handle error
    cmd = ['./mkp224o', '-d', f'onions/{prefix}', prefix]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=os.setsid, cwd='mkp224o')
        current_process = process
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'mkp224o binary not found in directory.'}), 500

    def monitor_process(proc):
        global current_process
        proc.wait()
        if current_process == proc:
            current_process = None

    threading.Thread(target=monitor_process, args=(process,)).start()

    raw_est = get_raw_estimate(prefix)
    return jsonify({
        'success': True, 
        'message': 'Generation started.', 
        'estimate_seconds': raw_est,
        'estimate_str': format_time(raw_est)
    })

@app.route('/status')
def status():
    global current_process, current_prefix, start_time
    
    keys = []
    if current_prefix:
        onions_dir = f'mkp224o/onions/{current_prefix}'
        if os.path.exists(onions_dir):
            try:
                items_with_mtime = []
                for item in os.listdir(onions_dir):
                    item_path = os.path.join(onions_dir, item)
                    if item.endswith('.onion') and os.path.isdir(item_path):
                        items_with_mtime.append((item, os.path.getmtime(item_path)))
                items_with_mtime.sort(key=lambda x: x[1], reverse=True)
                keys = [k[0] for k in items_with_mtime]
            except Exception: pass

    is_generating = current_process is not None and current_process.poll() is None
    elapsed = (time.time() - start_time) if (is_generating and start_time) else 0
    raw_est = get_raw_estimate(current_prefix) if current_prefix else None

    return jsonify({
        'generating': is_generating,
        'prefix': current_prefix,
        'keys': keys,
        'estimate_seconds': raw_est,
        'elapsed_seconds': elapsed
    })

@app.route('/stop', methods=['POST'])
@requires_auth
def stop():
    global current_process
    if current_process and current_process.poll() is None:
        try:
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            current_process = None
            return jsonify({'success': True, 'message': 'Generation stopped.'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    return jsonify({'success': False, 'message': 'No active generation.'}), 400

@app.route('/download')
@requires_auth
def download():
    prefix = request.args.get('prefix')
    if not prefix: return jsonify({'error': 'No prefix'}), 400

    onions_dir = f'mkp224o/onions/{prefix}'
    if not os.path.exists(onions_dir): return jsonify({'error': 'Not found'}), 404

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, filenames in os.walk(onions_dir):
            for filename in filenames:
                path = os.path.join(root, filename)
                zip_file.write(path, os.path.relpath(path, onions_dir))

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'{prefix}_onions.zip', mimetype='application/zip')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
