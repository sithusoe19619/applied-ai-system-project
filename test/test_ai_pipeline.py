import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_logging import AIRunLogger
from ai_retrieval import LocalKnowledgeBase
from ai_validation import RecommendationValidator
from bedrock_client import RecommendationCandidate, SpeciesProfile
from pawpal_ai import PawPalAIPlanner
from pawpal_system import Owner, Pet, Priority, Task


class FakeClaudeClient:
    model = "fake-claude"
    last_recommend_kwargs = None

    def profile_species(self, species: str, breed: str = "", special_needs: str = ""):
        normalized = species.strip().lower()
        if normalized == "monkey":
            return SpeciesProfile(
                species_label="Monkey",
                lifespan_min_years=20,
                lifespan_max_years=35,
                characteristics="Monkeys often need complex enrichment, social structure, secure housing, and close observation of stress, diet routine, and handling tolerance.",
                summary="Pip is in the young stage for a monkey. A typical companion-care lifespan is about 20-35 years.",
                confidence=0.73,
            )
        return SpeciesProfile(
            species_label=species,
            lifespan_min_years=10,
            lifespan_max_years=12,
            characteristics="This pet benefits from predictable routines, hydration monitoring, enrichment, and close observation of mobility, appetite, and behavior changes.",
            summary=f"A typical lifespan for {species} is about 10-12 years in a pet-care context.",
            confidence=0.71,
        )

    def recommend(self, **kwargs):
        self.last_recommend_kwargs = kwargs
        return [
            RecommendationCandidate(
                name="Mobility check",
                duration_minutes=10,
                priority="high",
                category="health",
                notes="Observe gait and comfort, then record completion.",
                scheduled_time="08:00",
                frequency="daily",
                rationale="Senior pets benefit from short comfort checks and observation.",
                source_ids=["senior_pet_support"],
                confidence=0.72,
            ),
            RecommendationCandidate(
                name="Calm enrichment",
                duration_minutes=15,
                priority="medium",
                category="enrichment",
                notes="Use a short, low-impact play or brushing session.",
                scheduled_time="16:00",
                frequency="daily",
                rationale="Short enrichment blocks help maintain quality of life without intense activity.",
                source_ids=["senior_pet_support"],
                confidence=0.7,
            ),
        ]


class TestKnowledgeBase:
    def test_retrieval_returns_relevant_senior_doc(self):
        kb = LocalKnowledgeBase()
        results = kb.retrieve("senior dog mobility support hydration routine", top_k=3)

        assert results
        assert results[0].doc_id == "senior_pet_support"


class TestValidator:
    def test_validator_blocks_unsafe_or_ungrounded_recommendations(self):
        validator = RecommendationValidator()
        kb = LocalKnowledgeBase()
        passages = kb.retrieve("senior dog medication routine", top_k=3)

        recommendations = [
            RecommendationCandidate(
                name="Adjust medication dosage",
                duration_minutes=5,
                priority="high",
                category="health",
                notes="Increase dosage if the pet seems uncomfortable.",
                scheduled_time="08:00",
                frequency="daily",
                rationale="This will treat pain quickly.",
                source_ids=["medication_and_safety"],
                confidence=0.6,
            ),
            RecommendationCandidate(
                name="Hydration check",
                duration_minutes=5,
                priority="medium",
                category="health",
                notes="Refresh water and observe appetite.",
                scheduled_time="09:00",
                frequency="daily",
                rationale="Track hydration for a senior pet.",
                source_ids=[],
                confidence=0.6,
            ),
        ]

        result = validator.validate(recommendations, passages, available_minutes=60)

        assert result.accepted == []
        assert len(result.blocked) == 2
        assert result.reliability_score == 0.0


class TestPlanner:
    def test_planner_adds_validated_ai_tasks_and_logs_run(self, tmp_path):
        owner = Owner("Jordan", available_minutes=60)
        pet = Pet(
            "Mochi",
            "dog",
            11,
            special_needs="stiff joints",
            breed="golden retriever",
        )
        owner.add_pet(pet)

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=FakeClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="build a low-impact senior routine",
            extra_context="owner has one hour today",
            apply_to_pet=True,
        )

        assert len(run.accepted_tasks) == 2
        assert any(task.ai_generated for task in pet.tasks)
        assert len(run.schedule_plan["scheduled"]) == 2
        assert run.schedule_plan["skipped"] == []
        assert os.path.exists(run.log_path)
        assert run.reliability_score > 0
        assert pet.get_lifespan_range_years() == (10, 12)
        assert pet.species_profile_source == "Model-derived profile from fake-claude"

    def test_planner_replaces_old_ai_tasks_but_keeps_manual_tasks(self, tmp_path):
        owner = Owner("Jordan", available_minutes=45)
        pet = Pet("Addy", "cat", 8, special_needs="kidney diet")
        manual = Task("Breakfast", 10, Priority.HIGH, "nutrition", "", scheduled_time="07:30")
        stale_ai = Task(
            "Old AI task",
            10,
            Priority.LOW,
            "general",
            "",
            scheduled_time="12:00",
            ai_generated=True,
            source_ids=["old_doc"],
            validation_status="validated",
        )
        pet.add_task(manual)
        pet.add_task(stale_ai)
        owner.add_pet(pet)

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=FakeClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        planner.recommend_and_schedule(owner=owner, pet=pet, goal="kidney support routine", apply_to_pet=True)

        names = [task.name for task in pet.tasks]
        assert "Breakfast" in names
        assert "Old AI task" not in names
        assert "Mobility check" in names

    def test_planner_uses_model_species_profile_for_other_species(self, tmp_path):
        owner = Owner("Jordan", available_minutes=45)
        pet = Pet("Pip", "other", 5, custom_species="Monkey")
        owner.add_pet(pet)

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=FakeClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        planner.recommend_and_schedule(owner=owner, pet=pet, goal="build a routine", apply_to_pet=True)

        assert pet.get_lifespan_range_years() == (20, 35)
        assert "complex enrichment" in pet.get_species_characteristics().lower()
        assert "20-35 years" in pet.get_age_context()["summary"]

    def test_planner_enforces_weekly_only_request(self, tmp_path):
        owner = Owner("Jordan", available_minutes=60)
        pet = Pet("Mochi", "dog", 11, special_needs="stiff joints", breed="golden retriever")
        owner.add_pet(pet)
        client = FakeClaudeClient()

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=client,
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="build a low-impact senior routine",
            extra_context="generate weekly plan only",
            apply_to_pet=True,
        )

        assert client.last_recommend_kwargs["species"] == "dog"
        assert client.last_recommend_kwargs["breed"] == "golden retriever"
        assert client.last_recommend_kwargs["age"] == 11
        assert client.last_recommend_kwargs["special_needs"] == "stiff joints"
        assert client.last_recommend_kwargs["extra_context"] == "generate weekly plan only"
        assert client.last_recommend_kwargs["requested_frequencies"] == ["weekly"]
        assert run.accepted_tasks == []
        assert len(run.blocked_recommendations) == 2
        assert all("requested cadence" in " ".join(item.reasons).lower() for item in run.blocked_recommendations)


class TestPetProfileContext:
    def test_age_context_interprets_senior_dog(self):
        pet = Pet(
            "Mochi",
            "dog",
            11,
            special_needs="stiff joints",
            breed="golden retriever",
        )

        context = pet.get_age_context()

        assert context["life_stage"] == "senior"
        assert context["lifespan_range_years"] == (10, 13)
        assert "typical lifespan" in context["summary"].lower()

    def test_species_characteristics_are_inferred_for_cat(self):
        pet = Pet("Luna", "cat", 9, special_needs="kidney diet", breed="domestic shorthair")

        characteristics = pet.get_species_characteristics()

        assert "feeding consistency" in characteristics.lower()
        assert "litter" in characteristics.lower()

    def test_breed_traits_fall_back_to_species_traits_when_unknown(self):
        pet = Pet("Mochi", "dog", 6, breed="mixed")

        characteristics = pet.get_species_characteristics()

        assert "dogs often benefit" in characteristics.lower()
        assert "breed context" in characteristics.lower()

    def test_effective_species_uses_custom_species_for_other(self):
        pet = Pet("Pip", "other", 2, custom_species="rabbit")

        assert pet.get_effective_species_label() == "rabbit"

    def test_breed_validation_rejects_obvious_junk(self):
        assert Pet.is_valid_breed_label("adfasf", "dog") is False
        assert Pet.is_valid_breed_label("ehfasdhf;asd2324", "dog") is False
        assert Pet.is_valid_breed_label("golden retriever", "dog") is True
        assert Pet.is_valid_breed_label("siamese", "cat") is True
        assert Pet.is_valid_breed_label("mixed", "dog") is True
        assert Pet.is_valid_breed_label("beagle", "cat") is False

    def test_custom_species_validation_accepts_open_ended_labels(self):
        assert Pet.is_valid_species_label("Monkey") is True
        assert Pet.is_valid_species_label("Capuchin Monkey") is True
        assert Pet.is_valid_species_label("adfasf") is True
        assert Pet.is_valid_species_label("mini lop rabbit") is True
        assert Pet.is_valid_species_label("rabbit") is True

    def test_context_text_validation_allows_human_notes_but_blocks_garbage(self):
        assert Pet.is_valid_context_text("Kidney diet, mobility support, and 2x daily meds.") is True
        assert Pet.is_valid_context_text("rainy weak so keep routiens indoors") is True
        assert Pet.is_valid_context_text(
            "Senior cat with stiff joints. Needs short low-impact exercise, hydration monitoring, and calm\n enrichment."
        ) is True
        assert Pet.is_valid_context_text("sdhfoashdfoi345u23002uxbvx3") is False
        assert Pet.is_valid_context_text("!!!@@@###") is False

    def test_bedrock_settings_validation_checks_structure(self):
        assert Pet.is_valid_aws_region("us-west-2") is True
        assert Pet.is_valid_aws_region("west2") is False
        assert Pet.is_valid_aws_profile("default") is True
        assert Pet.is_valid_aws_profile("bad profile!") is False
        assert Pet.is_valid_bedrock_model_id("global.anthropic.claude-haiku-4-5-20251001-v1:0") is True
        assert Pet.is_valid_bedrock_model_id("not a valid model id") is False

    def test_owner_save_and_load_persists_characteristics(self, tmp_path):
        owner = Owner("Jordan", available_minutes=1440)
        pet = Pet(
            "Luna",
            "cat",
            9,
            special_needs="kidney diet",
            breed="domestic shorthair",
            custom_species="",
            lifespan_min_years=13,
            lifespan_max_years=18,
            species_profile_summary="Luna is in the adult stage for a cat. A typical lifespan is about 13-18 years.",
            species_profile_source="Model-derived profile from fake-claude",
        )
        owner.add_pet(pet)

        path = tmp_path / "owner.json"
        owner.save_to_json(str(path))
        loaded = Owner.load_from_json(str(path))

        assert loaded is not None
        assert loaded.pets[0].breed == "domestic shorthair"
        assert loaded.pets[0].custom_species == ""
        assert loaded.pets[0].get_lifespan_range_years() == (13, 18)
        assert loaded.pets[0].species_profile_source == "Model-derived profile from fake-claude"
