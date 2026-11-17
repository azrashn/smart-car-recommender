# M3 Recommendation Engine — Hard Constraint Filters

> **Module:** M3 — Recommendation Engine (`app/engine/`)  
> **Author:** @karya-karya  
> **Related tasks:** T21 (hard filters), T22 (weighted scoring), T24 (conflict detection)

---

## 1. Overview

The filter layer is the first stage of the recommendation pipeline. It eliminates vehicles that **absolutely cannot** satisfy the user's requirements, before any scoring takes place.

All filter functions are **pure**: they receive input data and return a filtered list. They do not read from or write to a database, make network calls, or rely on global state.

---

## 2. Filter Functions

Filters are implemented in `app/engine/filters.py`.

### 2.1 Budget Filter — `filter_by_budget`

```
Keeps: vehicle.price_try <= budget_max
```

| Parameter | Type | Description |
|---|---|---|
| `vehicles` | list | Candidate vehicle list |
| `budget_max` | int | Maximum purchase price in TRY |

If `budget_max` is `None` or ≤ 0, the filter is skipped (all vehicles pass).

### 2.2 Transmission Filter — `filter_by_transmission`

```
Keeps: vehicle.transmission == transmission
```

| Parameter | Type | Accepted values |
|---|---|---|
| `transmission` | str | `"manual"`, `"automatic"` |

If `transmission` is `None`, empty, or `"any"`, the filter is skipped.

### 2.3 Fuel Type Filter — `filter_by_fuel_type`

```
Keeps: vehicle.fuel_type ∈ fuel_types
```

| Parameter | Type | Accepted values |
|---|---|---|
| `fuel_types` | str or list | `"petrol"`, `"diesel"`, `"hybrid"`, `"electric"` |

Accepts both a single string (`"electric"`) and a list (`["petrol", "hybrid"]`).

### 2.4 Seat Filter — `filter_by_seats`

```
Keeps: vehicle.seats >= seats_min
```

| Parameter | Type | Description |
|---|---|---|
| `seats_min` | int | Minimum required seat count |

If `seats_min` is `None` or ≤ 0, the filter is skipped.

### 2.5 Body Type Filter — `filter_by_body_type`

```
Keeps: vehicle.body_type ∈ body_types
```

| Parameter | Type | Accepted values |
|---|---|---|
| `body_types` | str or list | `"hatchback"`, `"sedan"`, `"suv"`, `"wagon"`, `"mpv"` |

---

## 3. Combined Filter — `apply_hard_filters`

Applies all active filters **sequentially** in this order:

```
Input: all vehicles
  → budget filter
  → transmission filter
  → fuel type filter
  → seats filter
  → body type filter
Output: vehicles satisfying all constraints
```

**Usage example:**

```python
from app.engine.filters import apply_hard_filters

criteria = {
    "budget_max": 2_000_000,
    "transmission": "automatic",
    "fuel_types": ["petrol", "hybrid"],
    "seats_min": 5,
    "body_types": "suv",
}

results = apply_hard_filters(vehicles, criteria)
```

---

## 4. Diagnostic Evaluation — `evaluate_hard_filters`

Returns both the final matched list and a per-filter elimination count:

```python
matched, eliminated = evaluate_hard_filters(vehicles, criteria)
# Example output:
# eliminated = {"budget_max": 8, "transmission": 4, "fuel_type": 2}
```

This is used by **T24 Conflict Detection** to determine which constraint is most restrictive and suggest targeted relaxations to the user.

---

## 5. Conflict Detection Logic (T24 — upcoming)

If `len(matched) == 0`, the engine will:
1. Identify which constraints individually produce `0` results.
2. For each blocking constraint, calculate how many vehicles are unlocked by relaxing it by a minimum step.
3. Return a `ConflictReport` with ranked `RelaxationSuggestion` objects (defined in `app/schemas/recommendation.py`).
