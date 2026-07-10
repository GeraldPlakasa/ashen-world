"""
Authentication routes: Register, Login, Logout.
"""
import hmac
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from config import ENV_ADMIN_USERNAME, ENV_ADMIN_PASSWORD
from src.repositories.user_repo import load_users, save_user
from src.repositories.site_stats_repo import increment_stat
from src.utils.rate_limit import hit as rate_limit_hit, reset as rate_limit_reset

auth_bp = Blueprint("auth", __name__)


_MIN_PASSWORD_LEN = 8
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
# Deliberately loose: one @, no whitespace, a dot in the domain. Full RFC
# validation is a losing game; this just blocks garbage like "asdf".
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _password_is_strong(pw: str) -> tuple[bool, str]:
    """Minimal complexity: 8+ chars and at least two character classes.
    Rejects the obvious weak cases without forcing punctuation gymnastics."""
    if len(pw) < _MIN_PASSWORD_LEN:
        return False, f"Password must be at least {_MIN_PASSWORD_LEN} characters."
    classes = sum([
        any(c.islower() for c in pw),
        any(c.isupper() for c in pw),
        any(c.isdigit() for c in pw),
        any(not c.isalnum() for c in pw),
    ])
    if classes < 2:
        return False, "Password must mix at least two of: lowercase, uppercase, digits, symbols."
    return True, ""


def _admin_credentials_match(username: str, password: str) -> bool:
    """Constant-time comparison so probing one byte at a time can't leak the
    admin password via response-timing differences."""
    if not ENV_ADMIN_USERNAME or not ENV_ADMIN_PASSWORD:
        return False
    u_ok = hmac.compare_digest(username.encode("utf-8"), ENV_ADMIN_USERNAME.encode("utf-8"))
    p_ok = hmac.compare_digest(password.encode("utf-8"), ENV_ADMIN_PASSWORD.encode("utf-8"))
    return u_ok and p_ok


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page: username + email + password.
    Saves user to database, then redirect to login.
    """
    if request.method == "POST":
        # Same rationale as /login: account creation writes DB rows, so an
        # unthrottled loop is a spam vector. 10 attempts per IP per 10 min
        # leaves room for humans failing validation a few times.
        if rate_limit_hit("register", limit=10, window_seconds=600):
            flash("Too many registration attempts. Try again in a few minutes.", "info")
            return render_template("register.html"), 429

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "info")
            return render_template("register.html")

        if not _USERNAME_RE.match(username):
            flash("Username must be 3-30 characters, letters/digits/._- only.", "info")
            return render_template("register.html")

        if not _EMAIL_RE.match(email) or len(email) > 254:
            flash("Please enter a valid email address.", "info")
            return render_template("register.html")

        if password != confirm:
            flash("Password and confirmation do not match.", "info")
            return render_template("register.html")

        strong, reason = _password_is_strong(password)
        if not strong:
            flash(reason, "info")
            return render_template("register.html")

        users = load_users()

        if any(u.get("username", "").lower() == username.lower() for u in users):
            flash("Username is already taken.", "info")
            return render_template("register.html")

        if ENV_ADMIN_USERNAME and username.lower() == ENV_ADMIN_USERNAME.lower():
            flash("This username is reserved for the high steward. Please choose another.", "info")
            return render_template("register.html")

        if any(u.get("email", "").lower() == email.lower() for u in users):
            flash("Email is already registered.", "info")
            return render_template("register.html")

        save_user(username, email, password)
        increment_stat("user_registration")
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page.
    - Check user credentials from database.
    - Fallback: hardcoded admin credentials.
    """
    if request.method == "POST":
        # Rate-limit BEFORE touching the password hash — bcrypt-style hashes
        # are intentionally slow, so an unbounded loop is a free DoS vector.
        # 10 attempts per IP per 5 min is loose enough for typo-prone humans,
        # tight enough that brute-force online is impractical.
        if rate_limit_hit("login", limit=10, window_seconds=300):
            flash("Too many login attempts. Try again in a few minutes.", "info")
            return render_template("login.html"), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        users = load_users()
        user = next(
            (u for u in users if u.get("username", "").lower() == username.lower()),
            None,
        )

        if user and check_password_hash(user.get("password_hash", ""), password):
            rate_limit_reset("login")
            session["logged_in"] = True
            session["username"] = user["username"]
            session["is_admin"] = False
            flash(f"Welcome back, {user['username']}.", "success")
            return redirect(url_for("main.landing"))

        if _admin_credentials_match(username, password):
            rate_limit_reset("login")
            session["logged_in"] = True
            session["username"] = username
            session["is_admin"] = True
            flash("Welcome back, steward of Ashen World.", "success")
            return redirect(url_for("admin.admin"))

        flash("Invalid username or password.", "info")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """
    Log out the current user and clear session.
    """
    session.clear()
    flash("You have left the control hall.", "info")
    return redirect(url_for("auth.login"))
