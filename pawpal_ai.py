from dataclasses import asdict, dataclass
from typing import Any, Dict, List
import re
import uuid

from ai_logging import AIRunLogger
from ai_retrieval import LocalKnowledgeBase, RetrievedPassage
from ai_validation import BlockedRecommendation, RecommendationValidator, ValidationResult
from bedrock_client import BedrockRecommendationClient, RecommendationCandidate, RecommendationProviderError
from pawpal_system import Owner, Pet, Priority, Scheduler, Task


@dataclass
class AICareRun:
    run_id: str
    query: str
    retrieved_passages: List[RetrievedPassage]
    accepted_tasks: List[Task]
    blocked_recommendations: List[BlockedRecommendation]
    warnings: List[str]
    reliability_score: float
    schedule_plan: Dict[str, List[Task]]
    log_path: str
    model_name: str


class PawPalAIPlanner:
    """Coordinate retrieval, Claude recommendations, validation, logging, and scheduling."""

    def __init__(
        self,
        knowledge_base: LocalKnowledgeBase | None = None,
        client: BedrockRecommendationClient | None = None,
        validator: RecommendationValidator | None = None,
        logger: AIRunLogger | None = None,
        region: str | None = None,
        profile: str | None = None,
        model: str | None = None,
    ):
        self.knowledge_base = knowledge_base or LocalKnowledgeBase()
        self.client = client or BedrockRecommendationClient(region=region, profile=profile, model=model)
        self.validator = validator or RecommendationValidator()
        self.logger = logger or AIRunLogger()

    def recommend_and_schedule(
        self,
        owner: Owner,
        pet: Pet,
        goal: str = "",
        extra_context: str = "",
        apply_to_pet: bool = True,
    ) -> AICareRun:
        profile_warning = ""
        try:
            species_profile = self.client.profile_species(
                species=pet.get_effective_species_label(),
                breed=pet.get_effective_breed_label(),
                special_needs=pet.special_needs,
            )
            pet.apply_species_profile(
                lifespan_min_years=species_profile.lifespan_min_years,
                lifespan_max_years=species_profile.lifespan_max_years,
                characteristics=species_profile.characteristics,
                summary=species_profile.summary,
                source=f"Model-derived profile from {self.client.model}",
            )
        except RecommendationProviderError as exc:
            profile_warning = f"Species profile lookup fell back to local defaults: {exc}"

        age_context = pet.get_age_context()
        species_characteristics = pet.get_species_characteristics()
        effective_species = pet.get_effective_species_label()
        effective_breed = pet.get_effective_breed_label()
        requested_frequencies = self._extract_requested_frequencies(goal=goal, extra_context=extra_context)
        query = self._build_query(owner, pet, goal, extra_context)
        retrieved_passages = self.knowledge_base.retrieve(query, top_k=5)
        existing_tasks = [self._task_snapshot(task) for task in pet.tasks if not task.ai_generated]

        recommendations = self.client.recommend(
            owner_name=owner.name,
            available_minutes=owner.available_minutes,
            pet_name=pet.name,
            species=effective_species,
            age=pet.age,
            special_needs=pet.special_needs,
            characteristics=species_characteristics,
            age_context=age_context["summary"],
            goal=goal,
            breed=effective_breed,
            extra_context=extra_context,
            requested_frequencies=requested_frequencies,
            existing_tasks=existing_tasks,
            retrieved_passages=retrieved_passages,
        )

        validation = self.validator.validate(
            recommendations=recommendations,
            retrieved_passages=retrieved_passages,
            available_minutes=owner.available_minutes,
            allowed_frequencies=set(requested_frequencies) if requested_frequencies else None,
        )
        accepted_tasks = [self._candidate_to_task(candidate) for candidate in validation.accepted]

        if apply_to_pet:
            pet.replace_ai_tasks(accepted_tasks)

        schedule_plan = Scheduler(owner).generate_plan(enforce_budget=False)
        run_id = uuid.uuid4().hex[:12]
        log_payload = self._build_log_payload(
            run_id=run_id,
            owner=owner,
            pet=pet,
            query=query,
            age_context=age_context,
            goal=goal,
            extra_context=extra_context,
            requested_frequencies=requested_frequencies,
            retrieved_passages=retrieved_passages,
            recommendations=recommendations,
            validation=validation,
            accepted_tasks=accepted_tasks,
            schedule_plan=schedule_plan,
        )
        log_path = str(self.logger.log_run(log_payload))

        return AICareRun(
            run_id=run_id,
            query=query,
            retrieved_passages=retrieved_passages,
            accepted_tasks=accepted_tasks,
            blocked_recommendations=validation.blocked,
            warnings=([profile_warning] if profile_warning else []) + validation.warnings,
            reliability_score=validation.reliability_score,
            schedule_plan=schedule_plan,
            log_path=log_path,
            model_name=self.client.model,
        )

    def _build_query(self, owner: Owner, pet: Pet, goal: str, extra_context: str) -> str:
        age_context = pet.get_age_context()
        species_characteristics = pet.get_species_characteristics()
        effective_species = pet.get_effective_species_label()
        effective_breed = pet.get_effective_breed_label()
        parts = [
            effective_species,
            effective_breed,
            pet.name,
            f"age {pet.age}",
            age_context["life_stage"],
            pet.special_needs,
            species_characteristics,
            goal,
            extra_context,
            "pet care routine",
        ]
        return " ".join(part for part in parts if part).strip()

    def _extract_requested_frequencies(self, goal: str, extra_context: str) -> List[str]:
        """Extract explicit cadence requests like 'weekly only' from the user-facing inputs."""
        text = f"{goal} {extra_context}".lower()
        frequencies = ["daily", "weekly", "monthly", "as needed"]
        matches: List[str] = []
        for frequency in frequencies:
            escaped = re.escape(frequency)
            patterns = [
                rf"\b{escaped}\b(?:\s+\w+){{0,3}}\s+\bonly\b",
                rf"\bonly\b(?:\s+\w+){{0,3}}\s+\b{escaped}\b",
            ]
            if any(re.search(pattern, text) for pattern in patterns):
                matches.append(frequency)
        return matches

    def _candidate_to_task(self, candidate: RecommendationCandidate) -> Task:
        priority_map = {
            "low": Priority.LOW,
            "medium": Priority.MEDIUM,
            "high": Priority.HIGH,
        }
        return Task(
            name=candidate.name,
            duration_minutes=candidate.duration_minutes,
            priority=priority_map[candidate.priority],
            category=candidate.category,
            notes=candidate.notes,
            scheduled_time=candidate.scheduled_time,
            frequency=candidate.frequency,
            ai_generated=True,
            rationale=candidate.rationale,
            confidence_score=candidate.confidence,
            source_ids=list(candidate.source_ids),
            validation_status="validated",
        )

    def _task_snapshot(self, task: Task) -> Dict[str, Any]:
        return {
            "name": task.name,
            "duration_minutes": task.duration_minutes,
            "priority": task.priority.value,
            "category": task.category,
            "scheduled_time": task.scheduled_time,
            "frequency": task.frequency,
        }

    def _build_log_payload(
        self,
        run_id: str,
        owner: Owner,
        pet: Pet,
        query: str,
        age_context: Dict[str, Any],
        goal: str,
        extra_context: str,
        requested_frequencies: List[str],
        retrieved_passages: List[RetrievedPassage],
        recommendations: List[RecommendationCandidate],
        validation: ValidationResult,
        accepted_tasks: List[Task],
        schedule_plan: Dict[str, List[Task]],
    ) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "model": self.client.model,
            "owner": owner.name,
            "available_minutes": owner.available_minutes,
            "pet": {
                "name": pet.name,
                "species": pet.species,
                "effective_species": pet.get_effective_species_label(),
                "breed": pet.get_effective_breed_label(),
                "custom_species": pet.custom_species,
                "age": pet.age,
                "special_needs": pet.special_needs,
                "characteristics": pet.characteristics,
                "lifespan_range_years": pet.get_lifespan_range_years(),
                "species_profile_summary": pet.species_profile_summary,
                "species_profile_source": pet.species_profile_source,
                "age_context": age_context,
            },
            "query": query,
            "goal": goal,
            "extra_context": extra_context,
            "requested_frequencies": requested_frequencies,
            "retrieved_passages": [asdict(item) for item in retrieved_passages],
            "raw_recommendations": [asdict(item) for item in recommendations],
            "blocked_recommendations": [asdict(item) for item in validation.blocked],
            "warnings": validation.warnings,
            "reliability_score": validation.reliability_score,
            "accepted_tasks": [self._task_snapshot(task) | {
                "ai_generated": task.ai_generated,
                "rationale": task.rationale,
                "confidence_score": task.confidence_score,
                "source_ids": task.source_ids,
                "validation_status": task.validation_status,
            } for task in accepted_tasks],
            "schedule_plan": {
                "scheduled": [self._task_snapshot(task) for task in schedule_plan["scheduled"]],
                "skipped": [self._task_snapshot(task) for task in schedule_plan["skipped"]],
                "reasoning": schedule_plan["reasoning"],
            },
        }
