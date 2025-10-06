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

P3_YEAR_END_TOPICS = {
    "English": [
        "Vocab MCQ",
        "Grammar MCQ",
        "Grammar Cloze",
        "Comprehension Cloze",
        "Sentence Combining",
        "Comprehension (Open-Ended)"
    ],
    "Maths": [
        "Numbers to 10 000",
        "Addition and Subtraction",
        "Money",
        "Multiplication Tables of 6, 7, 8 and 9",
        "Multiplication and Division",
        "More Word Problems",
        "Bar Graphs",
        "Angles",
        "Perpendicular and Parallel Lines",
        "Fractions",
        "Length, Mass and Volume",
        "Area and Perimeter",
        "Time"
    ],
    "Science": [
        "Diversity of Living Things",
        "Classification of Living Things",
        "Diversity of Materials",
        "Life cycles (Plants & Animals)",
        "Properties of Magnets",
        "Making and Using Magnets"
    ]
}

def _json_error(message, status_code=400):
    """Return a JSON error response with a consistent structure."""
    return jsonify({"error": message}), status_code

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

def _handle_generate_quiz(data):
    required_fields = ['classLevel', 'subject', 'topic', 'difficulty']

    if not data:
        return _json_error("Request body must be JSON.")

    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return _json_error(f"Missing or empty required fields: {', '.join(missing_fields)}")

    # Build the base prompt
    english_mcq_topics = {"Vocab MCQ", "Grammar MCQ", "Grammar Cloze", "Comprehension Cloze"}
    comprehension_topics = {"Comprehension (Open-Ended)"}

    if data.get('subject') == 'English' and data.get('topic') in english_mcq_topics:
        prompt = (
            f"Act as a Primary School teacher in Singapore. "
            f"Generate a quiz with exactly 5 'single-choice' multiple-choice questions for a {data['classLevel']} student. "
            f"The subject is {data['subject']} and the specific topic is {data['topic']}. "
            f"The difficulty level should be {data['difficulty']}. "
            "Each question must have four options with exactly one correct answer. "
            "Ensure the questions are aligned with the Singapore MOE syllabus. "
        )
    else:
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

    if data.get('subject') == 'English' and data.get('template'):
        prompt += f"\nUse the following question template for formatting:\n{data['template']}"

    if data.get('subject') == 'English' and data.get('topic') in comprehension_topics:
        prompt += ("\nAll five questions must be based on the same image. Include an 'image' field with the same URL for each question.")

    # Add instruction to avoid repeating questions if a history is provided
    previous_questions = data.get('previous_questions', [])
    if previous_questions:
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
            "type": "OBJECT",
            "properties": {
                "questions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type": {"type": "STRING"},
                            "question": {"type": "STRING"},
                            "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "image": {"type": "STRING"}
                        },
                        "required": ["type", "question"]
                    }
                }
            }
        }
    }
    return call_gemini_api(prompt, generation_config)


def _handle_question_paper(data):
    data = data or {}
    class_level = data.get('classLevel')
    subject = data.get('subject')

    if not class_level or not subject:
        return _json_error("Missing 'classLevel' or 'subject'.")

    try:
        question_count = int(data.get('questionCount', 10))
    except (TypeError, ValueError):
        return _json_error("'questionCount' must be a number.")

    if question_count < 1:
        return _json_error("'questionCount' must be at least 1.")

    question_count = min(question_count, 15)

    prompt = (
        f"Act as a Primary School teacher in Singapore. "
        f"Create a question paper with exactly {question_count} questions for a {class_level} student. "
        f"The subject is {subject}. "
        "Provide a healthy mix of question types that reflects the MOE syllabus: include several 'single-choice' multiple-choice questions, at least one 'multi-select' question, and at least two 'free-text' questions. "
        "For all multiple-choice or multi-select questions, include four options with clear wording. "
        "Do not include answer keys, hints, or explanations in the question paper itself. "
    )

    previous_questions = data.get('previous_questions', [])
    if previous_questions:
        previous_questions_text = "\n".join([f"- {q}" for q in previous_questions])
        prompt += (
            "\nAvoid reusing any of the following questions that the student has already seen for this subject:\n"
            f"{previous_questions_text}\n"
            "Create fresh variations with different numbers, scenarios, or phrasing wherever possible."
        )

    prompt += (
        "\nReturn a single JSON object with a key 'questions', which is an array of question objects. "
        "Each question object must contain: 'type' (one of 'single-choice', 'multi-select', or 'free-text'), "
        "a 'question' field containing the question text, and an 'options' array of four strings for choice-based questions."
    )

    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "questions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type": {"type": "STRING"},
                            "question": {"type": "STRING"},
                            "options": {"type": "ARRAY", "items": {"type": "STRING"}}
                        },
                        "required": ["type", "question"]
                    }
                }
            }
        }
    }

    return call_gemini_api(prompt, generation_config)


def _dispatch_to_handler(target_path, data):
    route_map = {
        'generate': _handle_generate_quiz,
        'generate-year-end': _handle_year_end_paper,
        'evaluate': _handle_evaluate,
        'get-hint': _handle_hint,
        'question-paper': _handle_question_paper,
    }

    handler = route_map.get(target_path)
    if not handler:
        return _json_error("Requested endpoint was not found.", 404)

    return handler(data)


@app.route('/api/index.py', methods=['POST', 'OPTIONS'])
def vercel_dispatch_handler():
    if request.method == 'OPTIONS':
        return ('', 204)

    target_path = (request.args.get('path') or '').strip('/')
    data = request.get_json(silent=True)
    if not target_path and isinstance(data, dict):
        target_path = data.get('__route', '').strip('/')

    if not target_path:
        return _json_error('Requested endpoint was not found.', 404)

    return _dispatch_to_handler(target_path, data)


@app.route('/api/generate', methods=['POST'])
def generate_handler():
    data = request.get_json()
    return _handle_generate_quiz(data)


@app.route('/api/question-paper', methods=['POST'])
def question_paper_handler():
    data = request.get_json()
    return _handle_question_paper(data)


def _handle_year_end_paper(data):
    data = data or {}
    class_level = data.get('classLevel')

    if not class_level:
        return _json_error("Missing 'classLevel' in request.")

    if class_level != 'P3':
        return _json_error("Year-end paper generation is currently supported for Primary 3 only.")

    difficulty_input = (data.get('difficulty') or '').strip().lower()
    normalized_difficulty = ''.join(ch for ch in difficulty_input if ch.isalnum())
    difficulty_map = {
        'medium': 'medium',
        'med': 'medium',
        'mediumhard': 'medium-hard',
        'mediumhardmix': 'medium-hard',
        'mediumtohardmix': 'medium-hard',
        'hard': 'hard'
    }
    difficulty_level = difficulty_map.get(normalized_difficulty, 'medium-hard')

    if difficulty_level == 'medium':
        difficulty_sentence = (
            "Ensure every question reflects medium difficulty suitable for confident Primary 3 pupils preparing for the year-end assessment."
        )
    elif difficulty_level == 'hard':
        difficulty_sentence = (
            "Ensure every question is hard difficulty, stretching capable Primary 3 pupils while staying within MOE expectations."
        )
    else:
        difficulty_sentence = (
            "Ensure the questions span medium to hard difficulty, mirroring the rigour of Primary 3 year-end examinations."
        )

    subjects_input = data.get('subjects')
    subjects = {}
    if isinstance(subjects_input, dict):
        for subject, topics in subjects_input.items():
            if not isinstance(topics, list):
                continue
            valid_topic_list = P3_YEAR_END_TOPICS.get(subject, [])
            filtered_topics = [topic for topic in topics if topic in valid_topic_list]
            if filtered_topics:
                subjects[subject] = filtered_topics

    for subject, default_topics in P3_YEAR_END_TOPICS.items():
        subjects.setdefault(subject, default_topics)

    ordered_subjects = ["English", "Maths", "Science"]
    topic_lines = []
    for subject in ordered_subjects:
        topic_list = subjects.get(subject, P3_YEAR_END_TOPICS.get(subject, []))
        if topic_list:
            topic_lines.append(f"{subject}: {', '.join(topic_list)}")
    topic_text = "\n".join(topic_lines)

    prompt = (
        "Act as an experienced Primary 3 teacher in Singapore preparing a year-end practice examination that follows the latest"
        "Singapore MOE syllabus. "
        "Create a complete Primary 3 practice paper with separate sections for English, Mathematics, and Science. "
        "Follow these requirements:\n"
        "1. Present the paper in three sections (English, Mathematics, Science) in that order with clear section titles.\n"
        "2. Use only these Primary 3 topics and tag every question with a 'topic' field that matches one of them exactly:\n"
        f"{topic_text}\n"
        f"3. {difficulty_sentence}\n"
        "4. Provide an overall paper title and recommended total duration in minutes.\n"
        "5. English section (align with Paper 2 Language Use & Comprehension):\n"
        "   • Include section instructions suitable for Primary 3 students.\n"
        "   • Add 3 Vocabulary MCQ questions and 3 Grammar MCQ questions.\n"
        "   • Add 2 Grammar Cloze questions. Each Grammar Cloze question should contain a short passage with three blanks, each blank offering four MCQ options.\n"
        "   • Add 1 Comprehension Cloze passage with five blanks (treated as five questions) and four MCQ options for each blank.\n"
        "   • Add 2 Sentence Combining questions that are open-ended.\n"
        "   • Add 2 Comprehension open-ended questions tied to one short passage.\n"
        "6. Mathematics section:\n"
        "   • Provide section instructions, suggested time, and total marks.\n"
        "   • Include 10 questions: 4 MCQ, 4 short-answer, and 2 structured word problems that expect working steps.\n"
        "7. Science section:\n"
        "   • Provide section instructions, suggested time, and total marks.\n"
        "   • Include 8 questions: 4 MCQ and 4 open-ended questions focusing on explanation or application of concepts.\n"
        "8. For every question, include an answer and, where helpful, a short explanation aligned with MOE marking expectations.\n"
        "9. Number questions within each section starting from Q1.\n"
        "10. Return the paper strictly as JSON that follows the provided schema."
    )

    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "paper_title": {"type": "STRING"},
                "duration_minutes": {"type": "INTEGER"},
                "sections": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "subject": {"type": "STRING"},
                            "section_title": {"type": "STRING"},
                            "instructions": {"type": "STRING"},
                            "time_allocated_minutes": {"type": "INTEGER"},
                            "total_marks": {"type": "INTEGER"},
                            "questions": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "number": {"type": "STRING"},
                                        "type": {"type": "STRING"},
                                        "prompt": {"type": "STRING"},
                                        "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                                        "topic": {"type": "STRING"},
                                        "marks": {"type": "INTEGER"},
                                        "answer": {"type": "STRING"},
                                        "answer_explanation": {"type": "STRING"}
                                    },
                                    "required": ["number", "type", "prompt", "answer", "topic"]
                                }
                            }
                        },
                        "required": ["subject", "section_title", "instructions", "questions"]
                    }
                }
            },
            "required": ["paper_title", "sections"]
        }
    }

    return call_gemini_api(prompt, generation_config)


@app.route('/api/generate-year-end', methods=['POST'])
def generate_year_end_handler():
    data = request.get_json()
    return _handle_year_end_paper(data)


def _handle_evaluate(data):
    if not data or 'questions' not in data or 'answers' not in data:
        return _json_error("Missing 'questions' or 'answers' in request.")

    question_count = len(data.get('questions', []))
    if question_count == 0:
        return _json_error("At least one question is required for evaluation.")

    questions_and_answers_text = ""
    for i, q in enumerate(data['questions']):
        answer_text = str(data['answers'][i])  # Convert answer to string for the prompt
        questions_and_answers_text += (
            f"Question {i+1} (type: {q['type']}): {q['question']}\n"
            f"Options: {q.get('options', 'N/A')}\n"
            f"Student's Answer: {answer_text}\n\n"
        )

    prompt = (
        f"Act as a Primary School teacher in Singapore. "
        f"Evaluate the following questions and student answers. For each one, provide whether it is correct, the correct answer (be concise), and a simple, encouraging one-sentence explanation. "
        f"Here are the questions and answers:\n{questions_and_answers_text}"
        f"Return the response as a single JSON object with a key 'evaluation', which is an array of {question_count} objects. "
        f"Each object must have three keys: 'is_correct' (boolean), 'correct_answer' (string), and 'explanation' (string)."
    )

    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "evaluation": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "is_correct": {"type": "BOOLEAN"},
                            "correct_answer": {"type": "STRING"},
                            "explanation": {"type": "STRING"}
                        },
                        "required": ["is_correct", "correct_answer", "explanation"]
                    }
                }
            }
        }
    }
    return call_gemini_api(prompt, generation_config)


@app.route('/api/evaluate', methods=['POST'])
def evaluate_handler():
    data = request.get_json()
    return _handle_evaluate(data)


def _handle_hint(data):
    if not data or 'question' not in data:
        return _json_error("Missing 'question' in request.")

    prompt = (
        "Provide a simple one-sentence hint for a Primary 3 student for the following question, "
        "but do not give away the answer: \"{question}\""
    ).format(question=data['question'])

    return call_gemini_api(prompt)


@app.route('/api/get-hint', methods=['POST'])
def get_hint_handler():
    data = request.get_json()
    return _handle_hint(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
