from dataclasses import dataclass
from typing import Any, List
import hashlib

from ai_retrieval import LocalKnowledgeBase, RetrievedPassage
from ai_validation import UNSAFE_PATTERNS
from bedrock_client import BedrockRecommendationClient
from pawpal_system import Owner, Pet


SAFE_CHAT_FALLBACK = (
    "I can help with general pet-care guidance, but I cannot diagnose conditions, change medication dosages, "
    "prescribe treatment, or replace a veterinarian. For medical decisions or urgent symptoms, contact your veterinarian."
)


@dataclass
class ChatContext:
    mode: str
    fingerprint: str
    banner: str
    owner: Owner | None = None
    pet: Pet | None = None
    ai_run: Any = None
    current_context: str = ""


def derive_chat_context(
    result_owner: Owner | None,
    result_pet: Pet | None,
    result_ai_run: Any | None,
    draft_owner: Owner | None,
    draft_pet: Pet | None,
    draft_current_context: str = "",
) -> ChatContext:
    if result_owner and result_pet and result_ai_run:
        return ChatContext(
            mode="result",
            fingerprint=f"result:{result_ai_run.run_id}",
            banner=f"Using the active AI result for {result_pet.name}.",
            owner=result_owner,
            pet=result_pet,
            ai_run=result_ai_run,
            current_context=getattr(result_ai_run, "extra_context", "") or "",
        )

    if draft_owner and draft_pet:
        fingerprint_input = "|".join(
            [
                draft_owner.name,
                draft_pet.name,
                draft_pet.species,
                draft_pet.breed,
                draft_pet.custom_species,
                str(draft_pet.age),
                draft_pet.special_needs,
                draft_current_context,
            ]
        )
        fingerprint = hashlib.sha1(fingerprint_input.encode("utf-8")).hexdigest()[:12]
        return ChatContext(
            mode="draft",
            fingerprint=f"profile:{fingerprint}",
            banner=f"Using the current pet profile draft for {draft_pet.name}.",
            owner=draft_owner,
            pet=draft_pet,
            current_context=draft_current_context,
        )

    return ChatContext(
        mode="general",
        fingerprint="general",
        banner="General chat mode. Add a pet profile for more personalized answers.",
    )


class PawPalChatAssistant:
    """Coordinate contextual pet-care chat replies using Bedrock."""

    def __init__(
        self,
        knowledge_base: LocalKnowledgeBase | None = None,
        client: BedrockRecommendationClient | None = None,
        region: str | None = None,
        profile: str | None = None,
        model: str | None = None,
    ):
        self.knowledge_base = knowledge_base or LocalKnowledgeBase()
        self.client = client or BedrockRecommendationClient(region=region, profile=profile, model=model)

    def reply(self, messages: List[dict[str, str]], context: ChatContext) -> str:
        latest_user_message = next(
            (message["content"] for message in reversed(messages) if message.get("role") == "user" and message.get("content")),
            "",
        )
        passages = self._get_supporting_passages(context, latest_user_message)
        context_summary = self._build_context_summary(context, passages)
        response = self.client.chat(messages=messages, context_summary=context_summary)
        return self._guard_chat_response(response)

    def _get_supporting_passages(self, context: ChatContext, latest_user_message: str) -> List[RetrievedPassage]:
        if context.ai_run and getattr(context.ai_run, "retrieved_passages", None):
            return list(context.ai_run.retrieved_passages[:4])

        query_parts = [latest_user_message]
        if context.pet:
            query_parts.extend(
                [
                    context.pet.get_effective_species_label(),
                    context.pet.get_effective_breed_label(),
                    f"age {context.pet.age}",
                    context.pet.special_needs,
                    context.current_context,
                ]
            )
        query = " ".join(part for part in query_parts if part).strip()
        if not query:
            return []
        return self.knowledge_base.retrieve(query, top_k=4)

    def _build_context_summary(self, context: ChatContext, passages: List[RetrievedPassage]) -> str:
        lines = [f"Chat mode: {context.mode}."]
        if context.owner and context.pet:
            lines.extend(
                [
                    f"Owner: {context.owner.name}",
                    f"Pet: {context.pet.name}",
                    f"Species: {context.pet.get_effective_species_label()}",
                    f"Breed: {context.pet.get_effective_breed_label() or 'not provided'}",
                    f"Age: {context.pet.age}",
                    f"Special needs or vet guidance: {context.pet.special_needs or 'none'}",
                ]
            )
            if context.pet.species_profile_summary:
                lines.append(f"AI-derived species profile summary: {context.pet.species_profile_summary}")
            if context.current_context:
                lines.append(f"Current situation or concern: {context.current_context}")

        if context.ai_run:
            accepted = ", ".join(
                f"{task.name} ({task.frequency})"
                for task in getattr(context.ai_run, "accepted_tasks", [])[:8]
            ) or "none"
            blocked = ", ".join(
                blocked_item.name
                for blocked_item in getattr(context.ai_run, "blocked_recommendations", [])[:5]
            ) or "none"
            lines.extend(
                [
                    f"Current plan reliability score: {getattr(context.ai_run, 'reliability_score', 0.0):.2f}",
                    f"Accepted plan tasks: {accepted}",
                    f"Blocked recommendations: {blocked}",
                ]
            )
            warnings = getattr(context.ai_run, "warnings", [])
            if warnings:
                lines.append(f"Warnings: {' | '.join(warnings)}")

        if passages:
            lines.append("Helpful knowledge snippets:")
            lines.extend(f"- [{passage.doc_id}] {passage.content}" for passage in passages)

        return "\n".join(lines)

    def _guard_chat_response(self, response_text: str) -> str:
        lowered = response_text.lower()
        if any(pattern.search(lowered) for pattern in UNSAFE_PATTERNS):
            return SAFE_CHAT_FALLBACK
        return response_text.strip()
