"""M3 Ağırlıklı Puanlama Motoru (T22).

Bu modül, sert kısıt filtrelerinden (T21) geçen araçları kullanıcının
önceliklerine göre 0–100 arasında puanlar ve en uygun araçları sıralar.

Temel Prensipler:
1. Min-Max Normalizasyonu: Değerler katalog aralığına göre 0.0 – 1.0 arasına çekilir.
   - Tüketim ve Fiyat için: Düşük olan daha iyi (ters oranlı).
   - İç Hacim, Güç ve Güvenlik için: Yüksek olan daha iyi (doğru orantılı).
2. Ağırlıklı Ortalama:
   - Öncelik seviyeleri: low=1, medium=2, high=3.
   - Formül: Skor = 100 * sum(w_i * s_i) / sum(w_i)
3. Eksik Veri Yönetimi (NFR-04):
   - Eksik veri tahmin edilmez.
   - Verisi eksik olan kriter (örn. Euro NCAP testi olmayan araç),
     hem paydan hem de toplam paydadan çıkarılır. Böylece araç haksız yere cezalandırılmaz.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


# ==============================================================================
# 1. Yardımcı Alan Okuma ve Fiziksel Dönüşüm Fonksiyonları
# ==============================================================================

def _get_val(vehicle: Any, key: str) -> Any:
    """Sözlük veya nesne (Pydantic / SQLAlchemy) üzerinden güvenli alan okur."""
    if isinstance(vehicle, dict):
        return vehicle.get(key)
    return getattr(vehicle, key, None)


def _to_float(val: Any) -> Optional[float]:
    """Değeri float'a dönüştürür; boş veya geçersizse None döner."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_equivalent_consumption(vehicle: Any) -> Optional[float]:
    """Yakıt veya elektrik tüketimini karşılaştırılabilir eşdeğer L/100km değerine çevirir.
    
    Fosil ve hibrit araçlarda: consumption_l_100km (Litre/100km)
    Elektrikli araçlarda: 1 Litre benzin ~ 8.9 kWh enerji eşdeğeridir.
    Örn: 15.6 kWh/100km elektrik tüketimi ≈ 1.75 L/100km eşdeğer fosil tüketimdir.
    """
    fuel_type = str(_get_val(vehicle, "fuel_type") or "").lower()
    
    if fuel_type == "electric":
        kwh = _to_float(_get_val(vehicle, "consumption_kwh_100km"))
        if kwh is not None and kwh > 0:
            return round(kwh / 8.9, 2)
        return None

    # Benzin, dizel veya hibrit için litre tüketimi
    return _to_float(_get_val(vehicle, "consumption_l_100km"))


# ==============================================================================
# 2. Min-Max Normalizasyon Yardımcıları (0.0 - 1.0)
# ==============================================================================

def _normalize_higher_is_better(val: float, min_val: float, max_val: float) -> float:
    """Yüksek değerin daha iyi olduğu kriterler için normalizasyon (Örn: Güç, Hacim).
    
    En yüksek değer = 1.0, En düşük değer = 0.0
    """
    if max_val == min_val:
        return 1.0
    score = (val - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, score))


def _normalize_lower_is_better(val: float, min_val: float, max_val: float) -> float:
    """Düşük değerin daha iyi olduğu kriterler için normalizasyon (Örn: Yakıt tüketimi, Fiyat).
    
    En düşük değer = 1.0, En yüksek değer = 0.0
    """
    if max_val == min_val:
        return 1.0
    score = (max_val - val) / (max_val - min_val)
    return max(0.0, min(1.0, score))


# ==============================================================================
# 3. Kriter Sınırlarını Hesaplama (Min ve Max Tespiti)
# ==============================================================================

def compute_catalogue_bounds(vehicles: Sequence[Any]) -> Dict[str, Tuple[float, float]]:
    """Araç havuzundaki kriterlerin min ve max sınırlarını belirler.
    
    Normalizasyon işlemi bu sınır değerlerine göre yapılır.
    """
    consumptions: List[float] = []
    prices: List[float] = []
    powers: List[float] = []
    spaces: List[float] = []

    for v in vehicles:
        # 1. Tüketim
        cons = _get_equivalent_consumption(v)
        if cons is not None and cons > 0:
            consumptions.append(cons)

        # 2. Fiyat
        price = _to_float(_get_val(v, "price_try"))
        if price is not None and price > 0:
            prices.append(price)

        # 3. Motor Gücü (HP)
        hp = _to_float(_get_val(v, "power_hp"))
        if hp is not None and hp > 0:
            powers.append(hp)

        # 4. İç Hacim (Bagaj + Koltuk Katsayısı)
        trunk = _to_float(_get_val(v, "trunk_l")) or 0.0
        seats = _to_float(_get_val(v, "seats")) or 5.0
        # 1 koltuk yaklaşık 50 Litre hacim değerinde kombine edilir
        combined_space = trunk + (seats * 50.0)
        spaces.append(combined_space)

    # Güvenli varsayılanlar (tek araç olması veya boş olması durumunda sıfıra bölünmeyi önler)
    return {
        "consumption": (min(consumptions), max(consumptions)) if consumptions else (4.0, 10.0),
        "price": (min(prices), max(prices)) if prices else (500000.0, 3000000.0),
        "power": (min(powers), max(powers)) if powers else (70.0, 300.0),
        "space": (min(spaces), max(spaces)) if spaces else (500.0, 1100.0),
    }


# ==============================================================================
# 4. Tek Bir Araç İçin Alt Kriter Puanları (0 - 100)
# ==============================================================================

def calculate_vehicle_sub_scores(
    vehicle: Any,
    bounds: Dict[str, Tuple[float, float]],
) -> Dict[str, Optional[float]]:
    """Bir aracın 5 temel kritere göre 0–100 arasındaki alt puanlarını hesaplar.
    
    Eksik veri varsa o kriterin alt puanı None olarak döner (NFR-04).
    """
    sub_scores: Dict[str, Optional[float]] = {}

    # 1. Yakıt / Enerji Ekonomisi (Düşük tüketim = Yüksek puan)
    cons = _get_equivalent_consumption(vehicle)
    if cons is not None:
        c_min, c_max = bounds["consumption"]
        sub_scores["fuel_economy"] = round(_normalize_lower_is_better(cons, c_min, c_max) * 100.0, 1)
    else:
        sub_scores["fuel_economy"] = None

    # 2. Bütçe Uyumu (Düşük fiyat = Yüksek puan)
    price = _to_float(_get_val(vehicle, "price_try"))
    if price is not None:
        p_min, p_max = bounds["price"]
        sub_scores["budget_fit"] = round(_normalize_lower_is_better(price, p_min, p_max) * 100.0, 1)
    else:
        sub_scores["budget_fit"] = None

    # 3. İç Hacim (Yüksek bagaj ve koltuk = Yüksek puan)
    trunk = _to_float(_get_val(vehicle, "trunk_l"))
    seats = _to_float(_get_val(vehicle, "seats")) or 5.0
    if trunk is not None:
        space = trunk + (seats * 50.0)
        s_min, s_max = bounds["space"]
        sub_scores["interior_space"] = round(_normalize_higher_is_better(space, s_min, s_max) * 100.0, 1)
    else:
        sub_scores["interior_space"] = None

    # 4. Performans (Yüksek motor gücü = Yüksek puan)
    hp = _to_float(_get_val(vehicle, "power_hp"))
    if hp is not None:
        hp_min, hp_max = bounds["power"]
        sub_scores["performance"] = round(_normalize_higher_is_better(hp, hp_min, hp_max) * 100.0, 1)
    else:
        sub_scores["performance"] = None

    # 5. Güvenlik (Euro NCAP Yıldız Puanı: 0-5)
    stars = _to_float(_get_val(vehicle, "euro_ncap_stars"))
    if stars is not None:
        # 5 yıldız = 100.0, 4 yıldız = 80.0, 3 yıldız = 60.0
        sub_scores["safety"] = round(min(1.0, max(0.0, stars / 5.0)) * 100.0, 1)
    else:
        # Eksik veri: Euro NCAP testi olmayan araç
        sub_scores["safety"] = None

    return sub_scores


# ==============================================================================
# 5. Ağırlıklı Toplam Skor ve Araç Sıralama
# ==============================================================================

def calculate_vehicle_total_score(
    sub_scores: Dict[str, Optional[float]],
    weights: Dict[str, int],
) -> float:
    """Verisi mevcut kriterler üzerinden ağırlıklı genel skoru (0–100) hesaplar.
    
    Kural (NFR-04): Verisi eksik (None) olan kriter hem paydan hem paydadan düşülür!
    Formül: toplam_puan = sum(w_i * s_i) / sum(w_i)
    """
    total_weighted_points = 0.0
    total_active_weight = 0

    for criterion, score in sub_scores.items():
        if score is not None:
            # Öncelik ağırlığı (Varsayılan 2 - medium)
            w = weights.get(criterion, 2)
            total_weighted_points += w * score
            total_active_weight += w

    if total_active_weight == 0:
        return 0.0

    return round(total_weighted_points / total_active_weight, 1)


def score_and_rank_vehicles(
    vehicles: Sequence[Any],
    weights: Optional[Dict[str, int]] = None,
    custom_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
) -> List[Dict[str, Any]]:
    """Araç listesini puanlar ve en yüksek puandan en düşüğe doğru sıralar.
    
    Parametreler:
    - vehicles: Puanlanacak araçlar listesi (sözlük veya nesne).
    - weights: Kriterlerin ağırlıkları (Örn: {"fuel_economy": 3, "budget_fit": 2}).
               Verilmezse tüm kriterlerin ağırlığı eşit (2) kabul edilir.
    - custom_bounds: İsteğe bağlı katalog sınırları. Verilmezse liste içinden hesaplanır.
    
    Dönüş:
    Her araç için sıralanmış liste:
    [
        {
            "vehicle": araç_nesnesi,
            "rank": 1,
            "score": 86.4,
            "sub_scores": {
                "fuel_economy": 92.0,
                "interior_space": 75.0,
                "performance": 78.0,
                "budget_fit": 88.0,
                "safety": 100.0
            }
        }, ...
    ]
    """
    if not vehicles:
        return []

    active_weights = {
        "fuel_economy": 2,
        "interior_space": 2,
        "performance": 2,
        "budget_fit": 2,
        "safety": 2,
    }
    if weights:
        active_weights.update(weights)

    bounds = custom_bounds or compute_catalogue_bounds(vehicles)

    scored_items: List[Dict[str, Any]] = []
    for vehicle in vehicles:
        sub_scores = calculate_vehicle_sub_scores(vehicle, bounds)
        total_score = calculate_vehicle_total_score(sub_scores, active_weights)

        scored_items.append({
            "vehicle": vehicle,
            "score": total_score,
            "sub_scores": sub_scores,
        })

    # Puanı en yüksek olan ilk sıraya gelecek şekilde sıralama
    scored_items.sort(key=lambda item: item["score"], reverse=True)

    # Sıralama numaralarını (rank: 1, 2, 3...) atama
    for index, item in enumerate(scored_items, start=1):
        item["rank"] = index

    return scored_items
