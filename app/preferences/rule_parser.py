"""Rule-based free-text preference extractor (M2, T13) — Turkish and English.

``parse_preferences_text`` is the fallback used by ``POST /api/preferences/text``
when the AI layer is unavailable or fails (NFR-02, api-contract R2/R3).

Design rules
------------
- Pure and deterministic: no AI, no network, no DB. Same text → same result (NFR-01).
- Never raises: any problem yields an empty ``PreferenceDraft``.
- Never guesses: a field that cannot be read from the text stays empty.
- Matching works on *normalised* text: Turkish-aware lower-casing, then ASCII
  folding (ı→i, ş→s, ...), so "OTOMATİK", "otomatik" and "otomatık" look the same
  and dictionaries below are written in folded form.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas.preference import PreferenceDraft, TextExtractionResult

# ---------------------------------------------------------------------------
# Constants — normalisation and language detection
# ---------------------------------------------------------------------------

# Applied after lower-casing. "ı" must be folded to "i" too.
_TR_FOLD_TABLE = str.maketrans(
    {
        "ı": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
        "â": "a",
        "î": "i",
        "û": "u",
    }
)

# Characters kept after normalisation; everything else becomes a space.
# "." and "," stay for numbers (1.500.000 / 1,5), "-" for ranges, "+" for "900k+".
_DROP_CHARS_RE = re.compile(r"[^a-z0-9.,\-+₺$]+")

# Turkish letters that never appear in English text.
_TR_ONLY_CHARS = frozenset("çğıöşüÇĞİÖŞÜ")

# Folded stop-words used by the language heuristic.
_TR_WORDS = frozenset(
    {
        "bir", "ve", "ile", "icin", "arac", "araba", "butce", "butcem", "olsun",
        "olmasin", "istiyorum", "ariyorum", "arayisindayim", "kadar", "arasi",
        "arasinda", "az", "fazla", "vites", "vitesli", "otomatik", "manuel",
        "milyon", "sehir", "yakan", "kisilik", "aile", "bana", "gibi", "cok",
        "ama", "veya", "ya", "da", "benim", "olan", "yok", "etmez", "lazim",
    }
)  # fmt: skip
_EN_WORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "under", "between", "up", "to", "for",
        "with", "car", "want", "need", "looking", "budget", "million",
        "thousand", "automatic", "manual", "at", "least", "most", "i", "my",
        "no", "not", "of", "please", "about", "around", "than", "less", "more",
        "over", "below", "above", "something", "preferably",
    }
)  # fmt: skip


# ---------------------------------------------------------------------------
# Text normalisation and language detection
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Return ``text`` lower-cased the Turkish way, ASCII-folded and tidied.

    ``İ→i`` and ``I→ı`` are handled *before* ``str.lower()`` (plain ``"I".lower()``
    gives ``"i"``, which is wrong for Turkish). Apostrophes become spaces so
    "SUV'u" turns into "suv u". Only ``a-z 0-9 . , - + ₺ $`` and single spaces remain.
    """
    chars: list[str] = []
    for ch in text:
        if ch == "İ":
            chars.append("i")
        elif ch == "I":
            chars.append("ı")
        else:
            lowered = ch.lower()
            chars.append(lowered if len(lowered) == 1 else ch)
    folded = "".join(chars).translate(_TR_FOLD_TABLE)
    # Drop remaining accents (é → e); the dotted-i case was handled above.
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", folded) if not unicodedata.combining(c)
    )
    folded = folded.replace("–", "-").replace("—", "-")
    return _DROP_CHARS_RE.sub(" ", folded).strip()


def detect_language(text: str) -> str:
    """Guess ``"tr"`` or ``"en"`` from ``text`` with a simple word/character count.

    Turkish-only letters count strongly towards Turkish. Ties (including empty or
    number-only text) return ``"tr"``, the schema default.
    """
    tr_score = 3 if any(ch in _TR_ONLY_CHARS for ch in text) else 0
    en_score = 0
    for word in re.findall(r"[a-z]+", normalize_text(text)):
        if word in _TR_WORDS:
            tr_score += 1
        if word in _EN_WORDS:
            en_score += 1
    return "en" if en_score > tr_score else "tr"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _build_draft(text: str) -> PreferenceDraft:
    # Field parsers are added in the following commits.
    fields: dict[str, object] = {"language": detect_language(text)}
    return PreferenceDraft(**fields)


def parse_preferences_text(text: str) -> TextExtractionResult:
    """Extract a ``PreferenceDraft`` from Turkish or English free text.

    Never raises. Empty, meaningless or non-string input gives an empty draft with
    ``missing_fields == ["budget_max_try"]``. The result is always ``method="rule"``.
    """
    try:
        draft = _build_draft(text)
    except Exception:  # noqa: BLE001 - the fallback parser must never fail
        draft = PreferenceDraft()
    return TextExtractionResult(
        preference=draft,
        missing_fields=draft.missing_required_fields(),
        method="rule",
    )
