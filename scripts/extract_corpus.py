"""
Extract Thermodynamics of Commercial Identity PDFs into per-chapter text
plus a master-equation reference card and an index.json for retrieval.

Run locally before committing. Requires `pdftotext` (poppler-utils).

Output (committed to the repo, baked into the Docker image):
    app/corpus_text/master_equation.txt   <- Appendix A, always loaded
    app/corpus_text/chapters/NN_slug.txt
    app/corpus_text/index.json            <- [{id,title,tags,file}]
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_COMPLETE = ROOT / "corpus" / "Thermodynamics_of_Commercial_Identity_COMPLETE.pdf"
PDF_BACK     = ROOT / "corpus" / "Thermodynamics_of_Commercial_Identity_BackMatter.pdf"
OUT_DIR      = ROOT / "app" / "corpus_text"
CHAPTERS_DIR = OUT_DIR / "chapters"


def pdf_to_text(pdf: Path) -> str:
    return subprocess.check_output(
        ["pdftotext", "-layout", str(pdf), "-"], text=True
    )


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:48]


# Chapter title + retrieval tags. Hand-curated against the TOC the book ships
# with, so retrieval can match user queries to the right section without
# bringing in a vector store.
CHAPTERS = [
    ( 1, "The Naming Problem Is Not What You Think",
       ["naming problem", "creative fallacy", "ghost state", "stable atom",
        "resolution environment", "deterministic naming"]),
    ( 2, "Tokens, Vectors, and the Machine's Eye",
       ["token", "vector", "embedding", "dependency graph",
        "naics", "o*net", "registry", "search field"]),
    ( 3, "The Four Components of a Resolved Name",
       ["category noun", "object", "function", "context",
        "Nc", "Os", "Fa", "Cl", "v* template"]),
    ( 4, "The Minimal Resolution Template V*",
       ["v*", "minimal resolution template", "stable atom",
        "algorithmic autonomy", "fully resolved"]),
    ( 5, "Alignment alpha: Trough Depth and Work-Offset",
       ["alpha", "alignment", "trough depth", "Dt",
        "work offset", "W_delta", "persistence Ps"]),
    ( 6, "Drift sigma: Misdirection and the Unintended Basin",
       ["sigma", "drift", "unintended basin", "misclassification"]),
    ( 7, "The Inference Tax tau_i",
       ["inference tax", "tau", "ambiguity cost", "monthly cost"]),
    ( 8, "Sector Friction Phi and the Atmospheric Resultant",
       ["phi", "sector friction", "atmospheric resultant", "Rsn",
        "incumbent density", "GMB", "google business profile"]),
    ( 9, "Differentiation Force Delta = U M T",
       ["delta", "differentiation", "uniqueness", "memorability",
        "transmissibility", "narrative lift"]),
    (10, "The Compensation Theorem",
       ["compensation theorem", "lambda delta", "survival threshold",
        "ambiguity penalty", "decorative differentiation"]),
    (11, "Worked Example: DuckDuckGo",
       ["duckduckgo", "case study", "worked example",
        "acquired alignment", "rho_m"]),
    (12, "Resolution Pressure Rp",
       ["resolution pressure", "Rp", "necessity", "urgency",
        "consequence of delay", "activation threshold", "eta",
        "search intent emergence", "Is"]),
    (13, "Pressure-Adjusted Trajectories",
       ["pressure adjusted", "alpha_p", "sigma_p", "chi(Rp)",
        "narrative lift under pressure"]),
    (14, "The Master Equation",
       ["master equation", "Sx", "trajectory", "execution effort", "E",
        "decay rate", "Rd", "crest height", "time to resolution"]),
    (15, "Dimensional Tear and Metaphor",
       ["dimensional tear", "metaphorical name", "two face recovery",
        "abstract token"]),
    (16, "Ghost States in Practice",
       ["ghost state", "phonetic trap", "escape sequence",
        "high recall zero classification"]),
    (17, "The Ten Failure Modes",
       ["failure mode", "FM1", "FM2", "FM3", "FM4", "FM5",
        "FM6", "FM7", "FM8", "FM9", "FM10",
        "missing category", "missing function", "missing object",
        "missing context", "ambiguity overload", "acquired debt"]),
    (18, "The Scoring Engine and Viability Bands",
       ["scoring", "viability bands", "rubric", "alpha rubric",
        "sigma rubric", "phi rubric", "delta rubric"]),
    (19, "Registry Alignment Tables (NAICS, GMB, O*NET)",
       ["naics", "gmb", "google business profile", "o*net",
        "task verb", "category code"]),
    (22, "Naming Workflows",
       ["compensation decision", "acquired alignment program",
        "new category", "multi-entity portfolio", "workflow"]),
    (23, "Open Problems",
       ["dynamic phi", "multi-language", "voice search",
        "ai generated names", "open problems"]),
]


def split_chapters(full_text: str) -> dict[int, str]:
    """Find chapter boundaries. pdftotext emits page-break form feeds (\\f)
    before each chapter header — we anchor on those."""
    # Normalise form feeds to newlines so multiline anchors work uniformly.
    norm = full_text.replace("\f", "\n")
    starts: list[tuple[int, int]] = []
    for m in re.finditer(r"^[ \t]*CHAPTER (\d+)[ \t]*$", norm, flags=re.M):
        starts.append((int(m.group(1)), m.start()))
    out: dict[int, str] = {}
    for i, (n, pos) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(norm)
        out[n] = norm[pos:end].strip()
    return out


def extract_master_equation_card(back_text: str) -> str:
    """Appendix A: Master Equation Reference Card.
    Bounded by 'APPENDIX A' header through 'APPENDIX B'."""
    norm = back_text.replace("\f", "\n")
    a = re.search(r"^[ \t]*APPENDIX A[ \t]*$", norm, flags=re.M)
    b = re.search(r"^[ \t]*APPENDIX B[ \t]*$", norm, flags=re.M)
    if not a:
        return ""
    end = b.start() if b else len(norm)
    return norm[a.start():end].strip()


def main() -> None:
    if not PDF_COMPLETE.exists():
        sys.exit(f"missing {PDF_COMPLETE}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    full = pdf_to_text(PDF_COMPLETE)
    back = pdf_to_text(PDF_BACK) if PDF_BACK.exists() else ""

    # 1. Master equation card (always loaded into the system prompt)
    card = extract_master_equation_card(back) or extract_master_equation_card(full)
    (OUT_DIR / "master_equation.txt").write_text(card)

    # 2. Per-chapter files
    chapters = split_chapters(full)
    index = []
    for num, title, tags in CHAPTERS:
        body = chapters.get(num, "").strip()
        if not body:
            continue
        slug = slugify(title)
        fname = f"{num:02d}_{slug}.txt"
        (CHAPTERS_DIR / fname).write_text(body)
        index.append({
            "id": num,
            "title": title,
            "tags": tags,
            "file": f"chapters/{fname}",
            "chars": len(body),
        })

    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"wrote master_equation.txt ({len(card)} chars)")
    print(f"wrote {len(index)} chapter files to {CHAPTERS_DIR}")


if __name__ == "__main__":
    main()
