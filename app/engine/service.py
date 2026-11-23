"""M3 Öneri Servisi (T25).

Bu servis, kullanıcı tercihlerini (Preference) alarak:
1. Sert kısıt filtrelerini (T21) ``preference.hard_filter_criteria()`` üzerinden uygular.
2. Eşleşen araç yoksa çelişki analizi yaparak ConflictReport ve esnetme önerileri üretir.
3. Eşleşen araçlar varsa TAM katalog sınırları üzerinden ağırlıklı puanlama (T22) ile
   en yüksek puanlı ilk 5 aracı seçer.
4. Güçlü/zayıf yan etiketlerini ve şablon açıklamasını ekleyerek RecommendationResult döner.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from app.config import get_settings
from app.engine.filters import evaluate_hard_filters
from app.engine.scoring import compute_catalogue_bounds, score_and_rank_vehicles
from app.schemas.preference import Preference
from app.schemas.recommendation import (
    ConflictReport,
    RecommendationItem,
    RecommendationResult,
    RelaxationSuggestion,
    ScoreBreakdown,
)
from app.schemas.vehicle import Vehicle


# ==============================================================================
# 1. Araç Verisini Yükleme (data/vehicles.csv — T04 gelince DB kullanılacak)
# ==============================================================================

def load_catalog_vehicles(csv_path: Optional[Path] = None) -> List[Vehicle]:
    """Katalogdaki gerçek araçları ``data/vehicles.csv`` dosyasından yükler.

    Üretim kodu ``tests/`` klasörüne bağımlı değildir; yol ``Settings.vehicles_csv_path``
    üzerinden okunur. Her satır ``Vehicle`` şeması ile doğrulanır.
    """
    path = csv_path or get_settings().vehicles_csv_path
    if not path.exists():
        return []

    vehicles: List[Vehicle] = []
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vehicles.append(Vehicle.model_validate(row))
    return vehicles


def _get_attr(vehicle: Any, field: str) -> Any:
    """Sözlük veya nesne (Vehicle) üzerinden güvenli alan okur."""
    if isinstance(vehicle, dict):
        return vehicle.get(field)
    return getattr(vehicle, field)


# ==============================================================================
# 2. Güçlü ve Zayıf Yönleri Belirleme (Deterministik Kural Tabanlı)
# ==============================================================================

def _extract_strengths_and_weaknesses(
    vehicle: Any,
    sub_scores: Dict[str, Optional[float]],
) -> Tuple[List[str], List[str]]:
    """Bir aracın alt puanlarına göre güçlü ve zayıf yön etiketlerini üretir."""
    strengths: List[str] = []
    weaknesses: List[str] = []

    fuel_score = sub_scores.get("fuel_economy")
    if fuel_score is not None:
        if fuel_score >= 80.0:
            strengths.append("Yüksek yakıt/enerji verimliliği")
        elif fuel_score <= 40.0:
            weaknesses.append("Sınıfına göre yüksek yakıt tüketimi")

    budget_score = sub_scores.get("budget_fit")
    if budget_score is not None:
        if budget_score >= 80.0:
            strengths.append("Bütçeye göre yüksek fiyat avantajı")
        elif budget_score <= 35.0:
            weaknesses.append("Bütçe sınırına yakın fiyat")

    space_score = sub_scores.get("interior_space")
    if space_score is not None:
        if space_score >= 80.0:
            strengths.append("Geniş bagaj ve yaşam alanı")
        elif space_score <= 40.0:
            weaknesses.append("Sınırlı bagaj hacmi")

    perf_score = sub_scores.get("performance")
    if perf_score is not None:
        if perf_score >= 80.0:
            strengths.append("Güçlü motor performansı")
        elif perf_score <= 40.0:
            weaknesses.append("Düşük motor gücü")

    safety_score = sub_scores.get("safety")
    if safety_score is not None:
        if safety_score >= 90.0:
            strengths.append("5 yıldızlı Euro NCAP güvenlik derecesi")
        elif safety_score <= 60.0:
            weaknesses.append("Orta seviye güvenlik skoru")

    if not strengths:
        strengths.append("Dengeli genel özellikler")

    return strengths, weaknesses


def _generate_template_explanation(
    brand: str,
    model: str,
    strengths: List[str],
) -> str:
    """Yapay zeka kapalıyken dönecek şablon açıklama metni."""
    strength_text = ", ".join(strengths[:2]).lower()
    return f"{brand} {model}, özellikle {strength_text} ile belirlediğiniz kriterlere en uygun dengeli seçenektir."


# ==============================================================================
# 3. Çelişki ve Gevşetme Analizi (Hiç Araç Bulunamadığında)
# ==============================================================================

def _build_conflict_report(
    vehicles: Sequence[Any],
    criteria: Dict[str, Any],
    eliminated_counts: Dict[str, int],
) -> ConflictReport:
    """Kriterlere uyan araç çıkmadığında detaylı çelişki raporu oluşturur."""
    conflicting_keys = [k for k, count in eliminated_counts.items() if count > 0]
    suggestions: List[RelaxationSuggestion] = []

    # 1. Bütçe esnetme önerisi: Diğer kısıtları sağlayan en ucuz araca göre bütçe öner
    budget_max = criteria.get("budget_max")
    if budget_max:
        without_budget = dict(criteria, budget_max=None)
        candidates_without_budget, _ = evaluate_hard_filters(vehicles, without_budget)
        if candidates_without_budget:
            cheapest = min(
                candidates_without_budget,
                key=lambda x: int(_get_attr(x, "price_try")),
            )
            cheapest_price = int(_get_attr(cheapest, "price_try"))
            if cheapest_price > budget_max:
                unlocked_count = len(
                    [c for c in candidates_without_budget if int(_get_attr(c, "price_try")) <= cheapest_price]
                )
                suggestions.append(
                    RelaxationSuggestion(
                        constraint="budget_max",
                        current_value=budget_max,
                        suggested_value=cheapest_price,
                        message=(
                            f"Bütçenizi {cheapest_price:,} TL seviyesine çıkarırsanız "
                            f"{unlocked_count} yeni araç seçeneği açılacaktır."
                        ),
                        additional_matches_unlocked=unlocked_count,
                    )
                )

    # 2. Yakıt türü esnetme önerisi
    fuel_types = criteria.get("fuel_types")
    if fuel_types:
        relaxed_criteria = dict(criteria, fuel_types=[])
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if unlocked:
            suggestions.append(
                RelaxationSuggestion(
                    constraint="fuel_types",
                    current_value=fuel_types,
                    suggested_value="any",
                    message=f"Yakıt tercihinizi esnetirseniz {len(unlocked)} yeni araç bütçenize dahil olacaktır.",
                    additional_matches_unlocked=len(unlocked),
                )
            )

    # 3. Vites tercihi esnetme önerisi
    transmission = criteria.get("transmission")
    if transmission and transmission != "any":
        relaxed_criteria = dict(criteria, transmission=None)
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if unlocked:
            suggestions.append(
                RelaxationSuggestion(
                    constraint="transmission",
                    current_value=transmission,
                    suggested_value="any",
                    message=f"Vites tercihini 'Farketmez' olarak esnetirseniz {len(unlocked)} yeni araç açılacaktır.",
                    additional_matches_unlocked=len(unlocked),
                )
            )

    # 4. Kasa tipi esnetme önerisi
    body_types = criteria.get("body_types")
    if body_types:
        relaxed_criteria = dict(criteria, body_types=[])
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if unlocked:
            suggestions.append(
                RelaxationSuggestion(
                    constraint="body_types",
                    current_value=body_types,
                    suggested_value="any",
                    message=f"Farklı kasa tiplerini de değerlendirirseniz {len(unlocked)} yeni araç seçeneği bulunabilir.",
                    additional_matches_unlocked=len(unlocked),
                )
            )

    # 5. Koltuk sayısı esnetme önerisi
    seats_min = criteria.get("seats_min")
    if seats_min and seats_min > 2:
        relaxed_criteria = dict(criteria, seats_min=None)
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if unlocked:
            max_available_seats = max(int(_get_attr(v, "seats")) for v in unlocked)
            suggestions.append(
                RelaxationSuggestion(
                    constraint="seats_min",
                    current_value=seats_min,
                    suggested_value=max_available_seats,
                    message=(
                        f"Minimum koltuk sayısını {max_available_seats} olarak esnetirseniz "
                        f"{len(unlocked)} yeni araç seçeneği açılacaktır."
                    ),
                    additional_matches_unlocked=len(unlocked),
                )
            )

    reason = "Belirttiğiniz sert kısıtlara (bütçe, vites, yakıt, koltuk veya kasa) uyan hiçbir araç bulunamadı."
    explanation = (
        "Seçtiğiniz kriter kombinasyonu mevcut pazar seçeneklerini tamamen daraltmaktadır. "
        "Yukarıdaki esnetme önerilerini değerlendirebilirsiniz."
    )

    return ConflictReport(
        status="conflict",
        has_conflict=True,
        reason=reason,
        conflicting_constraints=conflicting_keys,
        suggestions=suggestions,
        explanation=explanation,
    )


# ==============================================================================
# 4. Ana Öneri Üretim Fonksiyonu
# ==============================================================================

def generate_recommendations(
    preference: Union[Preference, Dict[str, Any]],
    vehicles: Optional[Sequence[Any]] = None,
) -> Union[RecommendationResult, ConflictReport]:
    """Kullanıcı tercihlerini değerlendirerek ilk 5 öneriyi veya çelişki raporunu döner.

    Parametreler:
    - preference: Doğrulanmış ``Preference`` nesnesi (sözlük verilirse doğrulanır).
    - vehicles: Test için opsiyonel araç havuzu (verilmezse ``data/vehicles.csv``'den yüklenir).
    """
    pref = preference if isinstance(preference, Preference) else Preference.model_validate(preference)
    candidate_pool: Sequence[Any] = vehicles if vehicles is not None else load_catalog_vehicles()

    # 1. Sert kısıt filtrelerini Preference.hard_filter_criteria() ile uygula
    criteria = pref.hard_filter_criteria()
    filtered_vehicles, eliminated = evaluate_hard_filters(candidate_pool, criteria)

    # 2. Hiç araç kalmadıysa -> Çelişki raporu (ConflictReport)
    if not filtered_vehicles:
        return _build_conflict_report(candidate_pool, criteria, eliminated)

    # 3. Öncelik ağırlıklarını ScoringPriorities.weights() üzerinden al (low=1, medium=2, high=3)
    weights = pref.priorities.weights()

    # 4. Ağırlıklı puanlama ve sıralama (T22) — sınırlar TAM katalogdan hesaplanır
    catalogue_bounds = compute_catalogue_bounds(candidate_pool)
    ranked_results = score_and_rank_vehicles(
        filtered_vehicles,
        weights=weights,
        custom_bounds=catalogue_bounds,
    )

    # 5. İlk 5 aracı RecommendationItem formatına çevir
    top_5_items: List[RecommendationItem] = []
    for item in ranked_results[:5]:
        v = item["vehicle"]
        sub_scores = item["sub_scores"]
        strengths, weaknesses = _extract_strengths_and_weaknesses(v, sub_scores)

        brand = str(_get_attr(v, "brand"))
        model = str(_get_attr(v, "model"))
        variant = str(_get_attr(v, "variant"))
        year = int(_get_attr(v, "year"))
        price = int(_get_attr(v, "price_try"))
        body_type = str(_get_attr(v, "body_type"))
        fuel_type = str(_get_attr(v, "fuel_type"))
        trans = str(_get_attr(v, "transmission"))
        v_id = int(_get_attr(v, "id"))

        # NFR-04: Eksik veri 0.0 olarak gösterilmez; None olarak bırakılır
        breakdown = ScoreBreakdown(
            fuel_economy=sub_scores.get("fuel_economy"),
            interior_space=sub_scores.get("interior_space"),
            performance=sub_scores.get("performance"),
            budget_fit=sub_scores.get("budget_fit"),
            safety=sub_scores.get("safety"),
        )

        top_5_items.append(
            RecommendationItem(
                rank=item["rank"],
                vehicle_id=v_id,
                brand=brand,
                model=model,
                variant=variant,
                year=year,
                price_try=price,
                body_type=body_type,
                fuel_type=fuel_type,
                transmission=trans,
                score=item["score"],
                score_breakdown=breakdown,
                strengths=strengths,
                weaknesses=weaknesses,
                explanation=_generate_template_explanation(brand, model, strengths),
            )
        )

    applied_filters = {k: v for k, v in criteria.items() if v is not None and v != []}

    return RecommendationResult(
        status="success",
        total_matches=len(filtered_vehicles),
        recommendations=top_5_items,
        applied_filters=applied_filters,
        weights_used=weights,
    )
