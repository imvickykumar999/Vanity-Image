import os
import json
import logging
import requests
from flask import Flask, render_template_string, request, jsonify, flash, redirect, url_for
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "railway-automation-secret-123")

# --- Railway API Client ---

class RailwayClient:
    """Refined Client for interacting with Railway's GraphQL API."""
    
    API_ENDPOINT = "https://backboard.railway.app/graphql/v2"
    
    def __init__(self, api_token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def _execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"query": query, "variables": variables or {}}
        try:
            response = self.session.post(self.API_ENDPOINT, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
                logger.error(f"GraphQL Error: {error_msg}")
                raise ValueError(error_msg)
            
            return data.get("data", {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Network Error: {str(e)}")
            raise ConnectionError(f"Failed to connect to Railway API: {str(e)}")

    def create_project(self, name: str) -> str:
        mutation = """
        mutation CreateProject($input: ProjectCreateInput!) {
            projectCreate(input: $input) { id name }
        }
        """
        result = self._execute(mutation, {"input": {"name": name}})
        return result["projectCreate"]["id"]

    def create_service(self, project_id: str, name: str, image: str) -> str:
        mutation = """
        mutation CreateService($input: ServiceCreateInput!) {
            serviceCreate(input: $input) { id }
        }
        """
        # Note: Railway often prefers creating service then linking source
        result = self._execute(mutation, {
            "input": {
                "projectId": project_id, 
                "name": name,
                "source": {"image": image}
            }
        })
        return result["serviceCreate"]["id"]

    def get_first_environment_id(self, project_id: str) -> str:
        query = """
        query GetEnvs($projectId: String!) {
            environments(projectId: $projectId) {
                edges { node { id name } }
            }
        }
        """
        result = self._execute(query, {"projectId": project_id})
        envs = result.get("environments", {}).get("edges", [])
        if not envs:
            raise ValueError("No environments found for this project.")
        return envs[0]["node"]["id"]

    def set_variables(self, project_id: str, env_id: str, service_id: str, variables: Dict[str, str]):
        mutation = """
        mutation UpsertVar($input: VariableUpsertInput!) {
            variableUpsert(input: $input)
        }
        """
        for k, v in variables.items():
            if not v: continue
            self._execute(mutation, {
                "input": {
                    "projectId": project_id,
                    "environmentId": env_id,
                    "serviceId": service_id,
                    "name": k,
                    "value": v
                }
            })

# --- Web UI Templates ---

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Railway Automation Hub</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-2xl w-full bg-slate-800 rounded-xl shadow-2xl border border-slate-700 overflow-hidden">
        <div class="p-6 border-b border-slate-700 bg-slate-800/50">
            <h1 class="text-2xl font-bold flex items-center gap-2">
                <span class="text-blue-400">🚀</span> Railway Deployer
            </h1>
            <p class="text-slate-400 text-sm mt-1">Automate Docker deployments to new Railway projects.</p>
        </div>

        <form method="POST" action="/deploy" class="p-6 space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Project Name</label>
                    <input type="text" name="project_name" required placeholder="My Awesome Project"
                           class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-blue-500 outline-none transition">
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Docker Image</label>
                    <input type="text" name="docker_image" required placeholder="nginx:latest"
                           class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-blue-500 outline-none transition">
                </div>
            </div>

            <div>
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Service Name (Optional)</label>
                <input type="text" name="service_name" placeholder="web-service"
                       class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-blue-500 outline-none transition">
            </div>

            <div class="space-y-3">
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500">Environment Variables</label>
                <div id="vars-container" class="space-y-2">
                    <div class="flex gap-2">
                        <input type="text" name="var_key[]" placeholder="KEY" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm outline-none">
                        <input type="text" name="var_val[]" placeholder="VALUE" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm outline-none">
                    </div>
                </div>
                <button type="button" onclick="addVarRow()" class="text-xs text-blue-400 hover:text-blue-300 transition">+ Add Variable</button>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="p-4 rounded-lg text-sm {{ 'bg-red-900/50 text-red-200 border border-red-700' if category == 'error' else 'bg-green-900/50 text-green-200 border border-green-700' }}">
                    {{ message }}
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}

            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg transition shadow-lg shadow-blue-900/20 active:transform active:scale-[0.98]">
                Launch Project
            </button>
        </form>
    </div>

    <script>
        function addVarRow() {
            const container = document.getElementById('vars-container');
            const div = document.createElement('div');
            div.className = 'flex gap-2';
            div.innerHTML = `
                <input type="text" name="var_key[]" placeholder="KEY" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm outline-none">
                <input type="text" name="var_val[]" placeholder="VALUE" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm outline-none">
            `;
            container.appendChild(div);
        }
    </script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route('/deploy', methods=['POST'])
def deploy():
    token = os.getenv("RAILWAY_TOKEN")
    if not token:
        flash("RAILWAY_TOKEN not found in environment variables.", "error")
        return redirect(url_for('index'))

    # Form Data
    proj_name = request.form.get('project_name')
    image = request.form.get('docker_image')
    svc_name = request.form.get('service_name') or "web-server"
    
    # Dynamic Variables
    keys = request.form.getlist('var_key[]')
    vals = request.form.getlist('var_val[]')
    env_vars = {k: v for k, v in zip(keys, vals) if k.strip()}

    try:
        client = RailwayClient(token)
        
        logger.info(f"Creating project: {proj_name}")
        project_id = client.create_project(proj_name)
        
        logger.info(f"Creating service: {svc_name}")
        service_id = client.create_service(project_id, svc_name, image)
        
        logger.info("Fetching environment...")
        env_id = client.get_first_environment_id(project_id)
        
        if env_vars:
            logger.info(f"Setting {len(env_vars)} variables...")
            client.set_variables(project_id, env_id, service_id, env_vars)
        
        flash(f"Successfully deployed! Project ID: {project_id}", "success")
        return render_template_string("""
            <script>
                alert('Success! Redirecting to Railway Dashboard.');
                window.location.href = 'https://railway.app/project/{{ pid }}';
            </script>
        """, pid=project_id)

    except Exception as e:
        logger.exception("Deployment failed")
        flash(f"Deployment failed: {str(e)}", "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    # Use environment variables for local testing
    # export RAILWAY_TOKEN='your_token_here' // macOS/Linux
    # set RAILWAY_TOKEN='your_token_here'    // windows cmd
    # $env:RAILWAY_TOKEN = 'your_token_here' // powershell
    app.run(host='0.0.0.0', port=5000, debug=False)
