"""
models.py — Data models for songs and user profiles.

Kept from Module 3 with minor extensions to support agentic planning.
"""

import csv
import os
import logging

logger = logging.getLogger(__name__)


class Song:
    """Represents a single song with audio features."""

    def __init__(self, title, artist, genre, mood, energy, tempo_bpm,
                 valence, danceability, acousticness):
        self.title = title
        self.artist = artist
        self.genre = genre.lower().strip()
        self.mood = mood.lower().strip()
        self.energy = float(energy)
        self.tempo_bpm = int(float(tempo_bpm))
        self.valence = float(valence)
        self.danceability = float(danceability)
        self.acousticness = float(acousticness)

    def to_dict(self):
        return {
            "title": self.title,
            "artist": self.artist,
            "genre": self.genre,
            "mood": self.mood,
            "energy": self.energy,
            "tempo_bpm": self.tempo_bpm,
            "valence": self.valence,
            "danceability": self.danceability,
            "acousticness": self.acousticness,
        }

    def __repr__(self):
        return f"Song('{self.title}' by {self.artist} | {self.genre}/{self.mood} | energy={self.energy})"


class UserProfile:
    """Stores a user's taste preferences."""

    def __init__(self, name, genre, mood, energy, likes_acoustic=False):
        self.name = name
        self.genre = genre.lower().strip()
        self.mood = mood.lower().strip()
        self.energy = float(energy)
        self.likes_acoustic = likes_acoustic

    def to_dict(self):
        return {
            "name": self.name,
            "genre": self.genre,
            "mood": self.mood,
            "energy": self.energy,
            "likes_acoustic": self.likes_acoustic,
        }

    def __repr__(self):
        return f"UserProfile('{self.name}' | {self.genre}/{self.mood} | energy={self.energy})"


def load_songs(filepath=None):
    """Load songs from CSV file. Returns a list of Song objects."""
    if filepath is None:
        # Try multiple paths for flexibility
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv"),
            os.path.join("data", "songs.csv"),
        ]
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break

    if filepath is None or not os.path.exists(filepath):
        logger.error(f"Song catalog not found at {filepath}")
        raise FileNotFoundError(f"Could not find songs.csv")

    songs = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                song = Song(
                    title=row["title"],
                    artist=row["artist"],
                    genre=row["genre"],
                    mood=row["mood"],
                    energy=row["energy"],
                    tempo_bpm=row["tempo_bpm"],
                    valence=row["valence"],
                    danceability=row["danceability"],
                    acousticness=row["acousticness"],
                )
                songs.append(song)
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping malformed row: {row} — {e}")

    logger.info(f"Loaded {len(songs)} songs from {filepath}")
    return songs
