"""
ITT Commercial Identity Scoring Engine
Thermodynamics of Commercial Identity - Armstrong Knight
Pure deterministic math. No AI required for scoring.
"""
from dataclasses import dataclass
from typing import Optional

# Viability bands from the framework
VIABILITY_BANDS = [
    (0.85, 1.0,  "Stable Atom",   "Algorithmic Autonomy achieved. System maintains, classifies, and surfaces without ongoing intervention."),
    (0.65, 0.85, "Transitional",  "Moderate ongoing effort required. Name is functional but leaving alignment value on the table."),
    (0.45, 0.65, "High Effort",   "Significant structural overhead. Marketing spend compensates for naming deficit every month."),
    (0.0,  0.45, "Ghost Risk",    "Rename strongly indicated. Name is working against the business in every resolution field."),
]

# Sector friction table from Appendix C
SECTOR_FRICTION = {
    "personal injury law": (0.93, 0.97),
    "seo": (0.91, 0.95),
    "financial planning": (0.87, 0.92),
    "digital marketing": (0.83, 0.89),
    "business consulting": (0.82, 0.88),
    "real estate": (0.82, 0.90),
    "it services": (0.80, 0.87),
    "health coaching": (0.78, 0.85),
    "tax preparation national": (0.76, 0.84),
    "staffing recruiting": (0.74, 0.82),
    "management training": (0.72, 0.80),
    "residential roofing": (0.68, 0.76),
    "plumbing": (0.65, 0.73),
    "hvac": (0.63, 0.71),
    "electrical": (0.62, 0.70),
    "landscaping": (0.60, 0.68),
    "commercial cleaning": (0.58, 0.66),
    "auto body": (0.57, 0.65),
    "catering": (0.55, 0.63),
    "tax preparation local": (0.54, 0.62),
    "pet grooming": (0.52, 0.62),
    "specialty food retail": (0.48, 0.58),
    "personal training": (0.45, 0.55),
    "commercial roofing": (0.44, 0.54),
    "specialty b2b": (0.40, 0.55),
    "divorce financial planning": (0.38, 0.50),
    "emerging professional": (0.30, 0.50),
    "new digital category": (0.20, 0.40),
    "pioneer category": (0.10, 0.25),
    "default": (0.65, 0.75),
}


@dataclass
class ScoringInputs:
    name: str
    sector: str
    alpha: float      # alignment [0,1]
    sigma: float      # drift [0,1]
    phi: float        # sector friction [0,1]
    delta: float      # differentiation [0,1]
    lam: float        # conversion constant lambda [0,1]
    mu: float = 0.25  # ambiguity burden (fixed per framework)


@dataclass
class ScoringOutputs:
    V: float          # viability score
    Dt: float         # trough depth
    W_delta: float    # work-offset ratio
    Rsn: float        # atmospheric resultant
    band: str         # viability band label
    band_desc: str    # band description
    inference_tax: float  # monthly inference tax proxy
    is_net_negative: bool


def score(inputs: ScoringInputs) -> ScoringOutputs:
    """
    Core ITT scoring. All equations from the Master Equation Reference Card.
    V = α + λΔ − μ(1−α)σ
    Dt = Φ(1−α)
    W_Δ = 1/α²
    Rsn = (α−σ) / [Φ(1+σ)]
    """
    a = inputs.alpha
    s = inputs.sigma
    p = inputs.phi
    d = inputs.delta
    l = inputs.lam
    m = inputs.mu

    # Guard against division by zero
    a_safe = max(a, 0.001)

    V    = a + l * d - m * (1 - a) * s
    Dt   = p * (1 - a)
    W_d  = 1 / (a_safe ** 2)
    Rsn  = (a - s) / (p * (1 + s)) if p > 0 else 0.0
    tax  = (1 / (a_safe ** 2)) - 1  # monthly inference tax proxy

    # Clamp V to reasonable range
    V = max(0.0, min(1.0, V))

    band, band_desc = "Ghost Risk", VIABILITY_BANDS[3][3]
    for low, high, label, desc in VIABILITY_BANDS:
        if low <= V <= high:
            band, band_desc = label, desc
            break

    return ScoringOutputs(
        V=round(V, 4),
        Dt=round(Dt, 4),
        W_delta=round(W_d, 3),
        Rsn=round(Rsn, 4),
        band=band,
        band_desc=band_desc,
        inference_tax=round(tax, 3),
        is_net_negative=(Rsn < 0),
    )


def get_phi_for_sector(sector_input: str) -> float:
    """Look up sector friction midpoint."""
    s = sector_input.lower().strip()
    for key, (low, high) in SECTOR_FRICTION.items():
        if key in s or s in key:
            return round((low + high) / 2, 3)
    return round(sum(SECTOR_FRICTION["default"]) / 2, 3)


def format_score_report(inputs: ScoringInputs, outputs: ScoringOutputs) -> str:
    """Generate a structured text report for injection into the AI context."""
    lines = [
        f"=== ITT SCORING REPORT: '{inputs.name}' ===",
        f"Sector: {inputs.sector} | Φ = {inputs.phi}",
        "",
        f"INPUTS:",
        f"  α  (alignment)        = {inputs.alpha}",
        f"  σ  (drift)            = {inputs.sigma}",
        f"  Φ  (sector friction)  = {inputs.phi}",
        f"  Δ  (differentiation)  = {inputs.delta}",
        f"  λ  (conversion)       = {inputs.lam}",
        "",
        f"OUTPUTS:",
        f"  V   (viability score)      = {outputs.V}",
        f"  Dt  (trough depth)         = {outputs.Dt}",
        f"  W_Δ (work-offset ratio)    = {outputs.W_delta}x",
        f"  Rsn (atmospheric resultant)= {outputs.Rsn}",
        f"  Monthly inference tax proxy= {outputs.inference_tax}x",
        "",
        f"VERDICT: {outputs.band}",
        f"  {outputs.band_desc}",
    ]
    if outputs.is_net_negative:
        lines.append("")
        lines.append("⚠ NET-NEGATIVE: Rsn < 0 — renaming is indicated regardless of V score.")
    return "\n".join(lines)
