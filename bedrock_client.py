from dataclasses import dataclass
from typing import Any, Dict, List
import ast
import importlib
import json
import os
import re

from ai_retrieval import RetrievedPassage


DEFAULT_BEDROCK_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_AWS_REGION = "us-west-2"


class RecommendationProviderError(Exception):
    """Raised when the model provider request fails."""


@dataclass
class RecommendationCandidate:
    name: str
    duration_minutes: int
    priority: str
    category: str
    notes: str
    scheduled_time: str
    frequency: str
    rationale: str
    source_ids: List[str]
    confidence: float = 0.0

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "RecommendationCandidate":
        return cls(
            name=str(payload.get("name", "")).strip(),
            duration_minutes=int(payload.get("duration_minutes", 0)),
            priority=str(payload.get("priority", "")).strip().lower(),
            category=str(payload.get("category", "")).strip().lower(),
            notes=str(payload.get("notes", "")).strip(),
            scheduled_time=str(payload.get("scheduled_time", "08:00")).strip(),
            frequency=str(payload.get("frequency", "daily")).strip().lower(),
            rationale=str(payload.get("rationale", "")).strip(),
            source_ids=[str(item).strip() for item in payload.get("source_ids", []) if str(item).strip()],
            confidence=float(payload.get("confidence", 0.0)),
        )


@dataclass
class SpeciesProfile:
    species_label: str
    lifespan_min_years: int
    lifespan_max_years: int
    characteristics: str
    summary: str
    confidence: float = 0.0

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SpeciesProfile":
        return cls(
            species_label=str(payload.get("species_label", "")).strip(),
            lifespan_min_years=int(payload.get("lifespan_min_years", 0)),
            lifespan_max_years=int(payload.get("lifespan_max_years", 0)),
            characteristics=str(payload.get("characteristics", "")).strip(),
            summary=str(payload.get("summary", "")).strip(),
            confidence=float(payload.get("confidence", 0.0)),
        )


class BedrockRecommendationClient:
    """Amazon Bedrock Converse wrapper for structured Claude recommendations."""

    def __init__(
        self,
        region: str | None = None,
        profile: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 60,
    ):
        self.region = region or os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
        self.profile = profile or os.getenv("AWS_PROFILE", "")
        self.model = model or os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)
        self.timeout_seconds = timeout_seconds

    def profile_species(
        self,
        species: str,
        breed: str = "",
        special_needs: str = "",
    ) -> SpeciesProfile:
        client = self._build_client()
        try:
            response = client.converse(
                modelId=self.model,
                system=[{"text": self._species_profile_system_prompt()}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": self._build_species_profile_prompt(
                            species=species,
                            breed=breed,
                            special_needs=special_needs,
                        )}],
                    }
                ],
                inferenceConfig={"maxTokens": 700, "temperature": 0.1},
            )
        except Exception as exc:
            raise RecommendationProviderError(
                f"Bedrock species-profile request failed. Check AWS credentials, region, model access, and IAM permissions: {exc}"
            ) from exc

        response_text = self._extract_text(response)
        parsed = self._parse_json_payload(response_text)
        payload = parsed.get("species_profile")
        if not isinstance(payload, dict):
            raise RecommendationProviderError("Bedrock returned a malformed species profile payload.")
        return SpeciesProfile.from_payload(payload)

    def recommend(
        self,
        owner_name: str,
        available_minutes: int,
        pet_name: str,
        species: str,
        breed: str,
        age: int,
        special_needs: str,
        characteristics: str,
        age_context: str,
        goal: str,
        extra_context: str,
        requested_frequencies: List[str],
        existing_tasks: List[Dict[str, Any]],
        retrieved_passages: List[RetrievedPassage],
    ) -> List[RecommendationCandidate]:
        client = self._build_client()
        try:
            response = client.converse(
                modelId=self.model,
                system=[{"text": self._system_prompt()}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": self._build_user_prompt(
                            owner_name=owner_name,
                            available_minutes=available_minutes,
                            pet_name=pet_name,
                            species=species,
                            breed=breed,
                            age=age,
                            special_needs=special_needs,
                            characteristics=characteristics,
                            age_context=age_context,
                            goal=goal,
                            extra_context=extra_context,
                            requested_frequencies=requested_frequencies,
                            existing_tasks=existing_tasks,
                            retrieved_passages=retrieved_passages,
                        )}],
                    }
                ],
                inferenceConfig={"maxTokens": 1400, "temperature": 0.2},
            )
        except Exception as exc:
            raise RecommendationProviderError(
                f"Bedrock request failed. Check AWS credentials, region, model access, and IAM permissions: {exc}"
            ) from exc

        response_text = self._extract_text(response)
        parsed = self._parse_json_payload(response_text)
        recommendations = parsed.get("recommendations", [])
        if not isinstance(recommendations, list):
            raise RecommendationProviderError("Bedrock returned a malformed recommendations payload.")
        return [RecommendationCandidate.from_payload(item) for item in recommendations]

    def _build_client(self):
        try:
            boto3 = importlib.import_module("boto3")
            botocore_config = importlib.import_module("botocore.config")
            botocore_exceptions = importlib.import_module("botocore.exceptions")
        except ModuleNotFoundError as exc:
            raise RecommendationProviderError(
                "boto3 is not installed. Install requirements.txt before using Bedrock."
            ) from exc

        config = botocore_config.Config(read_timeout=self.timeout_seconds, retries={"max_attempts": 2})
        try:
            if self.profile:
                session = boto3.Session(profile_name=self.profile, region_name=self.region)
                return session.client("bedrock-runtime", config=config)
            return boto3.client("bedrock-runtime", region_name=self.region, config=config)
        except getattr(botocore_exceptions, "ProfileNotFound") as exc:
            raise RecommendationProviderError(
                f"AWS profile '{self.profile}' was not found. Run aws configure or choose a valid profile."
            ) from exc
        except Exception as exc:
            raise RecommendationProviderError(f"Failed to initialize Bedrock client: {exc}") from exc

    def _system_prompt(self) -> str:
        return (
            "You are PawPal+, an AI pet-care planning assistant. "
            "Recommend safe, routine-oriented pet care tasks grounded only in the supplied source excerpts. "
            "Do not diagnose, prescribe, adjust medication dosage, or claim emergency treatment. "
            "Keep string values plain and compact. Avoid markdown, commentary, and unnecessary quotation marks inside values. "
            "Return JSON only with this shape: "
            "{\"recommendations\": [{\"name\": str, \"duration_minutes\": int, \"priority\": \"low|medium|high\", "
            "\"category\": str, \"notes\": str, \"scheduled_time\": \"HH:MM\", \"frequency\": \"daily|weekly|monthly|as needed\", "
            "\"rationale\": str, \"source_ids\": [str], \"confidence\": float}]}"
        )

    def _species_profile_system_prompt(self) -> str:
        return (
            "You are PawPal+, an AI species-context assistant for pet care planning. "
            "Return a cautious, best-effort species profile for a companion animal using common pet-care knowledge. "
            "Estimate a realistic typical lifespan range in years for the named species or breed in a pet/captive context when possible. "
            "Describe general care characteristics only; do not diagnose, prescribe, or provide emergency instructions. "
            "Keep string values plain and compact. Avoid markdown, commentary, and unnecessary quotation marks inside values. "
            "Return JSON only with this shape: "
            "{\"species_profile\": {\"species_label\": str, \"lifespan_min_years\": int, "
            "\"lifespan_max_years\": int, \"characteristics\": str, \"summary\": str, \"confidence\": float}}"
        )

    def _build_user_prompt(
        self,
        owner_name: str,
        available_minutes: int,
        pet_name: str,
        species: str,
        breed: str,
        age: int,
        special_needs: str,
        characteristics: str,
        age_context: str,
        goal: str,
        extra_context: str,
        requested_frequencies: List[str],
        existing_tasks: List[Dict[str, Any]],
        retrieved_passages: List[RetrievedPassage],
    ) -> str:
        sources = "\n\n".join(
            f"[{passage.doc_id}] {passage.title}\n{passage.content}"
            for passage in retrieved_passages
        )
        current_tasks = json.dumps(existing_tasks, indent=2)
        cadence_instruction = (
            f"Requested cadence constraint: {', '.join(requested_frequencies)} only."
            if requested_frequencies
            else "Requested cadence constraint: none."
        )

        return (
            f"Owner: {owner_name}\n"
            f"Available minutes today: {available_minutes}\n"
            f"Pet name: {pet_name}\n"
            f"Species: {species}\n"
            f"Breed: {breed or 'not provided'}\n"
            f"Age: {age}\n"
            f"Special needs: {special_needs or 'none'}\n"
            f"Inferred species characteristics: {characteristics or 'none available'}\n"
            f"Age context: {age_context}\n"
            f"Goal or situation: {goal or 'build a practical pet care routine'}\n"
            f"Extra context: {extra_context or 'none'}\n"
            f"{cadence_instruction}\n\n"
            "Current tasks already in the app:\n"
            f"{current_tasks}\n\n"
            "Retrieved source excerpts:\n"
            f"{sources}\n\n"
            "Generate a recurring pet care plan with 5 to 8 task recommendations that fit the pet profile. "
            "If a cadence constraint is present, obey it strictly and return only recommendations with that cadence. "
            "If no cadence constraint is present, include a realistic mix of daily, weekly, and monthly care tasks when supported by the profile and sources, "
            "plus 'as needed' guidance only when clearly grounded. "
            "Prefer routine care, monitoring, enrichment, hydration, feeding, mobility support, and reminders "
            "already grounded in the sources. Use only source IDs that appear in the excerpts above."
        )

    def _build_species_profile_prompt(self, species: str, breed: str, special_needs: str) -> str:
        return (
            f"Species: {species}\n"
            f"Breed: {breed or 'not provided'}\n"
            f"Special needs or context: {special_needs or 'none'}\n\n"
            "Provide a general pet-care species profile for this animal. "
            "If breed materially changes lifespan or temperament, account for it. "
            "Use years for lifespan values. "
            "Characteristics should be a concise paragraph about normal care tendencies, enrichment, monitoring, handling, diet rhythm, and environment. "
            "Summary should be one short sentence explaining the lifespan estimate and broad care context."
        )

    def _extract_text(self, response: Dict[str, Any]) -> str:
        try:
            blocks = response["output"]["message"]["content"]
        except KeyError as exc:
            raise RecommendationProviderError("Bedrock returned an unexpected response shape.") from exc

        text_blocks = [block.get("text", "") for block in blocks if isinstance(block, dict) and "text" in block]
        response_text = "".join(text_blocks).strip()
        if not response_text:
            raise RecommendationProviderError("Bedrock returned an empty response.")
        return response_text

    def _parse_json_payload(self, response_text: str) -> Dict[str, Any]:
        candidates: List[str] = []
        raw = response_text.strip()
        if raw:
            candidates.append(raw)

        fenced = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fenced:
            candidates.append(fenced.group(1).strip())

        extracted = self._extract_json_object(raw)
        if extracted:
            candidates.append(extracted)

        tried: set[str] = set()
        for candidate in candidates:
            for variant in (candidate, self._repair_json(candidate)):
                cleaned = variant.strip()
                if not cleaned or cleaned in tried:
                    continue
                tried.add(cleaned)
                parsed = self._parse_structured_candidate(cleaned)
                if parsed is not None:
                    return parsed

        preview = re.sub(r"\s+", " ", raw)[:220]
        raise RecommendationProviderError(
            f"Bedrock returned malformed JSON that could not be parsed. Response preview: {preview}"
        )

    def _parse_structured_candidate(self, text: str) -> Dict[str, Any] | None:
        """Parse a candidate payload as strict JSON, then as a Python-like dict literal."""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return None

        if isinstance(parsed, dict):
            return parsed
        return None

    def _extract_json_object(self, text: str) -> str:
        """Extract the first balanced top-level JSON object from mixed model output."""
        start = text.find("{")
        if start == -1:
            return ""

        in_string = False
        escape = False
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        end = text.rfind("}")
        if end > start:
            return text[start:end + 1]
        return ""

    def _repair_json(self, text: str) -> str:
        """Repair small, common JSON issues from model output."""
        repaired = (
            text.replace("\ufeff", "")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        repaired = re.sub(r"```(?:json)?", "", repaired, flags=re.IGNORECASE)
        repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

        output: List[str] = []
        in_string = False
        escape = False
        length = len(repaired)

        for index, char in enumerate(repaired):
            if escape:
                output.append(char)
                escape = False
                continue

            if char == "\\":
                output.append(char)
                escape = True
                continue

            if char == '"':
                if not in_string:
                    in_string = True
                    output.append(char)
                    continue

                next_nonspace = ""
                for look_ahead in range(index + 1, length):
                    next_char = repaired[look_ahead]
                    if not next_char.isspace():
                        next_nonspace = next_char
                        break

                if next_nonspace and next_nonspace not in {",", "}", "]", ":"}:
                    output.append('\\"')
                    continue

                in_string = False
                output.append(char)
                continue

            if in_string and char == "\n":
                output.append("\\n")
                continue
            if in_string and char == "\r":
                output.append("\\r")
                continue
            if in_string and char == "\t":
                output.append("\\t")
                continue

            output.append(char)

        return "".join(output)
