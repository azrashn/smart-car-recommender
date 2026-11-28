# AutoMatch — API Contract

> **Status:** Draft v0.1 — 2026-11-17  
> **Branch:** `feat/T10-fatih-preference-schema`  
> **Author:** @fatihoguzkaya (M2)  
>
> Sections marked **DRAFT – owner to confirm** contain placeholder schemas
> whose authoritative definition belongs to another module owner.
> **Do not implement against DRAFT sections** until the owner approves them.

---

## Table of Contents

1. [Base URL & conventions](#1-base-url--conventions)
2. [Shared error format](#2-shared-error-format)
3. [GET /api/vehicles](#3-get-apivehicles)
4. [GET /api/vehicles/{id}](#4-get-apivehiclesid)
5. [POST /api/preferences/form](#5-post-apipreferencesform)
6. [POST /api/preferences/text](#6-post-apipreferencestext)
7. [POST /api/recommendations](#7-post-apirecommendations)
8. [GET /api/compare](#8-get-apicompare)
9. [POST /api/scenarios](#9-post-apiscenarios)

---

## 1. Base URL & conventions

| Item | Value |
|---|---|
| Local base URL | `http://127.0.0.1:8000` |
| Content-Type | `application/json` (all request and response bodies) |
| Character encoding | UTF-8 |
| Enum case | All enum values are **lowercase** (e.g. `"petrol"`, `"suv"`) |
| Currency | Turkish Lira, integer TRY (no decimals) |
| Empty filter list | An empty array `[]` for multi-value filter fields means **no preference** (all values pass) |

---

## 2. Shared error format

AutoMatch uses **FastAPI's default error format** without any custom exception handlers.

### 422 Unprocessable Entity — Pydantic validation failure

FastAPI wraps Pydantic v2 errors in a `detail` array. Each item identifies the
failing field (`loc`), a human-readable message (`msg`), and an error type (`type`).

```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "budget_max_try"],
      "msg": "Input should be greater than 0",
      "input": -100000,
      "ctx": {"gt": 0}
    }
  ]
}
```

For cross-field validators (e.g. `budget_min_try > budget_max_try`) the `loc`
points to the model root:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, budget_min_try (1800000) must be <= budget_max_try (1500000)",
      "input": {"budget_max_try": 1500000, "budget_min_try": 1800000},
      "ctx": {"error": "budget_min_try (1800000) must be <= budget_max_try (1500000)"}
    }
  ]
}
```

### 404 Not Found

```json
{
  "detail": "Vehicle with id=99 not found."
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error."
}
```

---

## 3. GET /api/vehicles

**Owner:** @Belisozcelik (M1)

> [!NOTE]
> DRAFT – M1 owner to confirm field names, pagination style, and filter params.

Returns the filtered vehicle catalogue.

### Query parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fuel_type` | string | No | Filter by fuel type (`petrol`, `diesel`, `hybrid`, `electric`) |
| `body_type` | string | No | Filter by body type (`hatchback`, `sedan`, `suv`, `wagon`, `mpv`) |
| `transmission` | string | No | Filter by transmission (`manual`, `automatic`) |
| `max_price` | integer | No | Maximum price in TRY |
| `limit` | integer | No | Max results to return (default 20) |
| `offset` | integer | No | Pagination offset (default 0) |

### Response `200 OK` — DRAFT

```json
{
  "total": 40,
  "items": [
    {
      "id": 3,
      "brand": "Toyota",
      "model": "Corolla",
      "variant": "1.8 Hybrid Dream",
      "year": 2024,
      "body_type": "sedan",
      "fuel_type": "hybrid",
      "transmission": "automatic",
      "consumption_l_100km": 4.5,
      "consumption_kwh_100km": null,
      "range_km": null,
      "power_hp": 140,
      "seats": 5,
      "trunk_l": 471,
      "euro_ncap_stars": 5,
      "price_try": 1820000,
      "price_checked_at": "2026-11-16",
      "spec_source_url": "https://www.toyota.com.tr/modeller/corolla",
      "price_source_url": "https://www.toyota.com.tr/fiyat-listesi"
    }
  ]
}
```

---

## 4. GET /api/vehicles/{id}

**Owner:** @Belisozcelik (M1)

> [!NOTE]
> DRAFT – M1 owner to confirm. Same Vehicle object shape as above, single item.

### Path parameter

| Parameter | Type | Description |
|---|---|---|
| `id` | integer | Vehicle ID from the catalogue |

### Response `200 OK` — DRAFT

```json
{
  "id": 3,
  "brand": "Toyota",
  "model": "Corolla",
  "variant": "1.8 Hybrid Dream",
  "year": 2024,
  "body_type": "sedan",
  "fuel_type": "hybrid",
  "transmission": "automatic",
  "consumption_l_100km": 4.5,
  "consumption_kwh_100km": null,
  "range_km": null,
  "power_hp": 140,
  "seats": 5,
  "trunk_l": 471,
  "euro_ncap_stars": 5,
  "price_try": 1820000,
  "price_checked_at": "2026-11-16",
  "spec_source_url": "https://www.toyota.com.tr/modeller/corolla",
  "price_source_url": "https://www.toyota.com.tr/fiyat-listesi"
}
```

### Response `404 Not Found`

```json
{
  "detail": "Vehicle with id=99 not found."
}
```

---

## 5. POST /api/preferences/form

**Owner:** @fatihoguzkaya (M2) — **CONFIRMED**

Accepts a fully completed survey form and returns a validated `Preference` object.
Used by the step-by-step form UI (T11, T12).

### Request body

The body is the `Preference` schema defined in `app/schemas/preference.py`.
All fields except `budget_max_try` are optional.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `budget_max_try` | integer | **Yes** | > 0 | Maximum purchase price in TRY |
| `budget_min_try` | integer | No | ≥ 0, ≤ `budget_max_try` | Minimum purchase price in TRY |
| `usage_type` | string | No | `city` \| `highway` \| `mixed` \| `family` | Primary driving context |
| `annual_km` | integer | No | 1 000 – 200 000 | Expected annual mileage (km) |
| `transmission` | string | No | `manual` \| `automatic` \| `null` | Required transmission; `null` = no preference |
| `fuel_types` | array[string] | No | subset of `petrol`,`diesel`,`hybrid`,`electric` | Empty = no preference |
| `body_types` | array[string] | No | subset of `hatchback`,`sedan`,`suv`,`wagon`,`mpv` | Empty = no preference |
| `min_seats` | integer | No | 2 – 9 | Minimum seat count |
| `priorities` | object | No | see below | Per-criterion importance weights |
| `priorities.fuel_economy` | string | No | `low`\|`medium`\|`high` | Default `medium` |
| `priorities.interior_space` | string | No | `low`\|`medium`\|`high` | Default `medium` |
| `priorities.performance` | string | No | `low`\|`medium`\|`high` | Default `medium` |
| `priorities.budget_fit` | string | No | `low`\|`medium`\|`high` | Default `medium` |
| `priorities.safety` | string | No | `low`\|`medium`\|`high` | Default `medium` |
| `language` | string | No | `tr` \| `en` | Default `tr` |

Unknown extra fields are **rejected** (`extra="forbid"`).

### Request example

```json
{
  "budget_max_try": 2000000,
  "budget_min_try": 1500000,
  "usage_type": "family",
  "annual_km": 25000,
  "transmission": "automatic",
  "fuel_types": ["petrol", "hybrid"],
  "body_types": ["suv"],
  "min_seats": 5,
  "priorities": {
    "fuel_economy": "medium",
    "interior_space": "high",
    "performance": "low",
    "budget_fit": "medium",
    "safety": "high"
  },
  "language": "tr"
}
```

### Response `200 OK`

The endpoint echoes back the validated and normalised `Preference` object; normalisation only removes duplicate values from `fuel_types` and `body_types` (first occurrence order is kept).

```json
{
  "budget_max_try": 2000000,
  "budget_min_try": 1500000,
  "usage_type": "family",
  "annual_km": 25000,
  "transmission": "automatic",
  "fuel_types": ["petrol", "hybrid"],
  "body_types": ["suv"],
  "min_seats": 5,
  "priorities": {
    "fuel_economy": "medium",
    "interior_space": "high",
    "performance": "low",
    "budget_fit": "medium",
    "safety": "high"
  },
  "language": "tr"
}
```

### Response `422 Unprocessable Entity`

Returned when `budget_min_try > budget_max_try`, a value is out of range,
or an unknown field is present.
FastAPI default format (see §2):

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, budget_min_try (1800000) must be <= budget_max_try (1500000)",
      "input": {"budget_max_try": 1500000, "budget_min_try": 1800000},
      "ctx": {"error": "budget_min_try (1800000) must be <= budget_max_try (1500000)"}
    }
  ]
}
```

---

## 6. POST /api/preferences/text

**Owner:** @fatihoguzkaya (M2) — **CONFIRMED**

Accepts a free-text description in Turkish or English and extracts a `PreferenceDraft`
object from it using a rule-based parser (T13) or the AI layer (T31).
Fields that cannot be inferred from the text (including `budget_max_try` when omitted by the user)
are listed in `missing_fields`.

> [!NOTE]
> **Graceful Degradation (NFR-02):**  
> If the AI provider is unavailable (e.g. `GEMINI_API_KEY` not configured, provider set to `none`,
> rate limit hit, or upstream error), the endpoint silently falls back to the rule-based extractor
> and returns `method: "rule"`. It **never** returns `503 Service Unavailable`.

### Request body

```json
{
  "text": "Şehir içinde kullanacağım, otomatik vites, az yakan bir SUV arıyorum.",
  "language": "tr"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | **Yes** | Free-text user input (1 – 2 000 characters) |
| `language` | string | No | `tr` \| `en`, default `tr`. Hint for the parser. |

### Response `200 OK` — `TextExtractionResult`

The returned `preference` object uses the `PreferenceDraft` schema (all fields optional).
When mandatory fields (such as `budget_max_try`) are absent from the free text, they are set to `null`
and listed in `missing_fields`.

```json
{
  "preference": {
    "budget_max_try": null,
    "budget_min_try": null,
    "usage_type": "city",
    "annual_km": null,
    "transmission": "automatic",
    "fuel_types": [],
    "body_types": ["suv"],
    "min_seats": null,
    "priorities": {
      "fuel_economy": "high",
      "interior_space": "medium",
      "performance": "medium",
      "budget_fit": "medium",
      "safety": "medium"
    },
    "language": "tr"
  },
  "missing_fields": ["budget_max_try", "annual_km"],
  "method": "rule"
}
```

| Field | Type | Description |
|---|---|---|
| `preference` | PreferenceDraft | Extracted preference draft (all fields optional; defaults fill undetected priorities/language) |
| `missing_fields` | array[string] | Preference field names that could not be inferred from the text. The frontend prompts the user for these (FR-05) before submitting the finalized `Preference` to `POST /api/recommendations`. |
| `method` | string | `"ai"` or `"rule"` — which extractor was used |

> [!TIP]
> **Workflow (FR-05):**  
> 1. User submits free text to `POST /api/preferences/text`.
> 2. Backend returns `TextExtractionResult` containing a `PreferenceDraft` and `missing_fields`.
> 3. If `budget_max_try` (or any other required field) is in `missing_fields`, the frontend asks the user to fill it in.
> 4. Once `budget_max_try` is supplied, the draft is converted to a complete `Preference` and submitted to `POST /api/recommendations`.

### Response `422 Unprocessable Entity`

FastAPI default format (see §2):

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "text"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

---

## 7. POST /api/recommendations

**Owner:** @karya-karya (M3)

> [!NOTE]
> DRAFT – M3 owner (@karya-karya) to confirm. Schema source:
> `app/schemas/recommendation.py` (already committed on main).

Applies hard-constraint filters to the catalogue, scores passing vehicles
with weighted criteria, and returns the top 5 results — or a conflict report
if no vehicle passes all constraints.

### Request body

A `Preference` object directly in the request body (no session or token).
The engine reads:
- **Hard filters:** `budget_max_try`, `transmission`, `fuel_types`, `body_types`, `min_seats`
- **Scoring weights:** `priorities` (via `ScoringPriorities.weights()`)
- **Cost estimate:** `annual_km` (passed to M5)

```json
{
  "budget_max_try": 2000000,
  "transmission": "automatic",
  "fuel_types": ["petrol", "hybrid"],
  "body_types": ["suv"],
  "min_seats": 5,
  "priorities": {
    "fuel_economy": "high",
    "interior_space": "high",
    "performance": "low",
    "budget_fit": "medium",
    "safety": "high"
  },
  "annual_km": 20000,
  "language": "tr"
}
```

### Response `200 OK` — `RecommendationResult` — DRAFT

```json
{
  "status": "success",
  "total_matches": 4,
  "recommendations": [
    {
      "rank": 1,
      "vehicle_id": 3,
      "brand": "Toyota",
      "model": "Corolla",
      "variant": "1.8 Hybrid Dream",
      "year": 2024,
      "price_try": 1820000,
      "body_type": "sedan",
      "fuel_type": "hybrid",
      "transmission": "automatic",
      "score": 86.4,
      "score_breakdown": {
        "fuel_economy": 92.0,
        "interior_space": 75.0,
        "performance": 78.0,
        "budget_fit": 88.0,
        "safety": 100.0
      },
      "strengths": ["Düşük yakıt tüketimi (4.5 L/100km)", "5 yıldızlı Euro NCAP"],
      "weaknesses": ["Ortalama bagaj hacmi (471 L)"],
      "explanation": "Toyota Corolla Hybrid, önceliklerinize en uygun dengeli seçenektir.",
      "estimated_annual_cost_try": 31500.0
    }
  ],
  "applied_filters": {
    "budget_max": 2000000,
    "transmission": "automatic",
    "seats_min": 5
  },
  "weights_used": {
    "fuel_economy": 3,
    "interior_space": 3,
    "performance": 1,
    "budget_fit": 2,
    "safety": 3
  }
}
```

### Response `200 OK` — `ConflictReport` (no matches) — DRAFT

```json
{
  "status": "conflict",
  "has_conflict": true,
  "reason": "Belirttiğiniz kriterlere uyan hiçbir araç bulunamadı.",
  "conflicting_constraints": ["budget_max", "fuel_type"],
  "suggestions": [
    {
      "constraint": "budget_max",
      "current_value": 1500000,
      "suggested_value": 1790000,
      "message": "Bütçenizi 1.790.000 TL'ye çıkarırsanız BYD Atto 3 açılır.",
      "additional_matches_unlocked": 1
    }
  ],
  "explanation": "Piyasada 1.500.000 TL altında elektrikli SUV bulunmamaktadır."
}
```

---

## 8. GET /api/compare

**Owner:** @SudeKarakoc1 (M5)

Returns a side-by-side comparison of 2–3 vehicles with their estimated annual energy cost
(FR-10, FR-11). Vehicles are returned in the same order as in `ids`.

### Query parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `ids` | string | **Yes** | Comma-separated vehicle IDs, e.g. `1,2,3` (2–3 IDs). Spaces are allowed (`1, 2`). |
| `annual_km` | integer | No | Annual distance in km; default `15000`, allowed `0`–`1000000`. `0` is valid and gives a cost of `0`. |
| `petrol_price_try` | number | No | Petrol price in TRY per litre (also used for hybrids); `0`–`10000`; default from `app/cost/defaults.py` |
| `diesel_price_try` | number | No | Diesel price in TRY per litre; `0`–`10000`; default from `app/cost/defaults.py` |
| `electricity_price_try` | number | No | Electricity price in TRY per kWh; `0`–`10000`; default from `app/cost/defaults.py` |

### Error rules

| Case | Status |
|---|---|
| `ids` missing | `422` (FastAPI default format, see §2) |
| 1 ID, or 4 or more IDs | `422` |
| Duplicate ID (e.g. `1,1`) | `422` |
| Invalid ID format: empty item (`1,,2`), non-integer (`1,abc`), ID < 1 (`0,1`, `-1,2`) | `422` |
| `annual_km` or a price outside its allowed range | `422` (FastAPI default format, see §2) |
| One or more IDs not in the catalogue | `404` |

There is **no silent truncation**: extra IDs are an error, never dropped.

### Response `200 OK` — `CompareResponse`

```json
{
  "vehicles": [
    {
      "id": 2,
      "brand": "Hyundai",
      "model": "i20",
      "variant": "1.0 T-GDI 90 PS 7DCT Jump",
      "year": 2026,
      "body_type": "hatchback",
      "fuel_type": "petrol",
      "transmission": "automatic",
      "price_try": 1759000,
      "price_checked_at": "2026-11-19",
      "consumption_l_100km": 6.3,
      "consumption_kwh_100km": null,
      "power_hp": 90,
      "seats": 5,
      "trunk_l": 352,
      "euro_ncap_stars": 4,
      "spec_source_url": "https://www.hyundai.com/...",
      "price_source_url": "https://www.hyundai.com/tr/tr/satis/fiyat-listesi.html",
      "annual_cost_try": 64666
    },
    {
      "id": 4,
      "brand": "Opel",
      "model": "Astra",
      "variant": "1.5 130 HP Dizel AT8 Edition",
      "year": 2026,
      "body_type": "hatchback",
      "fuel_type": "diesel",
      "transmission": "automatic",
      "price_try": 2350000,
      "price_checked_at": "2026-11-19",
      "consumption_l_100km": 4.9,
      "consumption_kwh_100km": null,
      "power_hp": 130,
      "seats": 5,
      "trunk_l": null,
      "euro_ncap_stars": null,
      "spec_source_url": "https://www.opel.com.tr/...",
      "price_source_url": "https://fiyatlisteleri.opel.com.tr/tum-araclar",
      "annual_cost_try": 62181
    }
  ],
  "differences": {
    "price_try": [2],
    "annual_cost_try": [4],
    "power_hp": [4],
    "trunk_l": [],
    "seats": [],
    "euro_ncap_stars": []
  },
  "assumptions": {
    "annual_km": 15000,
    "petrol_price_try": 68.43,
    "diesel_price_try": 84.6,
    "electricity_price_try": 9.95,
    "prices_checked_at": "2026-11-27"
  }
}
```

**Notes**

- `annual_cost_try = annual_km / 100 × consumption × unit price`, rounded half up to an
  integer TRY. Electric vehicles use `consumption_kwh_100km` and the electricity price;
  all others use `consumption_l_100km`. Units are never converted.
- Hybrids use the **petrol** price.
- If a vehicle has no consumption value, `annual_cost_try` is `null` (never `0`, NFR-04),
  even when `annual_km` is `0`.
- `differences` maps a field name to the IDs of the vehicles with the best value. It only
  contains unit-independent fields: lower is better for `price_try` and `annual_cost_try`;
  higher is better for `power_hp`, `trunk_l`, `seats` and `euro_ncap_stars`. Consumption
  fields are **not** compared (L/100 km and kWh/100 km are different units).
- In `differences`, vehicles with a `null` value are skipped. The list is empty when fewer
  than two vehicles have a value or when all values are equal. On a tie for the best value
  (but not all equal), every tied ID is listed.
- `assumptions` echoes the inputs actually used. Default prices are example values from
  `app/cost/defaults.py`; the UI shows them as "example price, checked on
  `prices_checked_at`".

### Response `404 Not Found`

```json
{
  "detail": "Vehicles not found: [999999]"
}
```

### Response `422 Unprocessable Entity`

Invalid `ids` values return a plain message:

```json
{
  "detail": "ids must contain 2 to 3 vehicle IDs."
}
```

A missing `ids` parameter or an out-of-range `annual_km` / price uses the FastAPI default
format (see §2):

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "annual_km"],
      "msg": "Input should be greater than or equal to 0",
      "input": "-1",
      "ctx": {"ge": 0}
    }
  ]
}
```

---

## 9. POST /api/scenarios

**Owner:** @azrashn (M6)

> [!NOTE]
> DRAFT – M6 owner (@azrashn) to confirm. The request body extends `Preference`
> with scenario-specific overrides; the response mirrors `RecommendationResult`.

Reruns the recommendation engine with overridden `annual_km`, fuel price,
and/or priority weights — without re-submitting the full preference form.
Designed for Scenario Lab live sliders (T41, T42).

### Request body — DRAFT

```json
{
  "preference": {
    "budget_max_try": 2000000,
    "transmission": "automatic",
    "fuel_types": ["petrol", "hybrid"],
    "priorities": {
      "fuel_economy": "high",
      "interior_space": "medium",
      "performance": "low",
      "budget_fit": "high",
      "safety": "medium"
    },
    "annual_km": 20000,
    "language": "tr"
  },
  "overrides": {
    "annual_km": 40000,
    "fuel_price_try": 55.0,
    "priorities": {
      "fuel_economy": "high",
      "budget_fit": "low"
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `preference` | Preference | Base preference (from form or text endpoint) |
| `overrides.annual_km` | integer | Override annual mileage for cost recalculation |
| `overrides.fuel_price_try` | number | Override fuel price (TRY/litre or TRY/kWh) |
| `overrides.priorities` | object | Partial priority override; unset keys keep base values |

### Response `200 OK` — `RecommendationResult` — DRAFT

Same shape as §7 `RecommendationResult`. Rankings may differ from the
base recommendation due to the applied overrides.

```json
{
  "status": "success",
  "total_matches": 4,
  "recommendations": [
    {
      "rank": 1,
      "vehicle_id": 3,
      "brand": "Toyota",
      "model": "Corolla",
      "variant": "1.8 Hybrid Dream",
      "score": 91.2,
      "score_breakdown": {
        "fuel_economy": 95.0,
        "interior_space": 75.0,
        "performance": 78.0,
        "budget_fit": 88.0,
        "safety": 100.0
      },
      "strengths": ["Yüksek yıllık km'de hibrit avantajı"],
      "weaknesses": [],
      "explanation": null,
      "estimated_annual_cost_try": 63000.0
    }
  ],
  "applied_filters": {
    "budget_max": 2000000,
    "transmission": "automatic"
  },
  "weights_used": {
    "fuel_economy": 3,
    "interior_space": 2,
    "performance": 1,
    "budget_fit": 1,
    "safety": 2
  }
}
```

---

## Appendix A — Priority weight mapping

| `Priority` value | Numeric weight (M3) |
|---|---|
| `low` | 1 |
| `medium` | 2 |
| `high` | 3 |

Helper: `app.schemas.preference.priority_weight(Priority.high)` → `3`

## Appendix B — Enum reference

| Field | Allowed values |
|---|---|
| `fuel_type` / `fuel_types` | `petrol`, `diesel`, `hybrid`, `electric` |
| `body_type` / `body_types` | `hatchback`, `sedan`, `suv`, `wagon`, `mpv` |
| `transmission` | `manual`, `automatic` |
| `usage_type` | `city`, `highway`, `mixed`, `family` |
| `priorities.*` | `low`, `medium`, `high` |
| `language` | `tr`, `en` |
| `method` (TextExtractionResult) | `ai`, `rule` |

> [!IMPORTANT]
> **Source of enum values:**  
> Since `data/vehicles.csv` is part of M1/T01 (which has not yet been merged into main),
> the authoritative enum values were extracted directly from `tests/fixtures/sample_vehicles.csv`
> and cross-verified against `app/engine/filters.py` and `docs/algorithm.md`.
> When `data/vehicles.csv` is populated, its values must remain identical to these.

## Appendix C — Team coordination notes

### Resolved decisions

| # | Topic | Decision |
|---|---|---|
| R1 | `POST /api/recommendations` request body | **Direct Preference body.** Stateless; no session or token is used. |
| R2 | `/api/preferences/text` AI fallback | **Silent fallback to rule-based parser (NFR-02).** Returns `method: "rule"` with HTTP 200 when AI is unconfigured or fails. No 503 error. |
| R3 | `/api/preferences/text` partial extraction | **PreferenceDraft model.** Returns `PreferenceDraft` where all fields (including `budget_max_try`) are optional. Missing fields are reported in `missing_fields`. Frontend prompts the user before converting to `Preference` and calling `POST /api/recommendations`. |

### Open questions

| # | Question | Affects | Owner |
|---|---|---|---|
| 1 | `transmission` in Preference is currently a **single value** (`manual`\|`automatic`\|`null`), matching `filter_by_transmission` in `filters.py` which takes a single string. If M3 needs to accept *multiple* transmissions (e.g. `["manual","automatic"]`), the field must change to `list[Literal[...]]`. | M2, M3 | @karya-karya, @fatihoguzkaya |
| 2 | `POST /api/scenarios` overrides only partial priorities. Should unset priority keys fall back to the base preference, or always to `medium`? | M2, M6 | @azrashn, @fatihoguzkaya |

**Resolved**

- Q3: 2-3 vehicles; 1 or 4+ returns 422, no silent truncation.
