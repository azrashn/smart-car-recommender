"""Pure filter functions for M3 Hard Constraints.

Filters vehicles by deterministic criteria:
- Maximum budget (price_try <= budget_max)
- Transmission (manual, automatic)
- Fuel types (petrol, diesel, hybrid, electric)
- Minimum seats (seats >= seats_min)
- Body types (hatchback, sedan, suv, wagon, mpv)

All functions are pure: they do not interact with databases, network, or external state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union


def _get_value(vehicle: Any, field_name: str) -> Any:
    """Safely extracts a field from a dict or object."""
    if isinstance(vehicle, dict):
        return vehicle.get(field_name)
    return getattr(vehicle, field_name, None)


def _to_lower_set(values: Optional[Union[str, Sequence[str]]]) -> Set[str]:
    """Normalizes a single string or sequence of strings into a lowercase set."""
    if values is None:
        return set()
    if isinstance(values, str):
        v = values.strip().lower()
        return {v} if v and v != "any" else set()
    return {str(item).strip().lower() for item in values if str(item).strip().lower() != "any"}


def filter_by_budget(vehicles: Sequence[Any], budget_max: Optional[int]) -> List[Any]:
    """Filters vehicles whose price is within the specified maximum budget.
    
    If budget_max is None or <= 0, no filter is applied.
    """
    if budget_max is None or budget_max <= 0:
        return list(vehicles)

    matched: List[Any] = []
    for vehicle in vehicles:
        price = _get_value(vehicle, "price_try")
        if price is not None:
            try:
                if int(price) <= budget_max:
                    matched.append(vehicle)
            except (ValueError, TypeError):
                continue
    return matched


def filter_by_transmission(vehicles: Sequence[Any], transmission: Optional[str]) -> List[Any]:
    """Filters vehicles by transmission type (e.g. 'manual', 'automatic').
    
    If transmission is None, empty, or 'any', no filter is applied.
    """
    target = transmission.strip().lower() if transmission else None
    if not target or target == "any":
        return list(vehicles)

    return [
        v for v in vehicles
        if str(_get_value(v, "transmission") or "").strip().lower() == target
    ]


def filter_by_fuel_type(
    vehicles: Sequence[Any],
    fuel_types: Optional[Union[str, Sequence[str]]],
) -> List[Any]:
    """Filters vehicles by one or more accepted fuel types.
    
    Accepts e.g. 'electric' or ['petrol', 'hybrid'].
    If empty or contains 'any', no filter is applied.
    """
    allowed = _to_lower_set(fuel_types)
    if not allowed:
        return list(vehicles)

    return [
        v for v in vehicles
        if str(_get_value(v, "fuel_type") or "").strip().lower() in allowed
    ]


def filter_by_seats(vehicles: Sequence[Any], seats_min: Optional[int]) -> List[Any]:
    """Filters vehicles having at least the specified number of seats.
    
    If seats_min is None or <= 0, no filter is applied.
    """
    if seats_min is None or seats_min <= 0:
        return list(vehicles)

    matched: List[Any] = []
    for vehicle in vehicles:
        seats = _get_value(vehicle, "seats")
        if seats is not None:
            try:
                if int(seats) >= seats_min:
                    matched.append(vehicle)
            except (ValueError, TypeError):
                continue
    return matched


def filter_by_body_type(
    vehicles: Sequence[Any],
    body_types: Optional[Union[str, Sequence[str]]],
) -> List[Any]:
    """Filters vehicles by one or more accepted body types (e.g. 'suv', 'sedan').
    
    If empty or contains 'any', no filter is applied.
    """
    allowed = _to_lower_set(body_types)
    if not allowed:
        return list(vehicles)

    return [
        v for v in vehicles
        if str(_get_value(v, "body_type") or "").strip().lower() in allowed
    ]


def apply_hard_filters(vehicles: Sequence[Any], criteria: Dict[str, Any]) -> List[Any]:
    """Applies all active hard constraints sequentially.
    
    Supported criteria keys:
    - budget_max (int)
    - transmission (str)
    - fuel_types (str or list of str)
    - seats_min (int)
    - body_types (str or list of str)
    """
    result = list(vehicles)

    if "budget_max" in criteria and criteria["budget_max"] is not None:
        result = filter_by_budget(result, criteria["budget_max"])

    if "transmission" in criteria and criteria["transmission"] is not None:
        result = filter_by_transmission(result, criteria["transmission"])

    if "fuel_types" in criteria and criteria["fuel_types"] is not None:
        result = filter_by_fuel_type(result, criteria["fuel_types"])
    elif "fuel_type" in criteria and criteria["fuel_type"] is not None:
        result = filter_by_fuel_type(result, criteria["fuel_type"])

    if "seats_min" in criteria and criteria["seats_min"] is not None:
        result = filter_by_seats(result, criteria["seats_min"])

    if "body_types" in criteria and criteria["body_types"] is not None:
        result = filter_by_body_type(result, criteria["body_types"])
    elif "body_type" in criteria and criteria["body_type"] is not None:
        result = filter_by_body_type(result, criteria["body_type"])

    return result


def evaluate_hard_filters(
    vehicles: Sequence[Any],
    criteria: Dict[str, Any],
) -> Tuple[List[Any], Dict[str, int]]:
    """Evaluates each constraint independently and sequentially.
    
    Returns:
    - matched_vehicles: Vehicles satisfying all applied constraints.
    - eliminated_counts: Number of vehicles eliminated by each specific filter.
      (Useful for T24 Conflict Detection and relaxation feedback).
    """
    eliminated_counts: Dict[str, int] = {}
    total = len(vehicles)

    # Check each filter independently to see its elimination power
    if criteria.get("budget_max") is not None:
        passed = filter_by_budget(vehicles, criteria["budget_max"])
        eliminated_counts["budget_max"] = total - len(passed)

    if criteria.get("transmission") not in (None, "", "any"):
        passed = filter_by_transmission(vehicles, criteria["transmission"])
        eliminated_counts["transmission"] = total - len(passed)

    fuel = criteria.get("fuel_types") or criteria.get("fuel_type")
    if fuel not in (None, "", "any", []):
        passed = filter_by_fuel_type(vehicles, fuel)
        eliminated_counts["fuel_type"] = total - len(passed)

    if criteria.get("seats_min") is not None and criteria["seats_min"] > 0:
        passed = filter_by_seats(vehicles, criteria["seats_min"])
        eliminated_counts["seats_min"] = total - len(passed)

    body = criteria.get("body_types") or criteria.get("body_type")
    if body not in (None, "", "any", []):
        passed = filter_by_body_type(vehicles, body)
        eliminated_counts["body_type"] = total - len(passed)

    matched = apply_hard_filters(vehicles, criteria)
    return matched, eliminated_counts
