import streamlit as st

from bedrock_client import RecommendationProviderError
from pawpal_chat import PawPalChatAssistant, derive_chat_context
from pawpal_system import Owner, Pet
from ui_theme import apply_theme, render_badges, render_card_heading, render_note, render_page_intro


RESULT_KEYS = ("result_owner", "result_pet", "result_ai_run")
CHAT_KEYS = ("chat_messages", "chat_context_fingerprint")
SPECIES_PLACEHOLDER = "-None-"


def clear_chat_state() -> None:
    for key in CHAT_KEYS:
        st.session_state.pop(key, None)


def format_provider_error(exc: RecommendationProviderError) -> str:
    message = str(exc)
    if "malformed JSON" in message:
        return f"Chat failed because Bedrock returned a response the app could not fully read: {message}"
    return f"Chat is unavailable until AWS Bedrock is configured correctly outside the app: {message}"


def build_profile_from_session() -> tuple[Owner | None, Pet | None]:
    owner_name = st.session_state.get("owner_name", "")
    pet_name = st.session_state.get("pet_name", "")
    species = st.session_state.get("species", SPECIES_PLACEHOLDER)
    breed = st.session_state.get("breed", "")
    custom_species = st.session_state.get("custom_species", "")
    pet_age = st.session_state.get("pet_age", 0)
    special_needs = st.session_state.get("special_needs", "")

    normalized_species = "" if species == SPECIES_PLACEHOLDER else species.lower()
    if not owner_name.strip() or not pet_name.strip() or not normalized_species:
        return None, None
    if normalized_species == "other" and not custom_species.strip():
        return None, None

    pet = Pet(
        pet_name.strip(),
        normalized_species,
        age=int(pet_age),
        special_needs=special_needs.strip(),
        breed=breed.strip(),
        custom_species=custom_species.strip(),
    )
    owner = Owner(owner_name.strip(), available_minutes=24 * 60)
    owner.add_pet(pet)
    return owner, pet


apply_theme()

result_owner = st.session_state.get("result_owner")
result_pet = st.session_state.get("result_pet")
result_ai_run = st.session_state.get("result_ai_run")
draft_owner, draft_pet = build_profile_from_session()
draft_current_context = st.session_state.get("current_context", "")

chat_context = derive_chat_context(
    result_owner=result_owner,
    result_pet=result_pet,
    result_ai_run=result_ai_run,
    draft_owner=draft_owner,
    draft_pet=draft_pet,
    draft_current_context=draft_current_context,
)

stored_fingerprint = st.session_state.get("chat_context_fingerprint")
if stored_fingerprint and stored_fingerprint != chat_context.fingerprint:
    clear_chat_state()

st.session_state["chat_context_fingerprint"] = chat_context.fingerprint
messages = st.session_state.setdefault("chat_messages", [])

header_col, action_col = st.columns([2.25, 1], gap="large")
with header_col:
    render_page_intro(
        "Help and Questions",
        "Ask Paw",
        "Ask follow-up questions about your pet's routine, reminders, enrichment, or current care plan.",
    )
    badges = [chat_context.mode.title()]
    if result_pet:
        badges.append(f"Active result for {result_pet.name}")
    elif draft_pet:
        badges.append(f"Draft profile for {draft_pet.name}")
    render_badges(badges)

with action_col:
    with st.container(border=True):
        render_card_heading(
            "Navigation",
            "Move between chat, the planner, and the current care plan.",
        )
        if result_ai_run:
            if st.button("View Current Result", type="secondary", use_container_width=True):
                st.switch_page("pages/Results.py")
        if st.button("Back to Planner", type="secondary", use_container_width=True):
            st.switch_page("planner.py")

render_note(chat_context.banner, title="Using this information.")

if not messages:
    with st.container(border=True):
        render_card_heading(
            "Start Here",
            "You can ask about routines, schedule changes, enrichment ideas, reminders, or what a suggested task means.",
        )

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask a question about your pet or care plan")
if prompt:
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    assistant = PawPalChatAssistant()
    try:
        reply = assistant.reply(messages=messages, context=chat_context)
    except RecommendationProviderError as exc:
        reply = format_provider_error(exc)
    except Exception as exc:
        reply = f"Chat failed: {exc}"

    messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)
