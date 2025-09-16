import os
import json
import uuid
import psycopg2.extras
from flask import Flask, request, jsonify, render_template, send_file
import google.generativeai as genai
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
import io
import re
import random 
import datetime

# PostgreSQL specific imports
import psycopg2
from psycopg2 import sql

# Load environment variables from a .env file
load_dotenv()

# Configure the Gemini API with your API key
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

app = Flask(__name__)

# PostgreSQL connection details from .env file
# You can keep these, but they will be overridden by the DATABASE_URL
DB_NAME = os.environ.get("POSTGRES_DB_NAME")
DB_USER = os.environ.get("POSTGRES_DB_USER")
DB_PASSWORD = os.environ.get("POSTGRES_DB_PASSWORD")
DB_HOST = os.environ.get("POSTGRES_DB_HOST")
DB_PORT = os.environ.get("POSTGRES_DB_PORT", 5432)

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        # Prioritize the single DATABASE_URL environment variable
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            # Connect using the URL string
            conn = psycopg2.connect(db_url)
        else:
            # Fallback to individual variables
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
        print("Database connection Successful")
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection failed: {e}")
        return None
     

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = get_db_connection()
    if not conn:
        print("Could not connect to the database to initialize tables.")
        return
        
    cur = conn.cursor()
    
    # Create quizzes table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            topic TEXT NOT NULL,
            total_questions INTEGER,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            score INTEGER,
            current_question_index INTEGER DEFAULT 0,
            ai_summary TEXT
        );
    ''')
    
    # Create questions table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            quiz_id TEXT NOT NULL,
            question_text TEXT NOT NULL,
            options TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct BOOLEAN,
            difficulty TEXT,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

# Initialize the database tables when the app starts
init_db()

def get_fallback_question(topic, difficulty):
    """Generates a simple, hardcoded question as a fallback."""
    generic_concepts = {
        "Data Structures and Algorithms": ["Array", "Linked List", "Stack", "Queue"],
        "Mathematics": ["Algebra", "Geometry", "Calculus", "Statistics"],
        "Physics": ["Force", "Energy", "Motion", "Gravity"],
    }
    options = generic_concepts.get(topic, ["Concept A", "Concept B", "Concept C", "Concept D"])
    random.shuffle(options)
    return {
        "question": f"Which of these is a key concept in {topic}?",
        "options": options,
        "answer": options[0],
        "difficulty": difficulty
    }

def generate_question(topic, difficulty_level, retries=5):
    """
    Generates a question using the Gemini API with retries and a fallback.
    """
    difficulty_map = ["easy", "medium", "hard"]
    selected_difficulty = difficulty_map[difficulty_level]
    prompt = f"""
    Generate a single, multiple-choice aptitude test question in JSON format about the topic: {topic}.
    The question must be of '{selected_difficulty}' difficulty.

    The JSON object must have the following keys:
    - "question": The main question text.
    - "options": A list containing exactly 4 detailed, relevant, and plausible options.
    - "answer": The correct option from the list.
    - "difficulty": "{selected_difficulty}"

    Output ONLY the valid JSON object. Do not include any other text or code block markers.
    """
    
    for attempt in range(retries):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            if not response.candidates:
                continue

            text = response.text.strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_string = match.group(0)
                question_data = json.loads(json_string)
                
                if all(key in question_data for key in ["question", "options", "answer", "difficulty"]) and \
                   isinstance(question_data["options"], list) and len(question_data["options"]) == 4 and \
                   question_data["answer"] in question_data["options"]:
                    return question_data
        except (json.JSONDecodeError, Exception) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
    
    print("All attempts failed. Using fallback question.")
    return get_fallback_question(topic, selected_difficulty)

def create_pdf_report(quiz_data):
    """
    Creates a professionally styled PDF report for a completed quiz.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontSize=20, spaceAfter=20, alignment=TA_CENTER, fontName='Helvetica-Bold')
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Normal'], fontSize=14, spaceBefore=10, spaceAfter=5, fontName='Helvetica-Bold')
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, spaceAfter=5, alignment=TA_LEFT)
    
    story = []

    story.append(Paragraph("Quiz Performance Report", title_style))
    story.append(Paragraph(f"<b>Name:</b> {quiz_data['user_name']}", body_style))
    story.append(Paragraph(f"<b>Topic:</b> {quiz_data['topic']}", body_style))
    story.append(Paragraph(f"<b>Date:</b> {quiz_data['start_time']}", body_style))
    
    score_display = f"{quiz_data['score']}" if quiz_data['score'] is not None else "N/A"
    story.append(Paragraph(f"<b>Final Score:</b> {score_display} / {quiz_data['total_questions']}", body_style))
    story.append(Spacer(1, 12))

    # AI Analysis Section
    ai_analysis = {}
    summary_text = quiz_data.get('ai_summary', "Analysis not available.")
    
    if summary_text and summary_text != "Analysis not available.":
        try:
            ai_analysis = json.loads(summary_text)
        except (json.JSONDecodeError, TypeError):
            ai_analysis = {
                "performance_summary": summary_text,
                "recommendations": "No recommendations available."
            }
    else:
        ai_analysis = {
            "performance_summary": f"Could not generate a detailed analysis. Your final score was {score_display}/{quiz_data['total_questions']}.",
            "recommendations": "No recommendations available."
        }

    story.append(Paragraph("<b>AI Performance Summary</b>", heading_style))
    story.append(Paragraph(ai_analysis['performance_summary'], body_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("<b>Recommendations & Resources</b>", heading_style))
    story.append(Paragraph(ai_analysis['recommendations'], body_style))
    story.append(PageBreak())

    # Detailed Question Breakdown Section (Using a table for clarity)
    story.append(Paragraph("<b>Question-by-Question Breakdown</b>", title_style))
    
    questions_data = quiz_data.get('questions', [])
    
    table_data = [['#', 'Question', 'Your Answer', 'Correct Answer', 'Result']]
    
    for idx, q_row in enumerate(questions_data):
        q = dict(q_row)
        correct_status = "Correct ✅" if q['is_correct'] else "Incorrect ❌"
        table_data.append([
            str(idx + 1),
            Paragraph(q['question_text'], body_style),
            Paragraph(q['user_answer'], body_style),
            Paragraph(q['correct_answer'], body_style),
            correct_status
        ])
        
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F0F0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white)
    ])
    
    question_table = Table(table_data, colWidths=[20, 200, 100, 100, 60])
    question_table.setStyle(table_style)
    story.append(question_table)
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    data = request.json
    username = data.get('username')
    topic = data.get('topic')
    num_questions = int(data.get('num_questions', 10))
    if not username or not topic:
        return jsonify({"error": "Username and topic are required"}), 400

    quiz_id = str(uuid.uuid4())
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cur = conn.cursor()
    cur.execute("INSERT INTO quizzes (id, user_name, topic, total_questions, start_time, current_question_index) VALUES (%s, %s, %s, %s, NOW(), %s)",
                (quiz_id, username, topic, num_questions, 0))
    conn.commit()
    cur.close()
    conn.close()
    
    first_question = generate_question(topic, 1) # Start with medium
    
    return jsonify({
        "quiz_id": quiz_id,
        "question": first_question,
        "question_index": 0
    })

@app.route('/submit_and_next', methods=['POST'])
def submit_and_next():
    data = request.json
    quiz_id = data.get('quiz_id')
    question_data = data.get('question')
    user_answer = data.get('user_answer')
    current_index = data.get('question_index')
    
    if not all([quiz_id, question_data, user_answer is not None, current_index is not None]):
        return jsonify({"error": "Missing required fields"}), 400
    
    correct_answer = question_data['answer']
    is_correct = (user_answer == correct_answer)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_info = cur.fetchone()
    if not quiz_info or quiz_info['current_question_index'] >= quiz_info['total_questions']:
        cur.close()
        conn.close()
        return jsonify({"status": "quiz_finished"})

    cur.execute("INSERT INTO questions (quiz_id, question_text, options, user_answer, correct_answer, is_correct, difficulty) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (quiz_id, question_data['question'], json.dumps(question_data['options']), user_answer, correct_answer, is_correct, question_data['difficulty']))
    conn.commit()

    new_index = current_index + 1
    
    if new_index >= quiz_info['total_questions']:
        cur.execute("UPDATE quizzes SET end_time = NOW(), current_question_index = %s WHERE id = %s", (new_index, quiz_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "quiz_finished"})

    # Adaptive logic to determine the next question's difficulty
    next_difficulty_level = 1 # Default to medium
    cur.execute("SELECT is_correct FROM questions WHERE quiz_id = %s ORDER BY id DESC LIMIT 2", (quiz_id,))
    recent_questions_status = cur.fetchall()
    
    if len(recent_questions_status) == 2:
        correct_count = sum(1 for q in recent_questions_status if q['is_correct'])
        if correct_count == 2:
            next_difficulty_level = 2 # Two correct -> Hard
        elif correct_count == 0:
            next_difficulty_level = 0 # Two incorrect -> Easy
        else:
            next_difficulty_level = 1 # One of each -> Medium
    elif len(recent_questions_status) == 1:
        if recent_questions_status[0]['is_correct']:
            next_difficulty_level = 2 # One correct -> Hard
        else:
            next_difficulty_level = 0 # One incorrect -> Easy
    
    next_question = generate_question(quiz_info['topic'], next_difficulty_level)
    
    cur.execute("UPDATE quizzes SET current_question_index = %s WHERE id = %s", (new_index, quiz_id))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "status": "success",
        "question": next_question,
        "question_index": new_index
    })

@app.route('/analyze_quiz', methods=['POST'])
def analyze_quiz():
    data = request.json
    quiz_id = data.get('quiz_id')
    if not quiz_id:
        return jsonify({"error": "Quiz ID is required"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    results = cur.fetchall()
    
    total_score = sum(1 for r in results if r['is_correct'])
    total_questions = len(results)
    
    cur.execute("UPDATE quizzes SET score = %s, end_time = NOW() WHERE id = %s",
                (total_score, quiz_id))
    conn.commit()

    cur.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_info = cur.fetchone()
    cur.close()
    conn.close()

    prompt = f"""
    Analyze the quiz performance for user '{quiz_info['user_name']}' on the topic '{quiz_info['topic']}'.
    The user's final score was {total_score} out of {quiz_info['total_questions']}.
    Here are the results of each question: {json.dumps([dict(r) for r in results])}.
    Provide a detailed, professional analysis in two distinct sections.
    1. A **Performance Summary**: Begin with an overall evaluation of the user's performance. Mention their score and highlight specific strengths and weaknesses (e.g., "The user demonstrated strong knowledge in X but struggled with Y, particularly in 'hard' difficulty questions.").
    2. **Actionable Recommendations & Resources**: Based on the weaknesses identified, provide a clear, step-by-step plan for improvement. Suggest specific concepts to review and provide an example search query for each. Recommend a variety of learning resources, such as textbooks, online courses, and YouTube channels. Be encouraging and concise.
    The response should be a valid JSON object with keys "performance_summary" and "recommendations".
    """
    
    ai_analysis = {}
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        ai_analysis = json.loads(response.text.strip())
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("UPDATE quizzes SET ai_summary = %s WHERE id = %s",
                        (json.dumps(ai_analysis), quiz_id))
            conn.commit()
            cur.close()
            conn.close()
    except (json.JSONDecodeError, Exception) as e:
        print(f"AI analysis failed with error: {e}")
        ai_analysis = {
            "performance_summary": f"Could not generate a detailed analysis. Your final score was {total_score}/{total_questions}.",
            "recommendations": "Please try again later or focus on the topics you found difficult."
        }
    
    return jsonify({"analysis": ai_analysis})

@app.route('/get_history', methods=['GET'])
def get_history():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, user_name, topic, start_time, score, total_questions FROM quizzes ORDER BY start_time DESC")
    history = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify([dict(row) for row in history])

@app.route('/download_report/<quiz_id>', methods=['GET'])
def download_report(quiz_id):
    conn = get_db_connection()
    if not conn:
        return "Report or quiz not found", 404

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_info = cur.fetchone()

    cur.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions_data = cur.fetchall()

    cur.close()
    conn.close()
    
    if not quiz_info or not questions_data:
        return "Report or quiz not found", 404
        
    quiz_data = dict(quiz_info)
    quiz_data['questions'] = [dict(q) for q in questions_data]
    
    pdf_buffer = create_pdf_report(quiz_data)
    
    return send_file(pdf_buffer, as_attachment=True, download_name=f"quiz_report_{quiz_id}.pdf", mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=True, port=5500)
