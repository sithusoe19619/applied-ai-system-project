from dataclasses import asdict, dataclass, replace
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
    goal: str
    extra_context: str
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
        desired_frequencies = self._extract_desired_frequencies(goal=goal, extra_context=extra_context)
        care_alerts_relevant = self._needs_care_alerts(
            pet=pet,
            goal=goal,
            extra_context=extra_context,
            characteristics=species_characteristics,
            retrieved_passages=retrieved_passages,
        )
        if care_alerts_relevant and "as needed" not in desired_frequencies:
            desired_frequencies.append("as needed")
        existing_tasks = [self._task_snapshot(task) for task in pet.tasks if not task.ai_generated]

        recommendations = self.client.recommend(
            owner_name=owner.name,
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
        all_recommendations = list(recommendations)

        validation = self.validator.validate(
            recommendations=recommendations,
            retrieved_passages=retrieved_passages,
            allowed_frequencies=set(requested_frequencies) if requested_frequencies else None,
        )
        accepted_candidates = list(validation.accepted)
        accepted_tasks = [self._candidate_to_task(candidate) for candidate in accepted_candidates]

        if not requested_frequencies:
            accepted_frequencies = {task.frequency for task in accepted_tasks}
            missing_frequencies = [frequency for frequency in desired_frequencies if frequency not in accepted_frequencies]
            if missing_frequencies:
                follow_up_recommendations = self.client.recommend(
                    owner_name=owner.name,
                    pet_name=pet.name,
                    species=effective_species,
                    age=pet.age,
                    special_needs=pet.special_needs,
                    characteristics=species_characteristics,
                    age_context=age_context["summary"],
                    goal=f"{goal} Add only the missing cadence types for this plan.",
                    breed=effective_breed,
                    extra_context=self._build_missing_frequency_context(extra_context, missing_frequencies),
                    requested_frequencies=missing_frequencies,
                    existing_tasks=existing_tasks + [self._task_snapshot(task) for task in accepted_tasks],
                    retrieved_passages=retrieved_passages,
                )
                all_recommendations.extend(follow_up_recommendations)
                follow_up_validation = self.validator.validate(
                    recommendations=follow_up_recommendations,
                    retrieved_passages=retrieved_passages,
                    allowed_frequencies=set(missing_frequencies),
                )
                validation.blocked.extend(follow_up_validation.blocked)
                validation.warnings.extend(follow_up_validation.warnings)
                merged_candidates = self._merge_candidates(accepted_candidates, follow_up_validation.accepted)
                accepted_candidates = merged_candidates
                accepted_tasks = [self._candidate_to_task(candidate) for candidate in accepted_candidates]
                if not all(frequency in {task.frequency for task in accepted_tasks} for frequency in missing_frequencies):
                    validation.warnings.append(
                        "The generated plan is still missing some requested cadence types after a second pass."
                    )

        accepted_tasks = self._normalize_accepted_tasks(accepted_tasks)

        if not requested_frequencies and self._needs_daily_variation_backfill(accepted_tasks):
            daily_follow_up_recommendations = self.client.recommend(
                owner_name=owner.name,
                pet_name=pet.name,
                species=effective_species,
                age=pet.age,
                special_needs=pet.special_needs,
                characteristics=species_characteristics,
                age_context=age_context["summary"],
                goal=f"{goal} Add only distinct daily-care tasks that improve weekday variety in the Daily Care Plan.",
                breed=effective_breed,
                extra_context=self._build_daily_variation_context(extra_context),
                requested_frequencies=["daily"],
                existing_tasks=existing_tasks + [self._task_snapshot(task) for task in accepted_tasks],
                retrieved_passages=retrieved_passages,
            )
            all_recommendations.extend(daily_follow_up_recommendations)
            daily_follow_up_validation = self.validator.validate(
                recommendations=daily_follow_up_recommendations,
                retrieved_passages=retrieved_passages,
                allowed_frequencies={"daily"},
            )
            validation.blocked.extend(daily_follow_up_validation.blocked)
            validation.warnings.extend(daily_follow_up_validation.warnings)
            accepted_candidates = self._merge_candidates(accepted_candidates, daily_follow_up_validation.accepted)
            accepted_tasks = self._normalize_accepted_tasks(
                [self._candidate_to_task(candidate) for candidate in accepted_candidates]
            )
            if self._needs_daily_variation_backfill(accepted_tasks):
                validation.warnings.append(
                    "The generated plan still has limited daily-care variety after a daily follow-up pass."
                )

        can_backfill_care_alerts = not requested_frequencies or "as needed" in requested_frequencies
        if care_alerts_relevant and can_backfill_care_alerts:
            care_alert_candidates = self._build_care_alert_fallback_candidates(
                pet=pet,
                goal=goal,
                extra_context=extra_context,
                characteristics=species_characteristics,
                retrieved_passages=retrieved_passages,
                accepted_tasks=accepted_tasks,
            )
            if care_alert_candidates:
                fallback_validation = self.validator.validate(
                    recommendations=care_alert_candidates,
                    retrieved_passages=retrieved_passages,
                    allowed_frequencies={"as needed"},
                )
                validation.blocked.extend(fallback_validation.blocked)
                validation.warnings.extend(fallback_validation.warnings)
                accepted_candidates = self._merge_candidates(accepted_candidates, fallback_validation.accepted)
                accepted_tasks = self._normalize_accepted_tasks(
                    [self._candidate_to_task(candidate) for candidate in accepted_candidates]
                )

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
            recommendations=all_recommendations,
            validation=validation,
            accepted_tasks=accepted_tasks,
            schedule_plan=schedule_plan,
        )
        log_path = str(self.logger.log_run(log_payload))

        return AICareRun(
            run_id=run_id,
            query=query,
            goal=goal,
            extra_context=extra_context,
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

    def _extract_desired_frequencies(self, goal: str, extra_context: str) -> List[str]:
        """Infer cadence coverage the user appears to want without treating it as a strict only-constraint."""
        text = f"{goal} {extra_context}".lower()
        desired: List[str] = []
        for frequency in ["daily", "weekly", "monthly"]:
            if re.search(rf"\b{re.escape(frequency)}\b", text):
                desired.append(frequency)

        conditional_markers = (
            "as needed",
            "watch for changes",
            "watch for change",
            "condition-aware",
            "condition based",
            "condition-based",
            "symptom",
            "appetite",
            "limping",
            "stiffness",
            "low energy",
            "if ",
            "when ",
        )
        if any(marker in text for marker in conditional_markers):
            desired.append("as needed")

        if not desired:
            return ["daily", "weekly", "monthly"]

        return list(dict.fromkeys(desired))

    def _build_missing_frequency_context(self, extra_context: str, missing_frequencies: List[str]) -> str:
        follow_up = (
            f"{extra_context.strip()} "
            f"Return only the missing cadence types: {', '.join(missing_frequencies)}. "
            "Do not repeat daily tasks that are already covered. "
            "Use cadence meanings strictly: daily is everyday care across the week, weekly is once-per-week check-ins or appointments, monthly is once-per-month preventive care or maintenance, and as needed is symptom-triggered guidance only. "
            "Do not use weekly or monthly cadence for generic daily maintenance tasks. "
            "If 'as needed' is requested, frame those tasks as watch-for-change guidance tied to symptoms or situation changes."
        ).strip()
        return follow_up

    def _build_daily_variation_context(self, extra_context: str) -> str:
        follow_up = (
            f"{extra_context.strip()} "
            "Return only distinct daily tasks that are not core basics like feeding, medication, hydration, bathroom care, or sleep schedule. "
            "Add multiple daily-care themes such as walks, snack time, grooming, training, park or outing time, monitoring, or calm enrichment when grounded in the profile. "
            "Do not repeat the same enrichment or check-in idea with slightly different wording."
        ).strip()
        return follow_up

    def _needs_care_alerts(
        self,
        pet: Pet,
        goal: str,
        extra_context: str,
        characteristics: str,
        retrieved_passages: List[RetrievedPassage],
    ) -> bool:
        del retrieved_passages
        texts = [
            goal,
            extra_context,
            pet.special_needs,
            characteristics,
        ]
        combined_text = " ".join(text for text in texts if text).lower()
        explicit_markers = (
            "as needed",
            "condition-aware",
            "condition based",
            "condition-based",
            "watch for change",
            "watch for changes",
            "alert sign",
            "warning sign",
            "care alert",
            "symptom",
            "when symptoms",
            "when the current situation",
        )
        condition_markers = (
            "chronic",
            "flare-up",
            "flare up",
            "respiratory",
            "appetite drop",
            "refuses multiple meals",
            "meal decline",
            "low body weight",
            "weight loss",
            "lethargy",
            "low energy",
            "labored breathing",
            "worsening feather",
            "feather plucking",
            "adverse reaction",
            "tolerance change",
            "humidity",
            "droppings",
        )
        return any(marker in combined_text for marker in explicit_markers) or any(
            marker in combined_text for marker in condition_markers
        )

    def _build_care_alert_fallback_candidates(
        self,
        pet: Pet,
        goal: str,
        extra_context: str,
        characteristics: str,
        retrieved_passages: List[RetrievedPassage],
        accepted_tasks: List[Task],
    ) -> List[RecommendationCandidate]:
        existing_alerts = [task for task in accepted_tasks if task.frequency == "as needed"]
        existing_themes = {self._care_alert_theme(task.name, task.notes, task.category) for task in existing_alerts}

        signals = self._collect_care_alert_signals(
            pet=pet,
            goal=goal,
            extra_context=extra_context,
            characteristics=characteristics,
            retrieved_passages=retrieved_passages,
        )
        if not signals:
            return []

        target_count = min(4, max(2, len(signals)))
        remaining_slots = max(0, target_count - len(existing_alerts))
        if remaining_slots == 0:
            return []

        fallback_candidates: List[RecommendationCandidate] = []
        seen_themes = set(existing_themes)
        for signal in signals:
            theme = str(signal["theme"])
            if theme in seen_themes:
                continue
            seen_themes.add(theme)
            fallback_candidates.append(
                RecommendationCandidate(
                    name=str(signal["name"]),
                    duration_minutes=2,
                    priority=str(signal["priority"]),
                    category=str(signal["category"]),
                    notes=str(signal["notes"]),
                    scheduled_time="00:00",
                    frequency="as needed",
                    rationale=str(signal["rationale"]),
                    source_ids=list(signal["source_ids"]),
                    confidence=0.74,
                )
            )
            if len(fallback_candidates) >= remaining_slots:
                break

        return fallback_candidates

    def _collect_care_alert_signals(
        self,
        pet: Pet,
        goal: str,
        extra_context: str,
        characteristics: str,
        retrieved_passages: List[RetrievedPassage],
    ) -> List[Dict[str, Any]]:
        extra_context_text = (extra_context or "").lower()
        owner_text = " ".join(part for part in [extra_context, goal, pet.special_needs] if part).lower()
        weighted_texts = [
            (extra_context, 6),
            (goal, 3),
            (pet.special_needs, 4),
            (characteristics, 2),
        ]
        weighted_texts.extend((passage.content, 1) for passage in retrieved_passages)

        signal_specs = [
            {
                "theme": "respiratory",
                "name": "Breathing changes or respiratory distress",
                "category": "monitoring",
                "priority": "high",
                "keywords": ("respiratory", "labored breathing", "breathing effort", "open-mouth", "wheez", "tail bob"),
                "notes": "If breathing effort increases, breathing becomes labored, or respiratory distress appears, document the change and contact the veterinarian promptly.",
                "rationale": "Respiratory changes are a meaningful alert sign in the current care context and should trigger prompt veterinary follow-up.",
            },
            {
                "theme": "appetite",
                "name": "Appetite drop or meal refusal",
                "category": "nutrition",
                "priority": "high",
                "keywords": ("appetite", "meal", "feeding", "refuse", "portion", "weight loss", "low body weight"),
                "notes": "If appetite drops, multiple meals are refused, or intake falls below the current plan, record the change and contact the veterinarian rather than changing food or portions on your own.",
                "rationale": "Appetite decline is a relevant alert sign when the profile calls for weight, feeding, or nutritional monitoring.",
            },
            {
                "theme": "energy",
                "name": "Lethargy or reduced activity tolerance",
                "category": "monitoring",
                "priority": "high",
                "keywords": ("lethargy", "low energy", "activity tolerance", "reduced stamina", "weak", "fatigue"),
                "notes": "If energy drops sharply, lethargy appears, or the pet tolerates far less activity than usual, log the change and contact the veterinarian.",
                "rationale": "A sudden decline in energy or activity tolerance is a meaningful change signal for condition-aware care.",
            },
            {
                "theme": "skin-feather",
                "name": "Worsening feather, coat, or skin damage",
                "category": "grooming",
                "priority": "high",
                "keywords": ("feather", "plucking", "skin", "coat", "wound", "self-trauma"),
                "notes": "If feather damage, feather plucking, skin irritation, or coat damage worsens, document what changed and contact the veterinarian for guidance.",
                "rationale": "Visible worsening in feather, coat, or skin condition is a concrete alert sign when stress or self-directed damage is part of the profile.",
            },
            {
                "theme": "droppings",
                "name": "Droppings or bathroom habit changes",
                "category": "monitoring",
                "priority": "medium",
                "keywords": ("droppings", "stool", "urine", "litter", "bathroom", "elimination"),
                "notes": "If droppings, litter habits, or other bathroom patterns change noticeably, add it to the observation log and contact the veterinarian if the change persists or is severe.",
                "rationale": "Bathroom habit changes are part of safe home monitoring when the profile or sources call for ongoing observation.",
            },
            {
                "theme": "medication",
                "name": "Medication refusal or tolerance change",
                "category": "medication",
                "priority": "high",
                "keywords": ("medication", "medication refusal", "dose", "adverse reaction", "tolerance change", "side effect"),
                "notes": "If medication is refused, a tolerance change appears, or an adverse reaction is observed, record the problem and contact the veterinarian instead of adjusting the dose yourself.",
                "rationale": "Medication-related problems should trigger documentation and veterinary contact rather than home dose changes.",
            },
            {
                "theme": "hydration",
                "name": "Hydration decline or dehydration signs",
                "category": "hydration",
                "priority": "medium",
                "keywords": ("hydration", "water intake", "dehydration", "drinking", "dry"),
                "notes": "If water intake drops noticeably or dehydration signs appear, note the change and contact the veterinarian if it does not improve quickly.",
                "rationale": "Hydration changes are an appropriate alert category when the profile or source support calls for intake monitoring.",
            },
            {
                "theme": "behavior",
                "name": "Behavior, vocalization, or stress changes",
                "category": "behavior",
                "priority": "medium",
                "keywords": ("vocalization", "behavior", "stress", "quiet", "restless", "agitation"),
                "notes": "If behavior, vocalization, or stress signs change sharply from baseline, document the trigger and discuss the change with the veterinarian.",
                "rationale": "Behavior or vocalization changes can be meaningful condition alerts when the care plan depends on stable routine and observation.",
            },
        ]

        scored_signals: List[Dict[str, Any]] = []
        for spec in signal_specs:
            score = 0
            for text, weight in weighted_texts:
                lowered = (text or "").lower()
                if any(keyword in lowered for keyword in spec["keywords"]):
                    score += weight
            if score <= 0:
                continue

            source_ids = self._select_care_alert_source_ids(spec["keywords"], retrieved_passages)
            if not source_ids:
                continue
            owner_mentioned = any(keyword in owner_text for keyword in spec["keywords"])
            extra_context_mentioned = any(keyword in extra_context_text for keyword in spec["keywords"])
            scored_signals.append(
                spec | {
                    "score": score,
                    "owner_mentioned": owner_mentioned,
                    "extra_context_mentioned": extra_context_mentioned,
                    "source_ids": source_ids,
                }
            )

        if not scored_signals and retrieved_passages:
            fallback_source = [retrieved_passages[0].doc_id]
            return [
                {
                    "theme": "general",
                    "name": "Sudden decline or major routine change",
                    "category": "monitoring",
                    "priority": "high",
                    "notes": "If a major change in breathing, appetite, energy, comfort, or routine appears, document what changed and contact the veterinarian rather than changing the care plan on your own.",
                    "rationale": "Condition-aware care requires clear escalation guidance when the overall profile indicates meaningful health risk.",
                    "source_ids": fallback_source,
                    "score": 1,
                }
            ]

        return sorted(
            scored_signals,
            key=lambda item: (
                0 if bool(item["extra_context_mentioned"]) else 1,
                0 if bool(item["owner_mentioned"]) else 1,
                -int(item["score"]),
                str(item["name"]),
            ),
        )

    def _select_care_alert_source_ids(
        self,
        keywords: tuple[str, ...],
        retrieved_passages: List[RetrievedPassage],
    ) -> List[str]:
        matched: List[str] = []
        for passage in retrieved_passages:
            passage_text = f"{passage.title} {passage.content}".lower()
            if any(keyword in passage_text for keyword in keywords) and passage.doc_id not in matched:
                matched.append(passage.doc_id)
            if len(matched) >= 2:
                break
        if matched:
            return matched
        return [retrieved_passages[0].doc_id] if retrieved_passages else []

    def _merge_candidates(
        self,
        primary: List[RecommendationCandidate],
        secondary: List[RecommendationCandidate],
    ) -> List[RecommendationCandidate]:
        merged: List[RecommendationCandidate] = []
        seen: set[tuple[str, str, str]] = set()
        for candidate in primary + secondary:
            key = (
                candidate.name.strip().lower(),
                candidate.frequency.strip().lower(),
                candidate.scheduled_time.strip(),
                candidate.scheduled_weekday.strip().lower(),
                tuple(candidate.scheduled_month_weeks),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
        return merged

    def _normalize_accepted_tasks(self, tasks: List[Task]) -> List[Task]:
        normalized: List[Task] = []
        for task in tasks:
            if task.frequency != "daily":
                normalized.append(task)
                continue

            duplicate_index = next(
                (
                    index
                    for index, existing in enumerate(normalized)
                    if existing.frequency == "daily" and self._daily_tasks_are_duplicates(existing, task)
                ),
                None,
            )
            if duplicate_index is None:
                normalized.append(task)
                continue

            normalized[duplicate_index] = self._merge_duplicate_daily_tasks(normalized[duplicate_index], task)

        daily_tasks = self._consolidate_daily_theme_duplicates(
            sorted((task for task in normalized if task.frequency == "daily"), key=lambda item: item.scheduled_time)
        )
        weekly_tasks = self._limit_weekly_tasks([task for task in normalized if task.frequency == "weekly"])
        care_alert_tasks = self._limit_care_alert_tasks([task for task in normalized if task.frequency == "as needed"])
        other_tasks = [task for task in normalized if task.frequency not in {"daily", "weekly", "as needed"}]
        return daily_tasks + weekly_tasks + other_tasks + care_alert_tasks

    def _limit_weekly_tasks(self, tasks: List[Task]) -> List[Task]:
        priority_order = {"high": 0, "medium": 1, "low": 2}
        weekday_order = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }
        ranked = sorted(
            tasks,
            key=lambda task: (
                priority_order.get(getattr(task.priority, "value", str(task.priority)).lower(), len(priority_order)),
                weekday_order.get(task.scheduled_weekday, len(weekday_order)),
                task.scheduled_time,
                task.name.lower(),
            ),
        )
        return ranked[:2]

    def _daily_task_theme(self, task: Task) -> str:
        text = f"{task.name} {task.notes} {task.category}".lower()
        if any(keyword in text for keyword in {"medication", "medicine", "med", "pill", "dose"}):
            return "basic"
        if any(keyword in text for keyword in {"feeding", "feed", "meal", "food", "breakfast", "dinner", "supper"}):
            return "basic"
        if any(keyword in text for keyword in {"water", "hydration", "litter", "potty", "bathroom", "sleep", "rest", "bedtime", "nap"}):
            return "basic"
        if any(keyword in text for keyword in {"snack", "treat"}):
            return "snack"
        if any(keyword in text for keyword in {"groom", "brush", "coat", "skin", "paw"}):
            return "grooming"
        if any(keyword in text for keyword in {"park", "outing", "spa"}):
            return "outing"
        if any(keyword in text for keyword in {"walk", "exercise"}):
            return "walk"
        if any(keyword in text for keyword in {"appetite", "weight", "monitor", "observe", "check", "comfort", "breathing", "cough"}):
            return "monitoring"
        if any(keyword in text for keyword in {"mobility", "gait", "joint", "stretch"}):
            return "mobility"
        if any(keyword in text for keyword in {"play", "enrichment", "puzzle", "training"}):
            return "enrichment"
        if any(keyword in text for keyword in {"environment", "routine", "stress", "space", "bedding"}):
            return "environment"
        return (task.category or "other").strip().lower() or "other"

    def _care_alert_theme(self, name: str, notes: str, category: str) -> str:
        text = f"{name} {notes} {category}".lower()
        theme_keywords = {
            "respiratory": {"respiratory", "breathing", "wheez", "open-mouth", "labored"},
            "appetite": {"appetite", "meal", "feeding", "weight", "refuse"},
            "energy": {"lethargy", "energy", "stamina", "activity tolerance", "fatigue"},
            "skin-feather": {"feather", "plucking", "skin", "coat", "wound"},
            "droppings": {"droppings", "stool", "urine", "litter", "bathroom"},
            "medication": {"medication", "dose", "adverse reaction", "tolerance"},
            "hydration": {"hydration", "water", "dehydration", "drinking"},
            "behavior": {"behavior", "vocalization", "stress", "restless", "agitation"},
        }
        for theme, keywords in theme_keywords.items():
            if any(keyword in text for keyword in keywords):
                return theme
        return (category or "alert").strip().lower() or "alert"

    def _limit_care_alert_tasks(self, tasks: List[Task]) -> List[Task]:
        priority_order = {"high": 0, "medium": 1, "low": 2}
        ranked = sorted(
            tasks,
            key=lambda task: (
                priority_order.get(getattr(task.priority, "value", str(task.priority)).lower(), len(priority_order)),
                -float(task.confidence_score),
                task.name.lower(),
            ),
        )
        limited: List[Task] = []
        seen_themes: set[str] = set()
        for task in ranked:
            theme = self._care_alert_theme(task.name, task.notes, task.category)
            if theme in seen_themes:
                continue
            seen_themes.add(theme)
            limited.append(task)
            if len(limited) >= 4:
                break
        return limited

    def _consolidate_daily_theme_duplicates(self, tasks: List[Task]) -> List[Task]:
        consolidated: List[Task] = []
        theme_indexes: dict[str, int] = {}
        for task in tasks:
            theme = self._daily_task_theme(task)
            if theme == "basic":
                consolidated.append(task)
                continue
            existing_index = theme_indexes.get(theme)
            if existing_index is None:
                theme_indexes[theme] = len(consolidated)
                consolidated.append(task)
                continue
            consolidated[existing_index] = self._merge_duplicate_daily_tasks(consolidated[existing_index], task)
        return sorted(consolidated, key=lambda item: item.scheduled_time)

    def _needs_daily_variation_backfill(self, tasks: List[Task]) -> bool:
        daily_tasks = [task for task in tasks if task.frequency == "daily"]
        non_basic_daily_tasks = [task for task in daily_tasks if self._daily_task_theme(task) != "basic"]
        distinct_themes = {self._daily_task_theme(task) for task in non_basic_daily_tasks}
        return len(non_basic_daily_tasks) < 4 or len(distinct_themes) < 4

    def _daily_tasks_are_duplicates(self, left: Task, right: Task) -> bool:
        synonym_map = {
            "feed": "feeding",
            "feeding": "feeding",
            "meal": "feeding",
            "meals": "feeding",
            "food": "feeding",
            "breakfast": "morning",
            "dinner": "evening",
            "supper": "evening",
            "med": "medication",
            "meds": "medication",
            "medicine": "medication",
            "medication": "medication",
            "pill": "medication",
            "pills": "medication",
            "dose": "medication",
            "doses": "medication",
            "water": "hydration",
            "drink": "hydration",
            "drinking": "hydration",
            "hydration": "hydration",
            "hydrate": "hydration",
            "walk": "walk",
            "walking": "walk",
            "potty": "bathroom",
        }
        filler_tokens = {
            "daily",
            "routine",
            "check",
            "support",
            "care",
            "pet",
            "minute",
            "minutes",
            "short",
            "quick",
            "gentle",
            "calm",
            "regular",
            "consistent",
            "track",
            "monitor",
            "observe",
            "note",
        }
        time_slot_patterns = {
            "morning": r"\b(morning|breakfast|wake[\s-]?up|am|a\.m\.)\b",
            "midday": r"\b(midday|noon|lunch|afternoon)\b",
            "evening": r"\b(evening|night|bedtime|dinner|supper|pm|p\.m\.)\b",
        }

        def normalize_token(token: str) -> str:
            normalized = synonym_map.get(token, token)
            if normalized.endswith("ies") and len(normalized) > 4:
                normalized = f"{normalized[:-3]}y"
            elif normalized.endswith("ing") and len(normalized) > 5:
                normalized = normalized[:-3]
            elif normalized.endswith("s") and len(normalized) > 4:
                normalized = normalized[:-1]
            return normalized

        def extract_intent(task: Task) -> set[str]:
            text = f"{task.name} {task.notes}".lower()
            tokens = []
            for raw_token in re.findall(r"[a-z0-9]+", text):
                normalized = normalize_token(raw_token)
                if normalized in filler_tokens or any(re.fullmatch(pattern, raw_token) for pattern in time_slot_patterns.values()):
                    continue
                tokens.append(normalized)

            if task.category:
                tokens.append(normalize_token(task.category.lower()))

            return {token for token in tokens if token}

        def extract_slots(task: Task) -> set[str]:
            text = f"{task.name} {task.notes}".lower()
            return {
                slot
                for slot, pattern in time_slot_patterns.items()
                if re.search(pattern, text)
            }

        left_intent = extract_intent(left)
        right_intent = extract_intent(right)
        if not left_intent or not right_intent:
            return False

        same_intent = left_intent == right_intent or left_intent.issubset(right_intent) or right_intent.issubset(left_intent)
        if not same_intent:
            return False

        left_slots = extract_slots(left)
        right_slots = extract_slots(right)
        if left_slots and right_slots and left_slots.isdisjoint(right_slots):
            return False
        return True

    def _merge_duplicate_daily_tasks(self, left: Task, right: Task) -> Task:
        priority_order = {"low": 0, "medium": 1, "high": 2}

        merged_notes = left.notes if len(left.notes.strip()) >= len(right.notes.strip()) else right.notes
        if left.notes.strip() and right.notes.strip() and left.notes.strip() != right.notes.strip():
            merged_notes = f"{left.notes.strip()} {right.notes.strip()}".strip()

        merged_rationale = left.rationale if len(left.rationale.strip()) >= len(right.rationale.strip()) else right.rationale
        merged_source_ids = list(dict.fromkeys([*left.source_ids, *right.source_ids]))
        merged_time = min(time for time in [left.scheduled_time, right.scheduled_time] if time)

        preferred = left if len(left.name.strip()) >= len(right.name.strip()) else right
        higher_priority = left.priority
        if priority_order.get(getattr(right.priority, "value", ""), -1) > priority_order.get(getattr(left.priority, "value", ""), -1):
            higher_priority = right.priority

        return replace(
            preferred,
            duration_minutes=max(left.duration_minutes, right.duration_minutes),
            priority=higher_priority,
            notes=merged_notes,
            scheduled_time=merged_time,
            rationale=merged_rationale,
            confidence_score=max(left.confidence_score, right.confidence_score),
            source_ids=merged_source_ids,
        )

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
            scheduled_weekday=candidate.scheduled_weekday,
            scheduled_month_weeks=list(candidate.scheduled_month_weeks),
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
            "scheduled_weekday": task.scheduled_weekday,
            "scheduled_month_weeks": list(task.scheduled_month_weeks),
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
