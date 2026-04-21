import streamlit as st

from ui_components import render_ai_profile_summary, render_plan_dashboard
from ui_theme import apply_theme, render_badges, render_card_heading, render_page_intro


FORM_KEYS = (
    "owner_name",
    "pet_name",
    "species",
    "breed",
    "custom_species",
    "pet_age",
    "special_needs",
    "current_context",
)
RESULT_KEYS = ("result_owner", "result_pet", "result_ai_run")
CHAT_KEYS = ("chat_messages", "chat_context_fingerprint")


def clear_result_state() -> None:
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)


def clear_form_state() -> None:
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


def clear_chat_state() -> None:
    for key in CHAT_KEYS:
        st.session_state.pop(key, None)


apply_theme()

owner = st.session_state.get("result_owner")
pet = st.session_state.get("result_pet")
ai_run = st.session_state.get("result_ai_run")

if not owner or not pet:
    render_page_intro(
        "Plan Results",
        "No care plan is available yet",
        "Generate a plan from the planner to review your pet's schedule, reminders, and supporting care details.",
    )
    with st.container(border=True):
        render_card_heading(
            "Next Step",
            "Return to the planner to create a new care plan for your pet.",
        )
        if st.button("Back to Planner", type="secondary", use_container_width=True):
            st.switch_page("planner.py")
else:
    header_col, action_col = st.columns([2.1, 1.15], gap="large")
    with header_col:
        render_page_intro(
            "Generated Care Plan",
            f"{pet.name}'s AI care plan",
            "This page shows the care plan created for your pet, including the suggested routine, reminders, and supporting details.",
        )
        badges = [f"Owner: {owner.name}", f"Pet: {pet.name}"]
        if pet.get_effective_breed_label():
            badges.append(pet.get_effective_breed_label())
        elif pet.get_effective_species_label():
            badges.append(pet.get_effective_species_label().title())
        if ai_run:
            badges.append(f"Reliability {ai_run.reliability_score:.2f}")
        render_badges(badges)

    with action_col:
        with st.container(border=True):
            render_card_heading(
                "What You Can Do Next",
                "Open chat for follow-up questions or start over with a new plan.",
            )
            st.page_link("pages/Chat.py", label="Ask About Plan", icon="💬")
            if st.button("Create Another Plan", type="secondary", use_container_width=True):
                clear_result_state()
                clear_form_state()
                clear_chat_state()
                st.switch_page("planner.py")

    render_ai_profile_summary(pet)
    current_ai_tasks = [task for task in pet.tasks if task.ai_generated]
    render_plan_dashboard(owner, current_ai_tasks, ai_run)
