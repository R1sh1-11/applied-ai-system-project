# 🎧 Model Card — VibeFinder 2.0

## 1. Model Name

> **VibeFinder 2.0** — Agentic Music Recommender System

---

## 2. Intended Use

This system generates playlists from natural language requests using an agentic workflow. It is designed for classroom exploration and portfolio demonstration — not for real music streaming users. The system demonstrates how AI agents can plan, execute, evaluate, and revise their outputs through structured reasoning.

---

## 3. How It Works (Short Explanation)

When a user types a request like "make me a workout playlist that starts chill and builds up," the system:

1. **Parses** the request to detect the user's intent — is this an energy arc (build-up/wind-down), a mood journey (happy → sad), a genre mix (EDM + rock), or a simple mood/genre filter?
2. **Plans** a series of retrieval steps based on the intent. For a build-up, it plans three steps: retrieve low-energy songs, medium-energy songs, and high-energy songs.
3. **Retrieves** songs from the catalog using tag-based filtering (genre, mood, energy range) and scores them with a weighted formula.
4. **Sequences** the songs according to the intent — ascending energy for build-ups, interleaved genres for mixes, etc.
5. **Evaluates** the playlist against five quality checks: correct length, genre diversity, energy flow, no duplicates, and mood alignment.
6. **Revises** if the evaluation fails — it might swap songs, re-sort, or fill gaps — up to 2 times.

No external AI API is used. The reasoning is rule-based, making every decision transparent and testable.

---

## 4. Data

The song catalog contains **30 songs** stored in `data/songs.csv`. Each song has 8 features: genre, mood, energy (0.0–1.0), tempo (BPM), valence (0.0–1.0), danceability (0.0–1.0), and acousticness (0.0–1.0).

The catalog spans **14 genres** (pop, rock, lofi, edm, jazz, folk, hip-hop, classical, ambient, synthwave, indie pop, indie rock, r&b, world) and **6 moods** (happy, chill, melancholy, intense, aggressive, romantic).

The data was hand-curated, so it reflects a particular taste — genres like pop and rock have more representation (4–5 songs) while classical and hip-hop have only 1–2 songs each. This creates an inherent bias toward well-represented genres.

---

## 5. Strengths

- **Transparency**: Every decision is logged in a reasoning trace. Users can see exactly why each song was chosen and how the playlist was sequenced.
- **Self-correction**: The evaluation + revision loop catches issues like missing songs, genre domination, and incorrect energy ordering.
- **Flexible intent handling**: The system understands 4 distinct intent types from natural language, covering most common playlist requests.
- **No dependencies**: Runs entirely locally with no API keys, network access, or paid services.
- **Testable**: 25 unit tests and a 10-scenario evaluation harness verify the system's behavior systematically.

---

## 6. Limitations and Bias

- **Small catalog bias**: With only 30 songs, some genres (classical, hip-hop) have very few options. A user who requests "10 classical songs" will only get 1, with the rest filled by tangentially related songs.
- **Genre weight dominance**: The +2.0 genre weight means genre match overwhelms other factors. A perfect mood + energy match in the "wrong" genre scores lower than a mediocre match in the right genre.
- **Keyword-only NLP**: The parser relies on predefined keyword lists. It can't understand negation ("not rock"), comparatives ("more upbeat than jazz"), or entirely novel descriptions.
- **Western-centric catalog**: The song selection skews toward English-language, Western genres. "World" music is represented by a single song, which is a gross oversimplification.
- **No personalization over time**: The system has no memory of past interactions. Each request starts from scratch with no learning from user feedback.
- **If used in a real product**, the static keyword matching could frustrate users whose requests don't align with the predefined vocabulary, creating a gap between what users expect and what the system can deliver.

---

## 7. Evaluation

### Unit Tests
25 tests cover:
- Score computation (genre match scores higher, mood adds points, energy similarity, acoustic bonus)
- Recommender behavior (correct count, sorted order, reason generation)
- Tag search (filter by genre, mood, energy range, combined filters, empty results)
- Agent behavior (intent detection for all 4 types, no duplicates, evaluation runs, energy ordering, vague request handling)
- Catalog statistics

**Result: 25/25 passed**

### Evaluation Harness
10 automated scenarios test diverse request types:

| Test Case | Confidence | Notes |
|-----------|-----------|-------|
| Simple chill request | 100% | Perfect match |
| Energy build-up | 100% | Correct ascending energy |
| Energy wind-down | 100% | Correct descending energy |
| Happy pop request | 100% | Genre + mood alignment |
| Mood journey | 100% | Multi-mood detection |
| Genre mix | 100% | EDM + rock interleaving |
| Workout request | 100% | Intense intent detected |
| Romantic evening | 80% | Classified as mood_journey instead of simple |
| Vague request | 100% | Graceful fallback |
| Large playlist | 75% | Got 7/10 songs (catalog limit) |

**Result: 10/10 passed, 96% average confidence, 0 revisions needed**

---

## 8. Future Work

- **Add collaborative filtering**: Track which songs tend to be enjoyed together and use that as a signal.
- **Expand the catalog**: Use a real music API (Spotify, Last.fm) to access thousands of songs with real audio features.
- **Learn from feedback**: Let users thumbs-up/down songs and adjust weights over time.
- **Add diversity constraints**: Ensure the agent doesn't always recommend the same songs for similar requests (inject controlled randomness).
- **Support negation**: Parse "not rock" or "no sad songs" in the request.
- **Multi-user playlists**: Generate group playlists that balance multiple people's preferences.

---

## 9. Personal Reflection

Building the agentic workflow was the most educational part of this project. In Module 3, the recommender was a single function — score and sort. Adding the planning and evaluation layers forced me to think about *what makes a good playlist* beyond just individual song scores. The sequencing matters (energy flow), the diversity matters (not all one genre), and the alignment with the original request matters. These are the kinds of quality criteria that real AI products need to define and enforce.

I was surprised that the rule-based approach worked as well as it did. The keyword parser correctly handles most natural phrasings, and the self-evaluation caught issues I would have missed manually. This taught me that "AI" doesn't always mean "neural network" — structured reasoning with clear rules can be powerful and, importantly, fully explainable.

The biggest lesson: the hardest part of building AI isn't the algorithm — it's defining what "good" means and building systems to measure it.
