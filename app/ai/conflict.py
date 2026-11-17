"""Conflict explanations (M4, T34).

Explains a ``ConflictReport`` produced by the engine (M3). Which constraints
conflict and how many vehicles a relaxation unlocks are always taken from the
report (computed by M3, T24); this module never recomputes them.
"""

from __future__ import annotations

from typing import Any

from app.ai.explanation import (
    Explanation,
    generate_or_fallback,
    normalize_language,
)
from app.ai.prompts.conflict import SYSTEM_INSTRUCTION, build_conflict_prompt
from app.ai.provider import LLMProvider, get_provider
from app.schemas.recommendation import ConflictReport

MAX_CONFLICT_EXPLANATION_CHARS = 800
MAX_SUGGESTIONS_IN_TEXT = 3

# Constraint names used by the engine filters (app/engine/filters.py).
CONSTRAINT_LABELS: dict[str, dict[str, str]] = {
    "tr": {
        "budget_max": "bütçe üst sınırı",
        "transmission": "vites türü",
        "fuel_type": "yakıt türü",
        "seats_min": "en az koltuk sayısı",
        "body_type": "kasa tipi",
    },
    "en": {
        "budget_max": "maximum budget",
        "transmission": "transmission",
        "fuel_type": "fuel type",
        "seats_min": "minimum seats",
        "body_type": "body type",
    },
}

VALUE_LABELS: dict[str, dict[str, str]] = {
    "tr": {
        "petrol": "benzinli",
        "diesel": "dizel",
        "hybrid": "hibrit",
        "electric": "elektrikli",
        "manual": "manuel",
        "automatic": "otomatik",
        "hatchback": "hatchback",
        "sedan": "sedan",
        "suv": "SUV",
        "wagon": "station wagon",
        "mpv": "MPV",
    },
    "en": {
        "petrol": "petrol",
        "diesel": "diesel",
        "hybrid": "hybrid",
        "electric": "electric",
        "manual": "manual",
        "automatic": "automatic",
        "hatchback": "hatchback",
        "sedan": "sedan",
        "suv": "SUV",
        "wagon": "station wagon",
        "mpv": "MPV",
    },
}


def _constraint_label(name: str, lang: str) -> str:
    return CONSTRAINT_LABELS[lang].get(name, name)


def _format_value(value: Any, lang: str) -> str:
    """Human-readable value; numbers get TR/EN thousand separators."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        text = f"{value:,}"
        return text.replace(",", ".") if lang == "tr" else text
    if isinstance(value, float):
        return _format_value(int(value), lang) if value.is_integer() else str(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_format_value(item, lang) for item in value)
    text = str(value)
    return VALUE_LABELS[lang].get(text.lower(), text)


def _suggestion_value(constraint: str, value: Any, lang: str) -> str:
    text = _format_value(value, lang)
    return f"{text} TL" if constraint == "budget_max" else text


def _join(items: list[str], lang: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    last_sep = " ve " if lang == "tr" else " and "
    return ", ".join(items[:-1]) + last_sep + items[-1]


def build_conflict_template(report: ConflictReport, language: str = "tr") -> str:
    """Deterministic explanation built only from fields of ``report``."""
    lang = normalize_language(language)
    constraints = _join(
        [_constraint_label(name, lang) for name in report.conflicting_constraints], lang
    )
    suggestions = report.suggestions[:MAX_SUGGESTIONS_IN_TEXT]

    if lang == "tr":
        parts = ["Seçtiğiniz kriterlerin tamamına uyan araç bulunamadı."]
        if constraints:
            parts.append(f"Sonucu engelleyen kriterler: {constraints}.")
        for s in suggestions:
            parts.append(
                f"{_constraint_label(s.constraint, lang).capitalize()} "
                f"{_suggestion_value(s.constraint, s.current_value, lang)} yerine "
                f"{_suggestion_value(s.constraint, s.suggested_value, lang)} olursa "
                f"{s.additional_matches_unlocked} araç daha uygun hale gelir."
            )
        if not suggestions:
            parts.append("Kriterlerinizden birini esnetmeyi deneyebilirsiniz.")
    else:
        parts = ["No vehicle matches all of your criteria."]
        if constraints:
            parts.append(f"The blocking criteria are: {constraints}.")
        for s in suggestions:
            count = s.additional_matches_unlocked
            noun = "vehicle" if count == 1 else "vehicles"
            parts.append(
                f"Changing {_constraint_label(s.constraint, lang)} from "
                f"{_suggestion_value(s.constraint, s.current_value, lang)} to "
                f"{_suggestion_value(s.constraint, s.suggested_value, lang)} would unlock "
                f"{count} more {noun}."
            )
        if not suggestions:
            parts.append("Try relaxing one of your criteria.")
    return " ".join(parts)


def conflict_facts(report: ConflictReport) -> dict:
    """The only data sent to the model: values already computed by M3."""
    return {
        "conflicting_constraints": report.conflicting_constraints,
        "suggestions": [
            {
                "constraint": s.constraint,
                "current_value": s.current_value,
                "suggested_value": s.suggested_value,
                "additional_matches_unlocked": s.additional_matches_unlocked,
            }
            for s in report.suggestions[:MAX_SUGGESTIONS_IN_TEXT]
        ],
    }


def explain_conflict(
    report: ConflictReport,
    language: str = "tr",
    provider: LLMProvider | None = None,
) -> Explanation:
    """Explain a conflict report; falls back to the template on any AI issue."""
    lang = normalize_language(language)
    return generate_or_fallback(
        provider or get_provider(),
        prompt=build_conflict_prompt(conflict_facts(report), lang),
        system_instruction=SYSTEM_INSTRUCTION,
        fallback_text=build_conflict_template(report, lang),
        max_chars=MAX_CONFLICT_EXPLANATION_CHARS,
    )


def explain_conflict_report(
    report: ConflictReport,
    language: str = "tr",
    provider: LLMProvider | None = None,
) -> ConflictReport:
    """Return a copy of ``report`` with only ``explanation`` filled in."""
    explanation = explain_conflict(report, language, provider)
    return report.model_copy(update={"explanation": explanation.text})
