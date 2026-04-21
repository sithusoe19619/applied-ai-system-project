import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_retrieval import RetrievedPassage
from ai_validation import BlockedRecommendation
from pawpal_chat import ChatContext, PawPalChatAssistant, SAFE_CHAT_FALLBACK, derive_chat_context
from pawpal_system import Owner, Pet, Priority, Task


class FakeChatClient:
    model = "fake-chat"

    def __init__(self, reply_text: str = "Safe pet-care answer."):
        self.reply_text = reply_text
        self.last_messages = None
        self.last_context_summary = ""

    def chat(self, messages, context_summary: str = ""):
        self.last_messages = messages
        self.last_context_summary = context_summary
        return self.reply_text


class FakeKnowledgeBase:
    def __init__(self):
        self.last_query = ""

    def retrieve(self, query: str, top_k: int = 4):
        self.last_query = query
        return [
            RetrievedPassage(
                doc_id="enrichment_and_monitoring",
                title="Enrichment",
                chunk_id="enrichment_and_monitoring#1",
                content="Short enrichment and monitoring routines can support comfort and engagement.",
                score=1.0,
            )
        ]


class TestChatContext:
    def test_result_context_takes_priority_over_draft_context(self):
        result_owner = Owner("Jordan", 60)
        result_pet = Pet("Mochi", "dog", 8, special_needs="stiff joints", breed="golden retriever")
        result_owner.add_pet(result_pet)

        draft_owner = Owner("Alex", 60)
        draft_pet = Pet("Pip", "cat", 3)
        draft_owner.add_pet(draft_pet)

        result_ai_run = SimpleNamespace(run_id="run123", extra_context="rainy week")

        context = derive_chat_context(
            result_owner=result_owner,
            result_pet=result_pet,
            result_ai_run=result_ai_run,
            draft_owner=draft_owner,
            draft_pet=draft_pet,
            draft_current_context="use indoor play",
        )

        assert context.mode == "result"
        assert context.fingerprint == "result:run123"
        assert context.current_context == "rainy week"

    def test_general_context_is_used_when_no_profile_or_result_exists(self):
        context = derive_chat_context(
            result_owner=None,
            result_pet=None,
            result_ai_run=None,
            draft_owner=None,
            draft_pet=None,
            draft_current_context="",
        )

        assert context.mode == "general"
        assert context.fingerprint == "general"


class TestChatAssistant:
    def test_chat_assistant_builds_context_from_pet_and_plan(self):
        owner = Owner("Jordan", 60)
        pet = Pet("Mochi", "dog", 8, special_needs="stiff joints", breed="golden retriever")
        owner.add_pet(pet)
        accepted_task = Task("Hydration check", 5, Priority.HIGH, "health", "", frequency="daily")
        ai_run = SimpleNamespace(
            run_id="run123",
            extra_context="rainy week",
            accepted_tasks=[accepted_task],
            blocked_recommendations=[BlockedRecommendation(name="Unsafe advice", reasons=["medical advice"])],
            retrieved_passages=[
                RetrievedPassage(
                    doc_id="senior_pet_support",
                    title="Senior Support",
                    chunk_id="senior_pet_support#1",
                    content="Senior pets benefit from short, low-impact activity blocks and observation.",
                    score=2.0,
                )
            ],
            reliability_score=0.84,
            warnings=["Use low-impact activity"],
        )
        context = ChatContext(
            mode="result",
            fingerprint="result:run123",
            banner="Using active result.",
            owner=owner,
            pet=pet,
            ai_run=ai_run,
            current_context="rainy week",
        )
        client = FakeChatClient()
        assistant = PawPalChatAssistant(knowledge_base=FakeKnowledgeBase(), client=client)

        reply = assistant.reply(
            messages=[{"role": "user", "content": "What should I focus on today?"}],
            context=context,
        )

        assert reply == "Safe pet-care answer."
        assert "Pet: Mochi" in client.last_context_summary
        assert "Species: dog" in client.last_context_summary
        assert "Breed: golden retriever" in client.last_context_summary
        assert "Age: 8" in client.last_context_summary
        assert "Special needs or vet guidance: stiff joints" in client.last_context_summary
        assert "Current situation or concern: rainy week" in client.last_context_summary
        assert "Accepted plan tasks: Hydration check (daily)" in client.last_context_summary
        assert "Helpful knowledge snippets:" in client.last_context_summary

    def test_chat_assistant_blocks_unsafe_freeform_response(self):
        context = ChatContext(mode="general", fingerprint="general", banner="General chat mode.")
        client = FakeChatClient("I can diagnose pain and increase dosage for now.")
        assistant = PawPalChatAssistant(knowledge_base=FakeKnowledgeBase(), client=client)

        reply = assistant.reply(
            messages=[{"role": "user", "content": "What should I do?"}],
            context=context,
        )

        assert reply == SAFE_CHAT_FALLBACK
