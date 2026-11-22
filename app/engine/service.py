"""M3 Öneri Servisi (T25).

Bu servis, kullanıcı tercihlerini (Preference) alarak:
1. Sert kısıt filtrelerini (T21) uygular.
2. Eşleşen araç yoksa çelişki analizi yaparak ConflictReport ve esnetme önerileri üretir.
3. Eşleşen araçlar varsa ağırlıklı puanlama (T22) ile en yüksek puanlı ilk 5 aracı seçer.
4. Güçlü/zayıf yan etiketlerini ve şablon açıklamasını ekleyerek RecommendationResult döner.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from app.engine.filters import evaluate_hard_filters
from app.engine.scoring import score_and_rank_vehicles
from app.schemas.recommendation import (
    ConflictReport,
    RecommendationItem,
    RecommendationResult,
    RelaxationSuggestion,
    ScoreBreakdown,
)


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


# ==============================================================================
# 1. Araç Verisini Yükleme (Veritabanı veya Fixture Yedeği)
# ==============================================================================

def load_catalog_vehicles() -> List[Dict[str, Any]]:
    """Katalogdaki araçları yükler.
    
    Veritabanı (T04) henüz hazır değilse tests/fixtures/sample_vehicles.csv dosyasından okur.
    Böylece API her zaman çalışır durumda kalır.
    """
    csv_path = FIXTURES_DIR / "sample_vehicles.csv"
    if not csv_path.exists():
        # Alternatif yol kontrolü (data/vehicles.csv)
        data_csv = Path(__file__).resolve().parent.parent.parent / "data" / "vehicles.csv"
        if data_csv.exists():
            csv_path = data_csv

    vehicles: List[Dict[str, Any]] = []
    if csv_path.exists():
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["id"] = int(row["id"])
                    row["year"] = int(row["year"])
                    row["price_try"] = int(row["price_try"])
                    row["seats"] = int(row["seats"])
                    row["power_hp"] = int(row["power_hp"]) if row.get("power_hp") else None
                    row["trunk_l"] = int(row["trunk_l"]) if row.get("trunk_l") else None
                    row["euro_ncap_stars"] = int(row["euro_ncap_stars"]) if row.get("euro_ncap_stars") else None
                    vehicles.append(row)
                except (ValueError, TypeError):
                    continue
    return vehicles


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

    # En az 1 güçlü yön garantisi
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
        # Bütçe hariç diğer kriterleri sağlayan araçlara bak
        without_budget = dict(criteria, budget_max=None)
        candidates_without_budget, _ = evaluate_hard_filters(vehicles, without_budget)
        if candidates_without_budget:
            cheapest = min(
                candidates_without_budget,
                key=lambda x: int(x.get("price_try") if isinstance(x, dict) else getattr(x, "price_try", 99999999)),
            )
            cheapest_price = int(cheapest.get("price_try") if isinstance(cheapest, dict) else getattr(cheapest, "price_try"))
            if cheapest_price > budget_max:
                suggestions.append(
                    RelaxationSuggestion(
                        constraint="budget_max",
                        current_value=budget_max,
                        suggested_value=cheapest_price,
                        message=f"Bütçenizi {cheapest_price:,} TL seviyesine çıkarırsanız en az 1 araç seçeneği açılacaktır.",
                        additional_matches_unlocked=len([c for c in candidates_without_budget if int(c.get("price_try") if isinstance(c, dict) else getattr(c, "price_try")) <= cheapest_price]),
                    )
                )

    # 2. Yakıt türü esnetme önerisi
    fuel_types = criteria.get("fuel_types") or criteria.get("fuel_type")
    if fuel_types and fuel_types != "any":
        relaxed_criteria = dict(criteria, fuel_types=None, fuel_type=None)
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if len(unlocked) > 0:
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
        relaxed_criteria = dict(criteria, transmission="any")
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if len(unlocked) > 0:
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
    body_types = criteria.get("body_types") or criteria.get("body_type")
    if body_types and body_types != "any":
        relaxed_criteria = dict(criteria, body_types=None, body_type=None)
        unlocked, _ = evaluate_hard_filters(vehicles, relaxed_criteria)
        if len(unlocked) > 0:
            suggestions.append(
                RelaxationSuggestion(
                    constraint="body_types",
                    current_value=body_types,
                    suggested_value="any",
                    message=f"Farklı kasa tiplerini de değerlendirirseniz {len(unlocked)} yeni araç seçeneği bulunabilir.",
                    additional_matches_unlocked=len(unlocked),
                )
            )

    reason = "Belirttiğiniz sert kısıtlara (bütçe, vites, yakıt veya kasa) uyan hiçbir araç bulunamadı."
    explanation = "Seçtiğiniz kriter kombinasyonu mevcut pazar seçeneklerini tamamen daraltmaktadır. Yukarıdaki esnetme önerilerini değerlendirebilirsiniz."

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
    preference: Any,
    vehicles: Optional[List[Any]] = None,
) -> Union[RecommendationResult, ConflictReport]:
    """Kullanıcı tercihlerini değerlendirerek ilk 5 öneriyi veya çelişki raporunu döner.
    
    Parametreler:
    - preference: Pydantic Preference nesnesi veya sözlük.
    - vehicles: Test için opsiyonel araç havuzu (verilmezse katalogdan yüklenir).
    """
    candidate_pool = vehicles if vehicles is not None else load_catalog_vehicles()

    # Tercih verisini güvenli sözlüğe normalize etme
    pref_dict: Dict[str, Any] = {}
    if hasattr(preference, "model_dump"):
        pref_dict = preference.model_dump()
    elif hasattr(preference, "dict"):
        pref_dict = preference.dict()
    elif isinstance(preference, dict):
        pref_dict = dict(preference)

    # Filtre kriterlerini çıkarma
    budget = pref_dict.get("budget_max_try") or pref_dict.get("budget_max")
    transmission = pref_dict.get("transmission")
    fuel_types = pref_dict.get("fuel_types") or pref_dict.get("fuel_type")
    body_types = pref_dict.get("body_types") or pref_dict.get("body_type")
    seats_min = pref_dict.get("seats_min")

    criteria = {
        "budget_max": budget,
        "transmission": transmission,
        "fuel_types": fuel_types,
        "body_types": body_types,
        "seats_min": seats_min,
    }

    # 1. Sert kısıt filtrelerini uygula
    filtered_vehicles, eliminated = evaluate_hard_filters(candidate_pool, criteria)

    # 2. Hiç araç kalmadıysa -> Çelişki raporu (ConflictReport)
    if not filtered_vehicles:
        return _build_conflict_report(candidate_pool, criteria, eliminated)

    # 3. Öncelik ağırlıklarını belirle (low=1, medium=2, high=3)
    raw_weights = pref_dict.get("priorities") or pref_dict.get("weights") or {}
    weights: Dict[str, int] = {}
    weight_map = {"low": 1, "medium": 2, "high": 3}

    for key, val in raw_weights.items():
        if isinstance(val, str) and val.lower() in weight_map:
            weights[key] = weight_map[val.lower()]
        elif isinstance(val, (int, float)):
            weights[key] = int(val)

    # 4. Ağırlıklı puanlama ve sıralama (T22)
    ranked_results = score_and_rank_vehicles(filtered_vehicles, weights=weights)

    # 5. İlk 5 aracı RecommendationItem formatına çevir
    top_5_items: List[RecommendationItem] = []
    for item in ranked_results[:5]:
        v = item["vehicle"]
        sub_scores = item["sub_scores"]
        strengths, weaknesses = _extract_strengths_and_weaknesses(v, sub_scores)

        brand = str(v.get("brand") if isinstance(v, dict) else getattr(v, "brand"))
        model = str(v.get("model") if isinstance(v, dict) else getattr(v, "model"))
        variant = str(v.get("variant") if isinstance(v, dict) else getattr(v, "variant"))
        year = int(v.get("year") if isinstance(v, dict) else getattr(v, "year"))
        price = int(v.get("price_try") if isinstance(v, dict) else getattr(v, "price_try"))
        body_type = str(v.get("body_type") if isinstance(v, dict) else getattr(v, "body_type"))
        fuel_type = str(v.get("fuel_type") if isinstance(v, dict) else getattr(v, "fuel_type"))
        trans = str(v.get("transmission") if isinstance(v, dict) else getattr(v, "transmission"))
        v_id = int(v.get("id") if isinstance(v, dict) else getattr(v, "id"))

        breakdown = ScoreBreakdown(
            fuel_economy=sub_scores.get("fuel_economy") or 0.0,
            interior_space=sub_scores.get("interior_space") or 0.0,
            performance=sub_scores.get("performance") or 0.0,
            budget_fit=sub_scores.get("budget_fit") or 0.0,
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

    return RecommendationResult(
        status="success",
        total_matches=len(filtered_vehicles),
        recommendations=top_5_items,
        applied_filters={k: v for k, v in criteria.items() if v is not None},
        weights_used=weights or {"default": 2},
    )
