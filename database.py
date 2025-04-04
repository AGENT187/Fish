import sqlite3

DB_NAME = "users.db"

def init_db():
    """Инициализация базы данных."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone_number TEXT
            )
        """)
        conn.commit()

def add_user(user_id, username, first_name, last_name):
    """Добавляем нового пользователя в базу (если его нет)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, last_name))
        conn.commit()

def save_phone_number(user_id, phone_number):
    """Сохраняем номер телефона пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET phone_number = ? WHERE user_id = ?
        """, (phone_number, user_id))
        conn.commit()

def get_phone_number(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        phone = result[0] if result else None
    return phone

def user_exists(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result is not None and result[0] is not None

def get_total_users():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

# При первом импорте сразу создаём таблицу, если её нет
init_db()
