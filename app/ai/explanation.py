"""Recommendation explanations (M4, T33).

Explains results produced by the engine (M3). This module never selects,
ranks or scores vehicles: it only fills the ``explanation`` text field.
When AI is disabled or fails, a deterministic TR/EN template is used.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from app.ai.prompts.recommendation import (
    SYSTEM_INSTRUCTION,
    build_recommendation_prompt,
)
from app.ai.provider import LLMError, LLMProvider, get_provider
from app.schemas.recommendation import RecommendationItem, RecommendationResult

logger = logging.getLogger(__name__)

Language = Literal["tr", "en"]
SUPPORTED_LANGUAGES = ("tr", "en")
DEFAULT_LANGUAGE: Language = "tr"

MAX_EXPLANATION_CHARS = 600

CRITERION_LABELS: dict[str, dict[str, str]] = {
    "tr": {
        "fuel_economy": "yakıt ekonomisi",
        "interior_space": "iç hacim",
        "performance": "performans",
        "budget_fit": "bütçeye uygunluk",
        "safety": "güvenlik",
    },
    "en": {
        "fuel_economy": "fuel economy",
        "interior_space": "interior space",
        "performance": "performance",
        "budget_fit": "budget fit",
        "safety": "safety",
    },
}


class Explanation(BaseModel):
    """Explanation text plus the method that produced it."""

    text: str
    method: Literal["ai", "template"]


def normalize_language(language: str | None) -> Language:
    """Map any input to a supported language code (default: Turkish)."""
    code = (language or "").strip().lower()[:2]
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE  # type: ignore[return-value]


def _top_criteria(item: RecommendationItem, count: int = 2) -> list[tuple[str, float]]:
    """Highest sub-scores; missing (None) criteria are skipped (NFR-04)."""
    scores = {
        name: value
        for name, value in item.score_breakdown.model_dump().items()
        if value is not None
    }
    # Sort by score desc, then by name so ties are deterministic.
    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    return ranked[:count]


def build_template_explanation(item: RecommendationItem, language: str = "tr") -> str:
    """Deterministic explanation that only uses values from ``item``."""
    lang = normalize_language(language)
    labels = CRITERION_LABELS[lang]
    name = f"{item.brand} {item.model}"
    top = _top_criteria(item)
    top_text = (" ve " if lang == "tr" else " and ").join(
        f"{labels.get(key, key)} ({value:.0f}/100)" for key, value in top
    )

    if lang == "tr":
        parts = [f"{name}, {item.score:.0f}/100 puanla {item.rank}. sırada."]
        if top_text:
            parts.append(f"En güçlü yönleri: {top_text}.")
        if item.strengths:
            parts.append(f"Öne çıkan: {item.strengths[0]}.")
        if item.weaknesses:
            parts.append(f"Dikkat: {item.weaknesses[0]}.")
    else:
        parts = [f"{name} ranks #{item.rank} with a score of {item.score:.0f}/100."]
        if top_text:
            parts.append(f"Its strongest areas are {top_text}.")
        if item.strengths:
            parts.append(f"Highlight: {item.strengths[0]}.")
        if item.weaknesses:
            parts.append(f"Watch out: {item.weaknesses[0]}.")
    return " ".join(parts)


def recommendation_facts(item: RecommendationItem) -> dict:
    """The only data sent to the model: values already computed by M3/M1."""
    return {
        "rank": item.rank,
        "brand": item.brand,
        "model": item.model,
        "variant": item.variant,
        "year": item.year,
        "body_type": item.body_type,
        "fuel_type": item.fuel_type,
        "transmission": item.transmission,
        "price_try": item.price_try,
        "score": item.score,
        "score_breakdown": item.score_breakdown.model_dump(exclude_none=True),
        "strengths": item.strengths,
        "weaknesses": item.weaknesses,
    }


def _clean_ai_text(raw: str, max_chars: int = MAX_EXPLANATION_CHARS) -> str | None:
    """Basic output checks; stricter hallucination checks come in T35."""
    text = " ".join(raw.split())
    if not text or len(text) > max_chars:
        return None
    return text


def explain_recommendation(
    item: RecommendationItem,
    language: str = "tr",
    provider: LLMProvider | None = None,
) -> Explanation:
    """Explain one recommendation; falls back to the template on any AI issue."""
    lang = normalize_language(language)
    return generate_or_fallback(
        provider or get_provider(),
        prompt=build_recommendation_prompt(recommendation_facts(item), lang),
        system_instruction=SYSTEM_INSTRUCTION,
        fallback_text=build_template_explanation(item, lang),
    )


def generate_or_fallback(
    provider: LLMProvider,
    *,
    prompt: str,
    system_instruction: str,
    fallback_text: str,
    max_chars: int = MAX_EXPLANATION_CHARS,
) -> Explanation:
    """Ask the provider for text; return ``fallback_text`` on any AI issue."""
    if provider.is_available:
        try:
            raw = provider.generate(prompt, system_instruction=system_instruction)
        except LLMError as exc:
            logger.info("AI explanation unavailable, using template: %s", exc)
        else:
            text = _clean_ai_text(raw, max_chars)
            if text is not None:
                return Explanation(text=text, method="ai")
            logger.info("AI explanation rejected by validation, using template.")

    return Explanation(text=fallback_text, method="template")


def explain_recommendations(
    result: RecommendationResult,
    language: str = "tr",
    provider: LLMProvider | None = None,
) -> RecommendationResult:
    """Return a copy of ``result`` with every ``explanation`` filled in.

    Only the ``explanation`` field changes; order, scores and all other
    fields are kept exactly as produced by the engine.
    """
    provider = provider or get_provider()
    items = [
        item.model_copy(
            update={
                "explanation": explain_recommendation(item, language, provider).text
            }
        )
        for item in result.recommendations
    ]
    return result.model_copy(update={"recommendations": items})
