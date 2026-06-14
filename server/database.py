import sqlite3
import hashlib

DB_PATH = "secure_notes.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def hash_password(password):
    """
    Haszuje hasło użytkownika.
    W projekcie pokazuje, że nie przechowujemy hasła jawnym tekstem.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    """
    Tworzy tabele users, notes oraz sessions.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)
    # ---------------------------

    conn.commit()
    conn.close()


def create_user(username, password):
    """
    Dodaje nowego użytkownika.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_user(username, password):
    """
    Sprawdza login i hasło.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password_hash FROM users WHERE username = ?",
        (username,)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return False

    stored_hash = row[0]
    return stored_hash == hash_password(password)


def create_default_user():
    """
    Tworzy testowego użytkownika:
    login: test
    hasło: test123
    """
    create_user("test", "test123")


def add_note(username, title, content):
    """
    Dodaje notatkę przypisaną do użytkownika.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO notes (username, title, content) VALUES (?, ?, ?)",
        (username, title, content)
    )

    conn.commit()
    note_id = cursor.lastrowid
    conn.close()

    return note_id


def list_notes(username):
    """
    Zwraca listę notatek danego użytkownika.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, content, created_at
        FROM notes
        WHERE username = ?
        ORDER BY id DESC
        """,
        (username,)
    )

    rows = cursor.fetchall()
    conn.close()

    notes = []

    for row in rows:
        notes.append({
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "created_at": row[3]
        })

    return notes


def delete_note(username, note_id):
    """
    Usuwa notatkę tylko wtedy, gdy należy do danego użytkownika.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM notes WHERE id = ? AND username = ?",
        (note_id, username)
    )

    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    return deleted > 0


def create_session(username, token):
    """
    Zapisuje nowy token sesyjny w bazie danych.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO sessions (token, username) VALUES (?, ?)",
        (token, username)
    )

    conn.commit()
    conn.close()


def get_username_by_token(token):
    """
    Sprawdza, czy token istnieje w bazie i zwraca przypisanego użytkownika.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT username FROM sessions WHERE token = ?",
        (token,)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return row[0]


if __name__ == "__main__":
    init_db()
    create_default_user()
    print("Database initialized.")
    print("Default user: test / test123")