import sqlite3
from datetime import datetime

DB = "anpr.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email    TEXT,
            created  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            plate     TEXT NOT NULL,
            source    TEXT,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

# ── User functions ─────────────────────────────────────────────────────────
def register_user(username, password, email=""):
    import hashlib
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            "INSERT INTO users (username, password, email, created) VALUES (?, ?, ?, ?)",
            (username, pw_hash, email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # username already exists
    finally:
        conn.close()

def login_user(username, password):
    import hashlib
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id, username FROM users WHERE username=? AND password=?",
        (username, pw_hash)
    ).fetchone()
    conn.close()
    return row  # (id, username) or None

def get_user_by_id(user_id):
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id, username, email, created FROM users WHERE id=?", (user_id,)
    ).fetchone()
    conn.close()
    return row

# ── Detection functions ────────────────────────────────────────────────────
def save_plate(plate, source="unknown", user_id=1):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO detections (user_id, plate, source, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, plate, source, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_all(user_id=None):
    conn = sqlite3.connect(DB)
    if user_id:
        rows = conn.execute(
            "SELECT plate, source, timestamp, id FROM detections WHERE user_id=? ORDER BY id DESC",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT plate, source, timestamp, id FROM detections ORDER BY id DESC"
        ).fetchall()
    conn.close()
    return rows

def delete_all(user_id=None):
    conn = sqlite3.connect(DB)
    if user_id:
        conn.execute("DELETE FROM detections WHERE user_id=?", (user_id,))
    else:
        conn.execute("DELETE FROM detections")
    conn.commit()
    conn.close()

def delete_by_id(detection_id, user_id):
    conn = sqlite3.connect(DB)
    conn.execute(
        "DELETE FROM detections WHERE id=? AND user_id=?",
        (detection_id, user_id)
    )
    conn.commit()
    conn.close()

def add_plate_manual(plate, source, user_id):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO detections (user_id, plate, source, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, plate.upper().strip(), source, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_stats(user_id):
    conn = sqlite3.connect(DB)
    total = conn.execute(
        "SELECT COUNT(*) FROM detections WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM detections WHERE user_id=? AND DATE(timestamp)=DATE('now')",
        (user_id,)
    ).fetchone()[0]
    sources = conn.execute(
        "SELECT source, COUNT(*) FROM detections WHERE user_id=? GROUP BY source",
        (user_id,)
    ).fetchall()
    conn.close()
    return {"total": total, "today": today, "sources": sources}
