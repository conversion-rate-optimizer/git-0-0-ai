"""
Lightweight retrieval over the Thermodynamics of Commercial Identity corpus.

The book ships pre-extracted as plain text chapters under app/corpus_text/.
We load it once at import time and pick the most relevant 1-2 chapters for
each chat turn using a simple TF-style match against the user's message and
chapter tags. Plus the Appendix A master-equation card is always included so
the model never has to invent the formulas.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from dataclasses import dataclass

CORPUS_DIR = Path(__file__).parent / "corpus_text"


@dataclass(frozen=True)
class Chapter:
    id: int
    title: str
    tags: tuple[str, ...]
    text: str


def _load() -> tuple[str, tuple[Chapter, ...]]:
    card_path = CORPUS_DIR / "master_equation.txt"
    index_path = CORPUS_DIR / "index.json"
    card = card_path.read_text() if card_path.exists() else ""
    chapters: list[Chapter] = []
    if index_path.exists():
        for entry in json.loads(index_path.read_text()):
            text_path = CORPUS_DIR / entry["file"]
            if not text_path.exists():
                continue
            chapters.append(Chapter(
                id=entry["id"],
                title=entry["title"],
                tags=tuple(t.lower() for t in entry["tags"]),
                text=text_path.read_text(),
            ))
    return card, tuple(chapters)


MASTER_EQUATION_CARD, CHAPTERS = _load()


_TAG_BOOST_FOR_BAND = {
    # Pull the right diagnostic sections in based on the score band so the
    # model has the relevant playbook even when the user doesn't name it.
    "Stable Atom":   ["v*", "algorithmic autonomy", "stable atom", "naming workflow"],
    "Transitional":  ["scoring", "alpha rubric", "compensation theorem", "differentiation"],
    "High Effort":   ["compensation theorem", "inference tax", "work offset",
                      "differentiation", "narrative lift"],
    "Ghost Risk":    ["ghost state", "failure mode", "dimensional tear",
                      "escape sequence", "rename"],
}

_WORD_RE = re.compile(r"[A-Za-z*][A-Za-z*\-_]*")


def _tokens(s: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(s) if len(w) > 1}


def select_chapters(message: str, band: str | None, k: int = 2) -> list[Chapter]:
    """Score every chapter against the message + band-specific tag boosts.
    Returns up to k highest-scoring chapters."""
    if not CHAPTERS:
        return []

    msg_tokens = _tokens(message)
    band_boosts = {t.lower() for t in _TAG_BOOST_FOR_BAND.get(band or "", [])}

    scored: list[tuple[float, Chapter]] = []
    for ch in CHAPTERS:
        score = 0.0
        # Tag match against the user's message (strong signal, multi-word tags
        # count as a phrase hit).
        for tag in ch.tags:
            if tag in message.lower():
                score += 3.0
            else:
                # split tag into tokens; partial overlap with msg tokens
                tag_tokens = _tokens(tag)
                if tag_tokens and tag_tokens.issubset(msg_tokens):
                    score += 2.0
                elif tag_tokens & msg_tokens:
                    score += 0.5
        # Band-driven prior — pulls the playbook chapter for the user's band.
        for tag in ch.tags:
            if tag in band_boosts:
                score += 1.25
        # Title token overlap (mild).
        title_tokens = _tokens(ch.title)
        if title_tokens & msg_tokens:
            score += 0.5

        if score > 0:
            scored.append((score, ch))

    scored.sort(key=lambda x: (-x[0], x[1].id))
    return [c for _, c in scored[:k]]


CHAPTER_CHAR_BUDGET = 18_000  # cap per chapter to keep total context sane


def build_corpus_context(message: str, band: str | None, k: int = 1,
                         per_chapter_chars: int = 12_000) -> str:
    """Compose the corpus block for injection into the system prompt.
    Keeps total injected context around ~10k tokens so multi-turn
    conversations don't drift into context-limit territory."""
    parts: list[str] = []
    if MASTER_EQUATION_CARD:
        parts.append(
            "## CANONICAL FORMULAS (Appendix A — Master Equation Reference Card)\n"
            "Use these exact equations. Do not paraphrase the algebra.\n\n"
            + MASTER_EQUATION_CARD
        )
    for ch in select_chapters(message, band, k=k):
        body = ch.text
        if len(body) > per_chapter_chars:
            body = body[:per_chapter_chars] + "\n[…chapter truncated…]"
        parts.append(
            f"## CORPUS EXCERPT — Chapter {ch.id}: {ch.title}\n"
            f"(quoted verbatim from Thermodynamics of Commercial Identity)\n\n"
            f"{body}"
        )
    return "\n\n".join(parts)
