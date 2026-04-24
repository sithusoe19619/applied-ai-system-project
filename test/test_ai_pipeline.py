from contextlib import nullcontext
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ui_components
from ai_logging import AIRunLogger
from ai_retrieval import LocalKnowledgeBase, RetrievedPassage
from ai_validation import RecommendationValidator
from bedrock_client import RecommendationCandidate, SpeciesProfile
from pawpal_ai import PawPalAIPlanner
from pawpal_system import Owner, Pet, Priority, Scheduler, Task
from ui_components import (
    build_task_reference_entries,
    build_daily_care_tabs,
    build_profile_priority_groups,
    get_monthly_schedule_labels,
    get_task_guidance_schedule_label,
    get_task_support_line,
    get_weekly_schedule_label,
    render_compact_task_list,
    render_task_detail_expanders,
    sort_tasks_for_section,
)


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


class CoverageBackfillClaudeClient(FakeClaudeClient):
    def __init__(self):
        self.calls = []

    def recommend(self, **kwargs):
        self.last_recommend_kwargs = kwargs
        self.calls.append(kwargs)
        requested = kwargs.get("requested_frequencies", [])
        if requested == ["weekly", "monthly", "as needed"]:
            return [
                RecommendationCandidate(
                    name="Weekly weight check",
                    duration_minutes=5,
                    priority="medium",
                category="health",
                notes="Weigh Mochi once a week and note changes.",
                scheduled_time="09:00",
                frequency="weekly",
                scheduled_weekday="Monday",
                rationale="Weekly tracking helps monitor joint health and appetite changes.",
                source_ids=["senior_pet_support"],
                confidence=0.68,
            ),
                RecommendationCandidate(
                    name="Monthly preventive refill",
                    duration_minutes=10,
                    priority="medium",
                    category="preventive",
                    notes="Restock or apply the monthly preventive on schedule.",
                    scheduled_time="10:00",
                    frequency="monthly",
                    scheduled_month_weeks=["Week 1"],
                    rationale="Monthly preventive care is part of a complete routine for older dogs.",
                    source_ids=["medication_and_safety"],
                    confidence=0.66,
                ),
                RecommendationCandidate(
                    name="Monitor appetite changes",
                    duration_minutes=10,
                    priority="high",
                    category="health",
                    notes="If appetite drops after active days, track food and water intake closely.",
                    scheduled_time="18:30",
                    frequency="as needed",
                    rationale="Condition-based appetite guidance is warranted when the profile mentions fluctuating appetite.",
                    source_ids=["senior_pet_support"],
                    confidence=0.7,
                ),
            ]
        return super().recommend(**kwargs)


class DailyVariationClaudeClient(FakeClaudeClient):
    def __init__(self):
        self.calls = []

    def recommend(self, **kwargs):
        self.last_recommend_kwargs = kwargs
        self.calls.append(kwargs)
        requested = kwargs.get("requested_frequencies", [])
        if requested == ["weekly", "monthly"]:
            return [
                RecommendationCandidate(
                    name="Weekly weight check",
                    duration_minutes=5,
                    priority="medium",
                category="health",
                notes="Weigh Mochi once a week and note changes.",
                scheduled_time="09:00",
                frequency="weekly",
                scheduled_weekday="Monday",
                rationale="Weekly tracking helps monitor joint health and appetite changes.",
                source_ids=["senior_pet_support"],
                confidence=0.68,
            ),
                RecommendationCandidate(
                    name="Monthly preventive refill",
                    duration_minutes=10,
                    priority="medium",
                    category="preventive",
                    notes="Restock or apply the monthly preventive on schedule.",
                    scheduled_time="10:00",
                    frequency="monthly",
                    scheduled_month_weeks=["Week 1"],
                    rationale="Monthly preventive care is part of a complete routine.",
                    source_ids=["medication_and_safety"],
                    confidence=0.66,
                ),
            ]
        if requested == ["daily"]:
            return [
                RecommendationCandidate(
                    name="Neighborhood walk",
                    duration_minutes=15,
                    priority="medium",
                    category="exercise",
                    notes="Take a short neighborhood walk at an easy pace.",
                    scheduled_time="10:00",
                    frequency="daily",
                    rationale="A short walk adds structured movement without overdoing activity.",
                    source_ids=["senior_pet_support"],
                    confidence=0.7,
                ),
                RecommendationCandidate(
                    name="Snack time",
                    duration_minutes=10,
                    priority="medium",
                    category="nutrition",
                    notes="Offer a small approved snack during a calm break.",
                    scheduled_time="13:00",
                    frequency="daily",
                    rationale="A controlled snack adds variety to the daytime routine.",
                    source_ids=["senior_pet_support"],
                    confidence=0.67,
                ),
                RecommendationCandidate(
                    name="Dog park outing",
                    duration_minutes=20,
                    priority="medium",
                    category="enrichment",
                    notes="Plan a short, structured dog park outing when energy is steady.",
                    scheduled_time="16:00",
                    frequency="daily",
                    rationale="Occasional outings create distinct daily-care themes across the week.",
                    source_ids=["senior_pet_support"],
                    confidence=0.66,
                ),
                RecommendationCandidate(
                    name="Spa-style grooming check",
                    duration_minutes=10,
                    priority="medium",
                    category="grooming",
                    notes="Brush the coat and check paws during a calm grooming block.",
                    scheduled_time="20:00",
                    frequency="daily",
                    rationale="Short grooming blocks add another non-basic daily-care theme.",
                    source_ids=["senior_pet_support"],
                    confidence=0.69,
                ),
            ]
        return [
            RecommendationCandidate(
                name="Morning feeding",
                duration_minutes=15,
                priority="high",
                category="nutrition",
                notes="Serve the morning meal on a consistent schedule.",
                scheduled_time="07:00",
                frequency="daily",
                rationale="A consistent feeding routine supports daily care stability.",
                source_ids=["senior_pet_support"],
                confidence=0.72,
            ),
            RecommendationCandidate(
                name="Evening medication",
                duration_minutes=5,
                priority="high",
                category="health",
                notes="Give the evening medication with food.",
                scheduled_time="19:00",
                frequency="daily",
                rationale="Daily medication is a core routine task.",
                source_ids=["medication_and_safety"],
                confidence=0.73,
            ),
            RecommendationCandidate(
                name="Bedtime wind-down",
                duration_minutes=15,
                priority="medium",
                category="routine",
                notes="Keep the evening rest routine calm and predictable.",
                scheduled_time="21:00",
                frequency="daily",
                rationale="A steady rest routine is part of the daily basics.",
                source_ids=["senior_pet_support"],
                confidence=0.7,
            ),
        ]


class CareAlertFallbackClaudeClient(FakeClaudeClient):
    def __init__(self):
        self.calls = []

    def recommend(self, **kwargs):
        self.last_recommend_kwargs = kwargs
        self.calls.append(kwargs)
        requested = kwargs.get("requested_frequencies", [])
        if requested == ["as needed"]:
            return []
        return [
            RecommendationCandidate(
                name="Morning respiratory check",
                duration_minutes=5,
                priority="high",
                category="monitoring",
                notes="Observe breathing effort and appetite early in the day.",
                scheduled_time="08:00",
                frequency="daily",
                rationale="Daily monitoring supports chronic respiratory care.",
                source_ids=["enrichment_and_monitoring"],
                confidence=0.72,
            ),
            RecommendationCandidate(
                name="Weekly weigh-in",
                duration_minutes=5,
                priority="high",
                category="monitoring",
                notes="Check weight once a week and log any loss.",
                scheduled_time="10:00",
                frequency="weekly",
                scheduled_weekday="Monday",
                rationale="Weight checks help monitor low body weight risk.",
                source_ids=["enrichment_and_monitoring"],
                confidence=0.71,
            ),
            RecommendationCandidate(
                name="Monthly supply review",
                duration_minutes=10,
                priority="medium",
                category="supplies",
                notes="Confirm pellets, medication, and cage care supplies are stocked.",
                scheduled_time="09:00",
                frequency="monthly",
                scheduled_month_weeks=["Week 1"],
                rationale="Monthly supply review prevents care gaps.",
                source_ids=["medication_and_safety"],
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

        result = validator.validate(recommendations, passages)

        assert result.accepted == []
        assert len(result.blocked) == 2
        assert result.reliability_score == 0.0

    def test_validator_accepts_valid_monthly_month_weeks_and_blocks_invalid_shapes(self):
        validator = RecommendationValidator()
        kb = LocalKnowledgeBase()
        passages = kb.retrieve("monthly preventive restock follow-up care", top_k=5)
        source_ids = [passage.doc_id for passage in passages]
        assert source_ids

        valid = RecommendationCandidate(
            name="Monthly preventive refill",
            duration_minutes=10,
            priority="medium",
            category="preventive",
            notes="Restock or apply the monthly preventive on schedule.",
            scheduled_time="10:00",
            frequency="monthly",
            scheduled_month_weeks=["Week 1", "Week 3"],
            rationale="Twice-monthly preventive follow-up is required for this case.",
            source_ids=[source_ids[0]],
            confidence=0.66,
        )
        invalid_monthly = RecommendationCandidate(
            name="Broken monthly task",
            duration_minutes=10,
            priority="medium",
            category="preventive",
            notes="Bad month-week data.",
            scheduled_time="10:00",
            frequency="monthly",
            scheduled_month_weeks=["Week 1", "Week 2", "Week 3"],
            rationale="This should fail because it has too many weeks.",
            source_ids=[source_ids[0]],
            confidence=0.66,
        )
        invalid_daily = RecommendationCandidate(
            name="Daily hydration check",
            duration_minutes=5,
            priority="high",
            category="health",
            notes="Refresh water and observe intake.",
            scheduled_time="08:00",
            frequency="daily",
            scheduled_month_weeks=["Week 4"],
            rationale="This should fail because only monthly tasks may carry month-weeks.",
            source_ids=[source_ids[0]],
            confidence=0.7,
        )

        result = validator.validate([valid, invalid_monthly, invalid_daily], passages)

        assert [item.name for item in result.accepted] == ["Monthly preventive refill"]
        blocked_reasons = {item.name: " ".join(item.reasons) for item in result.blocked}
        assert "1 or 2 scheduled month-weeks" in blocked_reasons["Broken monthly task"]
        assert "only monthly recommendations may include scheduled month-weeks" in blocked_reasons["Daily hydration check"].lower()

    def test_validator_normalizes_minor_as_needed_formatting_gaps(self):
        validator = RecommendationValidator()
        kb = LocalKnowledgeBase()
        passages = kb.retrieve("respiratory appetite lethargy monitoring", top_k=3)
        source_ids = [passage.doc_id for passage in passages]

        recommendation = RecommendationCandidate(
            name="Breathing change alert",
            duration_minutes=0,
            priority="high",
            category="monitoring",
            notes="If breathing effort worsens, document the change and contact the veterinarian.",
            scheduled_time="",
            frequency="as needed",
            rationale="Respiratory changes are meaningful alert signs in this care context.",
            source_ids=[source_ids[0]],
            confidence=0.7,
        )

        result = validator.validate([recommendation], passages)

        assert len(result.accepted) == 1
        assert result.accepted[0].duration_minutes == 2
        assert result.accepted[0].scheduled_time == "00:00"


class TestPlanner:
    def test_planner_adds_validated_ai_tasks_and_logs_run(self, tmp_path):
        owner = Owner("Jordan")
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
        assert run.goal == "build a low-impact senior routine"
        assert run.extra_context == "owner has one hour today"
        assert pet.get_lifespan_range_years() == (10, 12)
        assert pet.species_profile_source == "Model-derived profile from fake-claude"

    def test_planner_replaces_old_ai_tasks_but_keeps_manual_tasks(self, tmp_path):
        owner = Owner("Jordan")
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
        owner = Owner("Jordan")
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
        owner = Owner("Jordan")
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

    def test_planner_backfills_missing_weekly_monthly_and_as_needed_tasks(self, tmp_path):
        owner = Owner("Jordan")
        pet = Pet("Mochi", "dog", 11, special_needs="stiff joints", breed="golden retriever")
        owner.add_pet(pet)
        client = CoverageBackfillClaudeClient()

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=client,
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="Create a complete pet care plan with daily, weekly, monthly tasks, reminders, and safe condition-aware guidance.",
            extra_context="Reduced appetite after active days; include watch-for-change guidance.",
            apply_to_pet=True,
        )

        frequencies = {task.frequency for task in run.accepted_tasks}
        assert "daily" in frequencies
        assert "weekly" in frequencies
        assert "monthly" in frequencies
        assert "as needed" in frequencies
        assert len(client.calls) == 3
        assert client.calls[1]["requested_frequencies"] == ["weekly", "monthly", "as needed"]
        assert client.calls[2]["requested_frequencies"] == ["daily"]

    def test_planner_backfills_care_alerts_from_full_input_when_model_misses_as_needed(self, tmp_path):
        owner = Owner("Maya")
        pet = Pet(
            "Kito",
            "other",
            18,
            custom_species="African Grey Parrot",
            special_needs=(
                "Chronic respiratory disease with recent flare-ups, low body weight risk, and stress-related feather "
                "plucking. Kito needs close daily observation of breathing effort, appetite, droppings, energy, "
                "vocalization, and tolerance for activity."
            ),
        )
        owner.add_pet(pet)
        client = CareAlertFallbackClaudeClient()

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=client,
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="Create a complete pet care plan with daily, weekly, monthly tasks, reminders, and safe condition-aware guidance.",
            extra_context=(
                "Owner works from home on Mondays, Wednesdays, and Fridays and wants clear watch-for-change guidance "
                "for labored breathing, appetite drop, lethargy, or worsening feather damage."
            ),
            apply_to_pet=True,
        )

        care_alerts = [task for task in run.accepted_tasks if task.frequency == "as needed"]
        combined_alert_text = " ".join(f"{task.name} {task.notes}" for task in care_alerts).lower()

        assert client.calls[1]["requested_frequencies"] == ["as needed"]
        assert len(care_alerts) >= 2
        assert "breathing" in combined_alert_text
        assert "appetite" in combined_alert_text
        assert "letharg" in combined_alert_text or "activity tolerance" in combined_alert_text
        assert "feather" in combined_alert_text

    def test_planner_preserves_weekly_scheduled_weekday_without_changing_other_cadences(self, tmp_path):
        class WeekdayClaudeClient(FakeClaudeClient):
            def recommend(self, **kwargs):
                return [
                    RecommendationCandidate(
                        name="Weekly weight check",
                        duration_minutes=5,
                        priority="medium",
                        category="health",
                        notes="Weigh Mochi once a week and note changes.",
                        scheduled_time="09:00",
                        frequency="weekly",
                        scheduled_weekday="Tuesday",
                        rationale="A Tuesday check-in leaves Monday for routine reset and supports midweek monitoring.",
                        source_ids=["senior_pet_support"],
                        confidence=0.68,
                    ),
                    RecommendationCandidate(
                        name="Morning feeding",
                        duration_minutes=15,
                        priority="high",
                        category="nutrition",
                        notes="Serve breakfast on a consistent schedule.",
                        scheduled_time="07:00",
                        frequency="daily",
                        rationale="Consistent feeding is part of the everyday routine.",
                        source_ids=["senior_pet_support"],
                        confidence=0.72,
                    ),
                    RecommendationCandidate(
                        name="Monthly preventive refill",
                        duration_minutes=10,
                        priority="medium",
                        category="preventive",
                        notes="Restock or apply the monthly preventive on schedule.",
                        scheduled_time="10:00",
                        frequency="monthly",
                        scheduled_month_weeks=["Week 4"],
                        rationale="Monthly preventive care is part of a complete routine.",
                        source_ids=["senior_pet_support"],
                        confidence=0.66,
                    ),
                ]

        owner = Owner("Jordan")
        pet = Pet("Mochi", "dog", 11, special_needs="stiff joints", breed="golden retriever")
        owner.add_pet(pet)

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=WeekdayClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="Create a complete pet care plan with daily, weekly, and monthly tasks.",
            apply_to_pet=True,
        )

        weekly_task = next(task for task in run.accepted_tasks if task.frequency == "weekly")
        daily_task = next(task for task in run.accepted_tasks if task.frequency == "daily")
        monthly_task = next(task for task in run.accepted_tasks if task.frequency == "monthly")

        assert weekly_task.scheduled_weekday == "Tuesday"
        assert daily_task.scheduled_weekday == ""
        assert monthly_task.scheduled_weekday == ""
        assert monthly_task.scheduled_month_weeks == ["Week 4"]

    def test_planner_preserves_monthly_month_weeks_into_task_snapshots(self, tmp_path):
        class MonthlyWeeksClaudeClient(FakeClaudeClient):
            def recommend(self, **kwargs):
                return [
                    RecommendationCandidate(
                        name="Monthly respiratory review",
                        duration_minutes=15,
                        priority="medium",
                        category="monitoring",
                        notes="Review breathing notes and prep for follow-up.",
                        scheduled_time="09:00",
                        frequency="monthly",
                        scheduled_month_weeks=["Week 2", "Week 4"],
                        rationale="A twice-monthly review keeps monitoring organized.",
                        source_ids=["senior_pet_support"],
                        confidence=0.7,
                    ),
                ]

        owner = Owner("Jordan")
        pet = Pet("Rio", "other", 6, custom_species="Parrot")
        owner.add_pet(pet)

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=MonthlyWeeksClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="Create a monthly monitoring plan.",
            apply_to_pet=True,
        )

        task = run.accepted_tasks[0]
        assert task.scheduled_month_weeks == ["Week 2", "Week 4"]
        assert run.schedule_plan["scheduled"][0].scheduled_month_weeks == ["Week 2", "Week 4"]
        with open(run.log_path, "r", encoding="utf-8") as log_file:
            log_payload = json.load(log_file)
        assert log_payload["accepted_tasks"][0]["scheduled_month_weeks"] == ["Week 2", "Week 4"]
        assert log_payload["schedule_plan"]["scheduled"][0]["scheduled_month_weeks"] == ["Week 2", "Week 4"]

    def test_planner_limits_weekly_care_to_two_tasks(self, tmp_path):
        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=FakeClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        normalized = planner._normalize_accepted_tasks(
            [
                Task(
                    "Weekly weigh-in",
                    5,
                    Priority.HIGH,
                    "health",
                    "Record weight after the weekend.",
                    scheduled_time="09:00",
                    frequency="weekly",
                    scheduled_weekday="Monday",
                    ai_generated=True,
                ),
                Task(
                    "Weekly grooming",
                    20,
                    Priority.MEDIUM,
                    "grooming",
                    "Brush coat and inspect skin.",
                    scheduled_time="14:00",
                    frequency="weekly",
                    scheduled_weekday="Wednesday",
                    ai_generated=True,
                ),
                Task(
                    "Weekly supply review",
                    10,
                    Priority.LOW,
                    "general",
                    "Check food and care supplies.",
                    scheduled_time="16:00",
                    frequency="weekly",
                    scheduled_weekday="Friday",
                    ai_generated=True,
                ),
            ]
        )

        weekly_names = [task.name for task in normalized if task.frequency == "weekly"]

        assert weekly_names == ["Weekly weigh-in", "Weekly grooming"]

    def test_planner_backfills_distinct_daily_tasks_for_weekday_variety(self, tmp_path):
        owner = Owner("Jordan")
        pet = Pet("Mochi", "dog", 11, special_needs="stiff joints", breed="golden retriever")
        owner.add_pet(pet)
        client = DailyVariationClaudeClient()

        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=client,
            logger=AIRunLogger(log_dir=tmp_path),
        )

        run = planner.recommend_and_schedule(
            owner=owner,
            pet=pet,
            goal="Create a complete pet care plan with daily, weekly, monthly tasks and reminders.",
            extra_context="Focus on a weekly daily-care routine with variety across the week.",
            apply_to_pet=True,
        )

        daily_names = {task.name for task in run.accepted_tasks if task.frequency == "daily"}

        assert len(client.calls) == 3
        assert client.calls[1]["requested_frequencies"] == ["weekly", "monthly"]
        assert client.calls[2]["requested_frequencies"] == ["daily"]
        assert "Neighborhood walk" in daily_names
        assert "Snack time" in daily_names
        assert "Dog park outing" in daily_names
        assert "Spa-style grooming check" in daily_names

    def test_planner_consolidates_duplicate_daily_care_intents(self, tmp_path):
        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=FakeClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        normalized = planner._normalize_accepted_tasks(
            [
                Task(
                    "Hydration check",
                    5,
                    Priority.MEDIUM,
                    "health",
                    "Refresh the water bowl and observe intake.",
                    scheduled_time="08:00",
                    frequency="daily",
                    ai_generated=True,
                ),
                Task(
                    "Water check",
                    7,
                    Priority.HIGH,
                    "health",
                    "Refresh the water bowl and observe intake.",
                    scheduled_time="09:00",
                    frequency="daily",
                    ai_generated=True,
                ),
                Task(
                    "Weekly weight check",
                    5,
                    Priority.MEDIUM,
                    "health",
                    "Weigh once this week and note any changes.",
                    scheduled_time="10:00",
                    frequency="weekly",
                    ai_generated=True,
                ),
            ]
        )

        daily_tasks = [task for task in normalized if task.frequency == "daily"]
        weekly_tasks = [task for task in normalized if task.frequency == "weekly"]

        assert len(daily_tasks) == 1
        assert daily_tasks[0].name == "Hydration check"
        assert daily_tasks[0].duration_minutes == 7
        assert daily_tasks[0].priority == Priority.HIGH
        assert len(weekly_tasks) == 1

    def test_planner_keeps_useful_morning_and_evening_daily_repeats(self, tmp_path):
        planner = PawPalAIPlanner(
            knowledge_base=LocalKnowledgeBase(),
            client=FakeClaudeClient(),
            logger=AIRunLogger(log_dir=tmp_path),
        )

        normalized = planner._normalize_accepted_tasks(
            [
                Task(
                    "Morning feeding",
                    15,
                    Priority.HIGH,
                    "nutrition",
                    "Morning meal for appetite support.",
                    scheduled_time="07:00",
                    frequency="daily",
                    ai_generated=True,
                ),
                Task(
                    "Evening feeding",
                    15,
                    Priority.HIGH,
                    "nutrition",
                    "Evening meal for appetite support.",
                    scheduled_time="18:00",
                    frequency="daily",
                    ai_generated=True,
                ),
            ]
        )

        daily_names = [task.name for task in normalized if task.frequency == "daily"]

        assert daily_names == ["Morning feeding", "Evening feeding"]


class TestResultsUiHelpers:
    def test_task_guidance_schedule_label_is_owner_friendly(self):
        weekly_task = Task(
            "Weekly weigh-in",
            5,
            Priority.MEDIUM,
            "health",
            "",
            scheduled_time="09:00",
            frequency="weekly",
            scheduled_weekday="Wednesday",
        )
        monthly_task = Task(
            "Monthly preventive refill",
            10,
            Priority.MEDIUM,
            "preventive",
            "",
            scheduled_time="10:00",
            frequency="monthly",
            scheduled_month_weeks=["Week 1", "Week 4"],
        )
        alert_task = Task(
            "Breathing alert",
            2,
            Priority.HIGH,
            "monitoring",
            "",
            frequency="as needed",
        )

        assert get_task_guidance_schedule_label(weekly_task) == "Wednesday"
        assert get_task_guidance_schedule_label(monthly_task) == "Week 1 and Week 4 of each month"
        assert get_task_guidance_schedule_label(alert_task) == "As needed"

    def test_build_task_reference_entries_uses_dynamic_titles_and_snippets(self):
        task = Task(
            "Lethargy alert",
            2,
            Priority.HIGH,
            "monitoring",
            "",
            frequency="as needed",
            source_ids=["senior_pet_support", "enrichment_and_monitoring", "missing_doc"],
        )
        references = build_task_reference_entries(
            task,
            [
                RetrievedPassage(
                    doc_id="senior_pet_support",
                    title="Senior Pet Support",
                    chunk_id="senior_pet_support#1",
                    content="Senior pets often need lower-impact exercise and closer observation of appetite and energy.",
                    score=2.0,
                ),
                RetrievedPassage(
                    doc_id="enrichment_and_monitoring",
                    title="Enrichment and Daily Monitoring",
                    chunk_id="enrichment_and_monitoring#1",
                    content="Observation tasks are useful for special-needs pets because they create a record of appetite and energy.",
                    score=1.5,
                ),
            ],
        )

        assert references == [
            {
                "title": "Senior Pet Support",
                "snippet": "Senior pets often need lower-impact exercise and closer observation of appetite and energy.",
            },
            {
                "title": "Enrichment and Daily Monitoring",
                "snippet": "Observation tasks are useful for special-needs pets because they create a record of appetite and energy.",
            },
        ]

    def test_get_task_support_line_returns_full_normalized_note_text(self):
        task = Task(
            "Medication refill check",
            10,
            Priority.MEDIUM,
            "supplies",
            "Check medication supply, order refills if needed, verify expiration dates, and confirm food stock meets respiratory support needs.",
            scheduled_time="10:00",
            frequency="monthly",
        )

        support_line = get_task_support_line(task)

        assert support_line == (
            "Check medication supply, order refills if needed, verify expiration dates, and confirm food stock "
            "meets respiratory support needs."
        )
        assert "..." not in support_line
        assert "…" not in support_line

    def test_build_daily_care_tabs_uses_base_routine_with_added_selected_day_tasks(self):
        tabs = build_daily_care_tabs(
            [
                Task(
                    "Evening medication",
                    5,
                    Priority.HIGH,
                    "health",
                    "PM medication with food.",
                    scheduled_time="19:00",
                    frequency="daily",
                ),
                Task(
                    "Morning feeding",
                    15,
                    Priority.HIGH,
                    "nutrition",
                    "Morning meal before activity.",
                    scheduled_time="07:00",
                    frequency="daily",
                ),
                Task(
                    "Bedtime wind-down",
                    15,
                    Priority.MEDIUM,
                    "routine",
                    "Keep the evening sleep schedule calm and predictable.",
                    scheduled_time="21:00",
                    frequency="daily",
                ),
                Task(
                    "Neighborhood walk",
                    10,
                    Priority.MEDIUM,
                    "exercise",
                    "Take a short walk at an easy pace.",
                    scheduled_time="10:00",
                    frequency="daily",
                ),
                Task(
                    "Snack time",
                    10,
                    Priority.MEDIUM,
                    "nutrition",
                    "Offer a small approved snack during a quiet break.",
                    scheduled_time="13:00",
                    frequency="daily",
                ),
                Task(
                    "Dog park outing",
                    20,
                    Priority.MEDIUM,
                    "enrichment",
                    "Visit the dog park for a short, structured outing.",
                    scheduled_time="16:00",
                    frequency="daily",
                ),
                Task(
                    "Spa-style grooming check",
                    10,
                    Priority.MEDIUM,
                    "grooming",
                    "Brush the coat and check paws during a calm grooming block.",
                    scheduled_time="20:00",
                    frequency="daily",
                ),
            ]
        )

        assert [str(tab_data["day"]) for tab_data in tabs] == [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        assert all(
            {"Morning feeding", "Evening medication", "Bedtime wind-down"}.issubset({task.name for task in tab_data["base_tasks"]})
            for tab_data in tabs
        )
        walk_days = sum("Neighborhood walk" in {task.name for task in tab_data["tasks"]} for tab_data in tabs)
        snack_days = sum("Snack time" in {task.name for task in tab_data["tasks"]} for tab_data in tabs)
        park_days = sum("Dog park outing" in {task.name for task in tab_data["tasks"]} for tab_data in tabs)
        grooming_days = sum("Spa-style grooming check" in {task.name for task in tab_data["tasks"]} for tab_data in tabs)
        assert 1 <= walk_days < 7
        assert 1 <= snack_days < 7
        assert 1 <= park_days < 7
        assert 1 <= grooming_days < 7
        assert all(len(tab_data["extra_tasks"]) >= 2 for tab_data in tabs)
        assert all(
            {"Morning feeding", "Evening medication", "Bedtime wind-down"}.issubset({task.name for task in tab_data["tasks"]})
            for tab_data in tabs
        )
        assert all("Weekly grooming check" not in {task.name for task in tab_data["tasks"]} for tab_data in tabs)
        assert all("Monthly preventive refill" not in {task.name for task in tab_data["tasks"]} for tab_data in tabs)
        assert any(len(tab_data["tasks"]) >= 4 for tab_data in tabs)

    def test_weekly_schedule_label_uses_weekday_with_neutral_fallback(self):
        assert get_weekly_schedule_label(
            Task(
                "Weekly weight check",
                5,
                Priority.MEDIUM,
                "health",
                "",
                scheduled_time="09:00",
                frequency="weekly",
                scheduled_weekday="Friday",
            )
        ) == "Friday"
        assert get_weekly_schedule_label(
            Task(
                "Legacy weekly task",
                5,
                Priority.MEDIUM,
                "health",
                "",
                scheduled_time="09:00",
                frequency="weekly",
            )
        ) == "Once this week"

    def test_render_compact_task_list_shows_weekday_for_weekly_without_regressing_other_sections(self, monkeypatch):
        captured: list[str] = []

        monkeypatch.setattr(ui_components.st, "markdown", lambda markup, unsafe_allow_html=True: captured.append(markup))

        weekly_task = Task(
            "Weekly weigh-in",
            5,
            Priority.MEDIUM,
            "health",
            "Record the weight and note changes.",
            scheduled_time="09:00",
            frequency="weekly",
            scheduled_weekday="Wednesday",
        )
        monthly_task = Task(
            "Monthly preventive refill",
            10,
            Priority.MEDIUM,
            "preventive",
            "Restock the preventive.",
            scheduled_time="10:00",
            frequency="monthly",
            scheduled_month_weeks=["Week 1", "Week 4"],
        )

        render_compact_task_list([weekly_task], "empty", schedule_style="weekday")
        render_compact_task_list([monthly_task], "empty", schedule_style="month-week")

        assert "Wednesday" in captured[0]
        assert "09:00" not in captured[0]
        assert "Week 1" in captured[1]
        assert "Week 4" in captured[1]
        assert "10:00" not in captured[1]

    def test_monthly_schedule_helpers_infer_and_sort_missing_week_labels_cleanly(self):
        owner = Owner("Jordan")
        pet = Pet("Mochi", "dog", 11)
        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        legacy = Task(
            "Legacy monthly reminder",
            5,
            Priority.LOW,
            "preventive",
            "",
            scheduled_time="12:00",
            frequency="monthly",
        )
        second_week = Task(
            "Second week check",
            5,
            Priority.MEDIUM,
            "monitoring",
            "",
            scheduled_time="09:00",
            frequency="monthly",
            scheduled_month_weeks=["Week 2"],
        )
        first_and_last = Task(
            "Twice monthly follow-up",
            10,
            Priority.HIGH,
            "monitoring",
            "",
            scheduled_time="08:00",
            frequency="monthly",
            scheduled_month_weeks=["Week 1", "Week 4"],
        )

        sorted_tasks = sort_tasks_for_section([legacy, second_week, first_and_last], scheduler, schedule_style="month-week")

        assert [task.name for task in sorted_tasks] == [
            "Twice monthly follow-up",
            "Legacy monthly reminder",
            "Second week check",
        ]
        assert get_monthly_schedule_labels(legacy) == ["Week 1"]

    def test_render_compact_task_list_keeps_full_long_support_text(self, monkeypatch):
        captured: list[str] = []

        monkeypatch.setattr(ui_components.st, "markdown", lambda markup, unsafe_allow_html=True: captured.append(markup))

        task = Task(
            "Respiratory alert",
            2,
            Priority.HIGH,
            "monitoring",
            "If Kito shows increased breathing effort, wheezing, or open-mouth breathing, contact veterinarian immediately and log the change.",
            scheduled_time="00:00",
            frequency="as needed",
        )

        render_compact_task_list([task], "empty", schedule_style="none")

        assert "If Kito shows increased breathing effort, wheezing, or open-mouth breathing, contact veterinarian immediately and log the change." in captured[0]
        assert "..." not in captured[0]
        assert "…" not in captured[0]

    def test_render_task_detail_expanders_uses_task_guidance_and_friendly_references(self, monkeypatch):
        headings: list[tuple[str, str]] = []
        markdown_calls: list[str] = []
        write_calls: list[str] = []

        monkeypatch.setattr(ui_components, "render_card_heading", lambda title, copy="": headings.append((title, copy)))
        monkeypatch.setattr(ui_components.st, "container", lambda border=True: nullcontext())
        monkeypatch.setattr(ui_components.st, "expander", lambda label: nullcontext())
        monkeypatch.setattr(ui_components.st, "markdown", lambda markup, unsafe_allow_html=False: markdown_calls.append(markup))
        monkeypatch.setattr(ui_components.st, "write", lambda value: write_calls.append(str(value)))

        owner = Owner("Jordan")
        pet = Pet("Mochi", "dog", 11)
        task = Task(
            "Lethargy or energy loss alert",
            2,
            Priority.HIGH,
            "monitoring",
            "If activity drops sharply, log the duration and contact the veterinarian.",
            frequency="as needed",
            rationale="Energy shifts matter because the owner explicitly asked for lethargy guidance.",
            source_ids=["senior_pet_support"],
        )
        pet.add_task(task)
        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        render_task_detail_expanders(
            [task],
            scheduler,
            retrieved_passages=[
                RetrievedPassage(
                    doc_id="senior_pet_support",
                    title="Senior Pet Support",
                    chunk_id="senior_pet_support#1",
                    content="Older pets may benefit from routines that include medication reminders and closer observation of appetite and energy.",
                    score=2.0,
                )
            ],
        )

        assert headings[0][0] == "Task Guidance"
        assert any("**Why this matters**" in item for item in markdown_calls)
        assert any("**What to do**" in item for item in markdown_calls)
        assert any("**When this applies**" in item for item in markdown_calls)
        assert any("**Helpful references**" in item for item in markdown_calls)
        assert any("As needed" == item for item in write_calls)
        assert any("Senior Pet Support:" in item for item in write_calls)
        assert all("senior_pet_support" not in item for item in write_calls)

    def test_render_plan_dashboard_no_longer_shows_planning_details_expander(self, monkeypatch):
        expander_labels: list[str] = []

        monkeypatch.setattr(ui_components, "render_results_plan_stack_marker", lambda: None)
        monkeypatch.setattr(ui_components, "render_card_heading", lambda *args, **kwargs: None)
        monkeypatch.setattr(ui_components, "render_plan_summary", lambda *args, **kwargs: None)
        monkeypatch.setattr(ui_components, "render_daily_care_tabs", lambda *args, **kwargs: None)
        monkeypatch.setattr(ui_components, "render_conflicts", lambda *args, **kwargs: None)
        monkeypatch.setattr(ui_components, "render_frequency_section", lambda *args, **kwargs: None)
        monkeypatch.setattr(ui_components, "render_task_detail_expanders", lambda *args, **kwargs: None)
        monkeypatch.setattr(ui_components.st, "container", lambda border=True: nullcontext())
        monkeypatch.setattr(ui_components.st, "expander", lambda label: expander_labels.append(label) or nullcontext())

        owner = Owner("Jordan")
        pet = Pet("Mochi", "dog", 11)
        task = Task("Hydration check", 5, Priority.HIGH, "health", "", scheduled_time="08:00", frequency="daily", ai_generated=True)
        pet.add_task(task)
        owner.add_pet(pet)
        ai_run = type(
            "Run",
            (),
            {
                "blocked_recommendations": [type("Blocked", (), {"name": "x", "reasons": ["y"]})()],
                "warnings": ["warning"],
                "retrieved_passages": [
                    RetrievedPassage(
                        doc_id="senior_pet_support",
                        title="Senior Pet Support",
                        chunk_id="senior_pet_support#1",
                        content="Senior pets benefit from extra observation.",
                        score=2.0,
                    )
                ],
                "model_name": "fake-model",
                "log_path": "/tmp/fake.json",
            },
        )()

        ui_components.render_plan_dashboard(owner, [task], ai_run)

        assert "Planning Details" not in expander_labels


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
        assert context["lifespan_range_years"] == (10, 15)
        assert "typical lifespan" in context["summary"].lower()

    def test_species_characteristics_are_inferred_for_cat(self):
        pet = Pet("Luna", "cat", 9, special_needs="kidney diet", breed="domestic shorthair")

        characteristics = pet.get_species_characteristics()

        assert "consistent care routine" in characteristics.lower()
        assert "breed context: domestic shorthair" in characteristics.lower()

    def test_breed_traits_fall_back_to_species_traits_when_unknown(self):
        pet = Pet("Mochi", "dog", 6, breed="mixed")

        characteristics = pet.get_species_characteristics()

        assert "consistent care routine" in characteristics.lower()
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

    def test_profile_priority_groups_prioritize_special_needs_and_parse_grouped_output(self):
        pet = Pet("Luna", "cat", 12, special_needs="early kidney support diet and appetite monitoring")

        groups = build_profile_priority_groups(
            pet,
            "Hydration: Keep fresh water easy to access; Encourage steady drinking || "
            "Monitoring: Track appetite and weight trends weekly; Watch litter habits and comfort changes closely",
        )

        assert groups[0]["title"] == "Current Focus"
        assert len(groups) <= 4
        assert any("fresh water" in item.lower() for group in groups for item in group["items"])
        assert all("||" not in item for group in groups for item in group["items"])
        assert any(group["title"] == "Monitoring" for group in groups)
        assert all(len(group["items"]) >= 2 for group in groups)

    def test_profile_priority_groups_support_older_flat_text_without_truncation(self):
        pet = Pet("Luna", "cat", 12)

        groups = build_profile_priority_groups(
            pet,
            (
                "Cats require consistent hydration access, high-quality protein-based diet with meal timing suited "
                "to individual metabolism. Senior cats benefit from easy litter box access and close monitoring "
                "for changes in appetite, water intake, mobility, and elimination patterns."
            ),
        )

        rendered_points = [item for group in groups for item in group["items"]]
        assert any("high-quality protein-based diet" in item for item in rendered_points)
        assert all("..." not in item for item in rendered_points)
        assert all(len(group["items"]) >= 2 for group in groups)
        assert any("12" in item or "senior" in item.lower() for item in rendered_points)

    def test_owner_save_and_load_persists_characteristics(self, tmp_path):
        owner = Owner("Jordan")
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
