"""
eval_harness.py — Automated evaluation harness for the playlist agent.

Runs a suite of predefined requests and prints a pass/fail summary
with confidence scores. This is the "Test Harness" stretch feature.

Usage:
    python -m src.eval_harness
"""

import sys
import os
import json
from dataclasses import dataclass
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import load_songs
from src.agent import PlaylistAgent


@dataclass
class TestCase:
    """A single evaluation test case."""
    name: str
    request: str
    expected_intent: str
    min_songs: int
    check_energy_ascending: bool = False
    check_energy_descending: bool = False
    expected_moods: list = None
    expected_genres: list = None


# ── Test Suite ─────────────────────────────────────────────────────

TEST_CASES = [
    TestCase(
        name="Simple chill request",
        request="Give me 5 chill songs for studying",
        expected_intent="simple",
        min_songs=4,
        expected_moods=["chill"],
    ),
    TestCase(
        name="Energy build-up",
        request="Make a 6 song playlist that starts slow and builds up to intense",
        expected_intent="energy_arc",
        min_songs=5,
        check_energy_ascending=True,
    ),
    TestCase(
        name="Energy wind-down",
        request="Start intense and wind down to calm, 6 songs",
        expected_intent="energy_arc",
        min_songs=5,
        check_energy_descending=True,
    ),
    TestCase(
        name="Happy pop request",
        request="I want happy pop songs, 5 please",
        expected_intent="simple",
        min_songs=4,
        expected_moods=["happy"],
        expected_genres=["pop"],
    ),
    TestCase(
        name="Mood journey: happy to sad",
        request="Take me from happy to melancholy with 6 songs",
        expected_intent="mood_journey",
        min_songs=4,
    ),
    TestCase(
        name="Genre mix: EDM and rock",
        request="Mix EDM and rock songs for a party, 6 songs",
        expected_intent="genre_mix",
        min_songs=4,
    ),
    TestCase(
        name="Workout request",
        request="High energy workout playlist with 5 songs",
        expected_intent="simple",
        min_songs=4,
    ),
    TestCase(
        name="Romantic evening",
        request="Romantic chill songs for a date night, 5 songs",
        expected_intent="simple",
        min_songs=4,
        expected_moods=["romantic"],
    ),
    TestCase(
        name="Vague request",
        request="play me something good",
        expected_intent="simple",
        min_songs=1,
    ),
    TestCase(
        name="Large playlist",
        request="Give me a big 10 song mix of everything happy",
        expected_intent="simple",
        min_songs=8,
    ),
]


def run_harness():
    """Run all test cases and print results."""
    songs = load_songs()
    agent = PlaylistAgent(songs)

    results = []
    passed = 0
    failed = 0

    print("=" * 70)
    print("  VIBEFINDER 2.0 — EVALUATION HARNESS")
    print("=" * 70)
    print(f"  Running {len(TEST_CASES)} test cases...\n")

    for tc in TEST_CASES:
        trace = agent.run(tc.request)
        checks_passed = 0
        checks_total = 0
        issues = []

        # Check 1: Intent detection
        checks_total += 1
        if trace.plan.detected_intent == tc.expected_intent:
            checks_passed += 1
        else:
            issues.append(f"Intent: expected '{tc.expected_intent}', "
                          f"got '{trace.plan.detected_intent}'")

        # Check 2: Minimum song count
        checks_total += 1
        if len(trace.final_playlist) >= tc.min_songs:
            checks_passed += 1
        else:
            issues.append(f"Songs: expected >= {tc.min_songs}, "
                          f"got {len(trace.final_playlist)}")

        # Check 3: Energy ordering
        if tc.check_energy_ascending and len(trace.final_playlist) >= 2:
            checks_total += 1
            energies = [s.energy for s in trace.final_playlist]
            if energies[-1] >= energies[0]:
                checks_passed += 1
            else:
                issues.append(f"Energy not ascending: {[f'{e:.2f}' for e in energies]}")

        if tc.check_energy_descending and len(trace.final_playlist) >= 2:
            checks_total += 1
            energies = [s.energy for s in trace.final_playlist]
            if energies[0] >= energies[-1]:
                checks_passed += 1
            else:
                issues.append(f"Energy not descending: {[f'{e:.2f}' for e in energies]}")

        # Check 4: Mood alignment
        if tc.expected_moods:
            checks_total += 1
            playlist_moods = {s.mood for s in trace.final_playlist}
            if any(m in playlist_moods for m in tc.expected_moods):
                checks_passed += 1
            else:
                issues.append(f"No mood match: expected {tc.expected_moods}, "
                              f"got {playlist_moods}")

        # Check 5: Genre alignment
        if tc.expected_genres:
            checks_total += 1
            playlist_genres = {s.genre for s in trace.final_playlist}
            if any(g in playlist_genres for g in tc.expected_genres):
                checks_passed += 1
            else:
                issues.append(f"No genre match: expected {tc.expected_genres}, "
                              f"got {playlist_genres}")

        # Check 6: No duplicates (always)
        checks_total += 1
        titles = [s.title for s in trace.final_playlist]
        if len(titles) == len(set(titles)):
            checks_passed += 1
        else:
            issues.append("Duplicate songs in playlist")

        # Check 7: Agent evaluation passed
        checks_total += 1
        if trace.evaluation and trace.evaluation.passed:
            checks_passed += 1
        else:
            issues.append(f"Agent self-eval failed "
                          f"(score={trace.evaluation.score:.2f})")

        # Compute result
        confidence = checks_passed / checks_total if checks_total > 0 else 0
        test_passed = confidence >= 0.7  # Allow some slack
        if test_passed:
            passed += 1
        else:
            failed += 1

        status = "✓ PASS" if test_passed else "✗ FAIL"
        print(f"  {status}  {tc.name}")
        print(f"         Confidence: {confidence:.0%} ({checks_passed}/{checks_total} checks)")
        print(f"         Playlist: {len(trace.final_playlist)} songs, "
              f"revisions={trace.revision_count}")
        if issues:
            for issue in issues:
                print(f"         ⚠ {issue}")
        print()

        results.append({
            "name": tc.name,
            "passed": test_passed,
            "confidence": round(confidence, 2),
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "playlist_size": len(trace.final_playlist),
            "revisions": trace.revision_count,
            "issues": issues,
        })

    # Summary
    print("─" * 70)
    total = len(TEST_CASES)
    print(f"  SUMMARY: {passed}/{total} passed, {failed}/{total} failed")
    avg_confidence = sum(r["confidence"] for r in results) / len(results)
    print(f"  Average confidence: {avg_confidence:.0%}")
    avg_revisions = sum(r["revisions"] for r in results) / len(results)
    print(f"  Average revisions: {avg_revisions:.1f}")
    print("─" * 70)

    return results


if __name__ == "__main__":
    run_harness()