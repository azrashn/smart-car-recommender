"""Tests for T13 stage 1: rule-based text parser (budget, transmission, language).

Covers:
- Turkish-aware normalisation (İ/I, apostrophes, ASCII folding)
- Language detection
- Budget: single numbers, ranges, "at least" / "at most" cues, TR and EN formats
- Numbers that are not budgets (km, seats, years) and never form ranges
- Transmission: both directions, "both"/"doesn't matter", negation, false positives
- Empty and meaningless input, determinism
"""

from __future__ import annotations

import pytest

from app.preferences.rule_parser import (
    detect_language,
    normalize_text,
    parse_preferences_text,
)
from app.schemas.preference import PreferenceDraft, TextExtractionResult


def budget(text: str) -> tuple[int | None, int | None]:
    pref = parse_preferences_text(text).preference
    return pref.budget_min_try, pref.budget_max_try


def transmission(text: str) -> str | None:
    return parse_preferences_text(text).preference.transmission


# ---------------------------------------------------------------------------
# Normalisation and language
# ---------------------------------------------------------------------------


def test_normalize_turkish_case_and_apostrophe():
    assert normalize_text("SUV'u İSTANBUL ILIK ÇOK") == "suv u istanbul ilik cok"


def test_normalize_keeps_number_separators():
    assert normalize_text("1.500.000 TL, 1,5 milyon!") == "1.500.000 tl, 1,5 milyon"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Şehir içinde otomatik bir SUV arıyorum", "tr"),
        ("1,5 milyona kadar bütçem var", "tr"),
        ("I am looking for an automatic car under 2 million", "en"),
        ("between 1 and 1.5 million", "en"),
        ("", "tr"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


def test_language_is_written_to_draft():
    assert parse_preferences_text("under 2 million").preference.language == "en"
    assert parse_preferences_text("2 milyona kadar").preference.language == "tr"


# ---------------------------------------------------------------------------
# Budget — Turkish
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "1,5 milyon",
        "1.5 milyon",
        "1.500.000",
        "1500000 TL",
        "1.500.000 ₺ bütçem var",
        "Bütçem 1,5 milyon civarı",
    ],
)
def test_single_budget_formats_are_max(text):
    assert budget(text) == (None, 1_500_000)


def test_budget_thousands_unit():
    assert budget("800 bin TL") == (None, 800_000)


def test_budget_with_suffix_and_kadar():
    assert budget("2 milyona kadar") == (None, 2_000_000)


def test_budget_en_fazla():
    assert budget("en fazla 1,2 milyon") == (None, 1_200_000)


def test_budget_en_az_is_min_only():
    assert budget("en az 900 bin") == (900_000, None)


def test_budget_range_with_dash_and_shared_unit():
    assert budget("1-1,5 milyon arası") == (1_000_000, 1_500_000)


def test_budget_range_with_ile():
    assert budget("1 ile 1.5 milyon arası") == (1_000_000, 1_500_000)


def test_budget_range_each_number_has_its_own_unit():
    assert budget("800 bin - 1 milyon") == (800_000, 1_000_000)


def test_budget_min_and_max_cues_in_one_sentence():
    assert budget("en az 1 milyon, en fazla 1,5 milyon") == (1_000_000, 1_500_000)


def test_budget_mid_sentence_with_other_words():
    assert budget("Şehir içi, otomatik, 7 kişilik, 1,8 milyona kadar bir araç") == (
        None,
        1_800_000,
    )


# ---------------------------------------------------------------------------
# Budget — English and short forms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.2M", (None, 1_200_000)),
        ("under 2 million", (None, 2_000_000)),
        ("1.5 million", (None, 1_500_000)),
        ("up to 900k", (None, 900_000)),
        ("at least 900k", (900_000, None)),
        ("between 1 and 1.5 million", (1_000_000, 1_500_000)),
    ],
)
def test_budget_english_and_short_forms(text, expected):
    assert budget(text) == expected


# ---------------------------------------------------------------------------
# Numbers that are NOT budgets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "150.000 km yapmış",
        "yılda 20 bin km kullanırım",
        "15k km a year",
        "7 kişilik araç",
        "7-seater",
        "2020 model",
        "5 bin TL",
    ],
)
def test_non_budget_numbers_are_ignored(text):
    assert budget(text) == (None, None)


def test_km_number_does_not_replace_budget():
    assert budget("yılda 20 bin km, bütçem 1,5 milyon") == (None, 1_500_000)


def test_excluded_number_never_forms_a_range():
    # "ve" + "7 kişilik" must not read as "between 1.5 million and 7".
    assert budget("1,5 milyon ve 7 kişilik") == (None, 1_500_000)
    assert budget("1,5 milyon ile 7 kişilik") == (None, 1_500_000)


# ---------------------------------------------------------------------------
# Transmission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["otomatik vitesli bir SUV", "OTOMATİK", "automatic", "auto gearbox"],
)
def test_transmission_automatic(text):
    assert transmission(text) == "automatic"


@pytest.mark.parametrize("text", ["manuel vites", "düz vites istiyorum", "düz vitesli", "manual"])
def test_transmission_manual(text):
    assert transmission(text) == "manual"


def test_duz_alone_is_not_manual():
    assert transmission("düz yolda uzun yol gideceğim") is None


@pytest.mark.parametrize(
    "text",
    [
        "otomatik ya da manuel",
        "otomatik veya manuel olabilir",
        "vites fark etmez",
        "any transmission",
    ],
)
def test_transmission_both_or_indifferent_is_none(text):
    assert transmission(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("manuel olmasın", "automatic"),
        ("manuel vites istemiyorum", "automatic"),
        ("no manual", "automatic"),
        ("otomatik olmasın", "manual"),
        ("not automatic", "manual"),
        ("I want automatic, not manual", "automatic"),
        ("manuel olmasın otomatik olsun", "automatic"),
    ],
)
def test_transmission_negation(text, expected):
    assert transmission(text) == expected


def test_unrelated_negation_does_not_flip_transmission():
    assert transmission("otomatik olsun bagaj önemli değil") == "automatic"


def test_otomobil_is_not_automatic():
    assert transmission("otomobil arıyorum") is None


# ---------------------------------------------------------------------------
# Whole result, empty and meaningless input
# ---------------------------------------------------------------------------


def test_result_shape_and_missing_fields():
    result = parse_preferences_text("otomatik vites, en fazla 1,2 milyon")
    assert isinstance(result, TextExtractionResult)
    assert result.method == "rule"
    assert result.preference.budget_max_try == 1_200_000
    assert result.preference.transmission == "automatic"
    assert result.missing_fields == []


def test_missing_budget_is_reported():
    result = parse_preferences_text("otomatik vitesli bir araç")
    assert result.preference.budget_max_try is None
    assert result.missing_fields == ["budget_max_try"]


@pytest.mark.parametrize("text", ["", "   ", "\n\t", "asdf qwer zxcv", "!!!???", "🚗🚗🚗"])
def test_empty_or_meaningless_text_gives_empty_draft(text):
    result = parse_preferences_text(text)
    default = PreferenceDraft()
    assert result.method == "rule"
    assert result.missing_fields == ["budget_max_try"]
    assert result.preference.model_dump(exclude={"language"}) == default.model_dump(
        exclude={"language"}
    )


@pytest.mark.parametrize("bad", [None, 123, ["otomatik"], b"bytes"])
def test_non_string_input_never_raises(bad):
    result = parse_preferences_text(bad)  # type: ignore[arg-type]
    assert result.preference == PreferenceDraft()
    assert result.missing_fields == ["budget_max_try"]


def test_very_long_text_never_raises():
    text = "otomatik 1,5 milyon " * 5_000
    assert parse_preferences_text(text).preference.transmission == "automatic"


def test_parser_is_deterministic():
    text = "1 ile 1.5 milyon arası, manuel olmasın"
    first = parse_preferences_text(text)
    assert all(parse_preferences_text(text) == first for _ in range(5))
