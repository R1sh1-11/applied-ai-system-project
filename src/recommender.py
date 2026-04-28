"""
recommender.py — Content-based scoring engine.

Evolved from Module 3: now supports filtered retrieval, tag-based search,
and returns structured score breakdowns for the agent to reason over.
"""

import logging

logger = logging.getLogger(__name__)


# ── Scoring weights (tunable) ──────────────────────────────────────
WEIGHT_GENRE = 2.0
WEIGHT_MOOD = 1.0
WEIGHT_ENERGY = 1.0  # max contribution when energy matches perfectly
WEIGHT_ACOUSTIC = 0.5
WEIGHT_DANCEABILITY = 0.5
WEIGHT_VALENCE = 0.5


def score_song(song, profile):
    """
    Score a single song against a user profile.
    Returns (total_score, breakdown_dict).
    """
    breakdown = {}

    # Genre match (exact)
    genre_pts = WEIGHT_GENRE if song.genre == profile.genre else 0.0
    breakdown["genre"] = genre_pts

    # Mood match (exact)
    mood_pts = WEIGHT_MOOD if song.mood == profile.mood else 0.0
    breakdown["mood"] = mood_pts

    # Energy similarity (1 - |diff|) scaled by weight
    energy_diff = abs(song.energy - profile.energy)
    energy_pts = WEIGHT_ENERGY * (1.0 - energy_diff)
    breakdown["energy"] = round(energy_pts, 3)

    # Acoustic bonus
    acoustic_pts = 0.0
    if profile.likes_acoustic and song.acousticness > 0.7:
        acoustic_pts = WEIGHT_ACOUSTIC
    breakdown["acoustic"] = acoustic_pts

    total = genre_pts + mood_pts + energy_pts + acoustic_pts
    return round(total, 3), breakdown


def recommend(songs, profile, top_k=5):
    """
    Score all songs and return top_k results with breakdowns.
    """
    scored = []
    for song in songs:
        total, breakdown = score_song(song, profile)
        scored.append({
            "song": song,
            "score": total,
            "breakdown": breakdown,
            "reasons": _build_reasons(breakdown),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    results = scored[:top_k]

    logger.info(f"Recommended {len(results)} songs for profile '{profile.name}'")
    return results


def search_by_tags(songs, genre=None, mood=None, min_energy=None,
                   max_energy=None, min_danceability=None):
    """
    Filter songs by attribute tags. Used by the agent for targeted retrieval.
    """
    results = songs
    if genre:
        results = [s for s in results if s.genre == genre.lower()]
    if mood:
        results = [s for s in results if s.mood == mood.lower()]
    if min_energy is not None:
        results = [s for s in results if s.energy >= min_energy]
    if max_energy is not None:
        results = [s for s in results if s.energy <= max_energy]
    if min_danceability is not None:
        results = [s for s in results if s.danceability >= min_danceability]

    logger.info(f"Tag search returned {len(results)} songs (genre={genre}, mood={mood})")
    return results


def get_catalog_stats(songs):
    """Return summary statistics about the song catalog."""
    genres = set(s.genre for s in songs)
    moods = set(s.mood for s in songs)
    return {
        "total_songs": len(songs),
        "genres": sorted(genres),
        "moods": sorted(moods),
        "energy_range": (
            round(min(s.energy for s in songs), 2),
            round(max(s.energy for s in songs), 2),
        ),
        "tempo_range": (
            min(s.tempo_bpm for s in songs),
            max(s.tempo_bpm for s in songs),
        ),
    }


def _build_reasons(breakdown):
    """Convert a score breakdown into human-readable reasons."""
    reasons = []
    if breakdown.get("genre", 0) > 0:
        reasons.append("genre match")
    if breakdown.get("mood", 0) > 0:
        reasons.append("mood match")
    if breakdown.get("energy", 0) > 0.7:
        reasons.append("strong energy fit")
    elif breakdown.get("energy", 0) > 0.4:
        reasons.append("moderate energy fit")
    if breakdown.get("acoustic", 0) > 0:
        reasons.append("acoustic preference")
    return reasons
