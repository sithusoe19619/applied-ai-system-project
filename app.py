import streamlit as st
from pawpal_system import Task, Pet, Owner, Scheduler, Priority

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# ── Step 1: Owner & Pet Setup ──────────────────────────────────────────────
st.subheader("Step 1: Set Up Your Profile")

owner_name = st.text_input("Owner name", value="Jordan")
pet_name = st.text_input("Pet name", value="Mochi")
species = st.selectbox("Species", ["dog", "cat", "other"])
available_minutes = st.number_input("Available time today (minutes)", min_value=10, max_value=480, value=90)

if st.button("Create Profile"):
    pet = Pet(pet_name, species, age=0)
    owner = Owner(owner_name, available_minutes=int(available_minutes))
    owner.add_pet(pet)
    st.session_state["owner"] = owner
    st.session_state["pet"] = pet
    st.success(f"Profile created for {owner_name} and {pet_name}!")

# ── Step 2: Add Tasks ──────────────────────────────────────────────────────
if "owner" in st.session_state:
    st.divider()
    st.subheader("Step 2: Add Tasks")

    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

    if st.button("Add task"):
        pet = st.session_state["pet"]
        priority_map = {"low": Priority.LOW, "medium": Priority.MEDIUM, "high": Priority.HIGH}
        task = Task(task_title, int(duration), priority_map[priority], "general", "")
        pet.add_task(task)
        st.success(f"Added '{task_title}' to {pet.name}'s tasks.")

    pet = st.session_state["pet"]
    if pet.tasks:
        st.write(f"**{pet.name}'s current tasks:**")
        st.table([
            {"Task": t.name, "Duration (min)": t.duration_minutes, "Priority": t.priority.value}
            for t in pet.tasks
        ])
    else:
        st.info("No tasks yet. Add one above.")

    # ── Step 3: Generate Schedule ──────────────────────────────────────────
    st.divider()
    st.subheader("Step 3: Generate Schedule")

    if st.button("Generate schedule"):
        owner = st.session_state["owner"]
        if not owner.get_all_tasks():
            st.warning("Add at least one task before generating a schedule.")
        else:
            scheduler = Scheduler(owner)
            plan = scheduler.generate_plan()

            st.success(f"Schedule generated for {owner.name}!")

            if plan["scheduled"]:
                st.markdown("**Scheduled Tasks**")
                for task in plan["scheduled"]:
                    st.markdown(
                        f"- **{task.name}** ({task.pet.name}) — "
                        f"{task.duration_minutes} min | {task.priority.value}"
                    )

            if plan["skipped"]:
                st.markdown("**Skipped Tasks**")
                for task in plan["skipped"]:
                    st.markdown(
                        f"- {task.name} ({task.pet.name}) — "
                        f"{task.duration_minutes} min | {task.priority.value}"
                    )

            time_used = sum(t.duration_minutes for t in plan["scheduled"])
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric("Scheduled", f"{len(plan['scheduled'])} tasks")
            col2.metric("Time Used", f"{time_used} / {owner.available_minutes} min")
            col3.metric("Remaining", f"{owner.available_minutes - time_used} min")
