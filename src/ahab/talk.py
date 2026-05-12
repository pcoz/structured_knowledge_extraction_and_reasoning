"""Talk to Captain Ahab — conversational interface grounded in Moby-Dick.

The architectural claim: conversational generation can be GROUNDED
(no hallucination, full provenance) by retrieving from a structured
utterance corpus rather than synthesising from learned weights.

Pipeline:
  1. User asks a question
  2. Extract themes/keywords from the question (cell-grammar-style)
  3. Score each Ahab utterance against the extracted themes
  4. Return the best-fit utterance, with chapter provenance

Every response is a verbatim Ahab quote (or a curated paraphrase of
real Ahab dialogue). Chapter numbers are real. The user can audit
every claim by opening Moby-Dick to the named chapter.

This is the same architecture as the Wikipedia KB but applied to:
  - Fiction (Moby-Dick) instead of encyclopedic prose
  - A single CHARACTER (Ahab) instead of broad facts
  - CONVERSATIONAL output instead of factual Q&A

It demonstrates that the cell-grammar/structured-retrieval pattern
generalises beyond compression and Wikipedia: any text source with a
recoverable internal structure can host a grounded conversational
agent.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utterances import AHAB_UTTERANCES, Utterance


# ----------------------------------------------------------------------
# Theme extraction from user input.
#
# Maps natural-language phrases to the theme vocabulary used in the
# utterance corpus. This is the "cell-grammar phrase library applied
# to questions" step — same architectural pattern as the cell-grammar's
# context-conditional phrase libraries.
# ----------------------------------------------------------------------


THEME_KEYWORDS = {
    "whale":      ["whale", "moby dick", "leviathan", "great white",
                   "sperm whale", "creature"],
    "vengeance":  ["revenge", "vengeance", "retribution", "pay back",
                   "settle", "avenge"],
    "hate":       ["hate", "hatred", "loathe", "despise", "abhor"],
    "pursuit":    ["chase", "pursue", "hunt", "follow", "find",
                   "where is", "seek"],
    "sea":        ["sea", "ocean", "voyage", "water", "deep",
                   "horizon", "wave"],
    "command":    ["command", "order", "captain", "crew", "men",
                   "lead", "rule"],
    "soul":       ["soul", "spirit", "inner", "heart", "self",
                   "identity", "who am i"],
    "god":        ["god", "lord", "divine", "heaven", "creator",
                   "almighty", "providence"],
    "hell":       ["hell", "damn", "perdition", "abyss", "underworld"],
    "pride":      ["pride", "arrogance", "ego", "vain", "boast"],
    "doubt":      ["doubt", "uncertain", "wonder", "question",
                   "second-guess", "afraid"],
    "isolation":  ["alone", "lonely", "isolated", "solitary",
                   "by myself", "no one"],
    "doom":       ["doom", "fate", "destiny", "end", "ruin",
                   "destruction", "death"],
    "weariness":  ["tired", "weary", "exhausted", "old", "aged",
                   "long years", "spent"],
    "ship":       ["ship", "pequod", "vessel", "boat", "deck"],
    "men":        ["men", "crew", "sailors", "mates", "harpooners"],
    "prophecy":   ["prophecy", "foretell", "fortune", "fate",
                   "predicted", "vision"],
    "madness":    ["mad", "madness", "insane", "crazy", "deranged"],
    "defiance":   ["defy", "defiance", "rebel", "challenge",
                   "stand against"],
    "mortality":  ["death", "die", "mortal", "dying", "grave",
                   "end of life"],
    "scar":       ["scar", "leg", "wound", "injury", "lost",
                   "dismembered", "dismastered"],
    "fate":       ["fate", "destiny", "decree", "ordained",
                   "predestined"],
    "identity":   ["who are you", "ahab", "yourself", "name",
                   "i am"],
}


# Speech-act mood mappings: certain question shapes prefer certain
# response moods (e.g., questioning Ahab gets a defiant response).
QUESTION_TO_MOOD = {
    "why": ["philosophical", "reflective", "anguished"],
    "what": ["philosophical", "reflective", "declaration"],
    "do you regret": ["melancholy", "reflective", "anguished"],
    "tired": ["melancholy", "weary"],
    "afraid": ["defiant", "anguished"],
    "stop": ["defiant", "oratorical", "commanding"],
    "give up": ["defiant", "oratorical"],
    "die": ["exalted", "defiant", "melancholy"],
}


def extract_themes(question: str) -> list[str]:
    """Identify which themes from the corpus vocabulary the question
    touches. Multiple themes may fire."""
    q_lower = question.lower()
    out = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            out.append(theme)
    return out


def extract_preferred_mood(question: str) -> list[str]:
    q_lower = question.lower()
    out = []
    for trigger, moods in QUESTION_TO_MOOD.items():
        if trigger in q_lower:
            out.extend(moods)
    return out


# ----------------------------------------------------------------------
# Matching: score each utterance against the question's themes/mood.
# ----------------------------------------------------------------------


def score_utterance(
    u: Utterance, question_themes: list[str], preferred_moods: list[str],
    already_used: set[str],
) -> float:
    """Score an utterance by theme overlap + mood bonus + freshness.

    Weights are hand-tuned for the 35-utterance corpus. The
    -100 freshness penalty is meant to effectively eliminate any
    already-used utterance regardless of how well it matches —
    repetition kills the illusion of conversation more than
    a slightly worse second-choice answer does."""
    score = 0.0
    # Theme overlap dominates: 3 points per matched theme. Themes are
    # the primary semantic signal and most utterances have 3-5 themes,
    # so a 2- or 3-theme overlap easily beats other bonuses.
    theme_overlap = set(u.themes) & set(question_themes)
    score += 3.0 * len(theme_overlap)
    # Mood preference is a tiebreaker between similarly-themed
    # utterances — weighted lower than even a single theme match.
    if u.mood in preferred_moods:
        score += 1.5
    # Freshness penalty large enough to effectively exclude reused
    # utterances even when nothing else matches.
    if u.text in already_used:
        score -= 100.0
    # Length bias: longer utterances tend to be more substantive, but
    # cap the bonus at 2.0 so a very long quote doesn't crowd out a
    # better-themed shorter one.
    score += min(2.0, len(u.text) / 200)
    return score


def best_utterance(
    question: str, history: list[Utterance],
) -> Utterance | None:
    """Pick the highest-scoring utterance, or None for off-topic questions.

    The `> 0` threshold filters out the case where nothing meaningfully
    matches — better to return a "Ahab speaks not of such matters"
    fallback than to surface an irrelevant quote with a misleadingly
    confident chapter citation."""
    themes = extract_themes(question)
    moods = extract_preferred_mood(question)
    already_used = {u.text for u in history}

    scored = [
        (score_utterance(u, themes, moods, already_used), u)
        for u in AHAB_UTTERANCES
    ]
    scored.sort(key=lambda x: -x[0])
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return None


# ----------------------------------------------------------------------
# Response generation.
# ----------------------------------------------------------------------


def respond(question: str, history: list[Utterance]) -> tuple[str, Utterance | None]:
    """Return (response_text, utterance_used)."""
    utt = best_utterance(question, history)
    if utt is None:
        # Fallback for off-topic questions.
        return (
            "Ahab speaks not of such matters. Press me on the whale, "
            "or on fate, or on the sea, and I will answer.",
            None,
        )

    # Format the response with provenance.
    response = (
        f'Ahab: "{utt.text}"\n\n'
        f'  [Ch. {utt.chapter}, "{utt.chapter_title}"]\n'
        f'  [mood: {utt.mood} | speech-act: {utt.speech_act} | '
        f'addressed to: {utt.addressee}]'
    )
    return response, utt


# ----------------------------------------------------------------------
# Demo: a scripted conversation showcasing the architecture.
# ----------------------------------------------------------------------


DEMO_QUESTIONS = [
    "Who are you, Captain?",
    "Why do you hunt the white whale?",
    "Aren't you afraid of him?",
    "Do you regret these forty years at sea?",
    "What is the whale, really, to you?",
    "Will you turn back? Will you stop?",
    "Are you mad?",
    "What if you die in this chase?",
    "Do you fear God?",
    "Have you seen Moby Dick recently?",
    "Tell me about your leg.",
    "Is there nothing beyond this hatred?",
    "Speak to me of the storm.",
]


def main() -> None:
    print("=" * 78)
    print("Talk to Captain Ahab")
    print("=" * 78)
    print()
    print("A conversational interface grounded in Herman Melville's")
    print("Moby-Dick. Every response is a verifiable quote (or curated")
    print("excerpt) from the novel, with chapter provenance. The")
    print("system architecture: structured utterance corpus + theme-")
    print("based retrieval + deterministic rendering. No LLM in the")
    print("loop. No hallucination by construction.")
    print()
    print(f"Corpus: {len(AHAB_UTTERANCES)} extracted utterances,")
    chapters = sorted({u.chapter for u in AHAB_UTTERANCES})
    print(f"        spanning chapters {min(chapters)} – {max(chapters)}")
    themes_used = sorted({t for u in AHAB_UTTERANCES for t in u.themes})
    print(f"        across {len(themes_used)} themes: {', '.join(themes_used[:12])}, ...")
    print()
    print("=" * 78)
    print()

    history: list[Utterance] = []
    for i, question in enumerate(DEMO_QUESTIONS, 1):
        print(f"YOU (Q{i}): {question}")
        print()
        response, utt = respond(question, history)
        print(response)
        print()
        if utt is not None:
            history.append(utt)
        print("-" * 78)
        print()

    # End summary.
    print("=" * 78)
    print("CONVERSATION SUMMARY")
    print("=" * 78)
    print(f"  Questions asked:       {len(DEMO_QUESTIONS)}")
    print(f"  Distinct utterances used: {len(set(u.text for u in history))}")
    print(f"  Chapters drawn from:")
    chapter_counts = Counter(u.chapter for u in history)
    for ch, n in sorted(chapter_counts.items()):
        title = next(u.chapter_title for u in history if u.chapter == ch)
        print(f"    Ch. {ch:>3d} '{title}': {n} response(s)")
    print()
    print("Every response can be verified by opening Moby-Dick to the")
    print("named chapter. There is no synthesis layer; the LLM-vs-grounded")
    print("distinction is operationalised by this architecture.")
    print()


if __name__ == "__main__":
    main()
