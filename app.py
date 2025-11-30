import os
import csv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'naati_secret_key_simple'
DB_NAME = "naati_vocab.db"
CSV_FILE = "NAATI_Vocabulary_Master_List.csv"


# --- Database Helper Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize DB and load CSV data if table is empty"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vocabulary (
            id TEXT PRIMARY KEY,
            english TEXT,
            nepali_roman TEXT,
            nepali_dev TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            username TEXT,
            vocab_id TEXT,
            status TEXT, -- 'known', 'unknown'
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, vocab_id),
            FOREIGN KEY (username) REFERENCES users(username),
            FOREIGN KEY (vocab_id) REFERENCES vocabulary(id)
        )
    ''')

    # Check if vocab exists, if not load from CSV
    cursor.execute('SELECT count(*) FROM vocabulary')
    if cursor.fetchone()[0] == 0:
        print("Initializing Database with CSV data...")
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                to_db = []
                for row in reader:
                    # CSV headers: ID, English, Nepali (Romanized), Nepali (Devanagari)
                    to_db.append((
                        row['ID'],
                        row['English'],
                        row['Nepali (Romanized)'],
                        row['Nepali (Devanagari)']
                    ))

                cursor.executemany("INSERT INTO vocabulary (id, english, nepali_roman, nepali_dev) VALUES (?, ?, ?, ?)",
                                   to_db)
                print(f"Imported {len(to_db)} words.")
        else:
            print("WARNING: CSV file not found. Database is empty.")

    conn.commit()
    conn.close()


# --- Routes ---

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('flashcards'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username').strip().lower()
    if username:
        conn = get_db_connection()
        conn.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (username,))
        conn.commit()
        conn.close()
        session['username'] = username
        return redirect(url_for('flashcards'))
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/app')
def flashcards():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('index.html', user=session['username'])


# --- API Endpoints ---

@app.route('/api/get_card')
def get_card():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['username']
    conn = get_db_connection()

    # Logic: Get a card that is NOT marked as 'known' by this user
    # Priority: Words never seen -> Words marked unknown

    # Try to find a new word first
    query = '''
        SELECT * FROM vocabulary 
        WHERE id NOT IN (SELECT vocab_id FROM progress WHERE username = ?)
        ORDER BY RANDOM() LIMIT 1
    '''
    card = conn.execute(query, (username,)).fetchone()

    # If no new words, get words marked as 'unknown' (review)
    if not card:
        query = '''
            SELECT v.* FROM vocabulary v
            JOIN progress p ON v.id = p.vocab_id
            WHERE p.username = ? AND p.status = 'unknown'
            ORDER BY RANDOM() LIMIT 1
        '''
        card = conn.execute(query, (username,)).fetchone()

    # If still no card, they know everything!
    if not card:
        conn.close()
        return jsonify({'finished': True})

    conn.close()
    return jsonify({
        'id': card['id'],
        'english': card['english'],
        'nepali_roman': card['nepali_roman'],
        'nepali_dev': card['nepali_dev']
    })


@app.route('/api/mark_card', methods=['POST'])
def mark_card():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    username = session['username']
    vocab_id = data.get('vocab_id')
    status = data.get('status')  # 'known' or 'unknown'

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO progress (username, vocab_id, status, updated_at) 
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(username, vocab_id) DO UPDATE SET 
        status=excluded.status, 
        updated_at=CURRENT_TIMESTAMP
    ''', (username, vocab_id, status))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/stats')
def get_stats():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['username']
    conn = get_db_connection()

    total = conn.execute('SELECT COUNT(*) FROM vocabulary').fetchone()[0]
    known = \
    conn.execute("SELECT COUNT(*) FROM progress WHERE username = ? AND status = 'known'", (username,)).fetchone()[0]
    unknown = \
    conn.execute("SELECT COUNT(*) FROM progress WHERE username = ? AND status = 'unknown'", (username,)).fetchone()[0]

    conn.close()
    return jsonify({'total': total, 'known': known, 'unknown': unknown})


if __name__ == '__main__':
    init_db()
    # Run on 0.0.0.0 to make it accessible to other devices on the network
    app.run(debug=True, host='0.0.0.0', port=5000)