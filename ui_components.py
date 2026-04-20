import streamlit as st

from pawpal_system import Scheduler, Task


PRIORITY_EMOJI = {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}


def render_task_table(tasks: list[Task]) -> None:
    st.table(
        [
            {
                "Time": task.scheduled_time,
                "Task": task.name,
                "Category": task.category.replace("_", " ").title(),
                "Duration (min)": task.duration_minutes,
                "Priority": PRIORITY_EMOJI[task.priority.value],
                "Frequency": task.frequency.title(),
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
        st.success("No schedule conflicts detected in the daily plan.")
        return

    with st.container(border=True):
        st.markdown(f"**Conflicts Found: {len(conflicts)}**")
        for conflict in conflicts:
            task_a, task_b = conflict["task_a"], conflict["task_b"]
            suggestion = scheduler.suggest_next_slot(task_b, tasks)
            suggestion_text = suggestion or "No open slot in the default planning window"
            if conflict["type"] == "same_pet":
                st.error(f"**Overlap for {task_a.pet.name}**")
            else:
                st.warning("**Cross-pet overlap**")

            col1, col2 = st.columns(2)
            col1.markdown(
                f"**{task_a.name}** ({task_a.pet.name})  \n"
                f"{task_a.scheduled_time} — {task_a.duration_minutes} min"
            )
            col2.markdown(
                f"**{task_b.name}** ({task_b.pet.name})  \n"
                f"{task_b.scheduled_time} — {task_b.duration_minutes} min"
            )
            st.info(f"Suggestion: Move **{task_b.name}** to **{suggestion_text}**")


def render_frequency_section(title: str, tasks: list[Task], scheduler: Scheduler, empty_message: str) -> None:
    st.subheader(title)
    if not tasks:
        st.info(empty_message)
        return
    render_task_table(scheduler.sort_by_time(tasks))


def render_reminder_group(title: str, tasks: list[Task], empty_message: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
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

    st.subheader("AI-Derived Pet Profile")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.metric("Life stage", age_context["life_stage"].title())
        col2.metric("Typical lifespan", f"{age_context['lifespan_range_years'][0]}-{age_context['lifespan_range_years'][1]} years")
        if effective_breed:
            st.caption(f"Breed: {effective_breed}")
        if pet.species == "other" and pet.custom_species:
            st.caption(f"Species: {effective_species}")
        if pet.species_profile_source:
            st.caption(pet.species_profile_source)
        st.caption(age_context["summary"])
        st.caption(f"Inferred traits: {species_characteristics}")


def render_plan_dashboard(owner, tasks: list[Task], ai_run) -> None:
    scheduler = Scheduler(owner)
    grouped = group_tasks_by_frequency(tasks)
    daily_tasks = scheduler.sort_by_time(grouped["daily"])

    st.subheader("AI Care Plan")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Daily", str(len(grouped["daily"])))
    col2.metric("Weekly", str(len(grouped["weekly"])))
    col3.metric("Monthly", str(len(grouped["monthly"])))
    col4.metric("Reliability", f"{ai_run.reliability_score:.2f}" if ai_run else "Saved plan")

    st.subheader("Daily Schedule")
    if daily_tasks:
        render_task_table(daily_tasks)
        render_conflicts(scheduler, daily_tasks)
    else:
        st.info("No daily tasks were generated for this pet profile.")

    render_frequency_section(
        "Weekly Care",
        grouped["weekly"],
        scheduler,
        "No weekly care tasks were generated for this profile.",
    )
    render_frequency_section(
        "Monthly Care",
        grouped["monthly"],
        scheduler,
        "No monthly care tasks were generated for this profile.",
    )
    render_frequency_section(
        "Condition-Based Guidance",
        grouped["as needed"],
        scheduler,
        "No condition-based tasks were generated.",
    )

    st.subheader("Reminders")
    render_reminder_group(
        "Today's Essentials",
        [task for task in grouped["daily"] if task.priority.value == "high"],
        "No urgent daily reminders right now.",
    )
    render_reminder_group(
        "Weekly Watchlist",
        grouped["weekly"],
        "No weekly reminders were generated.",
    )
    render_reminder_group(
        "Condition Watchouts",
        grouped["as needed"],
        "No as-needed watchouts were generated.",
    )

    st.subheader("Evidence / Why This Plan")
    for task in scheduler.sort_by_priority_then_time(tasks):
        with st.expander(f"{task.name}"):
            st.write(task.rationale or "No rationale was saved for this task.")
            if task.notes:
                st.write(f"Notes: {task.notes}")
            if task.source_ids:
                st.write(f"Sources: {', '.join(task.source_ids)}")
            st.write(f"Cadence: {task.frequency.title()}")

    if ai_run:
        if ai_run.blocked_recommendations:
            st.markdown("**Blocked recommendations**")
            for blocked in ai_run.blocked_recommendations:
                st.error(f"{blocked.name}: {' '.join(blocked.reasons)}")

        if ai_run.warnings:
            st.markdown("**Warnings**")
            for warning in ai_run.warnings:
                st.warning(warning)

        with st.expander("Retrieved evidence"):
            for passage in ai_run.retrieved_passages:
                st.markdown(f"**{passage.doc_id}** ({passage.score})")
                st.write(passage.content)

        st.caption(f"Model: {ai_run.model_name}")
        st.caption(f"Log: {ai_run.log_path}")
