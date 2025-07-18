# main.py
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# Initialize the Flask application
app = Flask(__name__)

# IMPORTANT: Set up CORS to allow requests from your hosted frontend.
# For development, you can allow all origins ('*').
# For production, you should restrict this to your website's domain.
# Example: CORS(app, resources={r"/api/*": {"origins": "https://your-homework-app.com"}})
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Retrieve your Google AI API key from environment variables for security
# To run this:
# On Linux/macOS: export GOOGLE_API_KEY="YOUR_API_KEY"
# On Windows: set GOOGLE_API_KEY="YOUR_API_KEY"
# Then run: python main.py
API_KEY = os.environ.get("GOOGLE_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=AIzaSyAGJTg9ibD2iyi6rRts-CJic4S8FQPqjWQ"

# --- API Endpoint for Generating Questions and Evaluations ---
@app.route('/api/generate', methods=['POST'])
def generate_content():
    """
    Receives a prompt from the frontend, adds the API key,
    and forwards it to the Google Gemini API.
    """
    if not API_KEY:
        return jsonify({"error": "API key is not configured on the server."}), 500

    # Get the JSON data sent from the frontend
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"error": "Invalid request. 'prompt' is required."}), 400

    prompt = data.get('prompt')
    generation_config = data.get('generationConfig', {}) # Get generation config if provided

    # Construct the payload for the Google API
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }
    if generation_config:
        payload["generationConfig"] = generation_config

    headers = {
        'Content-Type': 'application/json'
    }

    try:
        # Make the request to the actual Google API
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        # Return the Google API's response directly to the frontend
        return jsonify(response.json())

    except requests.exceptions.HTTPError as http_err:
        # Log the error for debugging on the server
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}")
        return jsonify({"error": "An error occurred with the AI service.", "details": response.text}), response.status_code
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# --- API Endpoint for Getting Hints (Simpler version) ---
@app.route('/api/get-hint', methods=['POST'])
def get_hint():
    """
    A specific endpoint for hints which doesn't require complex JSON parsing.
    """
    if not API_KEY:
        return jsonify({"error": "API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"error": "Invalid request. 'prompt' is required."}), 400

    prompt = data.get('prompt')
    
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        print(f"An error occurred while fetching hint: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


# To run the server, you would use a command like:
# flask --app main run --port=5001
# The server will then be available at http://127.0.0.1:5001
if __name__ == '__main__':
    # Note: `debug=True` is for development only. Do not use in production.
    app.run(host='0.0.0.0', port=5001, debug=True)

