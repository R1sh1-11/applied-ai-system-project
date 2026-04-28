"""
test_recommender.py — Unit tests for the scoring engine and agent.

Tests cover:
  - Score computation correctness
  - Tag-based search filtering
  - Agent plan parsing (intent detection)
  - Agent end-to-end playlist generation
  - Agent evaluation logic
  - Edge cases (empty catalog, unknown genres)
"""

import pytest
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import Song, UserProfile, load_songs
from src.recommender import score_song, recommend, search_by_tags, get_catalog_stats
from src.agent import PlaylistAgent


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def sample_songs():
    """A small set of songs for testing."""
    return [
        Song("Pop Hit", "Artist A", "pop", "happy", 0.8, 120, 0.7, 0.8, 0.1),
        Song("Chill Beat", "Artist B", "lofi", "chill", 0.3, 85, 0.5, 0.5, 0.75),
        Song("Rock Anthem", "Artist C", "rock", "intense", 0.95, 150, 0.4, 0.4, 0.02),
        Song("Sad Ballad", "Artist D", "indie pop", "melancholy", 0.2, 70, 0.2, 0.3, 0.8),
        Song("Dance Floor", "Artist E", "edm", "happy", 0.9, 140, 0.75, 0.9, 0.01),
        Song("Jazz Night", "Artist F", "jazz", "chill", 0.35, 90, 0.6, 0.6, 0.88),
        Song("Folk Morning", "Artist G", "folk", "happy", 0.45, 100, 0.7, 0.5, 0.9),
        Song("Ambient Drift", "Artist H", "ambient", "chill", 0.1, 60, 0.3, 0.2, 0.95),
    ]


@pytest.fixture
def pop_profile():
    return UserProfile("TestUser", genre="pop", mood="happy", energy=0.75)


@pytest.fixture
def chill_profile():
    return UserProfile("ChillUser", genre="lofi", mood="chill",
                        energy=0.3, likes_acoustic=True)


@pytest.fixture
def full_catalog():
    """Load the full song catalog."""
    return load_songs()


# ── Scoring Tests ──────────────────────────────────────────────────

class TestScoring:
    def test_perfect_genre_match_scores_highest(self, sample_songs, pop_profile):
        """A song matching the user's genre should score higher than non-matches."""
        pop_song = sample_songs[0]  # Pop Hit
        rock_song = sample_songs[2]  # Rock Anthem
        pop_score, _ = score_song(pop_song, pop_profile)
        rock_score, _ = score_song(rock_song, pop_profile)
        assert pop_score > rock_score

    def test_mood_match_adds_points(self, sample_songs, pop_profile):
        """A mood match should contribute to the score."""
        happy_song = sample_songs[0]  # happy mood
        sad_song = sample_songs[3]    # melancholy mood
        happy_score, happy_bd = score_song(happy_song, pop_profile)
        sad_score, sad_bd = score_song(sad_song, pop_profile)
        assert happy_bd["mood"] > sad_bd["mood"]

    def test_energy_similarity_scoring(self, sample_songs, pop_profile):
        """Songs closer in energy to the user should score higher on energy."""
        # pop_profile energy = 0.75
        pop_song = sample_songs[0]   # energy 0.8 (close)
        ambient = sample_songs[7]     # energy 0.1 (far)
        _, pop_bd = score_song(pop_song, pop_profile)
        _, amb_bd = score_song(ambient, pop_profile)
        assert pop_bd["energy"] > amb_bd["energy"]

    def test_acoustic_bonus(self, sample_songs, chill_profile):
        """Acoustic bonus should only apply when user likes acoustic."""
        acoustic_song = sample_songs[1]  # acousticness 0.75
        _, bd = score_song(acoustic_song, chill_profile)
        assert bd["acoustic"] > 0

    def test_no_acoustic_bonus_when_not_preferred(self, sample_songs, pop_profile):
        """No acoustic bonus when user doesn't prefer acoustic."""
        acoustic_song = sample_songs[1]
        _, bd = score_song(acoustic_song, pop_profile)
        assert bd["acoustic"] == 0

    def test_score_is_non_negative(self, sample_songs, pop_profile):
        """All scores should be >= 0."""
        for song in sample_songs:
            total, _ = score_song(song, pop_profile)
            assert total >= 0


# ── Recommender Tests ──────────────────────────────────────────────

class TestRecommender:
    def test_recommend_returns_correct_count(self, sample_songs, pop_profile):
        results = recommend(sample_songs, pop_profile, top_k=3)
        assert len(results) == 3

    def test_recommend_sorted_descending(self, sample_songs, pop_profile):
        results = recommend(sample_songs, pop_profile, top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_includes_reasons(self, sample_songs, pop_profile):
        results = recommend(sample_songs, pop_profile, top_k=1)
        assert "reasons" in results[0]
        assert isinstance(results[0]["reasons"], list)

    def test_top_k_larger_than_catalog(self, sample_songs, pop_profile):
        """Requesting more songs than available should return all songs."""
        results = recommend(sample_songs, pop_profile, top_k=100)
        assert len(results) == len(sample_songs)


# ── Tag Search Tests ───────────────────────────────────────────────

class TestTagSearch:
    def test_filter_by_genre(self, sample_songs):
        results = search_by_tags(sample_songs, genre="rock")
        assert all(s.genre == "rock" for s in results)
        assert len(results) == 1

    def test_filter_by_mood(self, sample_songs):
        results = search_by_tags(sample_songs, mood="chill")
        assert all(s.mood == "chill" for s in results)

    def test_filter_by_energy_range(self, sample_songs):
        results = search_by_tags(sample_songs, min_energy=0.8)
        assert all(s.energy >= 0.8 for s in results)

    def test_combined_filters(self, sample_songs):
        results = search_by_tags(sample_songs, mood="happy", min_energy=0.8)
        assert all(s.mood == "happy" and s.energy >= 0.8 for s in results)

    def test_no_results_for_missing_genre(self, sample_songs):
        results = search_by_tags(sample_songs, genre="k-pop")
        assert len(results) == 0


# ── Agent Tests ────────────────────────────────────────────────────

class TestAgent:
    def test_agent_returns_playlist(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("Give me a chill playlist with 4 songs")
        assert len(trace.final_playlist) > 0

    def test_agent_detects_energy_arc(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("Start slow and build up to intense, 5 songs")
        assert trace.plan.detected_intent == "energy_arc"
        assert trace.plan.constraints["arc"] == "build_up"

    def test_agent_detects_wind_down(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("Start intense and wind down to calm, 5 songs")
        assert trace.plan.detected_intent == "energy_arc"
        assert trace.plan.constraints["arc"] == "wind_down"

    def test_agent_detects_simple_intent(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("I want happy pop songs")
        assert trace.plan.detected_intent == "simple"

    def test_agent_detects_mood_journey(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("Take me from happy to melancholy, 6 songs")
        assert trace.plan.detected_intent == "mood_journey"

    def test_agent_no_duplicates(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("Make a 6 song playlist with chill vibes")
        titles = [s.title for s in trace.final_playlist]
        assert len(titles) == len(set(titles))

    def test_agent_evaluation_runs(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("Give me 4 chill songs")
        assert trace.evaluation is not None
        assert 0.0 <= trace.evaluation.score <= 1.0

    def test_agent_build_up_energy_order(self, full_catalog):
        """For a build-up request, final playlist should trend upward in energy."""
        agent = PlaylistAgent(full_catalog)
        trace = agent.run("Start chill and build up to high energy, 6 songs")
        if len(trace.final_playlist) >= 2:
            energies = [s.energy for s in trace.final_playlist]
            assert energies[-1] >= energies[0], \
                f"Energy should increase: {energies}"

    def test_agent_handles_empty_request(self, sample_songs):
        agent = PlaylistAgent(sample_songs)
        trace = agent.run("play something")
        assert len(trace.final_playlist) > 0


# ── Catalog Stats Tests ────────────────────────────────────────────

class TestCatalogStats:
    def test_stats_keys(self, sample_songs):
        stats = get_catalog_stats(sample_songs)
        assert "total_songs" in stats
        assert "genres" in stats
        assert "moods" in stats

    def test_stats_total(self, sample_songs):
        stats = get_catalog_stats(sample_songs)
        assert stats["total_songs"] == len(sample_songs)