import streamlit as st

from bedrock_client import RecommendationProviderError
from pawpal_ai import PawPalAIPlanner
from pawpal_system import Owner, Pet
from ui_theme import apply_theme, render_card_heading, render_note, render_page_intro

FORM_KEYS = [
    "owner_name",
    "pet_name",
    "species",
    "breed",
    "custom_species",
    "pet_age",
    "special_needs",
    "current_context",
]
RESULT_KEYS = ("result_owner", "result_pet", "result_ai_run")
CHAT_KEYS = ("chat_messages", "chat_context_fingerprint")
SPECIES_PLACEHOLDER = "-None-"


def clear_form_state() -> None:
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


def clear_chat_state() -> None:
    for key in CHAT_KEYS:
        st.session_state.pop(key, None)


def format_provider_error(exc: RecommendationProviderError) -> str:
    message = str(exc)
    if "malformed JSON" in message:
        return f"AI planning failed because Bedrock returned a response the app could not fully read: {message}"
    return f"AI planning is unavailable until AWS Bedrock is configured correctly outside the app: {message}"


def build_profile_from_inputs(
    owner_name: str,
    pet_name: str,
    species: str,
    breed: str,
    custom_species: str,
    pet_age: int,
    special_needs: str,
):
    validation_errors: list[str] = []
    normalized_species = "" if species == SPECIES_PLACEHOLDER else species.lower()
    if not owner_name.strip():
        validation_errors.append("Enter the owner's name.")
    if not pet_name.strip():
        validation_errors.append("Enter the pet's name.")
    if not normalized_species:
        validation_errors.append("Select a species.")
    if breed.strip() and normalized_species in {"dog", "cat"} and not Pet.is_valid_breed_label(breed, normalized_species):
        validation_errors.append("Enter a readable breed label without numbers or unusual symbols.")
    if normalized_species == "other" and not custom_species.strip():
        validation_errors.append("Specify the species name for this pet.")

    if validation_errors:
        return None, None, validation_errors

    pet = Pet(
        pet_name.strip(),
        normalized_species,
        age=int(pet_age),
        special_needs=special_needs.strip(),
        breed=breed.strip(),
        custom_species=custom_species.strip(),
    )
    owner = Owner(owner_name.strip())
    owner.add_pet(pet)
    return owner, pet, []


apply_theme()

render_page_intro(
    "🐾 PawPal+ Pet Care AI",
    "AI-powered reliable care for your pet",
    "Create a clear daily care plan based on your pet's profile, current needs, and trusted care information.",
)

st.caption("Complete the pet profile and current care details first for the most useful plan.")

ask_paw_col, _ = st.columns([1.1, 4], gap="medium")
with ask_paw_col:
    st.page_link("pages/Chat.py", label="Ask Paw", icon="💬")

with st.container(border=True):
    st.markdown('<div class="paw-pet-profile-scope" aria-hidden="true"></div>', unsafe_allow_html=True)
    render_card_heading(
        "Pet Profile",
        "Start with the basic details about your pet. These help the planner tailor the routine to the pet's age and type.",
    )
    name_col1, name_col2 = st.columns(2, gap="medium")
    with name_col1:
        owner_name = st.text_input(
            "Owner Name",
            value=st.session_state.get("owner_name", ""),
            key="owner_name",
            placeholder="Example: Jordan Kim",
        )
    with name_col2:
        pet_name = st.text_input(
            "Pet Name",
            value=st.session_state.get("pet_name", ""),
            key="pet_name",
            placeholder="Example: Mochi",
        )

    species_col, age_col = st.columns(2, gap="medium")
    with species_col:
        species_options = [SPECIES_PLACEHOLDER, "Dog", "Cat", "Other"]
        species = st.selectbox(
            "Species",
            species_options,
            key="species",
        )
    with age_col:
        pet_age = st.number_input(
            "Age (Years)",
            min_value=0,
            max_value=40,
            value=st.session_state.get("pet_age", 0),
            key="pet_age",
        )

    normalized_species = "" if species == SPECIES_PLACEHOLDER else species.lower()
    breed = ""
    custom_species = ""

    if normalized_species in {"dog", "cat"}:
        breed = st.text_input(
            "Breed",
            value=st.session_state.get("breed", ""),
            key="breed",
            placeholder="Examples: Golden Retriever, Domestic Shorthair, Mixed",
        )
        st.markdown(
            '<p class="paw-pet-profile-caption">Use a readable breed label such as "Pug," "Golden Retriever," "Siamese," or "Mixed."</p>',
            unsafe_allow_html=True,
        )
    elif normalized_species == "other":
        custom_species = st.text_input(
            "Species Name",
            value=st.session_state.get("custom_species", ""),
            key="custom_species",
            placeholder="Examples: Rabbit, Guinea Pig, Parrot, Monkey",
        )
        st.markdown(
            '<p class="paw-pet-profile-caption">Enter the animal name you want PawPal+ to reason about.</p>',
            unsafe_allow_html=True,
        )

with st.container(border=True):
    render_card_heading(
        "Health and Current Needs",
        "Add veterinary guidance, special needs, or recent changes so the plan can focus on the right care tasks and reminders.",
    )
    special_needs = st.text_area(
        "Veterinary Guidance or Special Needs",
        value=st.session_state.get("special_needs", ""),
        key="special_needs",
        placeholder="Kidney diet, joint support, medication reminder, anxiety triggers, hydration monitoring, or recovery guidance.",
    )
    current_context = st.text_area(
        "What should this care plan focus on?",
        value=st.session_state.get("current_context", ""),
        key="current_context",
        placeholder="Examples: Lower activity this week, indoor exercise during rainy weather, medication reminders, mobility support, appetite monitoring, or calmer enrichment.",
    )
    render_note(
        "The planner reviews your pet's profile, current needs, and care information before creating a plan.",
        title="How this works.",
    )

with st.container(border=True):
    render_card_heading(
        "Ready to Generate",
        "Save these details for this session, or generate the full care plan now.",
    )
    action_col1, action_col2 = st.columns([1, 1.25], gap="medium")
    with action_col1:
        if st.button("Save Profile", type="secondary", use_container_width=True):
            owner, pet, validation_errors = build_profile_from_inputs(
                owner_name=owner_name,
                pet_name=pet_name,
                species=species,
                breed=breed,
                custom_species=custom_species,
                pet_age=pet_age,
                special_needs=st.session_state.get("special_needs", ""),
            )
            if validation_errors:
                for message in validation_errors:
                    st.error(message)
            else:
                st.success(f"Profile saved for {pet.name}.")
    with action_col2:
        generate_clicked = st.button("Generate Care Plan", type="primary", use_container_width=True)

    if generate_clicked:
        owner, pet, validation_errors = build_profile_from_inputs(
            owner_name=owner_name,
            pet_name=pet_name,
            species=species,
            breed=breed,
            custom_species=custom_species,
            pet_age=pet_age,
            special_needs=special_needs,
        )
        if validation_errors:
            for message in validation_errors:
                st.error(message)
        else:
            planner = PawPalAIPlanner()
            try:
                run = planner.recommend_and_schedule(
                    owner=owner,
                    pet=pet,
                    goal="Create a complete pet care plan with daily, weekly, monthly tasks, reminders, and safe condition-aware guidance.",
                    extra_context=current_context.strip(),
                    apply_to_pet=True,
                )
                st.session_state["result_owner"] = owner
                st.session_state["result_pet"] = pet
                st.session_state["result_ai_run"] = run
                clear_chat_state()
                clear_form_state()
                st.switch_page("pages/Results.py")
            except RecommendationProviderError as exc:
                st.error(format_provider_error(exc))
            except Exception as exc:
                st.error(f"AI planning failed: {exc}")
