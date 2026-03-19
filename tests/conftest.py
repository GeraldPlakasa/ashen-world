"""
Shared pytest fixtures for Ashen World tests.
"""
from __future__ import annotations

import os
import sys
import random
import tempfile
from typing import Generator, Callable

import pytest

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Villager, Bank


@pytest.fixture
def sample_villager() -> Villager:
    """Minimal villager dict with known stats for testing."""
    return {
        "id": 1,
        "name": "Test Villager",
        "family": "Testfamily",
        "gender": "Male",
        "job": "Farmer",
        "coins": 100,
        "age": 25,
        "int": 50,
        "rep": 30,
        "level": 5,
        "exp": 0,
        "atk": 20,
        "def": 15,
        "hp": 100,
        "hunger": 0,
        "traits": "Brave, Wise",
        "last_action": "",
        "action_log": "",
        "relationships": {},
        "spouseId": 0,
        "spouseSinceDay": 0,
        "spouseId_at_death": 0,
        "alive": True,
        "origin": "generated",
        "owner": "",
        "gen": 1,
        "immigrantGen": 0,
        "motherId": 0,
        "fatherId": 0,
        "childrenIds": [],
        "kingTerms": 0,
        "death_day": 0,
        "huntWins": 0,
        "huntWinsYear": 0,
        "born_day": 1,
        "last_birth_day": 0,
    }


@pytest.fixture
def sample_king(sample_villager: Villager) -> Villager:
    """King villager for election tests."""
    king = sample_villager.copy()
    king.update({
        "id": 2,
        "name": "King Testus",
        "job": "King",
        "traits": "Wise, Loyal",
        "age": 35,
        "int": 70,
        "rep": 60,
        "level": 10,
        "atk": 40,
        "def": 35,
        "kingTerms": 1,
    })
    return king


@pytest.fixture
def sample_female_villager(sample_villager: Villager) -> Villager:
    """Female villager for marriage/relationship tests."""
    female = sample_villager.copy()
    female.update({
        "id": 3,
        "name": "Female Tester",
        "gender": "Female",
        "age": 24,
    })
    return female


@pytest.fixture
def sample_child(sample_villager: Villager) -> Villager:
    """Child villager (age <= 16) for child-related tests."""
    child = sample_villager.copy()
    child.update({
        "id": 4,
        "name": "Child Tester",
        "age": 10,
        "job": "Child",
        "atk": 5,
        "def": 5,
        "int": 20,
    })
    return child


@pytest.fixture
def sample_bank() -> Bank:
    """Village treasury/bank state for testing."""
    return {
        "tax_rate": 0.10,
        "balance": 1000,
        "building_levels": {},
        "building_health": {},
        "last_election_year": None,
        "last_election_message": "",
        "year_stats": {},
        "yearly_history": [],
    }


@pytest.fixture
def sample_bank_with_buildings(sample_bank: Bank) -> Bank:
    """Bank state with some buildings constructed."""
    bank = sample_bank.copy()
    bank["building_levels"] = {
        "market": 2,
        "barracks": 1,
        "granary": 1,
    }
    bank["building_health"] = {
        "market": 100,
        "barracks": 75,
        "granary": 50,
    }
    return bank


@pytest.fixture
def test_db_path() -> Generator[str, None, None]:
    """
    Temporary SQLite database path for testing.
    Returns the path to a temp file that is deleted after the test.
    """
    import time
    import gc

    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    yield path
    # Cleanup with retry for Windows file locking
    gc.collect()  # Force garbage collection to release any lingering connections
    for attempt in range(3):
        try:
            if os.path.exists(path):
                os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)  # Brief delay before retry
    # If still can't delete, ignore - temp files will be cleaned up eventually


@pytest.fixture
def test_db_connection(test_db_path: str, monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """
    Patches config.DB_PATH to use a temporary test database.
    """
    import config
    from src.repositories import base as repo_base

    monkeypatch.setattr(config, "DB_PATH", test_db_path)

    # Initialize the test database
    repo_base.init_db()

    yield test_db_path


@pytest.fixture
def seeded_random() -> Generator[Callable[[int], None], None, None]:
    """
    Fixture that seeds random for deterministic tests.
    Returns a function that can be called with a seed.
    """
    original_state = random.getstate()

    def seed(value=42):
        random.seed(value)

    yield seed

    # Restore original state
    random.setstate(original_state)


@pytest.fixture
def flask_client():
    """
    Flask test client for integration tests.
    """
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app.test_client() as client:
        with flask_app.app.app_context():
            yield client


@pytest.fixture
def multiple_villagers(sample_villager: Villager, sample_king: Villager, sample_female_villager: Villager) -> list[Villager]:
    """A list of multiple villagers for testing village-wide operations."""
    villagers = []

    # Add base villagers
    villagers.append(sample_villager.copy())
    villagers.append(sample_king.copy())
    villagers.append(sample_female_villager.copy())

    # Add more varied villagers
    for i in range(4, 10):
        v = sample_villager.copy()
        v["id"] = i
        v["name"] = f"Villager {i}"
        v["age"] = 18 + (i * 3) % 50
        v["gender"] = "Male" if i % 2 == 0 else "Female"
        v["atk"] = 10 + i * 2
        v["def"] = 10 + i
        v["int"] = 30 + i * 3
        v["rep"] = 20 + i * 2
        villagers.append(v)

    return villagers


@pytest.fixture
def dead_villager(sample_villager: Villager) -> Villager:
    """A dead villager for death/graveyard tests."""
    dead = sample_villager.copy()
    dead.update({
        "id": 99,
        "name": "Dead Villager",
        "alive": False,
        "hp": 0,
        "death_day": 100,
        "coins": 500,
    })
    return dead
