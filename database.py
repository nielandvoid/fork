import sqlite3
import os

if os.path.exists("/data") and os.path.isdir("/data"):
    DB_PATH = "/data/sessions.db"
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE NOT NULL,
                mentee_id INTEGER NOT NULL,
                mentor_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
        if cursor.fetchone():
            cursor.execute("""
                INSERT OR IGNORE INTO sqlite_sequence (name, seq)
                VALUES ('sessions', 1000)
            """)
        conn.commit()
    finally:
        conn.close()

def create_session(channel_id: int, mentee_id: int, mentor_id: int) -> int:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (channel_id, mentee_id, mentor_id, status)
            VALUES (?, ?, ?, 'active')
        """, (channel_id, mentee_id, mentor_id))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_session_by_id(session_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, channel_id, mentee_id, mentor_id, created_at, status
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_session_by_channel(channel_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, channel_id, mentee_id, mentor_id, created_at, status
            FROM sessions
            WHERE channel_id = ?
        """, (channel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def nuke_session(session_id: int) -> bool:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET status = 'nuked'
            WHERE session_id = ?
        """, (session_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
