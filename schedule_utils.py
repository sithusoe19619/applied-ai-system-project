from typing import Any


VALID_MONTH_WEEKS = ("Week 1", "Week 2", "Week 3", "Week 4")
MONTH_WEEK_ORDER = {label: index for index, label in enumerate(VALID_MONTH_WEEKS)}
MONTH_WEEK_ALIASES = {
    "first": "Week 1",
    "second": "Week 2",
    "third": "Week 3",
    "last": "Week 4",
    "week 1": "Week 1",
    "week 2": "Week 2",
    "week 3": "Week 3",
    "week 4": "Week 4",
    "week1": "Week 1",
    "week2": "Week 2",
    "week3": "Week 3",
    "week4": "Week 4",
    "1": "Week 1",
    "2": "Week 2",
    "3": "Week 3",
    "4": "Week 4",
}


def normalize_month_weeks(values: Any) -> list[str]:
    """Normalize month-week labels into a stable title-cased unique list."""
    if values is None:
        return []

    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, (list, tuple)):
        raw_values = list(values)
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        raw_label = str(value or "").strip()
        if not raw_label:
            continue
        label = MONTH_WEEK_ALIASES.get(raw_label.lower(), raw_label.title())
        if not label or label in seen:
            continue
        seen.add(label)
        normalized.append(label)
    return normalized


def infer_month_weeks(
    name: str = "",
    category: str = "",
    notes: str = "",
    rationale: str = "",
) -> list[str]:
    """Infer a stable month-week slot for legacy monthly tasks missing saved metadata."""
    text = " ".join(part for part in [name, category, notes, rationale] if part).lower()

    twice_monthly_markers = {
        "twice a month",
        "twice monthly",
        "twice-monthly",
        "two times a month",
        "2x monthly",
        "biweekly",
        "bi-weekly",
        "every other week",
    }
    if any(marker in text for marker in twice_monthly_markers):
        return ["Week 2", "Week 4"]

    if any(keyword in text for keyword in {"preventive", "restock", "refill", "parasite", "flea", "tick", "supply"}):
        return ["Week 1"]

    if any(keyword in text for keyword in {"groom", "brush", "clean", "deep-clean", "deep clean", "habitat", "tank", "cage", "litter"}):
        return ["Week 2"]

    if any(keyword in text for keyword in {"inspect", "maintenance", "filter", "rotation", "rotate"}):
        return ["Week 3"]

    if any(keyword in text for keyword in {"review", "follow-up", "follow up", "monitor", "monitoring", "log", "report", "trend", "check-in", "check in"}):
        return ["Week 4"]

    return ["Week 3"]
