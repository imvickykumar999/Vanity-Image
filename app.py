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

def estimate_time(prefix):
    length = len(prefix)
    if length < 2 or length > 10:
        return "Estimation not available for this length."

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

    rate = 6700000
    if length in trials:
        time_sec = trials[length] / rate
        if time_sec < 60:
            return f"~{time_sec:.1f} seconds"
        elif time_sec < 3600:
            return f"~{time_sec/60:.1f} minutes"
        else:
            return f"~{time_sec/3600:.1f} hours"
    return "Unknown"

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
                                <div class="card-body">
                                    <h5 class="card-title">Generation Status</h5>
                                    <p id="statusMessage" class="card-text"></p>
                                    <button id="stopButton" class="btn btn-danger w-100">Stop Generating</button>
                                </div>
                            </div>

                            <div class="mt-4">
                                <h5>How it works</h5>
                                <p class="text-muted">This page uses AJAX to call the backend without reloading. Results are saved in the <code>onions</code> directory.</p>
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
            const stopButton = document.getElementById('stopButton');
            const generateButton = document.getElementById('generateBtn');
            const downloadButton = document.getElementById('downloadBtn');

            function showAlert(message, type = 'info') {
                alertContainer.innerHTML = `
                    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                        ${message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                `;
            }

            function updateStatus(message) {
                statusMessage.innerHTML = message;
                statusCard.classList.remove('d-none');
            }

            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const formData = new FormData(form);
                showAlert('Starting generation...', 'info');

                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (!data.success) {
                    showAlert(`<strong>Error:</strong> ${data.error}`, 'danger');
                    statusCard.classList.add('d-none');
                    return;
                }

                showAlert('<strong>Generation started.</strong>', 'success');
                updateStatus(`Prefix: <strong>${formData.get('prefix')}</strong><br>Estimated 50% time: <strong>${data.estimate}</strong><br>${data.message}`);
                document.getElementById('prefix').disabled = true;
                generateButton.disabled = true;
                downloadButton.disabled = true;
            });

            stopButton.addEventListener('click', async () => {
                const response = await fetch('/stop', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    showAlert(`<strong>Stopped:</strong> ${data.message}`, 'warning');
                    statusCard.classList.add('d-none');
                    document.getElementById('prefix').disabled = false;
                    generateButton.disabled = false;
                    downloadButton.disabled = false;
                } else {
                    showAlert(`<strong>Error:</strong> ${data.message}`, 'danger');
                }
            });

            document.getElementById('downloadBtn').addEventListener('click', () => {
                const prefix = document.getElementById('prefix').value;
                if (!prefix) {
                    showAlert('Enter a prefix first', 'warning');
                    return;
                }
                window.location.href = `/download?prefix=${encodeURIComponent(prefix)}`;
            });

            window.addEventListener('load', async () => {
                const response = await fetch('/status');
                const data = await response.json();
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
            });
        </script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/generate', methods=['POST'])
def generate():
    global current_process, current_prefix
    prefix = request.form.get('prefix')
    if not prefix:
        return jsonify({'success': False, 'error': 'No prefix provided'}), 400

    if current_process and current_process.poll() is not None:
        return jsonify({'success': False, 'error': 'Already generating. Stop first.'}), 400

    current_prefix = prefix
    os.makedirs(f'mkp224o/onions/{prefix}', exist_ok=True)
    cmd = ['./mkp224o', '-d', f'onions/{prefix}', prefix]
    current_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=os.setsid, cwd='mkp224o')

    time.sleep(0.2)
    if current_process.poll() is not None:
        _, stderr = current_process.communicate()
        return_code = current_process.returncode
        current_process = None
        if return_code != 0:
            error_text = stderr.decode(errors='replace').strip()
            return jsonify({'success': False, 'error': error_text}), 400
        return jsonify({'success': True, 'message': 'mkp224o completed successfully. Check the onions folder for results.', 'estimate': estimate_time(prefix)})

    def run_mkp224o():
        global current_process
        try:
            _, stderr = current_process.communicate()
            if stderr:
                print("Error:", stderr.decode(errors='replace'))
        except Exception:
            pass
        finally:
            current_process = None

    thread = threading.Thread(target=run_mkp224o)
    thread.start()

    return jsonify({'success': True, 'message': 'Generation started.', 'estimate': estimate_time(prefix)})

@app.route('/status')
def status():
    global current_process, current_prefix
    if current_process and current_process.poll() is None:
        return jsonify({'generating': True, 'prefix': current_prefix, 'estimate': estimate_time(current_prefix)})
    else:
        return jsonify({'generating': False})

@app.route('/stop', methods=['POST'])
def stop():
    global current_process
    if current_process and current_process.poll() is None:
        os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
        current_process = None
        return jsonify({'success': True, 'message': 'Generation stopped.'})

    return jsonify({'success': False, 'message': 'No active generation to stop.'}), 400

@app.route('/download')
def download():
    prefix = request.args.get('prefix')
    if not prefix:
        return jsonify({'error': 'No prefix specified'}), 400

    onions_dir = f'mkp224o/onions/{prefix}'
    if not os.path.exists(onions_dir):
        return jsonify({'error': f'No folder found for prefix {prefix}'}), 404

    files = []
    for root, dirs, filenames in os.walk(onions_dir):
        for filename in filenames:
            files.append(os.path.join(root, filename))

    if not files:
        return jsonify({'error': 'No files to download'}), 404

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in files:
            arcname = os.path.relpath(file_path, onions_dir)
            zip_file.write(file_path, arcname)

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'{prefix}_onions.zip', mimetype='application/zip')

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=2000,
        debug=True
    )
