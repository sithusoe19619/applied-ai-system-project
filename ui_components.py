from html import escape
import re

import streamlit as st

from ai_retrieval import RetrievedPassage
from pawpal_system import Scheduler, Task, normalize_priority_value
from schedule_utils import MONTH_WEEK_ORDER, VALID_MONTH_WEEKS
from ui_theme import (
    render_badges,
    render_card_heading,
    render_results_plan_stack_marker,
)


PRIORITY_LABELS = {"high": "High priority", "medium": "Medium priority", "low": "Low priority"}
PROFILE_PRIORITY_GROUP_LABELS = {
    "current": "Current Focus",
    "hydration": "Hydration",
    "nutrition": "Nutrition",
    "mobility": "Mobility and Comfort",
    "monitoring": "Monitoring",
    "grooming": "Grooming and Skin Care",
    "environment": "Environment and Routine",
    "preventive": "Preventive Care",
    "general": "Care Priorities",
}
WEEKDAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_priority_label(task: Task) -> str:
    return PRIORITY_LABELS.get(normalize_priority_value(task.priority), "Unknown priority")


def format_count(value: int, singular: str, plural: str | None = None) -> str:
    label = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {label}"


def build_plan_summary(grouped: dict[str, list[Task]]) -> str:
    return (
        "These tabs show the same basic daily routine each day, with other daily care tasks rotating across the week, "
        f"plus {format_count(len(grouped['weekly']), 'weekly check-in')} and "
        f"{format_count(len(grouped['monthly']), 'monthly task')} below."
    )


def get_normalized_weekday_label(value: str) -> str:
    weekday = (value or "").strip().title()
    return weekday if weekday in WEEKDAY_LABELS else ""


def get_weekly_schedule_label(task: Task) -> str:
    return get_normalized_weekday_label(task.scheduled_weekday) or "Once this week"


def get_monthly_schedule_labels(task: Task) -> list[str]:
    labels = [label for label in task.scheduled_month_weeks if label in VALID_MONTH_WEEKS]
    return labels


def normalize_profile_priority_point(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip(" -\t\n.;:")
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def infer_profile_priority_group(text: str) -> str:
    lowered = text.lower()
    keyword_groups = {
        "hydration": {"water", "hydration", "drink", "fluid"},
        "nutrition": {"diet", "meal", "feeding", "protein", "appetite", "food", "weight"},
        "mobility": {"mobility", "joint", "stiff", "comfort", "exercise", "pain", "gait", "limping"},
        "monitoring": {"monitor", "watch", "observe", "track", "litter", "urine", "stool", "energy", "behavior"},
        "grooming": {"groom", "coat", "hairball", "shedding", "brush", "skin"},
        "environment": {"routine", "stress", "environment", "bedding", "temperature", "space", "enrichment"},
        "preventive": {"preventive", "parasite", "flea", "tick", "veterinary", "medication", "checkup"},
    }
    for group, keywords in keyword_groups.items():
        if any(keyword in lowered for keyword in keywords):
            return group
    return "general"


def build_profile_fact_candidates(pet) -> dict[str, list[str]]:
    species_label = pet.get_effective_species_label().title()
    breed_label = pet.get_effective_breed_label()
    life_stage = pet.get_age_context()["life_stage"]
    subject = pet.name or "This pet"
    descriptor = f"{breed_label} {species_label}".strip() if breed_label else species_label
    special_needs = re.sub(r"\s+", " ", pet.special_needs.strip()).strip(" .")

    candidates: dict[str, list[str]] = {
        "current": [],
        "hydration": [],
        "nutrition": [],
        "mobility": [],
        "monitoring": [],
        "grooming": [],
        "environment": [],
        "preventive": [],
        "general": [],
    }

    if special_needs:
        candidates["current"].append(f"Care decisions for {subject} should stay aligned with these noted needs: {special_needs}.")
        candidates["monitoring"].append(f"Because the profile notes {special_needs}, monitor closely for changes in comfort, appetite, and daily routine.")
        candidates["general"].append(f"The plan should stay centered on the special notes provided for {subject}: {special_needs}.")

    if species_label.lower() == "cat":
        candidates["hydration"].append(f"As a {descriptor}, {subject} benefits from easy access to fresh water and close attention to daily drinking habits.")
        candidates["nutrition"].append(f"{descriptor}s usually do best with consistent meal routines and portion tracking, especially when appetite changes are part of the profile.")
        candidates["monitoring"].append(f"For a {life_stage} {species_label.lower()}, watch litter habits, appetite, water intake, and day-to-day energy.")
        candidates["grooming"].append(f"{descriptor}s benefit from regular coat and skin checks, especially if shedding or hairball concerns are mentioned.")
    elif species_label.lower() == "dog":
        candidates["hydration"].append(f"As a {descriptor}, {subject} should have steady water access and hydration checks built into the daily routine.")
        candidates["nutrition"].append(f"{descriptor}s benefit from predictable feeding times and portion monitoring that match age, activity, and any special notes in the profile.")
        candidates["mobility"].append(f"For a {life_stage} {species_label.lower()}, keep activity aligned with comfort level and watch for any change in gait or stamina.")
        candidates["monitoring"].append(f"For a {life_stage} {species_label.lower()}, track appetite, energy, bathroom habits, and recovery after activity.")
        candidates["grooming"].append(f"{descriptor}s benefit from regular coat, skin, and paw checks as part of routine care.")
    else:
        candidates["hydration"].append(f"{subject}'s hydration routine should match the normal needs of a {descriptor} and stay easy to monitor each day.")
        candidates["nutrition"].append(f"The feeding plan for a {descriptor} should stay predictable and reflect the age and special-notes context provided.")
        candidates["monitoring"].append(f"For this {life_stage} {species_label.lower()}, watch for changes in appetite, energy, handling tolerance, and daily habits.")

    if life_stage == "senior":
        candidates["mobility"].append(f"At {pet.age} years old, {subject} may need closer attention to comfort, mobility, and recovery from activity.")
        candidates["monitoring"].append(f"Because {subject} is in the senior stage, monitor weight, appetite, and day-to-day behavior changes more closely.")
        candidates["environment"].append(f"A senior {species_label.lower()} usually does best with a stable, easy-to-access environment and low-stress routine.")
    elif life_stage == "adult":
        candidates["environment"].append(f"At {pet.age} years old, {subject} benefits from a predictable routine that supports steady activity, feeding, and rest.")
    else:
        candidates["environment"].append(f"At {pet.age} years old, {subject} benefits from a structured routine that supports development, enrichment, and regular monitoring.")

    candidates["preventive"].append(f"Preventive care for {subject} should reflect the {descriptor.lower()} profile, age, and any special notes already provided.")
    candidates["general"].append(f"The plan should stay specific to {subject}'s {descriptor.lower()} profile, age {pet.age}, and the care context supplied by the owner.")
    return candidates


def build_profile_priority_groups(
    pet,
    characteristics: str,
    max_groups: int = 4,
    max_points_per_group: int = 2,
) -> list[dict[str, list[str] | str]]:
    groups: list[dict[str, list[str] | str]] = []
    seen_points: set[str] = set()
    candidate_facts = build_profile_fact_candidates(pet)

    def add_group_point(group_key: str, point: str) -> None:
        normalized_point = normalize_profile_priority_point(point)
        if not normalized_point:
            return
        point_key = normalized_point.lower()
        if point_key in seen_points:
            return
        seen_points.add(point_key)

        for group in groups:
            if group["key"] == group_key:
                items = group["items"]
                if isinstance(items, list) and len(items) < max_points_per_group:
                    items.append(normalized_point)
                return

        if len(groups) >= max_groups:
            return
        groups.append(
            {
                "key": group_key,
                "title": PROFILE_PRIORITY_GROUP_LABELS[group_key],
                "items": [normalized_point],
            }
        )

    def fill_group_to_minimum(group: dict[str, list[str] | str]) -> None:
        items = group["items"]
        if not isinstance(items, list):
            return

        group_key = str(group["key"])
        fallback_keys = [group_key]
        if group_key != "general":
            fallback_keys.append("general")

        for fallback_key in fallback_keys:
            for candidate in candidate_facts.get(fallback_key, []):
                if len(items) >= max_points_per_group:
                    return
                add_group_point(group_key, candidate)
                items = group["items"]
                if not isinstance(items, list):
                    return

    special_needs = pet.special_needs.strip()
    if special_needs:
        add_group_point("current", special_needs)

    normalized = re.sub(r"\s+", " ", characteristics or "").strip()
    if normalized:
        if "||" in normalized:
            raw_groups = [part.strip() for part in normalized.split("||") if part.strip()]
            for raw_group in raw_groups:
                if ":" in raw_group:
                    raw_title, raw_items = raw_group.split(":", 1)
                    group_key = infer_profile_priority_group(raw_title)
                    candidates = [part.strip() for part in re.split(r";(?=\s|$)", raw_items) if part.strip()]
                else:
                    group_key = infer_profile_priority_group(raw_group)
                    candidates = [raw_group]
                for candidate in candidates:
                    add_group_point(group_key, candidate)
        elif "|" in normalized:
            for candidate in [part.strip() for part in normalized.split("|") if part.strip()]:
                add_group_point(infer_profile_priority_group(candidate), candidate)
        else:
            softened = normalized.replace(";", ". ")
            for candidate in [part.strip() for part in re.split(r"(?<=[.!?])\s+", softened) if part.strip()]:
                add_group_point(infer_profile_priority_group(candidate), candidate)

    if not groups:
        groups = [
            {"key": "hydration", "title": "Hydration", "items": []},
            {"key": "monitoring", "title": "Monitoring", "items": []},
            {"key": "environment", "title": "Environment and Routine", "items": []},
        ]

    for group in groups:
        fill_group_to_minimum(group)

    return groups[:max_groups]


def get_task_support_line(task: Task, max_length: int = 140) -> str:
    raw_text = task.notes.strip() or task.rationale.strip()
    if not raw_text:
        return ""

    normalized = re.sub(r"\s+", " ", raw_text).strip()
    return normalized


def build_task_chips(task: Task, chip_class: str = "paw-task-chip") -> str:
    labels = [
        get_priority_label(task),
        f"{task.duration_minutes} min",
        task.frequency.title(),
    ]
    return "".join(f'<span class="{chip_class}">{escape(label)}</span>' for label in labels)


def render_plan_summary(summary: str) -> None:
    st.markdown(f'<p class="paw-plan-summary">{escape(summary)}</p>', unsafe_allow_html=True)


def get_task_guidance_schedule_label(task: Task) -> str:
    if task.frequency == "weekly":
        return get_weekly_schedule_label(task)
    if task.frequency == "monthly":
        labels = get_monthly_schedule_labels(task)
        if not labels:
            return "Monthly"
        if len(labels) == 1:
            return f"{labels[0]} of each month"
        return f"{' and '.join(labels)} of each month"
    if task.frequency == "as needed":
        return "As needed"
    if task.scheduled_time and task.scheduled_time != "00:00":
        return f"Daily at {task.scheduled_time}"
    return task.frequency.title()


def get_reference_snippet(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content or "").strip()
    if not normalized:
        return ""
    first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0].strip()
    return first_sentence or normalized


def build_task_reference_entries(task: Task, retrieved_passages: list[RetrievedPassage] | None = None) -> list[dict[str, str]]:
    if not task.source_ids or not retrieved_passages:
        return []

    passages_by_doc: dict[str, RetrievedPassage] = {}
    for passage in retrieved_passages:
        passages_by_doc.setdefault(passage.doc_id, passage)

    references: list[dict[str, str]] = []
    seen_doc_ids: set[str] = set()
    for source_id in task.source_ids:
        if source_id in seen_doc_ids:
            continue
        seen_doc_ids.add(source_id)
        passage = passages_by_doc.get(source_id)
        if not passage:
            continue
        references.append(
            {
                "title": passage.title.strip(),
                "snippet": get_reference_snippet(passage.content),
            }
        )
    return references


def render_daily_task_cards(tasks: list[Task]) -> None:
    for task in tasks:
        support_line = get_task_support_line(task)
        support_markup = f'<p class="paw-task-support">{escape(support_line)}</p>' if support_line else ""
        chips = build_task_chips(task)
        st.markdown(
            (
                '<div class="paw-task-card">'
                '<div class="paw-task-card-header">'
                f'<span class="paw-time-pill">{escape(task.scheduled_time)}</span>'
                '<div class="paw-task-card-copy">'
                f"<h4>{escape(task.name)}</h4>"
                f'<div class="paw-task-chips">{chips}</div>'
                "</div>"
                "</div>"
                f"{support_markup}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def is_everyday_daily_task(task: Task) -> bool:
    text = f"{task.name} {task.notes} {task.category}".lower()
    basic_keywords = {
        "medication",
        "medicine",
        "med",
        "pill",
        "dose",
        "feeding",
        "feed",
        "meal",
        "food",
        "breakfast",
        "dinner",
        "supper",
        "water",
        "hydration",
        "litter",
        "potty",
        "bathroom",
        "sleep",
        "rest",
        "bedtime",
        "nap",
        "wind-down",
    }
    return any(keyword in text for keyword in basic_keywords)


def get_optional_task_weekday_indexes(task: Task, task_index: int) -> list[int]:
    text = f"{task.name} {task.notes} {task.category}".lower()
    if any(keyword in text for keyword in {"mobility", "gait", "joint", "stretch", "exercise"}):
        patterns = ([0, 2, 4], [1, 3, 5], [0, 3], [2, 5])
    elif any(keyword in text for keyword in {"enrichment", "play", "puzzle", "training", "walk", "park", "outing"}):
        patterns = ([1, 3, 5], [0, 2, 4], [2, 4], [5, 6])
    elif any(keyword in text for keyword in {"groom", "brush", "coat", "skin", "spa"}):
        patterns = ([1, 4], [2, 5], [0, 6])
    elif any(keyword in text for keyword in {"snack", "treat"}):
        patterns = ([1, 3, 5], [0, 2, 4], [2, 6])
    elif any(keyword in text for keyword in {"monitor", "observe", "check", "appetite", "comfort"}):
        patterns = ([0, 3, 6], [1, 4], [2, 5])
    else:
        patterns = ([0, 2, 4], [1, 3], [2, 5], [4, 6])
    return list(patterns[task_index % len(patterns)])


def get_daily_task_theme(task: Task) -> str:
    text = f"{task.name} {task.notes} {task.category}".lower()
    if any(keyword in text for keyword in {"snack", "treat"}):
        return "snack"
    if any(keyword in text for keyword in {"groom", "brush", "coat", "skin", "paw"}):
        return "grooming"
    if any(keyword in text for keyword in {"park", "outing", "spa"}):
        return "outing"
    if any(keyword in text for keyword in {"walk", "exercise", "mobility", "joint", "gait", "stretch"}):
        return "movement"
    if any(keyword in text for keyword in {"play", "enrichment", "puzzle", "training"}):
        return "enrichment"
    if any(keyword in text for keyword in {"appetite", "weight", "monitor", "observe", "check", "comfort", "breathing", "cough"}):
        return "monitoring"
    return (task.category or "other").strip().lower() or "other"


def build_daily_care_tabs(tasks: list[Task]) -> list[dict[str, object]]:
    recurring_daily_tasks = sorted(
        (task for task in tasks if task.frequency == "daily"),
        key=lambda item: item.scheduled_time,
    )
    base_tasks = [task for task in recurring_daily_tasks if is_everyday_daily_task(task)]
    optional_daily_tasks = [task for task in recurring_daily_tasks if not is_everyday_daily_task(task)]

    day_assignments: dict[int, dict[str, list[Task] | set[tuple[str, str, str]]]] = {
        index: {"base_tasks": list(base_tasks), "extra_tasks": [], "extra_keys": set()}
        for index in range(len(WEEKDAY_LABELS))
    }

    def add_extra_task(weekday_index: int, task: Task) -> None:
        entry = day_assignments[weekday_index]
        key = (task.name, task.scheduled_time, task.frequency)
        extra_keys = entry["extra_keys"]
        if not isinstance(extra_keys, set) or key in extra_keys:
            return
        extra_keys.add(key)
        extra_tasks = entry["extra_tasks"]
        if isinstance(extra_tasks, list):
            extra_tasks.append(task)

    for task_index, task in enumerate(optional_daily_tasks):
        for weekday_index in get_optional_task_weekday_indexes(task, task_index):
            add_extra_task(weekday_index, task)

    minimum_optional_tasks_per_day = 2 if len(optional_daily_tasks) >= 3 else 1
    for index in range(len(WEEKDAY_LABELS)):
        entry = day_assignments[index]
        extra_tasks = entry["extra_tasks"]
        if not isinstance(extra_tasks, list):
            continue
        seen_themes = {get_daily_task_theme(task) for task in extra_tasks}
        for offset in range(len(optional_daily_tasks)):
            if len(extra_tasks) >= min(minimum_optional_tasks_per_day, len(optional_daily_tasks)):
                break
            candidate = optional_daily_tasks[(index + offset) % len(optional_daily_tasks)]
            candidate_theme = get_daily_task_theme(candidate)
            if candidate_theme in seen_themes:
                continue
            add_extra_task(index, candidate)
            seen_themes.add(candidate_theme)

    daily_tabs: list[dict[str, object]] = []
    for index, day in enumerate(WEEKDAY_LABELS):
        extra_tasks = day_assignments[index]["extra_tasks"]
        unique_extra_tasks = sorted(extra_tasks, key=lambda item: item.scheduled_time) if isinstance(extra_tasks, list) else []
        combined_tasks = sorted([*base_tasks, *unique_extra_tasks], key=lambda item: item.scheduled_time)

        daily_tabs.append(
            {
                "day": day,
                "tasks": combined_tasks,
                "base_tasks": day_assignments[index]["base_tasks"],
                "extra_tasks": unique_extra_tasks,
            }
        )

    return daily_tabs


def render_daily_care_tabs(tasks: list[Task], empty_message: str) -> None:
    daily_tabs = build_daily_care_tabs(tasks)
    tab_panels = st.tabs([str(tab_data["day"]) for tab_data in daily_tabs])
    for tab_panel, tab_data in zip(tab_panels, daily_tabs):
        with tab_panel:
            day_tasks = tab_data["tasks"]
            if day_tasks:
                render_daily_task_cards(day_tasks)
            else:
                st.markdown(f'<p class="paw-section-empty">{escape(empty_message)}</p>', unsafe_allow_html=True)


def sort_tasks_for_section(tasks: list[Task], scheduler: Scheduler, schedule_style: str = "none") -> list[Task]:
    if schedule_style == "weekday":
        weekday_indexes = {label: index for index, label in enumerate(WEEKDAY_LABELS)}
        return sorted(
            tasks,
            key=lambda item: (
                weekday_indexes.get(get_normalized_weekday_label(item.scheduled_weekday), len(WEEKDAY_LABELS)),
                item.scheduled_time,
                item.name.lower(),
            ),
        )

    if schedule_style == "month-week":
        def month_week_key(item: Task) -> tuple[int, int, str, str]:
            labels = [label for label in get_monthly_schedule_labels(item) if label in MONTH_WEEK_ORDER]
            first_index = MONTH_WEEK_ORDER.get(labels[0], len(MONTH_WEEK_ORDER)) if labels else len(MONTH_WEEK_ORDER)
            second_index = MONTH_WEEK_ORDER.get(labels[1], len(MONTH_WEEK_ORDER)) if len(labels) > 1 else len(MONTH_WEEK_ORDER)
            return (first_index, second_index, item.name.lower(), item.scheduled_time)

        return sorted(tasks, key=month_week_key)

    return scheduler.sort_by_time(tasks)


def render_compact_task_list(tasks: list[Task], empty_message: str, schedule_style: str = "none") -> None:
    if not tasks:
        st.markdown(f'<p class="paw-section-empty">{escape(empty_message)}</p>', unsafe_allow_html=True)
        return

    item_markup: list[str] = []
    for task in tasks:
        support_line = get_task_support_line(task, max_length=110)
        note_markup = f'<p class="paw-task-list-note">{escape(support_line)}</p>' if support_line else ""
        schedule_markup = ""
        if schedule_style == "time" and task.scheduled_time and task.scheduled_time != "00:00":
            schedule_markup = f'<span class="paw-secondary-time-pill">{escape(task.scheduled_time)}</span>'
        elif schedule_style == "weekday":
            schedule_markup = f'<span class="paw-secondary-time-pill">{escape(get_weekly_schedule_label(task))}</span>'
        elif schedule_style == "month-week":
            schedule_markup = "".join(
                f'<span class="paw-secondary-time-pill">{escape(label)}</span>'
                for label in get_monthly_schedule_labels(task)
            )
        item_markup.append(
            (
                '<div class="paw-task-list-item">'
                '<div class="paw-task-list-header">'
                f"{schedule_markup}"
                '<div class="paw-task-list-copy">'
                f'<p class="paw-task-list-title">{escape(task.name)}</p>'
                f'<div class="paw-task-list-chips">{build_task_chips(task, chip_class="paw-task-chip paw-task-chip-secondary")}</div>'
                "</div>"
                "</div>"
                f"{note_markup}"
                "</div>"
            )
        )

    st.markdown(f'<div class="paw-task-list">{"".join(item_markup)}</div>', unsafe_allow_html=True)


def group_tasks_by_frequency(tasks: list[Task]) -> dict[str, list[Task]]:
    grouped = {"daily": [], "weekly": [], "monthly": [], "as needed": []}
    for task in tasks:
        grouped.setdefault(task.frequency, []).append(task)
    return grouped


def render_conflicts(scheduler: Scheduler, tasks: list[Task]) -> None:
    conflicts = scheduler.detect_conflicts(tasks)
    if not conflicts:
        return

    with st.container(border=True):
        render_card_heading(
            "Schedule Conflicts",
            "These items overlap in the current plan and may need to move to a different time slot.",
        )
        for conflict in conflicts:
            task_a, task_b = conflict["task_a"], conflict["task_b"]
            suggestion = scheduler.suggest_next_slot(task_b, tasks)
            suggestion_text = suggestion or "No open slot in the default planning window"
            if conflict["type"] == "same_pet":
                st.error(f"Overlap detected for {task_a.pet.name}.")
            else:
                st.warning("Two tasks overlap across different pets.")

            col1, col2 = st.columns(2)
            col1.markdown(
                f"**{task_a.name}** ({task_a.pet.name})  \n"
                f"{task_a.scheduled_time} • {task_a.duration_minutes} min"
            )
            col2.markdown(
                f"**{task_b.name}** ({task_b.pet.name})  \n"
                f"{task_b.scheduled_time} • {task_b.duration_minutes} min"
            )
            st.info(f"Recommended adjustment: move **{task_b.name}** to **{suggestion_text}**.")


def render_frequency_section(
    title: str,
    summary: str,
    tasks: list[Task],
    scheduler: Scheduler,
    empty_message: str,
    schedule_style: str = "none",
) -> None:
    with st.container(border=True):
        render_card_heading(title, summary)
        render_compact_task_list(sort_tasks_for_section(tasks, scheduler, schedule_style), empty_message, schedule_style=schedule_style)


def render_task_detail_expanders(
    tasks: list[Task],
    scheduler: Scheduler,
    retrieved_passages: list[RetrievedPassage] | None = None,
) -> None:
    with st.container(border=True):
        render_card_heading(
            "Task Guidance",
            "Open any task to see why it matters, what to do, when it applies, and the supporting references used for it.",
        )
        if not tasks:
            st.markdown(
                '<p class="paw-section-empty">Task guidance will appear here when a care plan includes saved tasks.</p>',
                unsafe_allow_html=True,
            )
            return
        for task in scheduler.sort_by_priority_then_time(tasks):
            with st.expander(task.name):
                st.markdown("**Why this matters**")
                st.write(task.rationale or "No planning rationale was saved for this task.")
                if task.notes:
                    st.markdown("**What to do**")
                    st.write(task.notes)
                st.markdown("**When this applies**")
                st.write(get_task_guidance_schedule_label(task))
                references = build_task_reference_entries(task, retrieved_passages)
                if references:
                    st.markdown("**Helpful references**")
                    for reference in references:
                        if reference["snippet"]:
                            st.write(f'{reference["title"]}: {reference["snippet"]}')
                        else:
                            st.write(reference["title"])


def render_ai_profile_summary(pet) -> None:
    age_context = pet.get_age_context()
    species_characteristics = pet.get_species_characteristics()
    effective_species = pet.get_effective_species_label()
    effective_breed = pet.get_effective_breed_label()
    profile_groups = build_profile_priority_groups(pet, species_characteristics)
    group_markup = "".join(
        (
            '<div class="paw-priority-group">'
            f'<p class="paw-priority-group-title">{escape(str(group["title"]))}</p>'
            f'<ul class="paw-priority-group-list">{"".join(f"<li>{escape(item)}</li>" for item in group["items"])}</ul>'
            "</div>"
        )
        for group in profile_groups
    )

    with st.container(border=True):
        render_card_heading(
            "Care Overview",
            "Essential profile details and the main care priorities used to shape this plan.",
        )
        col1, col2 = st.columns(2)
        col1.metric("Life Stage", age_context["life_stage"].title())
        col2.metric("Typical Lifespan", f"{age_context['lifespan_range_years'][0]}-{age_context['lifespan_range_years'][1]} years")

        profile_badges = [effective_species.title()]
        if effective_breed:
            profile_badges.append(effective_breed)
        render_badges(profile_badges)

        st.markdown(f'<p class="paw-profile-summary">{escape(age_context["summary"])}</p>', unsafe_allow_html=True)
        st.markdown('<p class="paw-profile-section-title">Key Care Priorities</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="paw-priority-groups">{group_markup}</div>', unsafe_allow_html=True)


def render_plan_dashboard(owner, tasks: list[Task], ai_run) -> None:
    scheduler = Scheduler(owner)
    grouped = group_tasks_by_frequency(tasks)
    daily_tasks = scheduler.sort_by_time(grouped["daily"])

    render_results_plan_stack_marker()
    with st.container(border=True):
        render_card_heading(
            "Daily Care Plan",
            "Follow the same basic daily care each day, with different daily-care tasks rotating across selected weekdays.",
        )
        render_plan_summary(build_plan_summary(grouped))
        render_daily_care_tabs(daily_tasks, "No daily tasks were generated for this profile.")

    if daily_tasks:
        render_conflicts(scheduler, daily_tasks)

    render_frequency_section(
        "Weekly Care",
        "These once-a-week check-ins are assigned to the day of the week that fits best for reviews, grooming, weigh-ins, or appointments.",
        grouped["weekly"],
        scheduler,
        "No weekly care tasks were generated for this profile.",
        schedule_style="weekday",
    )
    render_frequency_section(
        "Monthly Care",
        "These monthly preventive or maintenance tasks stay separate from the daily routine. Do them in the selected week number or week numbers of the month.",
        grouped["monthly"],
        scheduler,
        "No monthly care tasks were generated for this profile.",
        schedule_style="month-week",
    )
    render_frequency_section(
        "Care Alerts",
        "Use these condition-triggered alerts when symptoms, behavior changes, or other care concerns come up.",
        grouped["as needed"],
        scheduler,
        "No care alerts were generated for this profile.",
        schedule_style="none",
    )
    render_task_detail_expanders(tasks, scheduler, ai_run.retrieved_passages if ai_run else None)
