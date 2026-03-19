"""
Tests for normalized repository tables (relationships, achievements, votes).
"""
import pytest

from src.repositories.relationship_repo import (
    get_relationship_score,
    set_relationship_score,
    adjust_relationship_score,
    get_all_relationships,
    delete_relationships,
    get_top_relationships,
)
from src.repositories.achievement_repo import (
    get_achievements,
    has_achievement,
    add_achievement,
    remove_achievement,
    clear_achievements,
    count_achievements,
    get_villagers_with_achievement,
)
from src.repositories.vote_repo import (
    get_kings_voted_for,
    has_voted_for,
    add_vote,
    clear_votes,
    count_votes_for_king,
    get_voters_for_king,
)


class TestRelationshipRepo:
    """Tests for villager_relationships table operations."""

    @pytest.mark.integration
    def test_get_set_relationship(self, test_db_connection):
        """Should set and get relationship score."""
        set_relationship_score(1, 2, 50)
        assert get_relationship_score(1, 2) == 50
        assert get_relationship_score(2, 1) == 0  # Not symmetric by default

    @pytest.mark.integration
    def test_adjust_relationship(self, test_db_connection):
        """Should adjust relationship by delta."""
        set_relationship_score(1, 3, 0)
        new_score = adjust_relationship_score(1, 3, 25)
        assert new_score == 25
        
        # Test clamping
        new_score = adjust_relationship_score(1, 3, 100)
        assert new_score == 100  # Clamped to max
        
        new_score = adjust_relationship_score(1, 3, -250)
        assert new_score == -100  # Clamped to min

    @pytest.mark.integration
    def test_get_all_relationships(self, test_db_connection):
        """Should get all relationships for a villager."""
        set_relationship_score(10, 11, 30)
        set_relationship_score(10, 12, -20)
        set_relationship_score(10, 13, 50)
        
        rels = get_all_relationships(10)
        assert rels == {11: 30, 12: -20, 13: 50}

    @pytest.mark.integration
    def test_delete_relationships(self, test_db_connection):
        """Should delete all relationships for a villager."""
        set_relationship_score(20, 21, 10)
        set_relationship_score(22, 20, 20)  # Other direction
        
        delete_relationships(20)
        
        assert get_relationship_score(20, 21) == 0
        assert get_relationship_score(22, 20) == 0

    @pytest.mark.integration
    def test_get_top_relationships(self, test_db_connection):
        """Should get top N relationships by score."""
        set_relationship_score(30, 31, 10)
        set_relationship_score(30, 32, 50)
        set_relationship_score(30, 33, 30)
        set_relationship_score(30, 34, 80)
        
        top = get_top_relationships(30, limit=2)
        assert len(top) == 2
        assert top[0] == (34, 80)
        assert top[1] == (32, 50)


class TestAchievementRepo:
    """Tests for villager_achievements table operations."""

    @pytest.mark.integration
    def test_add_get_achievement(self, test_db_connection):
        """Should add and get achievements."""
        assert add_achievement(100, "centurion") is True
        assert add_achievement(100, "trader") is True
        assert add_achievement(100, "centurion") is False  # Already has
        
        achs = get_achievements(100)
        assert set(achs) == {"centurion", "trader"}

    @pytest.mark.integration
    def test_has_achievement(self, test_db_connection):
        """Should check if villager has achievement."""
        add_achievement(101, "hunter")
        
        assert has_achievement(101, "hunter") is True
        assert has_achievement(101, "warrior") is False

    @pytest.mark.integration
    def test_remove_achievement(self, test_db_connection):
        """Should remove specific achievement."""
        add_achievement(102, "scholar")
        add_achievement(102, "explorer")
        
        remove_achievement(102, "scholar")
        
        achs = get_achievements(102)
        assert achs == ["explorer"]

    @pytest.mark.integration
    def test_clear_achievements(self, test_db_connection):
        """Should clear all achievements."""
        add_achievement(103, "a1")
        add_achievement(103, "a2")
        
        clear_achievements(103)
        
        assert get_achievements(103) == []

    @pytest.mark.integration
    def test_count_achievements(self, test_db_connection):
        """Should count achievements."""
        add_achievement(104, "x1")
        add_achievement(104, "x2")
        add_achievement(104, "x3")
        
        assert count_achievements(104) == 3

    @pytest.mark.integration
    def test_get_villagers_with_achievement(self, test_db_connection):
        """Should get all villagers with specific achievement."""
        add_achievement(200, "hero")
        add_achievement(201, "hero")
        add_achievement(202, "hero")
        
        villagers = get_villagers_with_achievement("hero")
        assert set(villagers) == {200, 201, 202}


class TestVoteRepo:
    """Tests for villager_votes table operations."""

    @pytest.mark.integration
    def test_add_get_votes(self, test_db_connection):
        """Should add and get vote records."""
        assert add_vote(300, 1) is True
        assert add_vote(300, 2) is True
        assert add_vote(300, 1) is False  # Already voted
        
        kings = get_kings_voted_for(300)
        assert set(kings) == {1, 2}

    @pytest.mark.integration
    def test_has_voted_for(self, test_db_connection):
        """Should check if villager voted for king."""
        add_vote(301, 5)
        
        assert has_voted_for(301, 5) is True
        assert has_voted_for(301, 6) is False

    @pytest.mark.integration
    def test_clear_votes(self, test_db_connection):
        """Should clear all votes."""
        add_vote(302, 1)
        add_vote(302, 2)
        
        clear_votes(302)
        
        assert get_kings_voted_for(302) == []

    @pytest.mark.integration
    def test_count_votes_for_king(self, test_db_connection):
        """Should count votes for a king."""
        add_vote(400, 50)
        add_vote(401, 50)
        add_vote(402, 50)
        
        assert count_votes_for_king(50) == 3

    @pytest.mark.integration
    def test_get_voters_for_king(self, test_db_connection):
        """Should get all voters for a king."""
        add_vote(500, 99)
        add_vote(501, 99)
        
        voters = get_voters_for_king(99)
        assert set(voters) == {500, 501}
