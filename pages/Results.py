import streamlit as st

from ui_components import render_ai_profile_summary, render_plan_dashboard


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


def clear_result_state() -> None:
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)


def clear_form_state() -> None:
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


st.set_page_config(page_title="PawPal+ Results", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+ Results")
st.caption("AI-generated pet-care results for the current session.")

owner = st.session_state.get("result_owner")
pet = st.session_state.get("result_pet")
ai_run = st.session_state.get("result_ai_run")

if not owner or not pet:
    st.info("No active AI result is available in this session. Generate a new plan from the main page.")
    if st.button("Back to Planner"):
        st.switch_page("app.py")
else:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.caption(f"Pet: {pet.name}")
        st.caption(f"Owner: {owner.name}")
    with col2:
        if st.button("Create Another Plan"):
            clear_result_state()
            clear_form_state()
            st.switch_page("app.py")

    render_ai_profile_summary(pet)
    current_ai_tasks = [task for task in pet.tasks if task.ai_generated]
    render_plan_dashboard(owner, current_ai_tasks, ai_run)
