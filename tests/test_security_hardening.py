"""
Integration tests for security hardening:
- owner username masking on public API endpoints
- registration email validation and rate limiting
"""
import pytest

from src.repositories.villager_repo import save_villagers
from src.repositories.bank_repo import save_bank
from src.repositories.world_repo import save_day
from src.utils import rate_limit


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Rate-limit buckets are process-global; isolate them per test."""
    rate_limit._buckets.clear()
    yield
    rate_limit._buckets.clear()


@pytest.fixture
def world_with_player(test_db_connection, sample_villager, sample_bank):
    """Seed a world containing one player-owned villager (owner='alice')."""
    player = sample_villager.copy()
    player.update({"id": 7, "name": "Alice Char", "origin": "player", "owner": "alice"})
    save_villagers([sample_villager.copy(), player])
    save_bank(sample_bank)
    save_day(1)
    return player


def _login_as(client, username: str, is_admin: bool = False):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = username
        sess["is_admin"] = is_admin


class TestOwnerMasking:
    """/api/state and /api/character must not leak owner usernames."""

    @pytest.mark.integration
    def test_api_state_hides_owner_from_anonymous(self, flask_client, world_with_player):
        resp = flask_client.get("/api/state")
        assert resp.status_code == 200
        chars = resp.get_json()["characters"]
        player = next(c for c in chars if c["id"] == 7)
        assert player["owner"] == ""

    @pytest.mark.integration
    def test_api_state_hides_owner_from_other_user(self, flask_client, world_with_player):
        _login_as(flask_client, "bob")
        resp = flask_client.get("/api/state")
        player = next(c for c in resp.get_json()["characters"] if c["id"] == 7)
        assert player["owner"] == ""

    @pytest.mark.integration
    def test_api_state_shows_owner_to_self(self, flask_client, world_with_player):
        _login_as(flask_client, "alice")
        resp = flask_client.get("/api/state")
        player = next(c for c in resp.get_json()["characters"] if c["id"] == 7)
        assert player["owner"] == "alice"

    @pytest.mark.integration
    def test_api_state_shows_owner_to_admin(self, flask_client, world_with_player):
        _login_as(flask_client, "steward", is_admin=True)
        resp = flask_client.get("/api/state")
        player = next(c for c in resp.get_json()["characters"] if c["id"] == 7)
        assert player["owner"] == "alice"

    @pytest.mark.integration
    def test_api_character_detail_hides_owner_from_anonymous(self, flask_client, world_with_player):
        resp = flask_client.get("/api/character/7")
        assert resp.status_code == 200
        assert resp.get_json()["character"]["owner"] == ""

    @pytest.mark.integration
    def test_api_character_detail_shows_owner_to_self(self, flask_client, world_with_player):
        _login_as(flask_client, "alice")
        resp = flask_client.get("/api/character/7")
        assert resp.get_json()["character"]["owner"] == "alice"


class TestRegisterHardening:
    """Registration must validate email format and be rate limited."""

    VALID_FORM = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "Sup3rSecret",
        "confirm_password": "Sup3rSecret",
    }

    @pytest.mark.integration
    def test_register_rejects_invalid_email(self, flask_client, test_db_connection):
        for bad_email in ["asdf", "no-at.example.com", "a@b", "a b@example.com"]:
            form = dict(self.VALID_FORM, email=bad_email)
            resp = flask_client.post("/register", data=form)
            assert resp.status_code == 200  # re-rendered form, not a redirect
            assert b"valid email" in resp.data

    @pytest.mark.integration
    def test_register_accepts_valid_email(self, flask_client, test_db_connection):
        resp = flask_client.post("/register", data=self.VALID_FORM)
        assert resp.status_code == 302  # redirect to /login on success

    @pytest.mark.integration
    def test_register_rate_limited_after_10_attempts(self, flask_client, test_db_connection):
        form = dict(self.VALID_FORM, email="asdf")  # fails validation, still counts
        for _ in range(10):
            resp = flask_client.post("/register", data=form)
            assert resp.status_code == 200
        resp = flask_client.post("/register", data=form)
        assert resp.status_code == 429
