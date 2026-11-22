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


---

## 6. Weighted Scoring Engine (T22)

Once candidate vehicles pass all hard filters, they are ranked using a multi-criteria weighted scoring formula:

$$\text{score} = 100 \times \frac{\sum_i w_i \cdot s_i}{\sum_i w_i}$$

Where:
- $s_i \in [0.0, 1.0]$: Normalized score for criterion $i$.
- $w_i \in \{1, 2, 3\}$: User priority weight (`low=1`, `medium=2`, `high=3`).

### 6.1 Evaluation Criteria

| Criterion | Source Field | Direction | Normalization |
|---|---|---|---|
| **Fuel Economy** | `consumption_l_100km` / `consumption_kwh_100km` | Lower is better | $\frac{\max - x}{\max - \min}$ (Electric converted via $1\text{ L} \approx 8.9\text{ kWh}$) |
| **Budget Fit** | `price_try` | Lower is better | $\frac{\max - x}{\max - \min}$ (More affordable gives higher score) |
| **Interior Space** | `trunk_l` + `seats * 50` | Higher is better | $\frac{x - \min}{\max - \min}$ |
| **Performance** | `power_hp` | Higher is better | $\frac{x - \min}{\max - \min}$ |
| **Safety** | `euro_ncap_stars` | Higher is better | $\frac{\text{stars}}{5.0}$ |

### 6.2 Missing Data Exclusion (NFR-04)

If a criterion's data is missing (e.g., Euro NCAP stars is `None`):
1. That sub-score is excluded (`None`).
2. Its corresponding weight $w_i$ is removed from **both numerator and denominator**.
3. The vehicle is scored purely on its available metrics without being penalized.
