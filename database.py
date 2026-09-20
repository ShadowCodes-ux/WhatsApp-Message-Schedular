# ─────────────────────────────────────────────
# DATABASE — contacts.db via SQLite
# ─────────────────────────────────────────────
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.db")


def db_init():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT NOT NULL,
            number TEXT NOT NULL UNIQUE
        )
    """)
    con.commit()
    con.close()


def db_all():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, name, number FROM contacts ORDER BY name").fetchall()
    con.close()
    return rows


def db_add(name, number):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR IGNORE INTO contacts (name, number) VALUES (?, ?)", (name,
                                                                                  number))
    con.commit()
    con.close()


def db_delete(contact_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
    con.commit()
    con.close()


def db_search(query):
    con = sqlite3.connect(DB_PATH)
    q = f"%{query}%"
    rows = con.execute(
        "SELECT id, name, number FROM contacts WHERE name LIKE ? OR number LIKE ? ORDER BY name",
        (q, q)
    ).fetchall()
    con.close()
    return rows
