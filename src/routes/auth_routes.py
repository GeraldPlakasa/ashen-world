"""
Authentication routes: Register, Login, Logout.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from config import ENV_ADMIN_USERNAME, ENV_ADMIN_PASSWORD
from src.repositories.user_repo import load_users, save_user
from src.repositories.site_stats_repo import increment_stat

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page: username + email + password.
    Saves user to database, then redirect to login.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "info")
            return render_template("register.html")

        if password != confirm:
            flash("Password and confirmation do not match.", "info")
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
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        users = load_users()
        user = next(
            (u for u in users if u.get("username", "").lower() == username.lower()),
            None,
        )

        if user and check_password_hash(user.get("password_hash", ""), password):
            session["logged_in"] = True
            session["username"] = user["username"]
            session["is_admin"] = False
            flash(f"Welcome back, {user['username']}.", "success")
            return redirect(url_for("main.landing"))

        if username == ENV_ADMIN_USERNAME and password == ENV_ADMIN_PASSWORD:
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
