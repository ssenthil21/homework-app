# api/index.py
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# Initialize the Flask application
# Vercel will automatically find this 'app' variable
app = Flask(__name__)

# IMPORTANT: Set up CORS for your Vercel domain
# This allows your frontend to talk to your backend
CORS(app, resources={r"/api/*": {"origins": "https://homework-app-psi.vercel.app"}})

# Retrieve your Google AI API key from Vercel's Environment Variables
API_KEY = os.environ.get("GOOGLE_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# --- API Endpoint for Generating Questions and Evaluations ---
@app.route('/api/generate', methods=['POST'])
def generate_content():
    if not API_KEY:
        return jsonify({"error": "API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"error": "Invalid request. 'prompt' is required."}), 400

    prompt = data.get('prompt')
    generation_config = data.get('generationConfig', {})

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }
    if generation_config:
        payload["generationConfig"] = generation_config

    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}")
        return jsonify({"error": "An error occurred with the AI service.", "details": response.text}), response.status_code
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# --- API Endpoint for Getting Hints ---
@app.route('/api/get-hint', methods=['POST'])
def get_hint():
    if not API_KEY:
        return jsonify({"error": "API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"error": "Invalid request. 'prompt' is required."}), 400

    prompt = data.get('prompt')
    
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        print(f"An error occurred while fetching hint: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# Note: The if __name__ == '__main__': block is not needed for Vercel
