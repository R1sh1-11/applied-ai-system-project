"""
agent.py — Agentic Playlist Planner.

This is the core new feature for the final project. The agent follows a
structured Plan → Retrieve → Sequence → Evaluate → Revise loop to build
playlists from natural language requests.

No external LLM API is required. The agent uses rule-based NLP parsing
and a transparent reasoning engine so every decision is explainable.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.recommender import search_by_tags, score_song, get_catalog_stats
from src.models import UserProfile

logger = logging.getLogger(__name__)


# ── Data structures for the agent's reasoning trace ────────────────

@dataclass
class PlanStep:
    """One step in the agent's plan."""
    step_number: int
    action: str          # e.g., "retrieve_chill", "retrieve_intense"
    description: str     # human-readable explanation
    parameters: dict = field(default_factory=dict)


@dataclass
class AgentPlan:
    """The agent's full plan for building a playlist."""
    request_summary: str
    detected_intent: str         # "energy_arc", "mood_journey", "genre_mix", "simple"
    target_length: int
    steps: List[PlanStep] = field(default_factory=list)
    constraints: dict = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Result of the agent's self-evaluation."""
    passed: bool
    score: float                 # 0.0 to 1.0
    checks: dict                 # individual check results
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class AgentTrace:
    """Complete reasoning trace for transparency and debugging."""
    request: str
    plan: Optional[AgentPlan] = None
    retrieved_songs: list = field(default_factory=list)
    sequenced_playlist: list = field(default_factory=list)
    evaluation: Optional[EvaluationResult] = None
    revision_count: int = 0
    final_playlist: list = field(default_factory=list)
    log: List[str] = field(default_factory=list)

    def add_log(self, message):
        self.log.append(message)
        logger.info(f"[Agent] {message}")


# ── Keyword dictionaries for intent parsing ────────────────────────

MOOD_KEYWORDS = {
    "happy": ["happy", "upbeat", "cheerful", "fun", "joyful", "bright", "party"],
    "chill": ["chill", "relax", "calm", "peaceful", "mellow", "easy", "lounge"],
    "melancholy": ["sad", "melancholy", "emotional", "heartbreak", "lonely", "blue"],
    "intense": ["intense", "pump", "workout", "hype", "adrenaline", "power", "beast"],
    "aggressive": ["angry", "aggressive", "rage", "hard", "heavy", "thrash"],
    "romantic": ["romantic", "love", "date", "intimate", "tender", "sweet"],
}

GENRE_KEYWORDS = {
    "pop": ["pop"],
    "rock": ["rock"],
    "lofi": ["lofi", "lo-fi", "lo fi"],
    "edm": ["edm", "electronic", "dance music", "club"],
    "jazz": ["jazz"],
    "folk": ["folk", "acoustic"],
    "hip-hop": ["hip-hop", "hip hop", "rap"],
    "classical": ["classical", "orchestra"],
    "ambient": ["ambient"],
    "synthwave": ["synthwave", "synth"],
    "indie pop": ["indie pop"],
    "indie rock": ["indie rock", "indie"],
    "r&b": ["r&b", "rnb", "r and b", "soul"],
    "world": ["world"],
}

ENERGY_ARC_PATTERNS = {
    "build_up": ["start slow", "starts slow", "build up", "builds up",
                 "starts chill", "start chill", "ramp up", "ramps up",
                 "warm up", "gradually", "crescendo", "low to high"],
    "wind_down": ["wind down", "winds down", "cool down", "cools down",
                  "start intense", "starts intense", "calm down",
                  "slow down", "slows down", "high to low",
                  "end chill", "end calm", "ends chill", "ends calm"],
    "peak_valley": ["peak and valley", "roller coaster", "ups and downs",
                    "mix of high and low", "mix of fast and slow"],
}


# ── The Agent ──────────────────────────────────────────────────────

class PlaylistAgent:
    """
    An agentic playlist builder that plans, retrieves, sequences,
    evaluates, and revises playlists from natural language requests.
    """

    MAX_REVISIONS = 2
    DEFAULT_PLAYLIST_LENGTH = 6
    EVAL_PASS_THRESHOLD = 0.6

    def __init__(self, songs):
        self.songs = songs
        self.catalog_stats = get_catalog_stats(songs)

    def run(self, request: str) -> AgentTrace:
        """
        Main entry point. Takes a natural language request and returns
        a complete reasoning trace with the final playlist.
        """
        trace = AgentTrace(request=request)
        trace.add_log(f"Received request: '{request}'")

        # ── Step 1: PLAN ──
        trace.add_log("PHASE 1: Planning...")
        plan = self._plan(request, trace)
        trace.plan = plan
        trace.add_log(f"Plan created: intent='{plan.detected_intent}', "
                       f"{len(plan.steps)} steps, target={plan.target_length} songs")

        # ── Step 2: EXECUTE (retrieve + sequence) ──
        trace.add_log("PHASE 2: Executing plan...")
        playlist = self._execute(plan, trace)
        trace.sequenced_playlist = playlist

        # ── Step 3: EVALUATE ──
        trace.add_log("PHASE 3: Evaluating playlist...")
        evaluation = self._evaluate(playlist, plan, trace)
        trace.evaluation = evaluation
        trace.add_log(f"Evaluation: score={evaluation.score:.2f}, passed={evaluation.passed}")

        # ── Step 4: REVISE if needed ──
        while not evaluation.passed and trace.revision_count < self.MAX_REVISIONS:
            trace.revision_count += 1
            trace.add_log(f"PHASE 4: Revision #{trace.revision_count} — "
                           f"Issues: {evaluation.issues}")
            playlist = self._revise(playlist, evaluation, plan, trace)
            trace.sequenced_playlist = playlist
            evaluation = self._evaluate(playlist, plan, trace)
            trace.evaluation = evaluation
            trace.add_log(f"Re-evaluation: score={evaluation.score:.2f}, passed={evaluation.passed}")

        trace.final_playlist = playlist
        trace.add_log(f"Done! Final playlist has {len(playlist)} songs "
                       f"(score={evaluation.score:.2f}, revisions={trace.revision_count})")
        return trace

    # ── Planning ───────────────────────────────────────────────────

    def _plan(self, request: str, trace: AgentTrace) -> AgentPlan:
        """Parse the request and create an execution plan."""
        lower = request.lower()

        # Detect playlist length
        length = self.DEFAULT_PLAYLIST_LENGTH
        length_match = re.search(r'(\d+)\s*songs?', lower)
        if length_match:
            length = min(int(length_match.group(1)), len(self.songs))

        # Detect moods
        detected_moods = []
        for mood, keywords in MOOD_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                detected_moods.append(mood)

        # Detect genres
        detected_genres = []
        for genre, keywords in GENRE_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                detected_genres.append(genre)

        # Detect energy arc
        detected_arc = None
        for arc, patterns in ENERGY_ARC_PATTERNS.items():
            if any(p in lower for p in patterns):
                detected_arc = arc
                break

        # Determine intent
        if detected_arc:
            intent = "energy_arc"
        elif len(detected_moods) > 1:
            intent = "mood_journey"
        elif len(detected_genres) > 1:
            intent = "genre_mix"
        else:
            intent = "simple"

        trace.add_log(f"Parsed: moods={detected_moods}, genres={detected_genres}, "
                       f"arc={detected_arc}, intent={intent}")

        # Build plan steps
        steps = []
        constraints = {
            "moods": detected_moods,
            "genres": detected_genres,
            "arc": detected_arc,
        }

        if intent == "energy_arc":
            steps = self._plan_energy_arc(detected_arc, detected_moods,
                                           detected_genres, length)
        elif intent == "mood_journey":
            steps = self._plan_mood_journey(detected_moods, detected_genres, length)
        elif intent == "genre_mix":
            steps = self._plan_genre_mix(detected_genres, detected_moods, length)
        else:
            steps = self._plan_simple(detected_moods, detected_genres, length)

        return AgentPlan(
            request_summary=request,
            detected_intent=intent,
            target_length=length,
            steps=steps,
            constraints=constraints,
        )

    def _plan_energy_arc(self, arc, moods, genres, length):
        """Plan steps for an energy-arc playlist (build up / wind down)."""
        steps = []
        genre_filter = genres[0] if genres else None

        if arc == "build_up":
            # Low energy → medium → high
            thirds = max(length // 3, 1)
            steps.append(PlanStep(1, "retrieve_low_energy",
                         "Find calm, low-energy songs to start",
                         {"max_energy": 0.35, "genre": genre_filter, "count": thirds}))
            steps.append(PlanStep(2, "retrieve_mid_energy",
                         "Find medium-energy songs for the middle",
                         {"min_energy": 0.35, "max_energy": 0.7, "genre": genre_filter,
                          "count": thirds}))
            steps.append(PlanStep(3, "retrieve_high_energy",
                         "Find high-energy songs for the climax",
                         {"min_energy": 0.7, "genre": genre_filter,
                          "count": length - 2 * thirds}))
        elif arc == "wind_down":
            thirds = max(length // 3, 1)
            steps.append(PlanStep(1, "retrieve_high_energy",
                         "Find high-energy songs to open strong",
                         {"min_energy": 0.7, "genre": genre_filter, "count": thirds}))
            steps.append(PlanStep(2, "retrieve_mid_energy",
                         "Find medium-energy songs to transition",
                         {"min_energy": 0.35, "max_energy": 0.7, "genre": genre_filter,
                          "count": thirds}))
            steps.append(PlanStep(3, "retrieve_low_energy",
                         "Find calm songs to close out",
                         {"max_energy": 0.35, "genre": genre_filter,
                          "count": length - 2 * thirds}))
        else:  # peak_valley
            half = max(length // 2, 1)
            steps.append(PlanStep(1, "retrieve_high_energy",
                         "Find high-energy peak songs",
                         {"min_energy": 0.7, "genre": genre_filter, "count": half}))
            steps.append(PlanStep(2, "retrieve_low_energy",
                         "Find low-energy valley songs",
                         {"max_energy": 0.4, "genre": genre_filter,
                          "count": length - half}))

        steps.append(PlanStep(len(steps) + 1, "sequence",
                     f"Order songs to follow {arc} energy arc", {}))
        return steps

    def _plan_mood_journey(self, moods, genres, length):
        """Plan steps for a multi-mood playlist."""
        steps = []
        per_mood = max(length // len(moods), 1)
        genre_filter = genres[0] if genres else None

        for i, mood in enumerate(moods):
            count = per_mood if i < len(moods) - 1 else length - per_mood * (len(moods) - 1)
            steps.append(PlanStep(i + 1, f"retrieve_{mood}",
                         f"Find {mood} songs",
                         {"mood": mood, "genre": genre_filter, "count": count}))

        steps.append(PlanStep(len(steps) + 1, "sequence",
                     "Order songs to create a mood journey", {}))
        return steps

    def _plan_genre_mix(self, genres, moods, length):
        """Plan steps for a multi-genre playlist."""
        steps = []
        per_genre = max(length // len(genres), 1)
        mood_filter = moods[0] if moods else None

        for i, genre in enumerate(genres):
            count = per_genre if i < len(genres) - 1 else length - per_genre * (len(genres) - 1)
            steps.append(PlanStep(i + 1, f"retrieve_{genre}",
                         f"Find {genre} songs",
                         {"genre": genre, "mood": mood_filter, "count": count}))

        steps.append(PlanStep(len(steps) + 1, "sequence",
                     "Interleave genres for variety", {}))
        return steps

    def _plan_simple(self, moods, genres, length):
        """Plan for a straightforward single-mood/genre request."""
        mood = moods[0] if moods else None
        genre = genres[0] if genres else None

        steps = [
            PlanStep(1, "retrieve",
                     f"Find top songs matching mood={mood}, genre={genre}",
                     {"mood": mood, "genre": genre, "count": length}),
            PlanStep(2, "sequence",
                     "Order songs by energy flow and diversity", {}),
        ]
        return steps

    # ── Execution ──────────────────────────────────────────────────

    def _execute(self, plan: AgentPlan, trace: AgentTrace) -> list:
        """Execute the plan steps to build a raw playlist."""
        collected = []
        used_titles = set()

        for step in plan.steps:
            if step.action == "sequence":
                continue  # handled after retrieval

            params = step.parameters
            trace.add_log(f"  Executing step {step.step_number}: {step.description}")

            # Run tag-based search
            candidates = search_by_tags(
                self.songs,
                genre=params.get("genre"),
                mood=params.get("mood"),
                min_energy=params.get("min_energy"),
                max_energy=params.get("max_energy"),
                min_danceability=params.get("min_danceability"),
            )

            # Remove duplicates already selected
            candidates = [s for s in candidates if s.title not in used_titles]
            target_count = params.get("count", plan.target_length)

            # If too few results, relax the genre filter and retry
            if len(candidates) < target_count:
                trace.add_log(f"    Only {len(candidates)} candidates — relaxing genre filter")
                relaxed = search_by_tags(
                    self.songs,
                    mood=params.get("mood"),
                    min_energy=params.get("min_energy"),
                    max_energy=params.get("max_energy"),
                )
                relaxed = [s for s in relaxed if s.title not in used_titles]
                # Merge: originals first, then relaxed
                seen = {s.title for s in candidates}
                for s in relaxed:
                    if s.title not in seen:
                        candidates.append(s)
                        seen.add(s.title)

            # Score candidates against a synthetic profile for this step
            mood_target = params.get("mood", plan.constraints.get("moods", [None])[0] if plan.constraints.get("moods") else None) or "chill"
            genre_target = params.get("genre", plan.constraints.get("genres", [None])[0] if plan.constraints.get("genres") else None) or "pop"
            energy_target = 0.5
            if params.get("min_energy") is not None and params.get("max_energy") is not None:
                energy_target = (params["min_energy"] + params["max_energy"]) / 2
            elif params.get("min_energy") is not None:
                energy_target = min(params["min_energy"] + 0.15, 1.0)
            elif params.get("max_energy") is not None:
                energy_target = max(params["max_energy"] - 0.15, 0.0)

            synth_profile = UserProfile(
                name="agent_step",
                genre=genre_target,
                mood=mood_target,
                energy=energy_target,
            )

            scored = []
            for song in candidates:
                total, breakdown = score_song(song, synth_profile)
                scored.append((song, total))

            scored.sort(key=lambda x: x[1], reverse=True)
            selected = [s for s, _ in scored[:target_count]]

            for s in selected:
                used_titles.add(s.title)
            collected.extend(selected)

            trace.add_log(f"    Selected {len(selected)} songs: "
                           f"{[s.title for s in selected]}")

        trace.retrieved_songs = collected

        # ── Sequencing ──
        playlist = self._sequence(collected, plan, trace)
        return playlist

    def _sequence(self, songs, plan: AgentPlan, trace: AgentTrace) -> list:
        """Order songs based on the detected intent."""
        if not songs:
            return songs

        arc = plan.constraints.get("arc")
        intent = plan.detected_intent

        if intent == "energy_arc" and arc == "build_up":
            songs.sort(key=lambda s: s.energy)
            trace.add_log("  Sequenced: ascending energy (build-up)")
        elif intent == "energy_arc" and arc == "wind_down":
            songs.sort(key=lambda s: s.energy, reverse=True)
            trace.add_log("  Sequenced: descending energy (wind-down)")
        elif intent == "energy_arc" and arc == "peak_valley":
            # Interleave high and low
            highs = sorted([s for s in songs if s.energy >= 0.6],
                           key=lambda s: s.energy, reverse=True)
            lows = sorted([s for s in songs if s.energy < 0.6],
                          key=lambda s: s.energy)
            interleaved = []
            for h, l in zip(highs, lows):
                interleaved.extend([h, l])
            # Add any remainder
            used = {s.title for s in interleaved}
            for s in songs:
                if s.title not in used:
                    interleaved.append(s)
            songs = interleaved
            trace.add_log("  Sequenced: interleaved peaks and valleys")
        elif intent == "mood_journey":
            # Already in mood order from retrieval
            trace.add_log("  Sequenced: mood journey order preserved from retrieval")
        elif intent == "genre_mix":
            # Interleave genres so same genre isn't consecutive
            from itertools import groupby
            genre_groups = {}
            for s in songs:
                genre_groups.setdefault(s.genre, []).append(s)
            interleaved = []
            while any(genre_groups.values()):
                for g in list(genre_groups.keys()):
                    if genre_groups[g]:
                        interleaved.append(genre_groups[g].pop(0))
                    if not genre_groups[g]:
                        del genre_groups[g]
            songs = interleaved
            trace.add_log("  Sequenced: interleaved genres for variety")
        else:
            # Default: sort by energy for smooth flow
            songs.sort(key=lambda s: s.energy)
            trace.add_log("  Sequenced: default energy-ascending order")

        return songs

    # ── Evaluation ─────────────────────────────────────────────────

    def _evaluate(self, playlist, plan: AgentPlan, trace: AgentTrace) -> EvaluationResult:
        """Self-evaluate the playlist against quality criteria."""
        checks = {}
        issues = []
        suggestions = []

        # Check 1: Playlist length
        target = plan.target_length
        actual = len(playlist)
        length_ok = actual >= max(target - 1, 1)
        checks["length"] = {
            "passed": length_ok,
            "detail": f"Target={target}, Actual={actual}"
        }
        if not length_ok:
            issues.append(f"Too few songs ({actual}/{target})")
            suggestions.append("Relax filters or expand catalog")

        # Check 2: Genre diversity (no single genre > 70% unless requested)
        if actual > 0:
            genre_counts = {}
            for s in playlist:
                genre_counts[s.genre] = genre_counts.get(s.genre, 0) + 1
            max_genre_pct = max(genre_counts.values()) / actual
            # If user asked for a specific genre, high concentration is fine
            requested_genres = plan.constraints.get("genres", [])
            if len(requested_genres) == 1:
                diversity_ok = True  # Expected to be concentrated
            else:
                diversity_ok = max_genre_pct <= 0.7 or actual <= 3
            checks["genre_diversity"] = {
                "passed": diversity_ok,
                "detail": f"Genre distribution: {genre_counts}"
            }
            if not diversity_ok:
                issues.append(f"One genre dominates ({max_genre_pct:.0%})")
                suggestions.append("Add songs from underrepresented genres")

        # Check 3: Energy flow (for arc intents)
        if plan.detected_intent == "energy_arc" and actual >= 3:
            energies = [s.energy for s in playlist]
            arc = plan.constraints.get("arc")
            if arc == "build_up":
                flow_ok = energies[-1] > energies[0]
                checks["energy_flow"] = {
                    "passed": flow_ok,
                    "detail": f"First={energies[0]:.2f}, Last={energies[-1]:.2f}"
                }
                if not flow_ok:
                    issues.append("Energy doesn't build up")
                    suggestions.append("Re-sort by ascending energy")
            elif arc == "wind_down":
                flow_ok = energies[0] > energies[-1]
                checks["energy_flow"] = {
                    "passed": flow_ok,
                    "detail": f"First={energies[0]:.2f}, Last={energies[-1]:.2f}"
                }
                if not flow_ok:
                    issues.append("Energy doesn't wind down")
                    suggestions.append("Re-sort by descending energy")
            else:
                checks["energy_flow"] = {"passed": True, "detail": "N/A for this arc type"}
        else:
            checks["energy_flow"] = {"passed": True, "detail": "Not an energy-arc request"}

        # Check 4: No duplicate songs
        titles = [s.title for s in playlist]
        dupes_ok = len(titles) == len(set(titles))
        checks["no_duplicates"] = {
            "passed": dupes_ok,
            "detail": f"Unique={len(set(titles))}, Total={len(titles)}"
        }
        if not dupes_ok:
            issues.append("Duplicate songs found")
            suggestions.append("Remove duplicates")

        # Check 5: Mood alignment
        if plan.constraints.get("moods") and actual > 0:
            target_moods = set(plan.constraints["moods"])
            playlist_moods = set(s.mood for s in playlist)
            overlap = target_moods & playlist_moods
            mood_ok = len(overlap) > 0
            checks["mood_alignment"] = {
                "passed": mood_ok,
                "detail": f"Requested={target_moods}, Found={playlist_moods}"
            }
            if not mood_ok:
                issues.append("No songs match requested mood(s)")
                suggestions.append("Broaden mood search")
        else:
            checks["mood_alignment"] = {"passed": True, "detail": "No mood constraint"}

        # Compute overall score
        passed_count = sum(1 for c in checks.values() if c["passed"])
        total_checks = len(checks)
        score = passed_count / total_checks if total_checks > 0 else 0.0
        passed = score >= self.EVAL_PASS_THRESHOLD

        return EvaluationResult(
            passed=passed,
            score=round(score, 2),
            checks=checks,
            issues=issues,
            suggestions=suggestions,
        )

    # ── Revision ───────────────────────────────────────────────────

    def _revise(self, playlist, evaluation: EvaluationResult,
                plan: AgentPlan, trace: AgentTrace) -> list:
        """Attempt to fix issues found during evaluation."""
        revised = list(playlist)

        for issue in evaluation.issues:
            if "Too few songs" in issue:
                trace.add_log("    Revision: adding more songs with relaxed filters")
                needed = plan.target_length - len(revised)
                existing_titles = {s.title for s in revised}
                extras = [s for s in self.songs if s.title not in existing_titles]
                # Sort extras by general appeal (valence + danceability)
                extras.sort(key=lambda s: s.valence + s.danceability, reverse=True)
                revised.extend(extras[:needed])

            elif "dominates" in issue:
                trace.add_log("    Revision: swapping dominant-genre songs for variety")
                genre_counts = {}
                for s in revised:
                    genre_counts[s.genre] = genre_counts.get(s.genre, 0) + 1
                dominant_genre = max(genre_counts, key=genre_counts.get)
                existing_titles = {s.title for s in revised}
                alternatives = [s for s in self.songs
                                if s.genre != dominant_genre
                                and s.title not in existing_titles]
                if alternatives:
                    # Replace the last dominant-genre song
                    for i in range(len(revised) - 1, -1, -1):
                        if revised[i].genre == dominant_genre and alternatives:
                            trace.add_log(f"      Swapped '{revised[i].title}' → "
                                           f"'{alternatives[0].title}'")
                            revised[i] = alternatives.pop(0)
                            break

            elif "Duplicate" in issue:
                trace.add_log("    Revision: removing duplicates")
                seen = set()
                deduped = []
                for s in revised:
                    if s.title not in seen:
                        deduped.append(s)
                        seen.add(s.title)
                revised = deduped

            elif "doesn't build up" in issue:
                trace.add_log("    Revision: re-sorting for ascending energy")
                revised.sort(key=lambda s: s.energy)

            elif "doesn't wind down" in issue:
                trace.add_log("    Revision: re-sorting for descending energy")
                revised.sort(key=lambda s: s.energy, reverse=True)

        return revised


# ── Pretty-printing helpers ────────────────────────────────────────

def format_trace(trace: AgentTrace) -> str:
    """Format the agent's reasoning trace for display."""
    lines = []
    lines.append("=" * 65)
    lines.append("  PLAYLIST AGENT — REASONING TRACE")
    lines.append("=" * 65)
    lines.append(f"\n  Request: \"{trace.request}\"")

    if trace.plan:
        lines.append(f"\n{'─' * 65}")
        lines.append("  PHASE 1: PLAN")
        lines.append(f"{'─' * 65}")
        lines.append(f"  Intent detected : {trace.plan.detected_intent}")
        lines.append(f"  Target length   : {trace.plan.target_length} songs")
        lines.append(f"  Constraints     : {trace.plan.constraints}")
        for step in trace.plan.steps:
            lines.append(f"    Step {step.step_number}: {step.description}")
            if step.parameters:
                lines.append(f"              Params: {step.parameters}")

    lines.append(f"\n{'─' * 65}")
    lines.append("  PHASE 2: EXECUTE")
    lines.append(f"{'─' * 65}")
    lines.append(f"  Retrieved {len(trace.retrieved_songs)} songs total")

    if trace.evaluation:
        lines.append(f"\n{'─' * 65}")
        lines.append("  PHASE 3: EVALUATE")
        lines.append(f"{'─' * 65}")
        ev = trace.evaluation
        lines.append(f"  Overall score: {ev.score:.2f} ({'PASS' if ev.passed else 'FAIL'})")
        for name, check in ev.checks.items():
            status = "✓" if check["passed"] else "✗"
            lines.append(f"    {status} {name}: {check['detail']}")
        if ev.issues:
            lines.append(f"  Issues: {ev.issues}")

    if trace.revision_count > 0:
        lines.append(f"\n{'─' * 65}")
        lines.append(f"  PHASE 4: REVISED {trace.revision_count} time(s)")
        lines.append(f"{'─' * 65}")

    lines.append(f"\n{'─' * 65}")
    lines.append("  FINAL PLAYLIST")
    lines.append(f"{'─' * 65}")
    for i, song in enumerate(trace.final_playlist, 1):
        lines.append(f"  {i:2d}. {song.title:<25s} by {song.artist:<20s} "
                      f"[{song.genre}/{song.mood}] energy={song.energy:.2f}")

    lines.append(f"\n{'=' * 65}")
    return "\n".join(lines)