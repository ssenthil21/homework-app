# api/index.py
import os
import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# Configure CORS to allow requests from your Vercel domain and localhost.
CORS(app)

# Get API Key from Environment Variables and strip any whitespace
API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

def call_gemini_api(prompt, generation_config=None):
    """Helper function to call the Gemini API."""
    if not API_KEY:
        return jsonify({"error": "API key is not configured on the server."}), 500

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if generation_config:
        payload["generationConfig"] = generation_config

    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        gemini_response = response.json()
        
        if not gemini_response.get('candidates'):
            print("API response missing 'candidates':", gemini_response)
            return jsonify({"error": "Received an invalid response from the AI service."}), 500
            
        content_text = gemini_response['candidates'][0]['content']['parts'][0]['text']
        
        if generation_config and generation_config.get("responseMimeType") == "application/json":
            try:
                parsed_json = json.loads(content_text)
                return jsonify(parsed_json)
            except json.JSONDecodeError as e:
                print(f"Failed to parse LLM JSON response: {e}")
                print(f"Content was: {content_text}")
                return jsonify({"error": "Failed to parse LLM JSON response"}), 500
        else:
            return jsonify({"text": content_text})

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}")
        return jsonify({"error": "An error occurred with the AI service.", "details": response.text}), response.status_code
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/generate', methods=['POST'])
def generate_handler():
    data = request.get_json()
    required_fields = ['classLevel', 'subject', 'topic', 'difficulty']
    
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return jsonify({"error": f"Missing or empty required fields: {', '.join(missing_fields)}"}), 400

    # Build the base prompt
    prompt = (
        f"Act as a Primary School teacher in Singapore. "
        f"Generate a quiz with exactly 5 questions for a {data['classLevel']} student. "
        f"The subject is {data['subject']} and the specific topic is {data['topic']}. "
        f"The difficulty level should be {data['difficulty']}. "
        "The quiz must have this structure: "
        "1. Two 'single-choice' questions (select one correct answer from 4 options). "
        "2. One 'multi-select' question (select one or more correct answers from 4 options). "
        "3. Two 'free-text' questions (open-ended questions requiring a written answer). "
        "Ensure the questions are aligned with the Singapore MOE syllabus. "
    )

    # Add instruction to avoid repeating questions if a history is provided
    previous_questions = data.get('previous_questions', [])
    if previous_questions:
        # Create a formatted list of previous questions for the prompt
        previous_questions_text = "\n".join([f"- {q}" for q in previous_questions])
        prompt += (
            "\nIMPORTANT: To ensure variety, do not generate any of the following questions that the student has already answered for this topic:\n"
            f"{previous_questions_text}\n"
            "Also, try to create questions with different patterns and structures than the ones listed above."
        )

    # Add the final JSON formatting instruction
    prompt += (
        "\nReturn a single JSON object with a key 'questions', which is an array of 5 question objects. "
        "Each question object must have: a 'type' (string: 'single-choice', 'multi-select', or 'free-text'), "
        "a 'question' (string), and for choice questions, an 'options' array of 4 strings."
    )
    
    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT", "properties": { "questions": { "type": "ARRAY", "items": { "type": "OBJECT", "properties": { "type": {"type": "STRING"}, "question": {"type": "STRING"}, "options": {"type": "ARRAY", "items": {"type": "STRING"}} }, "required": ["type", "question"] } } }
        }
    }
    return call_gemini_api(prompt, generation_config)

@app.route('/evaluate', methods=['POST'])
def evaluate_handler():
    data = request.get_json()
    if not data or 'questions' not in data or 'answers' not in data:
        return jsonify({"error": "Missing 'questions' or 'answers' in request."}), 400

    questions_and_answers_text = ""
    for i, q in enumerate(data['questions']):
        answer_text = str(data['answers'][i]) # Convert answer to string for the prompt
        questions_and_answers_text += f"Question {i+1} (type: {q['type']}): {q['question']}\nOptions: {q.get('options', 'N/A')}\nStudent's Answer: {answer_text}\n\n"

    prompt = (
        f"Act as a Primary School teacher in Singapore. "
        f"Evaluate the following questions and student answers. For each one, provide whether it is correct, the correct answer (be concise), and a simple, encouraging one-sentence explanation. "
        f"Here are the questions and answers:\n{questions_and_answers_text}"
        f"Return the response as a single JSON object with a key 'evaluation', which is an array of 5 objects. "
        f"Each object must have three keys: 'is_correct' (boolean), 'correct_answer' (string), and 'explanation' (string)."
    )

    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT", "properties": { "evaluation": { "type": "ARRAY", "items": { "type": "OBJECT", "properties": { "is_correct": {"type": "BOOLEAN"}, "correct_answer": {"type": "STRING"}, "explanation": {"type": "STRING"} }, "required": ["is_correct", "correct_answer", "explanation"] } } }
        }
    }
    return call_gemini_api(prompt, generation_config)

@app.route('/get-hint', methods=['POST'])
def get_hint_handler():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Missing 'question' in request."}), 400
    
    prompt = f"Provide a simple one-sentence hint for a Primary 3 student for the following question, but do not give away the answer: \"{data['question']}\""
    
    return call_gemini_api(prompt)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
