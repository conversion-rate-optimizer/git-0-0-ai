"""
ITT Business Name Generator - FastAPI Service
Groq backend + ITT scoring engine
Deploy: Docker → Render
"""
import os
import json
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field

from app.scoring import (
    ScoringInputs, score, get_phi_for_sector,
    format_score_report
)
from app.prompts import ITT_SYSTEM_PROMPT

STATIC_DIR = Path(__file__).parent / "static"

# ── Groq client (lazy init so missing key gives clear error) ──────────────────
_groq_client = None

def get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(500, "GROQ_API_KEY environment variable not set")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ITT Business Name Resolver",
    description="Thermodynamics of Commercial Identity — Field-theoretic business name scoring",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    business_name: str = ""
    sector: str = ""
    # Optional: let user pass explicit scores; if absent, AI estimates
    alpha: float | None = Field(None, ge=0, le=1)
    sigma: float | None = Field(None, ge=0, le=1)
    delta: float | None = Field(None, ge=0, le=1)
    lam: float | None = Field(None, ge=0, le=1)

class ScoreRequest(BaseModel):
    name: str
    sector: str
    alpha: float = Field(..., ge=0, le=1)
    sigma: float = Field(..., ge=0, le=1)
    delta: float = Field(0.35, ge=0, le=1)
    lam: float = Field(0.55, ge=0, le=1)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "field nominal", "service": "ITT Business Name Resolver"}


@app.post("/score")
def score_endpoint(req: ScoreRequest):
    """Pure deterministic scoring — no AI, instant, free."""
    phi = get_phi_for_sector(req.sector)
    inputs = ScoringInputs(
        name=req.name,
        sector=req.sector,
        alpha=req.alpha,
        sigma=req.sigma,
        phi=phi,
        delta=req.delta,
        lam=req.lam,
    )
    outputs = score(inputs)
    return {
        "inputs": inputs.__dict__,
        "outputs": outputs.__dict__,
        "report": format_score_report(inputs, outputs),
    }


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming chat with ITT framework injected as system context.
    If business_name + sector provided, pre-computes the score
    and injects the full report into the system prompt.
    """
    groq = get_groq()

    # Build system prompt — inject pre-computed score if available
    system = ITT_SYSTEM_PROMPT

    if req.business_name and req.sector:
        phi = get_phi_for_sector(req.sector)
        # Use provided scores or sensible defaults for AI to refine
        inputs = ScoringInputs(
            name=req.business_name,
            sector=req.sector,
            alpha=req.alpha if req.alpha is not None else 0.5,
            sigma=req.sigma if req.sigma is not None else 0.25,
            phi=phi,
            delta=req.delta if req.delta is not None else 0.35,
            lam=req.lam if req.lam is not None else 0.55,
        )
        outputs = score(inputs)
        report = format_score_report(inputs, outputs)
        system += f"\n\n## PRE-COMPUTED SCORE (use these exact numbers)\n{report}"

    messages = [{"role": "system", "content": system}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]

    async def token_stream() -> AsyncGenerator[str, None]:
        try:
            stream = groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=1024,
                temperature=0.3,   # low temp = deterministic, math-accurate
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    # SSE format for easy consumption by any frontend
                    yield f"data: {json.dumps({'token': delta.content})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/chat")
async def chat(req: ChatRequest):
    """Non-streaming fallback."""
    groq = get_groq()

    system = ITT_SYSTEM_PROMPT
    if req.business_name and req.sector:
        phi = get_phi_for_sector(req.sector)
        inputs = ScoringInputs(
            name=req.business_name,
            sector=req.sector,
            alpha=req.alpha or 0.5,
            sigma=req.sigma or 0.25,
            phi=phi,
            delta=req.delta or 0.35,
            lam=req.lam or 0.55,
        )
        outputs = score(inputs)
        system += f"\n\n## PRE-COMPUTED SCORE\n{format_score_report(inputs, outputs)}"

    messages = [{"role": "system", "content": system}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]

    resp = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
        temperature=0.3,
    )
    return {"response": resp.choices[0].message.content}
