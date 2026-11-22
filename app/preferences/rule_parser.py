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
from decimal import Decimal
from enum import Enum
from typing import TypeVar

from app.schemas.preference import (
    BodyType,
    FuelType,
    PreferenceDraft,
    TextExtractionResult,
)

_E = TypeVar("_E", bound=Enum)

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
# Budget parsing
# ---------------------------------------------------------------------------
#
# Strategy
# 1. Find every number in the normalised text with its optional multiplier
#    (milyon / bin / million / thousand / M / k) and note currency words.
# 2. Drop numbers that are clearly not prices ("20 bin km", "7 kisilik", "3 yil")
#    BEFORE any range detection, so they can never pair with a price.
# 3. Two neighbouring numbers joined by "-", "ile", "to" (or "ve"/"and" together
#    with "arasi"/"between") form a range; a unit given only on the second number
#    ("1-1,5 milyon") is inherited by the first.
# 4. A single number is the maximum, unless a cue says otherwise ("en az", "at least").

_MILLION = 1_000_000
_THOUSAND = 1_000

# Plausibility limits. A bare number (no unit, no currency) must be >= _BARE_MIN to
# count as a price, so years ("2020") and counts are never read as budgets.
_BUDGET_FLOOR = 10_000
_BUDGET_CEILING = 100_000_000
_BARE_MIN = 100_000

_NUMBER_RE = re.compile(
    r"(?<![a-z\d])"
    r"(?P<num>\d+(?:[.,]\d+)*)"
    r"(?P<mult>"
    r"\s*(?:milyon(?:a|u|da|dan|luk|un)?|million|bin(?:e|i|den)?|thousand)\b"
    r"|[km]\b)?"
)

# What may follow a number to show it is NOT a price (after an optional multiplier).
_NOT_BUDGET_AFTER_RE = re.compile(
    r"^\s*-?\s*(?:km\b|kilometre|kilometer|kisilik|kisi\b|koltuk|seater|seats?\b"
    r"|yil|yilda|yillik|year|yr\b|sene|kapi|door|hp\b|bg\b|beygir|litre|liter"
    r"|lt\b|cc\b|ay\b|month|gun\b|day\b|saat|hour)"
)
_CURRENCY_AFTER_RE = re.compile(r"^\s*(?:tl\b|try\b|lira\w*|₺)")

# Cues placed right BEFORE the number (checked against the text ending at it).
_MAX_BEFORE_RE = re.compile(
    r"\b(?:en\s+fazla|en\s+cok|maksimum|maks|max|maximum|at\s+most|under|below"
    r"|up\s*to|less\s+than|not\s+more\s+than|no\s+more\s+than|within)"
    r"\s*(?:of\s+|about\s+|around\s+)?[₺$]?\s*$"
)
_MIN_BEFORE_RE = re.compile(
    r"\b(?:en\s+az|minimum|min|at\s+least|over|above|more\s+than"
    r"|not\s+less\s+than|no\s+less\s+than)"
    r"\s*(?:of\s+|about\s+|around\s+)?[₺$]?\s*$"
)
# Cues placed right AFTER the number (and its optional currency word).
_MAX_AFTER_RE = re.compile(
    r"^\s*(?:(?:tl|try|lira|₺)\s*)?(?:ve\s+)?"
    r"(?:kadar|altinda|altina|alti|asmasin|gecmesin|or\s+less|or\s+under|or\s+below)\b"
)
_MIN_AFTER_RE = re.compile(
    r"^\s*(?:(?:tl|try|lira|₺)\s*)?(?:(?:ve|or|and)\s+)?"
    r"(?:ustu|ustunde|uzeri|uzerinde|fazla|more|up|above|plus)\b|^\s*\+"
)

# Text allowed between the two numbers of a range.
_STRONG_JOINER_RE = re.compile(r"^\s*(?:tl\s*|try\s*|lira\s*|₺\s*)?(?:-|ile|ila|to)\s*$")
_WEAK_JOINER_RE = re.compile(r"^\s*(?:tl\s*|try\s*|lira\s*|₺\s*)?(?:ve|and)\s*$")
# "arasi" after the second number / "between" before the first one makes "ve"/"and" a range.
_RANGE_WORD_AFTER_RE = re.compile(r"^\s*(?:(?:tl|try|lira|₺)\s*)?(?:arasi|arasinda|araliginda)\b")
_RANGE_WORD_BEFORE_RE = re.compile(r"\bbetween\s*[₺$]?\s*$")


class _Amount:
    """One number found in the text, with its surroundings already analysed."""

    __slots__ = ("start", "end", "num", "mult", "currency", "kind")

    def __init__(
        self,
        start: int,
        end: int,
        num: str,
        mult: int | None,
        currency: bool,
        kind: str,
    ) -> None:
        self.start = start
        self.end = end
        self.num = num
        self.mult = mult
        self.currency = currency
        self.kind = kind  # "min" or "max" (cue-based; "max" when no cue)


def _multiplier_of(raw: str | None) -> int | None:
    if not raw:
        return None
    word = raw.strip()
    if word.startswith(("milyon", "million")) or word == "m":
        return _MILLION
    return _THOUSAND


def _to_int(num: str, mult: int | None, currency: bool) -> int | None:
    """Turn the digits ``num`` into a TRY amount, or ``None`` when not a plausible price."""
    seps = re.findall(r"[.,]", num)
    if mult is not None:
        # With a unit a single separator is the decimal point: "1,5 milyon", "1.2M".
        if len(seps) > 1:
            return None
        value = Decimal(num.replace(",", "."))
        amount = int(value * mult)
    else:
        # Without a unit separators must be thousands groups: "1.500.000".
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", num):
            amount = int(re.sub(r"[.,]", "", num))
        elif num.isdigit():
            amount = int(num)
        else:
            return None
        if not currency and amount < _BARE_MIN:
            return None
    if not _BUDGET_FLOOR <= amount <= _BUDGET_CEILING:
        return None
    return amount


def _find_amounts(norm: str) -> list[_Amount]:
    """Collect price-like numbers, dropping km / seats / years etc. up front."""
    found: list[_Amount] = []
    for m in _NUMBER_RE.finditer(norm):
        tail = norm[m.end() :]
        if _NOT_BUDGET_AFTER_RE.match(tail):
            continue
        before = norm[max(0, m.start() - 40) : m.start()]
        currency = bool(_CURRENCY_AFTER_RE.match(tail)) or before.rstrip().endswith("₺")
        is_min = bool(_MIN_BEFORE_RE.search(before) or _MIN_AFTER_RE.match(tail))
        is_max = bool(_MAX_BEFORE_RE.search(before) or _MAX_AFTER_RE.match(tail))
        kind = "min" if is_min and not is_max else "max"
        found.append(
            _Amount(
                m.start(), m.end(), m.group("num"), _multiplier_of(m.group("mult")),
                currency, kind,
            )
        )  # fmt: skip
    return found


def _try_range(norm: str, a: _Amount, b: _Amount) -> tuple[int, int] | None:
    """Return ``(low, high)`` when ``a`` and ``b`` form a plausible range."""
    between = norm[a.end : b.start]
    if _STRONG_JOINER_RE.match(between):
        pass
    elif _WEAK_JOINER_RE.match(between):
        word_after = _RANGE_WORD_AFTER_RE.match(norm[b.end :])
        word_before = _RANGE_WORD_BEFORE_RE.search(norm[max(0, a.start - 20) : a.start])
        if not (word_after or word_before):
            return None
    else:
        return None

    high = _to_int(b.num, b.mult, b.currency)
    if high is None:
        return None
    # "1-1,5 milyon": the first number may borrow the second one's unit.
    unit_options = [b.mult, a.mult] if a.mult is None and b.mult is not None else [a.mult]
    for unit in unit_options:
        low = _to_int(a.num, unit, a.currency)
        if low is None:
            continue
        if unit is not a.mult and low > high:
            continue  # the borrowed unit gave a nonsense range
        return (low, high) if low <= high else (high, low)
    return None


def parse_budget(norm: str) -> tuple[int | None, int | None]:
    """Return ``(budget_min_try, budget_max_try)`` read from normalised text.

    A range gives both; a single number is the maximum unless it carries an
    "at least" cue, in which case only the minimum is set.
    """
    amounts = _find_amounts(norm)
    for a, b in zip(amounts, amounts[1:], strict=False):
        found = _try_range(norm, a, b)
        if found is not None:
            return found

    low: int | None = None
    high: int | None = None
    for a in amounts:
        value = _to_int(a.num, a.mult, a.currency)
        if value is None:
            continue
        if a.kind == "min":
            low = value if low is None else low
        else:
            high = value if high is None else high
    if low is not None and high is not None and low > high:
        low, high = high, low
    return low, high


# ---------------------------------------------------------------------------
# Transmission parsing
# ---------------------------------------------------------------------------
#
# "otomatik" / "automatic" / "auto"  -> "automatic"
# "manuel" / "manual" / "duz vites"  -> "manual"
# Both wanted, or "vites fark etmez" / "any transmission" -> None.
# Negation flips the meaning: "manuel olmasin" -> automatic, "no automatic" -> manual.
# A bare "duz" is NOT manual ("duz yolda"); only "duz vites" is.

_AUTOMATIC_RE = re.compile(r"\b(?:otomatik\w*|automatic\w*|auto\b)")
_MANUAL_RE = re.compile(r"\b(?:manuel\w*|manual\w*|duz\s+vites\w*)")

# "vites fark etmez", "vites onemli degil", "any transmission", "don't care about the gearbox".
_TRANSMISSION_WORD = r"(?:vites\w*|transmission|gearbox|gear)"
_INDIFFERENT_WORD = (
    r"(?:fark\s*et\w*|farki\s+yok|onemli\s+degil|onemsiz|doesn\s+t\s+matter"
    r"|does\s+not\s+matter|not\s+important|don\s+t\s+care|dont\s+care|no\s+preference)"
)
_TRANSMISSION_INDIFFERENT_RE = re.compile(
    rf"\b{_TRANSMISSION_WORD}\b[^,.]{{0,40}}?\b{_INDIFFERENT_WORD}"
    rf"|\b(?:any|either)\s+(?:kind\s+of\s+)?{_TRANSMISSION_WORD}\b"
    rf"|\b(?:don\s+t|dont|do\s+not)\s+care\s+(?:about|for)\s+(?:the\s+)?{_TRANSMISSION_WORD}\b"
)

# Negation right after the term ("olmasin", "istemiyorum", "degil", "haric") — at most
# one filler word in between, so "otomatik olsun, bagaj onemli degil" is not negated.
_NEGATION_WORD = (
    r"(?:olmasin\w*|olmamali\w*|olmayan|olmayacak|istemiyor\w*|istemem|degil|haric"
    r"|disinda)\b"
)
_NEGATED_AFTER_RE = re.compile(
    r"^\s*(?:(?:vites\w*|arac\w*|araba\w*|motor\w*|yakit\w*|olarak|bir|de|da|ise)\s+)?"
    + _NEGATION_WORD
)
# Negation right before the term ("no manual", "not automatic", "non-automatic").
_NEGATED_BEFORE_RE = re.compile(
    r"\b(?:no|not|without|never|avoid|hate|except|excluding)\s+(?:a\s+|an\s+|the\s+)?$"
    r"|\bnon-?$"
)
# List-aware variants for fuel / body type lists, where one negation covers several
# items: "dizel ve benzinli olmasin", "no diesel or petrol".
_LIST_JOINER = r"(?:ve|veya|ya\s+da|ile|or|and|nor)"
_NEGATED_AFTER_LIST_RE = re.compile(
    rf"^(?:\s+{_LIST_JOINER}\s+[a-z]+)*"
    r"\s*(?:(?:arac\w*|araba\w*|motor\w*|yakit\w*|olarak|bir|de|da|ise)\s+)?" + _NEGATION_WORD
)
_NEGATED_BEFORE_LIST_RE = re.compile(
    r"\b(?:no|not|without|never|avoid|hate|except|excluding)\s+(?:a\s+|an\s+|the\s+)?"
    rf"(?:[a-z]+\s+{_LIST_JOINER}\s+)*$|\bnon-?$"
)


def _classify_matches(
    norm: str, pattern: re.Pattern[str], *, list_aware: bool = False
) -> list[tuple[int, bool]]:
    """Return ``(position, is_negated)`` for every match of ``pattern`` in ``norm``."""
    after_re = _NEGATED_AFTER_LIST_RE if list_aware else _NEGATED_AFTER_RE
    before_re = _NEGATED_BEFORE_LIST_RE if list_aware else _NEGATED_BEFORE_RE
    window = 40 if list_aware else 20
    result: list[tuple[int, bool]] = []
    for m in pattern.finditer(norm):
        before = norm[max(0, m.start() - window) : m.start()]
        negated = bool(after_re.match(norm[m.end() :]) or before_re.search(before))
        result.append((m.start(), negated))
    return result


def _term_polarity(norm: str, pattern: re.Pattern[str]) -> tuple[bool, bool]:
    """Return ``(mentioned_positively, mentioned_negatively)`` for ``pattern``."""
    matches = _classify_matches(norm, pattern)
    return any(not neg for _, neg in matches), any(neg for _, neg in matches)


def parse_transmission(norm: str) -> str | None:
    """Return ``"automatic"``, ``"manual"`` or ``None`` (no/unclear preference)."""
    if _TRANSMISSION_INDIFFERENT_RE.search(norm):
        return None
    auto_pos, auto_neg = _term_polarity(norm, _AUTOMATIC_RE)
    manual_pos, manual_neg = _term_polarity(norm, _MANUAL_RE)
    wants_automatic = auto_pos or manual_neg
    wants_manual = manual_pos or auto_neg
    if wants_automatic and not wants_manual:
        return "automatic"
    if wants_manual and not wants_automatic:
        return "manual"
    return None


# ---------------------------------------------------------------------------
# Fuel types and body types
# ---------------------------------------------------------------------------
#
# Every mention becomes one list entry, in order of first appearance, without
# duplicates. A negated mention ("dizel olmasin", "no diesel") is simply not added.
# Terms use a word-start match plus suffix tolerance (``\w*``) so "benzinliyi" and
# "SUV'u" are found; very short abbreviations are matched as whole words only.

_FUEL_TERMS: dict[FuelType, re.Pattern[str]] = {
    FuelType.petrol: re.compile(r"\b(?:benzin\w*|petrol\w*|gasoline\w*)"),
    FuelType.diesel: re.compile(r"\b(?:dizel\w*|diesel\w*|mazot\w*)"),
    FuelType.hybrid: re.compile(r"\b(?:hibrit\w*|hybrid\w*)"),
    FuelType.electric: re.compile(r"\b(?:elektrik\w*|electric\w*)"),
}
# "ev" means "house" in Turkish ("ev icin araba"), so it only counts as "electric
# vehicle" when the text is detected as English.
_EV_RE = re.compile(r"\bevs?\b")
# "hibrit elektrik" / "hybrid electric" is ONE fuel type (hybrid), not two.
_HYBRID_ELECTRIC_RE = re.compile(r"\b(hibrit|hybrid)\s+(?:elektrik\w*|electric\w*)")

_BODY_TERMS: dict[BodyType, re.Pattern[str]] = {
    BodyType.suv: re.compile(r"\bsuv\w*"),
    BodyType.sedan: re.compile(r"\bsedan\w*"),
    BodyType.hatchback: re.compile(r"\b(?:hatchback\w*|hecbek\w*|hatch\b|hb\b)"),
    BodyType.wagon: re.compile(r"\b(?:station\s*(?:wagon|vagon)\w*|wagon\w*|estate\b|sw\b)"),
    BodyType.mpv: re.compile(r"\b(?:mpv\b|mini\s*van\w*)"),
}


def _collect_enums(
    norm: str,
    terms: dict[_E, re.Pattern[str]],
    extra: list[tuple[_E, re.Pattern[str]]],
) -> list[_E]:
    """Return enum members mentioned positively, ordered by first appearance."""
    first_seen: dict[_E, int] = {}
    for member, pattern in [*terms.items(), *extra]:
        for pos, negated in _classify_matches(norm, pattern, list_aware=True):
            if not negated and pos < first_seen.get(member, pos + 1):
                first_seen[member] = pos
    return sorted(first_seen, key=first_seen.__getitem__)


def parse_fuel_types(norm: str, language: str) -> list[FuelType]:
    """Return the fuel types mentioned in ``norm`` (``language`` enables the "ev" term)."""
    norm = _HYBRID_ELECTRIC_RE.sub(r"\1", norm)
    extra = [(FuelType.electric, _EV_RE)] if language == "en" else []
    return _collect_enums(norm, _FUEL_TERMS, extra)


def parse_body_types(norm: str) -> list[BodyType]:
    """Return the body types mentioned in ``norm``."""
    return _collect_enums(norm, _BODY_TERMS, [])


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _build_draft(text: str) -> PreferenceDraft:
    if not isinstance(text, str):
        return PreferenceDraft()
    norm = normalize_text(text)
    language = detect_language(text)
    budget_min, budget_max = parse_budget(norm)
    fields: dict[str, object] = {
        "language": language,
        "budget_min_try": budget_min,
        "budget_max_try": budget_max,
        "transmission": parse_transmission(norm),
        "fuel_types": parse_fuel_types(norm, language),
        "body_types": parse_body_types(norm),
    }
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
