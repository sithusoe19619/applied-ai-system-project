from dataclasses import dataclass
from typing import List
import re

from bedrock_client import RecommendationCandidate
from ai_retrieval import RetrievedPassage
from schedule_utils import VALID_MONTH_WEEKS


TIME_RE = re.compile(r"^\d{2}:\d{2}$")
VALID_WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
VALID_MONTH_WEEK_SET = set(VALID_MONTH_WEEKS)
UNSAFE_PATTERNS = (
    re.compile(r"\bdiagnose\b"),
    re.compile(r"\bdiagnosis\b"),
    re.compile(r"\bprescribe\b"),
    re.compile(r"\bprescription\b"),
    re.compile(r"\bincrease dosage\b"),
    re.compile(r"\bdecrease dosage\b"),
    re.compile(r"\bhuman medication\b"),
    re.compile(r"\breplace your veterinarian\b"),
    re.compile(r"\bignore your veterinarian\b"),
    re.compile(r"\bemergency treatment\b"),
)


@dataclass
class BlockedRecommendation:
    name: str
    reasons: List[str]


@dataclass
class ValidationResult:
    accepted: List[RecommendationCandidate]
    blocked: List[BlockedRecommendation]
    warnings: List[str]
    reliability_score: float


class RecommendationValidator:
    """Validate groundedness and safety before tasks reach the scheduler."""

    def validate(
        self,
        recommendations: List[RecommendationCandidate],
        retrieved_passages: List[RetrievedPassage],
        allowed_frequencies: set[str] | None = None,
    ) -> ValidationResult:
        allowed_sources = {passage.doc_id for passage in retrieved_passages}
        accepted: List[RecommendationCandidate] = []
        blocked: List[BlockedRecommendation] = []
        warnings: List[str] = []

        for recommendation in recommendations:
            reasons: List[str] = []
            if recommendation.frequency == "as needed":
                if recommendation.duration_minutes < 1:
                    recommendation.duration_minutes = 2
                if not self._is_valid_time(recommendation.scheduled_time):
                    recommendation.scheduled_time = "00:00"
            if not recommendation.name:
                reasons.append("Missing task name.")
            if recommendation.duration_minutes < 1 or recommendation.duration_minutes > 240:
                reasons.append("Duration must be between 1 and 240 minutes.")
            if recommendation.priority not in {"low", "medium", "high"}:
                reasons.append("Priority must be low, medium, or high.")
            if recommendation.frequency not in {"daily", "weekly", "monthly", "as needed"}:
                reasons.append("Frequency must be daily, weekly, monthly, or as needed.")
            elif allowed_frequencies is not None and recommendation.frequency not in allowed_frequencies:
                allowed_list = ", ".join(sorted(allowed_frequencies))
                reasons.append(f"Frequency must match the requested cadence: {allowed_list}.")
            if recommendation.frequency != "as needed" and not self._is_valid_time(recommendation.scheduled_time):
                reasons.append("Scheduled time must use HH:MM in 24-hour format.")
            if recommendation.frequency == "weekly" and recommendation.scheduled_weekday not in VALID_WEEKDAYS:
                reasons.append("Weekly recommendations must include a full scheduled weekday from Monday through Sunday.")
            if recommendation.frequency != "weekly" and recommendation.scheduled_weekday:
                reasons.append("Only weekly recommendations may include a scheduled weekday.")
            if recommendation.frequency == "monthly":
                if not 1 <= len(recommendation.scheduled_month_weeks) <= 2:
                    reasons.append("Monthly recommendations must include 1 or 2 scheduled month-weeks.")
                if any(label not in VALID_MONTH_WEEK_SET for label in recommendation.scheduled_month_weeks):
                    reasons.append("Monthly recommendations may only use Week 1, Week 2, Week 3, or Week 4.")
            elif recommendation.scheduled_month_weeks:
                reasons.append("Only monthly recommendations may include scheduled month-weeks.")
            if not recommendation.rationale:
                reasons.append("Recommendation must include a rationale.")
            if not recommendation.source_ids:
                reasons.append("Recommendation is ungrounded because it cites no sources.")
            if any(source_id not in allowed_sources for source_id in recommendation.source_ids):
                reasons.append("Recommendation cites sources that were not retrieved.")

            combined_text = " ".join(
                [
                    recommendation.name,
                    recommendation.category,
                    recommendation.notes,
                    recommendation.rationale,
                ]
            ).lower()
            if any(pattern.search(combined_text) for pattern in UNSAFE_PATTERNS):
                reasons.append("Recommendation contains unsafe or unsupported medical advice.")

            if reasons:
                blocked.append(BlockedRecommendation(name=recommendation.name or "Unnamed task", reasons=reasons))
                continue

            grounded_bonus = min(len(set(recommendation.source_ids)) * 0.12, 0.24)
            confidence = recommendation.confidence or 0.65
            recommendation.confidence = round(max(0.0, min(0.99, confidence + grounded_bonus)), 2)
            accepted.append(recommendation)

        reliability_score = round(
            sum(item.confidence for item in accepted) / len(accepted),
            2,
        ) if accepted else 0.0

        return ValidationResult(
            accepted=accepted,
            blocked=blocked,
            warnings=warnings,
            reliability_score=reliability_score,
        )

    def _is_valid_time(self, time_value: str) -> bool:
        if not TIME_RE.match(time_value):
            return False
        hours, minutes = [int(part) for part in time_value.split(":")]
        return 0 <= hours <= 23 and 0 <= minutes <= 59
