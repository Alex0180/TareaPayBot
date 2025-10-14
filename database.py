# database.py
import sqlite3
import os
import json
import time

DB_FILE = "data.db"
DATA_JSON = "users.json"
WITHDRAW_JSON = "withdrawals.json"

START_BALANCE = 0.0

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0.0,
        created_at INTEGER,
        lang TEXT DEFAULT 'es',
        ads_seen TEXT DEFAULT '[]',
        last_daily INTEGER DEFAULT 0,
        referred_by TEXT,
        daily_earned REAL DEFAULT 0.0,
        last_earn_reset INTEGER DEFAULT 0,
        verified INTEGER DEFAULT 0,
        phone TEXT,
        history TEXT DEFAULT '[]'
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        method TEXT,
        account TEXT,
        balance REAL,
        status TEXT,
        timestamp INTEGER
    );
    """)
    conn.commit()
    conn.close()

def row_to_user(row):
    if row is None:
        return None
    u = dict(row)
    try:
        u["ads_seen"] = json.loads(u.get("ads_seen") or "[]")
    except:
        u["ads_seen"] = []
    try:
        u["history"] = json.loads(u.get("history") or "[]")
    except:
        u["history"] = []
    u["verified"] = bool(u.get("verified"))
    return u

def migrate_json_to_sqlite():
    conn = get_db()
    c = conn.cursor()
    # if users table already has data, skip migration
    c.execute("SELECT COUNT(1) as cnt FROM users;")
    if c.fetchone()["cnt"] > 0:
        conn.close()
        return

    if os.path.exists(DATA_JSON):
        try:
            with open(DATA_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        for sid, u in data.items():
            try:
                c.execute("""
                    INSERT OR REPLACE INTO users (id, username, balance, created_at, lang, ads_seen,
                        last_daily, referred_by, daily_earned, last_earn_reset, verified, phone, history)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(sid),
                    u.get("username"),
                    float(u.get("balance", 0.0)),
                    int(u.get("created_at", int(time.time()))),
                    u.get("lang", "es"),
                    json.dumps(u.get("ads_seen", []), ensure_ascii=False),
                    int(u.get("last_daily", 0)),
                    u.get("referred_by"),
                    float(u.get("daily_earned", 0.0)),
                    int(u.get("last_earn_reset", 0)),
                    1 if u.get("verified") else 0,
                    u.get("phone"),
                    json.dumps(u.get("history", []), ensure_ascii=False)
                ))
            except Exception as e:
                print("Error migrando user", sid, e)
        conn.commit()
        print("Migración users.json -> SQLite completada.")

    if os.path.exists(WITHDRAW_JSON):
        try:
            with open(WITHDRAW_JSON, "r", encoding="utf-8") as f:
                wdata = json.load(f)
        except Exception:
            wdata = {}
        for sid, w in wdata.items():
            try:
                c.execute("""
                    INSERT OR REPLACE INTO withdrawals (user_id, username, method, account, balance, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sid,
                    w.get("username"),
                    w.get("method"),
                    w.get("account"),
                    float(w.get("balance", 0.0)),
                    w.get("status", "pendiente"),
                    int(w.get("timestamp", int(time.time())))
                ))
            except Exception as e:
                print("Error migrando withdraw", sid, e)
        conn.commit()
        print("Migración withdrawals.json -> SQLite completada.")

    conn.close()

# USER operations
def ensure_user(user_id, username=None, lang="es"):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
    row = c.fetchone()
    if row:
        user = row_to_user(row)
        if not user.get("username") and username:
            c.execute("UPDATE users SET username = ? WHERE id = ?", (username, int(user_id)))
            conn.commit()
            user["username"] = username
        conn.close()
        return user
    created_at = int(time.time())
    c.execute("""
        INSERT INTO users (id, username, balance, created_at, lang, ads_seen, last_daily, referred_by,
            daily_earned, last_earn_reset, verified, phone, history)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (int(user_id), username or "", START_BALANCE, created_at, lang, json.dumps([]), 0, None, 0.0, 0, 0, None, json.dumps([])))
    conn.commit()
    c.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
    row = c.fetchone()
    conn.close()
    return row_to_user(row)

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
    row = c.fetchone()
    conn.close()
    return row_to_user(row) if row else None

def save_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE users SET username=?, balance=?, lang=?, ads_seen=?, last_daily=?, referred_by=?,
            daily_earned=?, last_earn_reset=?, verified=?, phone=?, history=?
        WHERE id=?
    """, (
        user.get("username"),
        float(user.get("balance", 0.0)),
        user.get("lang", "es"),
        json.dumps(user.get("ads_seen", []), ensure_ascii=False),
        int(user.get("last_daily", 0)),
        user.get("referred_by"),
        float(user.get("daily_earned", 0.0)),
        int(user.get("last_earn_reset", 0)),
        1 if user.get("verified") else 0,
        user.get("phone"),
        json.dumps(user.get("history", []), ensure_ascii=False),
        int(user.get("id"))
    ))
    conn.commit()
    conn.close()

# WITHDRAW operations
def save_withdraw(withdraw_obj):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO withdrawals (user_id, username, method, account, balance, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(withdraw_obj.get("user_id")),
        withdraw_obj.get("username"),
        withdraw_obj.get("method"),
        withdraw_obj.get("account"),
        float(withdraw_obj.get("balance", 0.0)),
        withdraw_obj.get("status", "pendiente"),
        int(withdraw_obj.get("timestamp", int(time.time())))
    ))
    conn.commit()
    conn.close()

def get_withdraw(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_pending_withdraws():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals WHERE status = 'pendiente'")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_withdraw_status(user_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE withdrawals SET status = ? WHERE user_id = ?", (status, str(user_id)))
    conn.commit()
    conn.close()
