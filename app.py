from flask import Flask, request, jsonify, render_template_string, send_file
import subprocess
import os
import threading
import signal
import time
import zipfile
import io

app = Flask(__name__)

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
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Onion Address Generator</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .timer-display {
                font-family: 'Courier New', Courier, monospace;
                font-size: 1.5rem;
                font-weight: bold;
                color: #0d6efd;
            }
        </style>
    </head>
    <body class="bg-light">
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-lg-8">
                    <div class="card shadow-sm">
                        <div class="card-header bg-primary text-white">
                            <h3 class="card-title mb-0">Onion Address Generator</h3>
                        </div>
                        <div class="card-body">
                            <div id="alertContainer"></div>

                            <form id="generateForm">
                                <div class="mb-3">
                                    <label for="prefix" class="form-label">Enter prefix</label>
                                    <input type="text" id="prefix" name="prefix" class="form-control" placeholder="e.g., heyvix" required>
                                </div>
                                <div class="row gx-2">
                                    <div class="col">
                                        <button id="generateBtn" type="submit" class="btn btn-primary w-100">Generate</button>
                                    </div>
                                    <div class="col">
                                        <button id="downloadBtn" type="button" class="btn btn-info w-100">Download ZIP</button>
                                    </div>
                                </div>
                            </form>

                            <div id="statusCard" class="card mt-4 d-none">
                                <div class="card-body text-center">
                                    <h5 class="card-title">Generation Status</h5>
                                    <div class="my-3">
                                        <p class="mb-1 text-muted">Estimated 50% probability countdown:</p>
                                        <div id="countdownDisplay" class="timer-display">00:00:00</div>
                                    </div>
                                    <p id="statusMessage" class="card-text text-start"></p>
                                    <button id="stopButton" class="btn btn-danger w-100">Stop Generating</button>
                                </div>
                            </div>

                            <div id="keysCard" class="card mt-4 d-none">
                                <div class="card-header bg-success text-white">
                                    <h5 class="card-title mb-0">Generated for <code class="text-white" id="keysPrefix"></code></h5>
                                </div>
                                <div class="card-body" id="keysCardBody" style="max-height: 250px; overflow-y: auto;">
                                    <div id="generatedKeysContainer"></div>
                                </div>
                            </div>

                            <div class="mt-4">
                                <h5>How it works</h5>
                                <p class="text-muted">Addresses are brute-forced using <code>mkp224o</code>. The countdown represents the statistical 50% probability of finding a match.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            const form = document.getElementById('generateForm');
            const alertContainer = document.getElementById('alertContainer');
            const statusCard = document.getElementById('statusCard');
            const statusMessage = document.getElementById('statusMessage');
            const countdownDisplay = document.getElementById('countdownDisplay');
            const stopButton = document.getElementById('stopButton');
            const generateButton = document.getElementById('generateBtn');
            const downloadButton = document.getElementById('downloadBtn');

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
                        countdownDisplay.classList.remove('text-primary');
                        countdownDisplay.classList.add('text-warning');
                        countdownDisplay.innerText = "Probability > 50%...";
                    } else {
                        countdownDisplay.classList.add('text-primary');
                        countdownDisplay.classList.remove('text-warning');
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
                    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                        ${message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                `;
            }

            async function fetchStatus() {
                try {
                    const response = await fetch('/status');
                    const data = await response.json();
                    
                    if (data.prefix) {
                        document.getElementById('keysCard').classList.remove('d-none');
                        if (data.prefix !== currentPrefix) {
                            currentPrefix = data.prefix;
                            currentKnownKeysLength = -1;
                            document.getElementById('keysPrefix').innerText = data.prefix;
                        }
                        
                        if (data.keys.length !== currentKnownKeysLength) {
                            currentKnownKeysLength = data.keys.length;
                            const container = document.getElementById('generatedKeysContainer');
                            if (data.keys.length === 0) {
                                container.innerHTML = '<p class="text-muted mb-0 text-center">Searching...</p>';
                            } else {
                                container.innerHTML = '<ul class="list-group">' + data.keys.map(k => `<li class="list-group-item d-flex justify-content-between"><code>${k}</code> <span class="badge bg-success">Found</span></li>`).join('') + '</ul>';
                            }
                            const keysCardBody = document.getElementById('keysCardBody');
                            keysCardBody.scrollTop = keysCardBody.scrollHeight;
                        }
                    }

                    if (data.generating) {
                        statusMessage.innerHTML = `Prefix: <strong>${data.prefix}</strong>`;
                        statusCard.classList.remove('d-none');
                        document.getElementById('prefix').disabled = true;
                        generateButton.disabled = true;
                        
                        // Handle timer
                        if (!countdownInterval && data.estimate_seconds) {
                            startCountdown(data.estimate_seconds, data.elapsed_seconds);
                        }
                    } else {
                        statusCard.classList.add('d-none');
                        document.getElementById('prefix').disabled = false;
                        generateButton.disabled = false;
                        clearInterval(countdownInterval);
                        countdownInterval = null;
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

            async function fetchStatus() {
                try {
                    const response = await fetch('/status');
                    const data = await response.json();
                    
                    if (data.prefix) {
                        document.getElementById('keysCard').classList.remove('d-none');
                        
                        if (data.prefix !== currentPrefix) {
                            currentPrefix = data.prefix;
                            currentKnownKeysLength = -1;
                            document.getElementById('keysPrefix').innerText = data.prefix;
                        }
                        
                        if (data.keys.length !== currentKnownKeysLength) {
                            currentKnownKeysLength = data.keys.length;
                            const container = document.getElementById('generatedKeysContainer');
                            if (data.keys.length === 0) {
                                container.innerHTML = '<p class="text-muted mb-0">No addresses generated yet...</p>';
                            } else {
                                container.innerHTML = '<ul class="list-group">' + data.keys.map(k => `<li class="list-group-item"><code>${k}</code></li>`).join('') + '</ul>';
                            }
                            // Auto-scroll to bottom
                            const keysCardBody = document.getElementById('keysCardBody');
                            if (keysCardBody) {
                                keysCardBody.scrollTop = keysCardBody.scrollHeight;
                            }
                        }
                    } else {
                        document.getElementById('keysCard').classList.add('d-none');
                        currentKnownKeysLength = -1;
                        currentPrefix = '';
                    }

                    if (data.generating) {
                        updateStatus(`Prefix: <strong>${data.prefix}</strong><br>Estimated 50% time: <strong>${data.estimate}</strong><br>Generation in progress.`);
                        document.getElementById('prefix').disabled = true;
                        generateButton.disabled = true;
                        downloadButton.disabled = true;
                    } else {
                        statusCard.classList.add('d-none');
                        document.getElementById('prefix').disabled = false;
                        generateButton.disabled = false;
                        downloadButton.disabled = false;
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
                showAlert('Initializing mkp224o...', 'info');

                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (!data.success) {
                    showAlert(`<strong>Error:</strong> ${data.error}`, 'danger');
                    return;
                }

                showAlert('<strong>Generation process started.</strong>', 'success');
                // resetting known list to force UI refresh for new form submit
                currentKnownKeysLength = -1; 
                await fetchStatus();
                startPolling();
            });

            stopButton.addEventListener('click', async () => {
                const response = await fetch('/stop', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    showAlert(`<strong>Stopped:</strong> ${data.message}`, 'warning');
                    await fetchStatus();
                } else {
                    showAlert(`<strong>Error:</strong> ${data.message}`, 'danger');
                }
            });

            document.getElementById('downloadBtn').addEventListener('click', () => {
                const prefix = document.getElementById('prefix').value || currentPrefix;
                if (!prefix) {
                    showAlert('Enter a prefix first or generate an address', 'warning');
                    return;
                }
                window.location.href = `/download?prefix=${encodeURIComponent(prefix)}`;
            });

            window.addEventListener('load', async () => {
                const isGenerating = await fetchStatus();
                if (isGenerating) {
                    startPolling();
                }
            });
        </script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/generate', methods=['POST'])
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
                for item in os.listdir(onions_dir):
                    if item.endswith('.onion') and os.path.isdir(os.path.join(onions_dir, item)):
                        keys.append(item)
            except Exception:
                pass

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
    app.run(host='0.0.0.0', port=2000, debug=True)
