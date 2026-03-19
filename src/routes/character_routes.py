"""
Character routes: Character creation.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from config import TRAITS
from src.services.world_service import get_current_state
from src.services.character_service import create_player_character

character_bp = Blueprint("character", __name__)


@character_bp.route("/character/new", methods=["GET", "POST"])
def create_character():
    """
    Create a custom character:
    - User inputs given name + family name
    - User chooses 1 trait (radio)
    - 1 extra trait is added randomly
    - origin = 'player'
    - Each user may only create 1 character.
    """
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    username = session.get("username") or ""

    # Get current state (characters + world time)
    characters, bank, year, day_in_year, _, weather = get_current_state()

    # Check if this user already has a player character
    existing_player = None
    if username:
        for c in characters:
            if c.get("origin") == "player" and c.get("owner") == username:
                existing_player = c
                break

    # If already have one, redirect to landing
    if request.method == "GET":
        if existing_player:
            flash("You already have a character in this world.", "info")
            return redirect(url_for("main.landing"))

        return render_template(
            "create_character.html",
            traits=TRAITS,
            year=year,
            day=day_in_year,
            active_page="create_character",
            form_name="",
            form_family="",
            chosen_trait="",
            form_gender="",
        )

    # POST
    if existing_player:
        flash("You already have a character in this world.", "info")
        return redirect(url_for("main.landing"))

    given_name = request.form.get("name", "").strip()
    family = request.form.get("family", "").strip()
    chosen_trait = request.form.get("trait", "").strip()
    gender = request.form.get("gender", "").strip()

    if not given_name or not family or not chosen_trait or not gender:
        flash("Name, family, gender, and one trait are required.", "info")
        return render_template(
            "create_character.html",
            traits=TRAITS,
            year=year,
            day=day_in_year,
            active_page="create_character",
            form_name=given_name,
            form_family=family,
            chosen_trait=chosen_trait,
            form_gender=gender,
        )

    success, result, new_villager = create_player_character(
        username, given_name, family, chosen_trait, gender
    )

    if not success:
        if result == "already_exists":
            flash("You already have a character in this world.", "info")
            return redirect(url_for("main.landing"))
        elif result == "name_taken":
            flash("A character with that full name already exists.", "info")
            return render_template(
                "create_character.html",
                traits=TRAITS,
                year=year,
                day=day_in_year,
                active_page="create_character",
                form_name=given_name,
                form_family=family,
                chosen_trait=chosen_trait,
                form_gender=gender,
            )

    flash(f"Created new character: {result} (Player).", "success")
    return redirect(url_for("main.landing"))
