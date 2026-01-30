from __future__ import annotations

from werkzeug.security import generate_password_hash

from src.repositories.base import db_conn, init_db
from src.models.user import User

# ---------------------------------------------------------------------------
#  Users (replaces users.csv)
# ---------------------------------------------------------------------------

def load_users() -> list[User]:
    init_db()
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT username, email, password_hash FROM users ORDER BY created_at DESC;"
        )
        return [dict(r) for r in cur.fetchall()]


def save_user(username: str, email: str, password_plain: str) -> None:
    """
    Insert a single user into SQLite with hashed password.
    Enforces unique username via PRIMARY KEY.
    """
    init_db()
    password_hash = generate_password_hash(password_plain)

    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO users(username, email, password_hash)
            VALUES(?, ?, ?);
            """,
            (username, email, password_hash),
        )
