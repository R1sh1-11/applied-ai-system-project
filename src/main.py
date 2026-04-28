"""
main.py — Entry point for VibeFinder 2.0.

Demonstrates both the original Module 3 recommender and the new
agentic playlist planner with full reasoning traces.
"""

import logging
import sys

from src.models import load_songs, UserProfile
from src.recommender import recommend, get_catalog_stats
from src.agent import PlaylistAgent, format_trace

# ── Logging setup ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("vibefinder.log", mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def divider(title=""):
    print(f"\n{'━' * 65}")
    if title:
        print(f"  {title}")
        print(f"{'━' * 65}")


def demo_original_recommender(songs):
    """Run the original Module 3 recommender with sample profiles."""
    divider("PART 1: ORIGINAL RECOMMENDER (Module 3)")

    profiles = [
        UserProfile("Happy Pop Fan", genre="pop", mood="happy", energy=0.7),
        UserProfile("Chill Lofi Listener", genre="lofi", mood="chill",
                     energy=0.3, likes_acoustic=True),
        UserProfile("Intense Rock Lover", genre="rock", mood="intense", energy=0.9),
    ]

    for profile in profiles:
        divider(f"Profile: {profile.name}")
        results = recommend(songs, profile, top_k=5)
        for i, r in enumerate(results, 1):
            song = r["song"]
            print(f"  {i}. {song.title:<25s} by {song.artist:<20s} "
                  f"score={r['score']:.2f}  reasons={r['reasons']}")
        print()


def demo_agent_planner(songs):
    """Run the new agentic playlist planner with diverse requests."""
    divider("PART 2: AGENTIC PLAYLIST PLANNER (New Feature)")

    agent = PlaylistAgent(songs)

    requests = [
        "I need a 6-song workout playlist that starts chill and builds up to intense energy",
        "Give me a relaxing chill playlist with 5 songs for studying",
        "Make me a party mix with EDM and pop songs, 6 songs that are happy and danceable",
    ]

    for request in requests:
        print()
        trace = agent.run(request)
        print(format_trace(trace))
        print()


def interactive_mode(songs):
    """Let the user type their own playlist requests."""
    divider("INTERACTIVE MODE")
    print("  Type a playlist request (or 'quit' to exit):")
    print("  Examples:")
    print("    - 'Make me a chill lofi playlist with 5 songs'")
    print("    - 'I want a workout mix that builds up from calm to intense'")
    print("    - 'Give me a sad indie rock playlist for a rainy day'")
    print()

    agent = PlaylistAgent(songs)

    while True:
        try:
            request = input("  🎵 Your request: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not request or request.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break

        trace = agent.run(request)
        print(format_trace(trace))
        print()


def main():
    logger.info("Starting VibeFinder 2.0")

    # Load song catalog
    songs = load_songs()
    stats = get_catalog_stats(songs)
    divider("VibeFinder 2.0 — Agentic Music Recommender")
    print(f"  Catalog: {stats['total_songs']} songs, "
          f"{len(stats['genres'])} genres, {len(stats['moods'])} moods")
    print(f"  Genres: {', '.join(stats['genres'])}")
    print(f"  Moods: {', '.join(stats['moods'])}")

    # Run demos
    demo_original_recommender(songs)
    demo_agent_planner(songs)

    # Interactive mode (skip if not a terminal)
    if sys.stdin.isatty():
        interactive_mode(songs)


if __name__ == "__main__":
    main()
