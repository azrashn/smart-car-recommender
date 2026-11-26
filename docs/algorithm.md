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
4. Unknown values are also **excluded from bound computation** (`compute_catalogue_bounds`). For example, a vehicle with an empty `trunk_l` is not counted as `0 L` when computing the `interior_space` min/max.

### 6.3 Normalization Bounds Come From the Full Catalogue

Min-max bounds are computed from the **entire catalogue**, not from the filtered candidate list. Otherwise a vehicle's score would change depending on the user's filters (e.g. if only one vehicle survives, every sub-score becomes 100).

```python
from app.engine.scoring import compute_catalogue_bounds, score_and_rank_vehicles

bounds = compute_catalogue_bounds(all_vehicles)          # once, full catalogue
ranked = score_and_rank_vehicles(filtered, weights, custom_bounds=bounds)
# or: score_and_rank_vehicles(filtered, weights, catalogue=all_vehicles)
```

If neither `custom_bounds` nor `catalogue` is given, `vehicles` itself is treated as the full catalogue.

### 6.4 Weights Validation

Weights must be integers in `{1, 2, 3}`. Any other value (`0`, negative, `> 3`, floats, booleans, strings) raises `ValueError`. Unspecified criteria default to `2` (medium).

### 6.5 Electric Consumption Conversion (Design Decision — pending team approval)

> [!IMPORTANT]
> This is a design decision and needs explicit team approval before merge.

To compare electric and combustion vehicles on a single **Fuel Economy** axis, electric consumption is converted into a petrol-litre equivalent by **energy content**:

$$\text{L}_{eq}/100\text{km} = \frac{\text{kWh}/100\text{km}}{8.9}$$

**Rationale:** 1 L of petrol contains ≈ 8.9 kWh of chemical energy (≈ 32 MJ/L lower heating value). The conversion therefore compares how much *energy* each vehicle consumes per 100 km, using only data present in the catalogue (`consumption_kwh_100km`, `consumption_l_100km`) with no price or tariff assumptions.

**Consequence:** Because electric drivetrains are ~3× more energy-efficient than combustion engines, EVs land at ≈ 1.7–2.2 L_eq/100km while the best hybrids are ≈ 4.5 L/100km. EVs will therefore almost always receive a Fuel Economy sub-score close to 100 (normalized ≈ 1.0). This is intentional under energy-efficiency semantics.

**Alternatives considered (not implemented):**
- *Cost-based equivalence* (TRY/100km using fuel and electricity prices) — closer to what users feel, but depends on volatile prices; the cost module (`app/cost/`) already covers running cost separately.
- *Separate normalization per powertrain* — avoids EV dominance but makes cross-powertrain scores incomparable.
