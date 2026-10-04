import sqlite3

def init_db():
    sql_statements = [
        """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                hashed_password TEXT NOT NULL,
                lijstje_link TEXT,
                lootje1 TEXT UNIQUE,
                lootje2 TEXT UNIQUE,
                rolled BOOLEAN DEFAULT 0,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT
            );""",
        """CREATE TABLE messages (
                id               INTEGER PRIMARY KEY,
                token_hash       TEXT UNIQUE NOT NULL,
                sender_id        INTEGER NOT NULL,
                recipient_name   TEXT NOT NULL,
                recipient_email  TEXT NOT NULL,
                body             TEXT NOT NULL,
                created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                replied_at       TEXT
            );"""
    ]

    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()

            for statement in sql_statements:
                cursor.execute(statement)

            conn.commit()

            print("Tables created successfully.")
    except sqlite3.OperationalError as e:
        print("Failed to create tables:", e)