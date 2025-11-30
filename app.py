import os
import csv
import random
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'naati_secret_key_simple'
DB_NAME = "naati_vocab.db"
CSV_FILE = "NAATI_Vocabulary_Master_List.csv"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

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
            status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, vocab_id),
            FOREIGN KEY (username) REFERENCES users(username),
            FOREIGN KEY (vocab_id) REFERENCES vocabulary(id)
        )
    ''')

    # Always check for new words in CSV
    if os.path.exists(CSV_FILE):
        print("Checking CSV for new words...")
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            to_db = []
            for row in reader:
                to_db.append((
                    row['ID'],
                    row['English'],
                    row['Nepali (Romanized)'],
                    row['Nepali (Devanagari)']
                ))
            # INSERT OR IGNORE will add new IDs and skip existing ones
            cursor.executemany("INSERT OR IGNORE INTO vocabulary (id, english, nepali_roman, nepali_dev) VALUES (?, ?, ?, ?)",
                               to_db)
            print(f"Database updated. Total words in CSV: {len(to_db)}")
            
    conn.commit()
    conn.close()


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


@app.route('/list')
def vocab_list():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    username = session['username']
    conn = get_db_connection()
    query = '''
        SELECT v.id, v.english, v.nepali_roman, v.nepali_dev, 
               COALESCE(p.status, 'New') as status
        FROM vocabulary v
        LEFT JOIN progress p ON v.id = p.vocab_id AND p.username = ?
        ORDER BY 
            CASE WHEN p.status = 'unknown' THEN 1
                 WHEN p.status IS NULL THEN 2
                 ELSE 3 END,
            v.id
    '''
    words = conn.execute(query, (username,)).fetchall()
    conn.close()
    return render_template('list.html', words=words, user=username)


@app.route('/api/get_card')
def get_card():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['username']
    conn = get_db_connection()

    # Check availability of 'new' and 'review' words
    count_new = conn.execute('''
        SELECT COUNT(*) FROM vocabulary 
        WHERE id NOT IN (SELECT vocab_id FROM progress WHERE username = ?)
    ''', (username,)).fetchone()[0]

    count_review = conn.execute('''
        SELECT COUNT(*) FROM progress 
        WHERE username = ? AND status = 'unknown'
    ''', (username,)).fetchone()[0]

    card = None
    
    # Strategy: Mix Review (15%) and New (85%)
    want_review = (random.random() < 0.15)
    
    # Prioritize review if that's what we want and we have them, OR if we have no new words
    if (want_review and count_review > 0) or (count_new == 0 and count_review > 0):
        query_review = '''
            SELECT v.* FROM vocabulary v
            JOIN progress p ON v.id = p.vocab_id
            WHERE p.username = ? AND p.status = 'unknown'
            ORDER BY RANDOM() LIMIT 1
        '''
        card = conn.execute(query_review, (username,)).fetchone()
    
    # Otherwise get new word if available
    if not card and count_new > 0:
        query_new = '''
            SELECT * FROM vocabulary 
            WHERE id NOT IN (SELECT vocab_id FROM progress WHERE username = ?)
            ORDER BY RANDOM() LIMIT 1
        '''
        card = conn.execute(query_new, (username,)).fetchone()
        
    # Fallback: If we wanted new but none left, try review again
    if not card and count_review > 0:
         query_review = '''
            SELECT v.* FROM vocabulary v
            JOIN progress p ON v.id = p.vocab_id
            WHERE p.username = ? AND p.status = 'unknown'
            ORDER BY RANDOM() LIMIT 1
        '''
         card = conn.execute(query_review, (username,)).fetchone()

    conn.close()

    if not card:
        return jsonify({'finished': True})

    # Randomly decide direction: 'en_to_ne' or 'ne_to_en'
    direction = random.choice(['en_to_ne', 'ne_to_en'])

    return jsonify({
        'id': card['id'],
        'english': card['english'],
        'nepali_roman': card['nepali_roman'],
        'nepali_dev': card['nepali_dev'],
        'direction': direction
    })


@app.route('/api/reset_card', methods=['POST'])
def reset_card():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    username = session['username']
    vocab_id = data.get('vocab_id')

    conn = get_db_connection()
    # Set status to 'unknown' so it goes back to the Review queue
    conn.execute('''
        INSERT INTO progress (username, vocab_id, status, updated_at) 
        VALUES (?, ?, 'unknown', CURRENT_TIMESTAMP)
        ON CONFLICT(username, vocab_id) DO UPDATE SET 
        status='unknown', 
        updated_at=CURRENT_TIMESTAMP
    ''', (username, vocab_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/mark_card', methods=['POST'])
def mark_card():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    username = session['username']
    vocab_id = data.get('vocab_id')
    status = data.get('status')

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
    app.run(debug=True, host='0.0.0.0', port=8000)