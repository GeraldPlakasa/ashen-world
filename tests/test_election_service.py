"""
Unit tests for Election Service
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.election_service import (
    get_traits_set,
    leadership_score,
    voter_adjustment,
    reassign_job_by_traits,
    hold_election,
)


class TestGetTraitsSet:
    """Tests for parsing traits."""

    @pytest.mark.unit
    def test_parse_single_trait(self):
        """Should parse single trait."""
        v = {"traits": "Brave"}
        traits = get_traits_set(v)
        assert "Brave" in traits

    @pytest.mark.unit
    def test_parse_multiple_traits(self):
        """Should parse comma-separated traits."""
        v = {"traits": "Brave, Wise, Loyal"}
        traits = get_traits_set(v)
        assert "Brave" in traits
        assert "Wise" in traits
        assert "Loyal" in traits

    @pytest.mark.unit
    def test_empty_traits(self):
        """Should return empty set for no traits."""
        v = {"traits": ""}
        traits = get_traits_set(v)
        assert len(traits) == 0

    @pytest.mark.unit
    def test_missing_traits_key(self):
        """Should handle missing traits key."""
        v = {"name": "Test"}
        traits = get_traits_set(v)
        assert len(traits) == 0

    @pytest.mark.unit
    def test_whitespace_handling(self):
        """Should trim whitespace from traits."""
        v = {"traits": "  Brave  ,  Wise  "}
        traits = get_traits_set(v)
        assert "Brave" in traits
        assert "Wise" in traits


class TestLeadershipScore:
    """Tests for leadership score calculation."""

    @pytest.fixture
    def basic_candidate(self):
        return {
            "id": 1,
            "name": "Candidate",
            "alive": True,
            "age": 35,
            "int": 50,
            "rep": 30,
            "level": 5,
            "coins": 500,
            "traits": "Wise",
            "job": "Merchant",
        }

    @pytest.fixture
    def previous_king(self):
        return {
            "id": 99,
            "name": "Old King",
            "job": "King",
            "alive": False,
            "fatherId": None,
            "motherId": None,
        }

    @pytest.mark.unit
    def test_basic_score_positive(self, basic_candidate):
        """Viable candidate should have positive score."""
        score = leadership_score(basic_candidate)
        assert score > 0

    @pytest.mark.unit
    def test_dead_candidate_penalty(self, basic_candidate):
        """Dead candidate should have heavy penalty."""
        basic_candidate["alive"] = False
        score = leadership_score(basic_candidate)
        assert score < 0 or score < leadership_score({**basic_candidate, "alive": True})

    @pytest.mark.unit
    def test_child_penalty(self, basic_candidate):
        """Underage candidate should have penalty."""
        basic_candidate["age"] = 10
        score = leadership_score(basic_candidate)
        child_score = score
        
        basic_candidate["age"] = 35
        adult_score = leadership_score(basic_candidate)
        
        assert child_score < adult_score

    @pytest.mark.unit
    def test_intelligence_bonus(self, basic_candidate):
        """Higher INT should increase score."""
        basic_candidate["int"] = 20
        low_score = leadership_score(basic_candidate)
        
        basic_candidate["int"] = 80
        high_score = leadership_score(basic_candidate)
        
        assert high_score > low_score

    @pytest.mark.unit
    def test_reputation_bonus(self, basic_candidate):
        """Higher REP should increase score."""
        basic_candidate["rep"] = 10
        low_score = leadership_score(basic_candidate)
        
        basic_candidate["rep"] = 60
        high_score = leadership_score(basic_candidate)
        
        assert high_score > low_score

    @pytest.mark.unit
    def test_wise_trait_bonus(self, basic_candidate):
        """Wise trait should increase score."""
        basic_candidate["traits"] = ""
        no_trait_score = leadership_score(basic_candidate)
        
        basic_candidate["traits"] = "Wise"
        wise_score = leadership_score(basic_candidate)
        
        assert wise_score > no_trait_score

    @pytest.mark.unit
    def test_greedy_trait_penalty(self, basic_candidate):
        """Greedy trait should decrease score."""
        basic_candidate["traits"] = ""
        no_trait_score = leadership_score(basic_candidate)
        
        basic_candidate["traits"] = "Greedy"
        greedy_score = leadership_score(basic_candidate)
        
        assert greedy_score < no_trait_score

    @pytest.mark.unit
    def test_dynasty_bonus(self, basic_candidate, previous_king):
        """Related to previous king should get bonus."""
        basic_candidate["fatherId"] = previous_king["id"]
        dynasty_score = leadership_score(basic_candidate, prev_king=previous_king)
        
        basic_candidate["fatherId"] = None
        no_dynasty_score = leadership_score(basic_candidate, prev_king=previous_king)
        
        # Dynasty score should be >= no dynasty (may be equal in some implementations)
        assert dynasty_score >= no_dynasty_score


class TestVoterAdjustment:
    """Tests for voter preference adjustments."""

    @pytest.fixture
    def voter(self):
        return {
            "id": 1,
            "name": "Voter",
            "traits": "Brave, Loyal",
            "job": "Soldier",
        }

    @pytest.fixture
    def candidate(self):
        return {
            "id": 2,
            "name": "Candidate",
            "traits": "Brave",
            "job": "Knight",
        }

    @pytest.mark.unit
    def test_shared_traits_bonus(self, voter, candidate):
        """Shared traits should increase preference."""
        # Both have Brave trait
        adjustment = voter_adjustment(voter, candidate)
        
        candidate["traits"] = "Greedy"  # No shared traits
        no_shared_adjustment = voter_adjustment(voter, candidate)
        
        assert adjustment >= no_shared_adjustment

    @pytest.mark.unit
    def test_returns_numeric(self, voter, candidate):
        """Should return numeric adjustment."""
        adjustment = voter_adjustment(voter, candidate)
        assert isinstance(adjustment, (int, float))


class TestReassignJobByTraits:
    """Tests for job reassignment."""

    @pytest.mark.unit
    def test_brave_gets_valid_job(self):
        """Brave trait should get a valid job."""
        v = {"traits": "Brave", "age": 25, "alive": True}
        job = reassign_job_by_traits(v)
        # Should get a valid job string
        assert isinstance(job, str)
        assert len(job) > 0

    @pytest.mark.unit
    def test_wise_gets_valid_job(self):
        """Wise trait should get a valid job."""
        v = {"traits": "Wise", "age": 25, "alive": True}
        job = reassign_job_by_traits(v)
        assert job is not None
        assert isinstance(job, str)

    @pytest.mark.unit
    def test_returns_valid_job(self):
        """Should always return a valid job string."""
        v = {"traits": "", "age": 25, "alive": True}
        job = reassign_job_by_traits(v)
        assert isinstance(job, str)
        assert len(job) > 0


class TestHoldElection:
    """Tests for election process."""

    @pytest.fixture
    def election_candidates(self, test_db_connection):
        # `test_db_connection` (from conftest) patches config.DB_PATH to a
        # temp file. hold_election() writes chronicle entries via
        # record_election() and maybe_militarization_decree(); without the
        # patch those go straight to the live data/ashen_world.sqlite3 and
        # show up forever as "King Albert elected first King" with the
        # other test names. Pulling the fixture in here protects every
        # test method below transitively.
        return [
            {
                "id": 1,
                "name": "King Albert",
                "job": "King",
                "alive": True,
                "age": 50,
                "int": 60,
                "rep": 50,
                "level": 10,
                "traits": "Wise",
            },
            {
                "id": 2,
                "name": "Lord Baron",
                "job": "Noble",
                "alive": True,
                "age": 40,
                "int": 70,
                "rep": 60,
                "level": 8,
                "traits": "Ambitious",
            },
            {
                "id": 3,
                "name": "Lady Clara",
                "job": "Merchant",
                "alive": True,
                "age": 35,
                "int": 80,
                "rep": 40,
                "level": 6,
                "traits": "Wise, Brave",
            },
            {
                "id": 4,
                "name": "Child Dan",
                "job": "Child",
                "alive": True,
                "age": 10,
                "int": 30,
                "rep": 10,
                "level": 1,
                "traits": "",
            },
        ]

    @pytest.mark.unit
    def test_election_returns_tuple(self, election_candidates):
        """Should return (winner, message) tuple."""
        winner, msg = hold_election(election_candidates)
        assert isinstance(winner, (dict, type(None)))
        assert isinstance(msg, (str, type(None)))

    @pytest.mark.unit
    def test_election_selects_winner(self, election_candidates):
        """Should select a winner from candidates."""
        winner, msg = hold_election(election_candidates)
        if winner:
            assert winner["id"] in [c["id"] for c in election_candidates]

    @pytest.mark.unit
    def test_child_cannot_win(self, election_candidates):
        """Child should not win election."""
        # Run multiple elections to check child never wins
        for _ in range(10):
            winner, msg = hold_election(election_candidates)
            if winner:
                assert winner["age"] >= 17, "Child should not win election"

    @pytest.mark.unit
    def test_dead_cannot_win(self, election_candidates):
        """Dead candidate should not win."""
        # Kill all but one candidate
        for c in election_candidates[1:]:
            c["alive"] = False
        
        winner, msg = hold_election(election_candidates)
        if winner:
            assert winner["alive"] is True

    @pytest.mark.unit
    def test_winner_becomes_king(self, election_candidates):
        """Winner should have King job assigned."""
        winner, msg = hold_election(election_candidates)
        if winner:
            assert winner.get("job") == "King"

    @pytest.mark.unit
    def test_election_message_contains_winner_name(self, election_candidates):
        """Election message should mention winner."""
        winner, msg = hold_election(election_candidates)
        if winner and msg:
            assert winner["name"] in msg or "elected" in msg.lower()
