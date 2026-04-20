import os

import streamlit as st

from bedrock_client import DEFAULT_AWS_REGION, DEFAULT_BEDROCK_MODEL_ID, RecommendationProviderError
from pawpal_ai import PawPalAIPlanner
from pawpal_system import Owner, Pet


DEFAULT_PLANNING_DAY_MINUTES = 24 * 60
FORM_KEYS = [
    "sidebar_region",
    "sidebar_profile",
    "sidebar_model",
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
SPECIES_PLACEHOLDER = "-None-"


def clear_form_state() -> None:
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


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
        validation_errors.append("Please enter the owner name.")
    if not pet_name.strip():
        validation_errors.append("Please enter the pet name.")
    if not normalized_species:
        validation_errors.append("Please select a species.")
    if breed.strip() and normalized_species in {"dog", "cat"} and not Pet.is_valid_breed_label(breed, normalized_species):
        validation_errors.append('That breed does not look valid. Try a real breed name such as "Golden Retriever," "Siamese," or "Mixed."')
    if normalized_species == "other" and not custom_species.strip():
        validation_errors.append("Please tell us what kind of species this pet is.")

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
    owner = Owner(owner_name.strip(), available_minutes=DEFAULT_PLANNING_DAY_MINUTES)
    owner.add_pet(pet)
    return owner, pet, []


st.set_page_config(page_title="PawPal+ Pet Care AI", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+ Pet Care AI")
st.caption("Profile-driven pet care planning with AI-generated routines, reminders, and explainable guidance.")

st.sidebar.header("AI Settings")
sidebar_region = st.sidebar.text_input(
    "AWS region",
    value=st.session_state.get("sidebar_region", os.getenv("AWS_REGION", DEFAULT_AWS_REGION)),
    key="sidebar_region",
    help="Region used for Amazon Bedrock runtime requests.",
)
sidebar_profile = st.sidebar.text_input(
    "AWS profile (optional)",
    value=st.session_state.get("sidebar_profile", os.getenv("AWS_PROFILE", "")),
    key="sidebar_profile",
    help="Leave blank to use your default AWS credentials chain.",
)
sidebar_model = st.sidebar.text_input(
    "Bedrock model ID",
    value=st.session_state.get("sidebar_model", os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)),
    key="sidebar_model",
)
st.sidebar.caption("Authenticate with AWS CLI/profile credentials. Example: run `aws configure` before launching Streamlit.")

st.subheader("Pet Profile")
owner_name = st.text_input(
    "Owner name",
    value=st.session_state.get("owner_name", ""),
    key="owner_name",
    placeholder="Example: Jordan",
)
pet_name = st.text_input(
    "Pet name",
    value=st.session_state.get("pet_name", ""),
    key="pet_name",
    placeholder="Example: Mochi",
)
species_options = [SPECIES_PLACEHOLDER, "Dog", "Cat", "Other"]
species = st.selectbox(
    "Species",
    species_options,
    key="species",
)
normalized_species = "" if species == SPECIES_PLACEHOLDER else species.lower()

breed = ""
custom_species = ""
if normalized_species in {"dog", "cat"}:
    breed = st.text_input(
        "Breed (optional)",
        value=st.session_state.get("breed", ""),
        key="breed",
        placeholder="Examples: Golden Retriever, Domestic Shorthair, Mixed",
    )
    st.caption('Enter a real breed like "Golden Retriever," "Siamese," or "Mixed."')
elif normalized_species == "other":
    custom_species = st.text_input(
        "What kind of species?",
        value=st.session_state.get("custom_species", ""),
        key="custom_species",
        placeholder="Examples: Rabbit, Guinea Pig, Parrot, Monkey",
    )
    st.caption('Enter the animal name you want the AI to reason about, such as "Rabbit," "Guinea Pig," or "Monkey."')

pet_age = st.number_input(
    "Pet age (years)",
    min_value=0,
    max_value=40,
    value=st.session_state.get("pet_age", 0),
    key="pet_age",
)
special_needs = st.text_area(
    "Special needs or vet guidance",
    value=st.session_state.get("special_needs", ""),
    key="special_needs",
    placeholder="Kidney diet, mobility support, anxiety trigger, medication reminder, etc.",
)
st.caption('Write a short note like "Kidney Diet," "Mobility Support," or "Give medication after breakfast."')

if st.button("Save profile"):
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
        st.success(f"Profile is ready for this session for {owner.name} and {pet.name}.")

st.subheader("Care Planning")
current_context = st.text_area(
    "Current situation or concern (optional)",
    value=st.session_state.get("current_context", ""),
    key="current_context",
    placeholder="Examples: New limp today, rainy week so keep routines indoors, appetite slightly down, new medication reminder needed.",
)
st.caption('Describe what is happening right now, such as "Rainy week so keep exercise indoors" or "Appetite slightly down today."')

if st.button("Generate Pet Care Plan"):
    owner, pet, validation_errors = build_profile_from_inputs(
        owner_name=owner_name,
        pet_name=pet_name,
        species=species,
        breed=breed,
        custom_species=custom_species,
        pet_age=pet_age,
        special_needs=special_needs,
    )
    generation_errors = list(validation_errors)
    if not Pet.is_valid_aws_region(sidebar_region):
        generation_errors.append('AWS region should look like a real region code, such as "us-west-2."')
    if not Pet.is_valid_aws_profile(sidebar_profile):
        generation_errors.append("AWS profile contains invalid characters.")
    if not Pet.is_valid_bedrock_model_id(sidebar_model):
        generation_errors.append("Bedrock model ID should look like a real model identifier.")

    if generation_errors:
        for message in generation_errors:
            st.error(message)
    else:
        planner = PawPalAIPlanner(
            region=sidebar_region.strip(),
            profile=sidebar_profile.strip(),
            model=sidebar_model.strip(),
        )
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
            clear_form_state()
            st.switch_page("pages/Results.py")
        except RecommendationProviderError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"AI planning failed: {exc}")

if any(st.session_state.get(key) for key in RESULT_KEYS):
    st.info("A generated result is available in this session.")
    if st.button("Open Latest Result"):
        st.switch_page("pages/Results.py")
