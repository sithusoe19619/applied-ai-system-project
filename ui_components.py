import streamlit as st

from pawpal_system import Scheduler, Task
from ui_theme import render_badges, render_card_heading, render_note


PRIORITY_EMOJI = {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}


def render_task_table(tasks: list[Task]) -> None:
    st.table(
        [
            {
                "Time": task.scheduled_time,
                "Task": task.name,
                "Category": task.category.replace("_", " ").title(),
                "Duration": f"{task.duration_minutes} min",
                "Priority": PRIORITY_EMOJI[task.priority.value],
                "Cadence": task.frequency.title(),
                "Confidence": f"{task.confidence_score:.2f}" if task.ai_generated else "—",
            }
            for task in tasks
        ]
    )


def group_tasks_by_frequency(tasks: list[Task]) -> dict[str, list[Task]]:
    grouped = {"daily": [], "weekly": [], "monthly": [], "as needed": []}
    for task in tasks:
        grouped.setdefault(task.frequency, []).append(task)
    return grouped


def render_conflicts(scheduler: Scheduler, tasks: list[Task]) -> None:
    conflicts = scheduler.detect_conflicts(tasks)
    if not conflicts:
        st.success("No timing conflicts were detected in the daily schedule.")
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


def render_frequency_section(title: str, summary: str, tasks: list[Task], scheduler: Scheduler, empty_message: str) -> None:
    with st.container(border=True):
        render_card_heading(title, summary)
        if not tasks:
            st.info(empty_message)
            return
        render_task_table(scheduler.sort_by_time(tasks))


def render_reminder_group(title: str, summary: str, tasks: list[Task], empty_message: str) -> None:
    with st.container(border=True):
        render_card_heading(title, summary)
        if not tasks:
            st.caption(empty_message)
            return
        for task in tasks:
            st.write(f"- `{task.scheduled_time}` {task.name}: {task.notes or task.rationale}")


def render_ai_profile_summary(pet) -> None:
    age_context = pet.get_age_context()
    species_characteristics = pet.get_species_characteristics()
    effective_species = pet.get_effective_species_label()
    effective_breed = pet.get_effective_breed_label()

    with st.container(border=True):
        render_card_heading(
            "Pet Care Summary",
            "This summary shows the age stage, typical lifespan, and general care needs used to build the plan.",
        )
        col1, col2 = st.columns(2)
        col1.metric("Life Stage", age_context["life_stage"].title())
        col2.metric("Typical Lifespan", f"{age_context['lifespan_range_years'][0]}-{age_context['lifespan_range_years'][1]} years")

        profile_badges = [f"Species: {effective_species.title()}"]
        if effective_breed:
            profile_badges.append(f"Breed: {effective_breed}")
        if pet.species_profile_source:
            profile_badges.append("AI-derived species context")
        render_badges(profile_badges)

        st.caption(age_context["summary"])
        if pet.species_profile_source:
            st.caption(f"Profile Source: {pet.species_profile_source}")
        else:
            st.caption("Profile Source: Fallback profile")
        st.write(f"**Typical care needs**  \n{species_characteristics}")


def render_plan_dashboard(owner, tasks: list[Task], ai_run) -> None:
    scheduler = Scheduler(owner)
    grouped = group_tasks_by_frequency(tasks)
    daily_tasks = scheduler.sort_by_time(grouped["daily"])

    st.subheader("Care Plan Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Daily Tasks", str(len(grouped["daily"])))
    col2.metric("Weekly Tasks", str(len(grouped["weekly"])))
    col3.metric("Monthly Tasks", str(len(grouped["monthly"])))
    col4.metric("Reliability", f"{ai_run.reliability_score:.2f}" if ai_run else "Saved plan")

    render_frequency_section(
        "Today's Schedule",
        "Tasks that should be handled each day and the suggested time for each one.",
        daily_tasks,
        scheduler,
        "No daily tasks were generated for this profile.",
    )
    if daily_tasks:
        render_conflicts(scheduler, daily_tasks)

    mid_col1, mid_col2 = st.columns(2, gap="large")
    with mid_col1:
        render_frequency_section(
            "Weekly Care",
            "Tasks that should be completed regularly during the week.",
            grouped["weekly"],
            scheduler,
            "No weekly care tasks were generated for this profile.",
        )
        render_frequency_section(
            "If Something Changes",
            "These suggestions apply when the situation or symptoms described in the profile come up.",
            grouped["as needed"],
            scheduler,
            "No condition-based guidance was generated.",
        )
    with mid_col2:
        render_frequency_section(
            "Monthly Care",
            "Tasks that should be checked or completed less often.",
            grouped["monthly"],
            scheduler,
            "No monthly care tasks were generated for this profile.",
        )
        with st.container(border=True):
            render_card_heading(
                "Reminders",
                "A quick view of the most important follow-ups to keep in mind.",
            )
            render_reminder_group(
                "High-Priority Today",
                "Daily tasks that need closer attention.",
                [task for task in grouped["daily"] if task.priority.value == "high"],
                "No urgent daily reminders right now.",
            )
            render_reminder_group(
                "Weekly Follow-Ups",
                "Weekly tasks worth keeping visible.",
                grouped["weekly"],
                "No weekly reminders were generated.",
            )
            render_reminder_group(
                "Watch for Changes",
                "Situations to watch for based on the current plan.",
                grouped["as needed"],
                "No watchouts were generated.",
            )

    with st.container(border=True):
        render_card_heading(
            "Why These Tasks Were Suggested",
            "Each task includes a short explanation and the care information used to support it.",
        )
        for task in scheduler.sort_by_priority_then_time(tasks):
            with st.expander(task.name):
                st.write(task.rationale or "No planning rationale was saved for this task.")
                if task.notes:
                    st.write(f"Notes: {task.notes}")
                if task.source_ids:
                    st.write(f"Sources: {', '.join(task.source_ids)}")
                st.write(f"How often: {task.frequency.title()}")

    if ai_run:
        if ai_run.blocked_recommendations:
            with st.container(border=True):
                render_card_heading(
                    "Suggestions That Were Not Included",
                    "These suggestions were left out because they did not meet the app's safety or quality checks.",
                )
                for blocked in ai_run.blocked_recommendations:
                    st.error(f"{blocked.name}: {' '.join(blocked.reasons)}")

        if ai_run.warnings:
            with st.container(border=True):
                render_card_heading(
                    "Important Notes",
                    "These notes were recorded while the plan was being created.",
                )
                for warning in ai_run.warnings:
                    st.warning(warning)

        with st.container(border=True):
            render_card_heading(
                "Care Information Used",
                "These care references were used to help create the final plan.",
            )
            for passage in ai_run.retrieved_passages:
                with st.expander(f"{passage.doc_id} • score {passage.score}"):
                    st.write(passage.content)

        render_note(f"Model: {ai_run.model_name} • Log file: {ai_run.log_path}", title="System record.")
