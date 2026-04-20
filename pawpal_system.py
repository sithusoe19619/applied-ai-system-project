from dataclasses import dataclass, field, replace
from typing import List, Optional
from enum import Enum
from datetime import date, timedelta
import json
import os
import re


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


SPECIES_LIFESPAN_YEARS = {
    "dog": (10, 13),
    "cat": (13, 17),
    "other": (10, 15),
}

SPECIES_CHARACTERISTICS = {
    "dog": (
        "Dogs often benefit from predictable routines, regular exercise or movement, hydration checks, "
        "feeding consistency, enrichment, and observation of mobility, appetite, and behavior changes."
    ),
    "cat": (
        "Cats often benefit from feeding consistency, hydration monitoring, litter box observation, "
        "calm enrichment, and close attention to appetite, grooming, and behavioral changes."
    ),
    "other": (
        "This pet may benefit from a steady care routine, feeding and hydration consistency, gentle enrichment, "
        "and observation of appetite, mobility, and behavior changes."
    ),
}

BREED_CHARACTERISTICS = {
    "dog": {
        "labrador retriever": (
            "Labrador retrievers are often social, food-motivated, and energetic, so they usually benefit from "
            "consistent exercise, structured enrichment, feeding consistency, and joint or weight monitoring as they age."
        ),
        "golden retriever": (
            "Golden retrievers are often social and active, and they usually benefit from steady exercise, "
            "grooming attention, enrichment, and observation for mobility or skin and coat changes."
        ),
        "german shepherd": (
            "German shepherds often benefit from structured routines, mental stimulation, exercise, and close "
            "observation of joint comfort, mobility, and stress-related behavior changes."
        ),
        "chihuahua": (
            "Chihuahuas often benefit from predictable routines, short activity sessions, warmth and comfort support, "
            "feeding consistency, and attention to stress or handling sensitivity."
        ),
        "bulldog": (
            "Bulldogs often benefit from low-impact routines, heat-awareness, feeding consistency, and close "
            "observation of breathing comfort, skin folds, and mobility changes."
        ),
        "poodle": (
            "Poodles often benefit from enrichment, grooming structure, regular movement, and consistent routines "
            "that support both mental stimulation and coat maintenance."
        ),
        "husky": (
            "Huskies often benefit from high engagement, structured exercise, enrichment, hydration checks, and "
            "careful planning for high energy needs and boredom prevention."
        ),
    },
    "cat": {
        "domestic shorthair": (
            "Domestic shorthair cats often benefit from feeding consistency, litter monitoring, calm enrichment, "
            "hydration support, and observation of appetite and grooming habits."
        ),
        "maine coon": (
            "Maine coons often benefit from grooming attention, steady exercise and enrichment, feeding consistency, "
            "and observation of mobility, appetite, and coat condition."
        ),
        "siamese": (
            "Siamese cats often benefit from social interaction, enrichment, feeding consistency, and observation "
            "for stress-related vocalization or behavior changes."
        ),
        "ragdoll": (
            "Ragdolls often benefit from calm routines, grooming attention, moderate play, feeding consistency, "
            "and observation of coat care and mobility."
        ),
        "bengal": (
            "Bengal cats often benefit from higher enrichment, active play, feeding consistency, and structured "
            "mental stimulation to prevent boredom."
        ),
        "persian": (
            "Persian cats often benefit from grooming structure, calm routines, feeding consistency, and close "
            "observation of coat condition, eye care, and comfort."
        ),
    },
}

MIXED_OR_UNKNOWN_BREEDS = {"mixed", "mix", "mixed breed", "unknown", "unknown breed"}
VALID_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z' -]{1,49}$")
FREE_TEXT_ALLOWED_RE = re.compile(r"^[A-Za-z0-9 .,;:()'\"!?/&%+\-\n]{1,500}$")
AWS_REGION_RE = re.compile(r"^[a-z]{2}(?:-[a-z]+)?-[a-z]+-\d$")
AWS_PROFILE_RE = re.compile(r"^[A-Za-z0-9+=,.@_-]{1,64}$")
BEDROCK_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._:/-]{3,200}$")
MEDICAL_SHORT_TOKENS = {"uti", "ckd", "ivdd", "fiv", "felv", "gi", "ibd", "dm", "uri", "rx", "qa", "am", "pm"}
KNOWN_DOG_BREED_NAMES = {
    "labrador retriever",
    "golden retriever",
    "german shepherd",
    "chihuahua",
    "bulldog",
    "poodle",
    "husky",
    "beagle",
    "boxer",
    "corgi",
    "dachshund",
    "doberman",
    "rottweiler",
    "pomeranian",
    "shih tzu",
    "yorkshire terrier",
    "border collie",
    "australian shepherd",
    "great dane",
    "cavalier king charles spaniel",
    "french bulldog",
    "miniature schnauzer",
    "pit bull",
}
KNOWN_CAT_BREED_NAMES = {
    "domestic shorthair",
    "domestic longhair",
    "maine coon",
    "siamese",
    "ragdoll",
    "bengal",
    "persian",
    "sphynx",
    "birman",
    "russian blue",
    "british shorthair",
    "norwegian forest cat",
}
KNOWN_BREED_NAMES = KNOWN_DOG_BREED_NAMES | KNOWN_CAT_BREED_NAMES
DOG_BREED_TOKENS = {
    "retriever", "shepherd", "terrier", "hound", "spaniel", "collie", "mastiff", "boxer",
    "corgi", "dachshund", "doberman", "rottweiler", "pomeranian", "poodle", "husky",
    "bulldog", "beagle", "chihuahua", "dane", "schnauzer", "pit", "bull", "cavalier",
    "king", "charles", "labrador", "golden", "german", "french", "yorkshire", "shih",
    "tzu", "australian", "border", "miniature", "mix", "mixed",
}
CAT_BREED_TOKENS = {
    "shorthair", "longhair", "maine", "coon", "siamese", "ragdoll", "bengal", "persian",
    "sphynx", "birman", "russian", "blue", "british", "norwegian", "forest", "domestic",
    "cat", "mix", "mixed",
}
KNOWN_SPECIES_NAMES = {
    "rabbit", "mini lop rabbit", "guinea pig", "hamster", "gerbil", "ferret", "parrot",
    "cockatiel", "budgie", "canary", "rabbit mix", "turtle", "tortoise", "gecko", "lizard",
    "bearded dragon", "snake", "frog", "fish", "betta fish", "goldfish", "chinchilla",
    "hedgehog", "rat", "mouse", "hamster mix", "parakeet", "conure", "lovebird",
    "axolotl", "hermit crab", "leopard gecko",
}
SPECIES_TOKENS = {
    "rabbit", "bunny", "lop", "guinea", "pig", "hamster", "gerbil", "ferret", "parrot",
    "cockatiel", "budgie", "canary", "bird", "turtle", "tortoise", "gecko", "lizard",
    "dragon", "snake", "frog", "fish", "chinchilla", "hedgehog", "rat", "mouse",
    "parakeet", "conure", "lovebird", "axolotl", "crab",
}


@dataclass
class Task:
    name: str
    duration_minutes: int
    priority: Priority
    category: str
    notes: str
    scheduled_time: str = "00:00"  # "HH:MM" format, e.g. "08:30"
    scheduled_date: str = ""       # "YYYY-MM-DD" format, defaults to today at runtime
    frequency: str = "daily"       # "daily", "weekly", "monthly", or "as needed"
    status: str = "pending"
    pet: Optional["Pet"] = None
    ai_generated: bool = False
    rationale: str = ""
    confidence_score: float = 0.0
    source_ids: List[str] = field(default_factory=list)
    validation_status: str = "manual"

    def __post_init__(self):
        if not self.scheduled_date:
            self.scheduled_date = date.today().isoformat()

    def is_high_priority(self) -> bool:
        """Return True if this task has HIGH priority."""
        return self.priority == Priority.HIGH

    def mark_complete(self) -> Optional["Task"]:
        """Mark this task as completed and auto-generate the next occurrence for recurring tasks.

        Sets this task's status to "completed". If the task's frequency is "daily" or
        "weekly", creates a new pending copy with the scheduled_date advanced by the
        appropriate timedelta and adds it to the same pet. Uses dataclasses.replace()
        to copy all fields, so new fields added to Task are carried forward automatically.

        Returns:
            Task: The newly created next occurrence, or None if frequency is "as needed"
                  or unrecognized.

        Example:
            >>> walk = Task("Walk", 30, Priority.HIGH, "exercise", "", scheduled_time="07:00", frequency="daily")
            >>> next_walk = walk.mark_complete()
            >>> walk.status
            'completed'
            >>> next_walk.scheduled_date  # today + 1 day
        """
        self.status = "completed"

        if self.frequency == "as needed":
            return None

        frequency_delta = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}
        delta = frequency_delta.get(self.frequency)
        if delta is None:
            return None

        next_date = date.fromisoformat(self.scheduled_date) + delta
        next_task = replace(
            self,
            scheduled_date=next_date.isoformat(),
            status="pending",
            pet=None,
            source_ids=list(self.source_ids),
        )

        if self.pet:
            self.pet.add_task(next_task)

        return next_task

    def __repr__(self) -> str:
        return (
            f"Task(name={self.name!r}, duration={self.duration_minutes}min, "
            f"priority={self.priority.value}, frequency={self.frequency!r}, status={self.status!r})"
        )


@dataclass
class Pet:
    name: str
    species: str
    age: int
    special_needs: str = ""
    characteristics: str = ""
    breed: str = ""
    custom_species: str = ""
    lifespan_min_years: int = 0
    lifespan_max_years: int = 0
    species_profile_summary: str = ""
    species_profile_source: str = ""
    tasks: List["Task"] = field(default_factory=list)

    def has_special_needs(self) -> bool:
        """Return True if this pet has a non-empty special needs description."""
        return bool(self.special_needs.strip())

    def add_task(self, task: "Task") -> None:
        """Add a task to this pet and set the task's pet reference."""
        task.pet = self
        self.tasks.append(task)

    def remove_task(self, task: "Task") -> None:
        """Remove a task from this pet and clear the task's pet reference."""
        self.tasks.remove(task)
        task.pet = None

    def get_tasks(self) -> List["Task"]:
        """Return the list of tasks assigned to this pet."""
        return self.tasks

    def get_effective_species_label(self) -> str:
        """Return the display species used in summaries and AI prompts."""
        if self.species == "other" and self.custom_species.strip():
            return self.custom_species.strip()
        return self.species

    def get_effective_breed_label(self) -> str:
        """Return the normalized breed label, if any."""
        return self.breed.strip()

    def get_lifespan_range_years(self) -> tuple[int, int]:
        """Return the best available lifespan range for this pet."""
        if self.lifespan_min_years > 0 and self.lifespan_max_years >= self.lifespan_min_years:
            return (self.lifespan_min_years, self.lifespan_max_years)
        return SPECIES_LIFESPAN_YEARS.get(self.species, SPECIES_LIFESPAN_YEARS["other"])

    def apply_species_profile(
        self,
        lifespan_min_years: int,
        lifespan_max_years: int,
        characteristics: str,
        summary: str = "",
        source: str = "",
    ) -> None:
        """Cache model-derived species information on the pet profile."""
        if lifespan_min_years > 0 and lifespan_max_years >= lifespan_min_years:
            self.lifespan_min_years = lifespan_min_years
            self.lifespan_max_years = lifespan_max_years
        if characteristics.strip():
            self.characteristics = characteristics.strip()
        if summary.strip():
            self.species_profile_summary = summary.strip()
        if source.strip():
            self.species_profile_source = source.strip()

    def get_age_context(self) -> dict:
        """Return a simple species lifespan estimate and life-stage interpretation."""
        lifespan_range = self.get_lifespan_range_years()
        estimated_total_years = round(sum(lifespan_range) / 2)
        age_ratio = (self.age / estimated_total_years) if estimated_total_years else 0.0

        if age_ratio < 0.3:
            life_stage = "young"
        elif age_ratio < 0.75:
            life_stage = "adult"
        else:
            life_stage = "senior"

        effective_species = self.get_effective_species_label()
        if self.species_profile_summary.strip():
            summary = self.species_profile_summary.strip()
        elif self.species == "other":
            summary = (
                f"{self.name} is estimated to be in the {life_stage} stage. "
                f"A typical lifespan for {effective_species} is approximated at {lifespan_range[0]}-{lifespan_range[1]} years."
            )
        else:
            summary = (
                f"{self.name} is in the {life_stage} stage for a {effective_species}. "
                f"A typical lifespan is about {lifespan_range[0]}-{lifespan_range[1]} years."
            )

        return {
            "life_stage": life_stage,
            "lifespan_range_years": lifespan_range,
            "estimated_total_years": estimated_total_years,
            "summary": summary,
        }

    def get_species_characteristics(self) -> str:
        """Return inferred breed/species care characteristics for AI planning."""
        if self.characteristics.strip():
            return self.characteristics.strip()

        normalized_breed = self.get_effective_breed_label().lower()
        if normalized_breed and normalized_breed not in MIXED_OR_UNKNOWN_BREEDS:
            breed_traits = BREED_CHARACTERISTICS.get(self.species, {})
            if normalized_breed in breed_traits:
                return breed_traits[normalized_breed]

        species_traits = SPECIES_CHARACTERISTICS.get(self.species, SPECIES_CHARACTERISTICS["other"])
        if normalized_breed:
            return f"{species_traits} Breed context: {self.get_effective_breed_label()}."
        if self.species == "other" and self.custom_species.strip():
            return f"{species_traits} Species context: {self.custom_species.strip()}."
        return species_traits

    @staticmethod
    def is_valid_profile_label(value: str) -> bool:
        """Return True for realistic breed/species labels and False for obvious junk."""
        cleaned = value.strip()
        if not cleaned:
            return False
        if not VALID_NAME_RE.match(cleaned):
            return False

        tokens = [token for token in re.split(r"[ -]+", cleaned.lower()) if token]
        if not tokens:
            return False

        vowels = set("aeiou")
        if all(not any(char in vowels for char in token) and token not in {"mix"} for token in tokens):
            return False
        if any(any(char.isdigit() for char in token) for token in tokens):
            return False
        return True

    @classmethod
    def is_valid_breed_label(cls, value: str, species: str) -> bool:
        """Return True for realistic breed input for the selected species."""
        cleaned = value.strip().lower()
        if not cleaned:
            return False
        if cleaned in MIXED_OR_UNKNOWN_BREEDS:
            return True
        if species == "dog" and cleaned in KNOWN_DOG_BREED_NAMES:
            return True
        if species == "cat" and cleaned in KNOWN_CAT_BREED_NAMES:
            return True
        if not cls.is_valid_profile_label(value):
            return False

        tokens = [token for token in re.split(r"[ -]+", cleaned) if token]
        if not tokens:
            return False

        breed_tokens = DOG_BREED_TOKENS if species == "dog" else CAT_BREED_TOKENS if species == "cat" else set()
        if not breed_tokens:
            return False

        recognized_tokens = [token for token in tokens if token in breed_tokens]
        if len(tokens) == 1:
            return tokens[0] in breed_tokens

        if not recognized_tokens:
            return False

        return len(recognized_tokens) >= max(1, len(tokens) // 2)

    @classmethod
    def is_valid_species_label(cls, value: str) -> bool:
        """Return True for readable custom species labels without requiring a fixed whitelist."""
        cleaned = value.strip()
        if not cls.is_valid_profile_label(cleaned):
            return False

        tokens = [token for token in re.split(r"[ -]+", cleaned.lower()) if token]
        if not tokens or len(tokens) > 5:
            return False

        # Allow any readable animal label so the AI can reason over uncommon or user-provided species.
        return True

    @staticmethod
    def is_valid_context_text(value: str) -> bool:
        """Return True when free-text guidance looks human-written rather than random junk."""
        cleaned = value.strip()
        if not cleaned:
            return True
        normalized = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
        normalized = re.sub(r"\n\s*", "\n", normalized)
        if not FREE_TEXT_ALLOWED_RE.match(normalized):
            return False

        letters = sum(char.isalpha() for char in normalized)
        digits = sum(char.isdigit() for char in normalized)
        punctuation = sum(not char.isalnum() and not char.isspace() for char in normalized)
        if letters < 3:
            return False
        if digits > max(8, letters // 2):
            return False
        if punctuation > max(8, len(normalized) // 3):
            return False

        tokens = [token for token in re.split(r"\s+", normalized) if token]
        suspicious_tokens = 0
        plausible_tokens = 0
        for raw_token in tokens:
            token = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", raw_token)
            if not token:
                continue

            lower = token.lower()
            alpha = sum(char.isalpha() for char in token)
            digit = sum(char.isdigit() for char in token)
            has_vowel = any(char in "aeiouy" for char in lower)

            if alpha == 0:
                suspicious_tokens += 1
                continue
            if digit >= 4 and digit >= alpha:
                suspicious_tokens += 1
                continue
            if len(token) >= 10 and digit > 0 and digit * 2 >= len(token):
                suspicious_tokens += 1
                continue
            if len(lower) >= 8 and not has_vowel and lower not in MEDICAL_SHORT_TOKENS:
                suspicious_tokens += 1
                continue
            if len(lower) >= 18:
                suspicious_tokens += 1
                continue

            plausible_tokens += 1

        if plausible_tokens == 0:
            return False
        return suspicious_tokens < max(2, (len(tokens) + 1) // 2)

    @staticmethod
    def is_valid_aws_region(value: str) -> bool:
        """Return True when the AWS region looks structurally valid."""
        cleaned = value.strip()
        if not cleaned:
            return False
        return bool(AWS_REGION_RE.match(cleaned))

    @staticmethod
    def is_valid_aws_profile(value: str) -> bool:
        """Return True when the optional AWS profile uses safe CLI profile characters."""
        cleaned = value.strip()
        if not cleaned:
            return True
        return bool(AWS_PROFILE_RE.match(cleaned))

    @staticmethod
    def is_valid_bedrock_model_id(value: str) -> bool:
        """Return True when the Bedrock model identifier looks structurally valid."""
        cleaned = value.strip()
        if not cleaned:
            return False
        return bool(BEDROCK_MODEL_ID_RE.match(cleaned))

    def clear_ai_tasks(self) -> None:
        """Remove AI-generated tasks while preserving manual tasks."""
        self.tasks = [task for task in self.tasks if not task.ai_generated]
        for task in self.tasks:
            task.pet = self

    def replace_ai_tasks(self, tasks: List["Task"]) -> None:
        """Replace all AI-generated tasks with a new validated task set."""
        self.clear_ai_tasks()
        for task in tasks:
            self.add_task(task)


class Owner:
    def __init__(self, name: str, available_minutes: int):
        self.name = name
        self.available_minutes = available_minutes
        self.pets: List[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's pet list."""
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner's pet list."""
        self.pets.remove(pet)

    def get_all_tasks(self) -> List[Task]:
        """Return a flat list of every task across all pets."""
        all_tasks = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks

    def save_to_json(self, filepath: str = "data.json") -> None:
        """Save the owner, all pets, and all tasks to a JSON file."""
        data = {
            "owner": self.name,
            "available_minutes": self.available_minutes,
            "pets": [
                {
                    "name": pet.name,
                    "species": pet.species,
                    "age": pet.age,
                    "special_needs": pet.special_needs,
                    "characteristics": pet.characteristics,
                    "breed": pet.breed,
                    "custom_species": pet.custom_species,
                    "lifespan_min_years": pet.lifespan_min_years,
                    "lifespan_max_years": pet.lifespan_max_years,
                    "species_profile_summary": pet.species_profile_summary,
                    "species_profile_source": pet.species_profile_source,
                    "tasks": [
                        {
                            "name": task.name,
                            "duration_minutes": task.duration_minutes,
                            "priority": task.priority.value,
                            "category": task.category,
                            "notes": task.notes,
                            "scheduled_time": task.scheduled_time,
                            "scheduled_date": task.scheduled_date,
                            "frequency": task.frequency,
                            "status": task.status,
                            "ai_generated": task.ai_generated,
                            "rationale": task.rationale,
                            "confidence_score": task.confidence_score,
                            "source_ids": task.source_ids,
                            "validation_status": task.validation_status,
                        }
                        for task in pet.tasks
                    ],
                }
                for pet in self.pets
            ],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str = "data.json") -> Optional["Owner"]:
        """Load an owner with all pets and tasks from a JSON file.

        Returns None if the file does not exist.
        """
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r") as f:
            data = json.load(f)

        priority_map = {"low": Priority.LOW, "medium": Priority.MEDIUM, "high": Priority.HIGH}
        owner = cls(data["owner"], data["available_minutes"])

        for pet_data in data["pets"]:
            pet = Pet(
                name=pet_data["name"],
                species=pet_data["species"],
                age=pet_data["age"],
                special_needs=pet_data.get("special_needs", ""),
                characteristics=pet_data.get("characteristics", ""),
                breed=pet_data.get("breed", ""),
                custom_species=pet_data.get("custom_species", ""),
                lifespan_min_years=pet_data.get("lifespan_min_years", 0),
                lifespan_max_years=pet_data.get("lifespan_max_years", 0),
                species_profile_summary=pet_data.get("species_profile_summary", ""),
                species_profile_source=pet_data.get("species_profile_source", ""),
            )
            for task_data in pet_data["tasks"]:
                task = Task(
                    name=task_data["name"],
                    duration_minutes=task_data["duration_minutes"],
                    priority=priority_map[task_data["priority"]],
                    category=task_data["category"],
                    notes=task_data["notes"],
                    scheduled_time=task_data.get("scheduled_time", "00:00"),
                    scheduled_date=task_data.get("scheduled_date", ""),
                    frequency=task_data.get("frequency", "daily"),
                    status=task_data.get("status", "pending"),
                    ai_generated=task_data.get("ai_generated", False),
                    rationale=task_data.get("rationale", ""),
                    confidence_score=task_data.get("confidence_score", 0.0),
                    source_ids=task_data.get("source_ids", []),
                    validation_status=task_data.get("validation_status", "manual"),
                )
                pet.add_task(task)
            owner.add_pet(pet)

        return owner


class Scheduler:
    def __init__(self, owner: Owner):
        self.owner = owner
        self.scheduled_tasks: List[Task] = []
        self.skipped_tasks: List[Task] = []

    def generate_plan(self, enforce_budget: bool = True) -> dict:
        """
        Returns: {"scheduled": List[Task], "skipped": List[Task], "reasoning": List[str]}
        Schedules high-priority tasks first and optionally enforces an owner time budget.
        """
        self.scheduled_tasks = []
        self.skipped_tasks = []
        reasoning = []

        all_tasks = self.sort_by_priority_then_time(self.owner.get_all_tasks())

        time_remaining = self.owner.available_minutes

        for task in all_tasks:
            if (not enforce_budget) or self.fits_in_budget(task, time_remaining):
                self.scheduled_tasks.append(task)
                if enforce_budget:
                    time_remaining -= task.duration_minutes
                reasoning.append(
                    f"Scheduled '{task.name}' for {task.pet.name} "
                    f"({task.duration_minutes} min, {task.priority.value} priority)"
                )
            else:
                self.skipped_tasks.append(task)
                reasoning.append(
                    f"Skipped '{task.name}' for {task.pet.name} "
                    f"({task.duration_minutes} min) — only {time_remaining} min remaining"
                )

        return {
            "scheduled": self.scheduled_tasks,
            "skipped": self.skipped_tasks,
            "reasoning": reasoning,
        }

    PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}

    def sort_by_time(self, tasks: List[Task]) -> List[Task]:
        """Sort tasks in chronological order by their scheduled_time.

        Converts each task's "HH:MM" string to minutes since midnight via
        _to_minutes(), then sorts ascending. Returns a new list; the original
        is not modified.

        Args:
            tasks: List of Task objects to sort.

        Returns:
            A new list of Tasks ordered from earliest to latest scheduled_time.

        Example:
            >>> scheduler.sort_by_time(tasks)
            # [Task at 07:00, Task at 08:00, Task at 14:00, ...]
        """
        return sorted(tasks, key=lambda t: self._to_minutes(t.scheduled_time))

    def sort_by_priority_then_time(self, tasks: List[Task]) -> List[Task]:
        """Sort tasks by priority (HIGH first) then by scheduled_time within each tier.

        Uses a composite key: (priority_order, minutes_since_midnight). HIGH-priority
        tasks always come before MEDIUM, which come before LOW. Within the same
        priority level, tasks are ordered earliest to latest.

        Args:
            tasks: List of Task objects to sort.

        Returns:
            A new list sorted by priority descending, then time ascending.

        Example:
            >>> scheduler.sort_by_priority_then_time(tasks)
            # [HIGH 07:00, HIGH 08:00, MEDIUM 07:00, MEDIUM 14:00, LOW 21:00]
        """
        return sorted(
            tasks,
            key=lambda t: (self.PRIORITY_ORDER[t.priority], self._to_minutes(t.scheduled_time))
        )

    def filter_tasks(self, tasks: List[Task], status: Optional[str] = None, pet_name: Optional[str] = None) -> List[Task]:
        """Filter a list of tasks by completion status and/or pet name.

        Both parameters are optional. When both are provided they combine with
        AND logic — only tasks matching both criteria are returned. Pet name
        matching is case-insensitive.

        Args:
            tasks: List of Task objects to filter.
            status: If provided, only include tasks with this status (e.g. "pending", "completed").
            pet_name: If provided, only include tasks belonging to this pet.

        Returns:
            A new filtered list of Tasks. Returns the original list unchanged if
            neither parameter is provided.

        Example:
            >>> scheduler.filter_tasks(tasks, status="pending", pet_name="Rex")
            # [Task(Morning Walk, pending, Rex), Task(Brush Teeth, pending, Rex)]
        """
        result = tasks
        if status is not None:
            result = [t for t in result if t.status == status]
        if pet_name is not None:
            result = [t for t in result if t.pet and t.pet.name.lower() == pet_name.lower()]
        return result

    def _to_minutes(self, time_str: str) -> int:
        """Convert 'HH:MM' to minutes since midnight."""
        h, m = time_str.split(":")
        return int(h) * 60 + int(m)

    def _overlaps(self, task_a: Task, task_b: Task) -> bool:
        """Return True if two tasks' time windows overlap on the same date."""
        if task_a.scheduled_date != task_b.scheduled_date:
            return False
        start_a = self._to_minutes(task_a.scheduled_time)
        end_a = start_a + task_a.duration_minutes
        start_b = self._to_minutes(task_b.scheduled_time)
        end_b = start_b + task_b.duration_minutes
        return start_a < end_b and start_b < end_a

    def detect_conflicts(self, tasks: List[Task]) -> List[dict]:
        """Detect scheduling conflicts where two tasks' time windows overlap.

        Compares every unique pair of tasks. Two tasks conflict when they share
        the same scheduled_date and their time ranges (scheduled_time through
        scheduled_time + duration_minutes) overlap. Each conflict is classified
        as "same_pet" (both tasks belong to one pet) or "cross_pet" (the owner
        is double-booked across two pets).

        Args:
            tasks: List of Task objects to check for conflicts.

        Returns:
            A list of dicts, each with keys:
                - "task_a" (Task): First task in the conflicting pair.
                - "task_b" (Task): Second task in the conflicting pair.
                - "type" (str): "same_pet" or "cross_pet".
            Returns an empty list if no conflicts are found.

        Example:
            >>> conflicts = scheduler.detect_conflicts(pending_tasks)
            >>> conflicts[0]
            {"task_a": <Morning Walk>, "task_b": <Training>, "type": "same_pet"}
        """
        conflicts = []
        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                if self._overlaps(tasks[i], tasks[j]):
                    conflict_type = (
                        "same_pet" if tasks[i].pet == tasks[j].pet else "cross_pet"
                    )
                    conflicts.append({
                        "task_a": tasks[i],
                        "task_b": tasks[j],
                        "type": conflict_type,
                    })
        return conflicts

    def detect_conflicts_warnings(self, tasks: List[Task]) -> List[str]:
        """Lightweight conflict check that returns human-readable warning strings.

        Wraps detect_conflicts() and formats each conflict as a plain English
        warning. Same-pet conflicts advise rescheduling; cross-pet conflicts
        remind the owner they can only attend one pet at a time. Never raises
        an exception — safe to call and print directly.

        Args:
            tasks: List of Task objects to check for conflicts.

        Returns:
            A list of warning strings. Empty list if no conflicts exist.

        Example:
            >>> scheduler.detect_conflicts_warnings(tasks)
            ["Warning: 'Morning Walk' (07:00) and 'Training' (07:00) overlap for Rex — consider rescheduling one."]
        """
        warnings = []
        conflicts = self.detect_conflicts(tasks)
        for c in conflicts:
            a, b = c["task_a"], c["task_b"]
            if c["type"] == "same_pet":
                warnings.append(
                    f"Warning: '{a.name}' ({a.scheduled_time}) and '{b.name}' ({b.scheduled_time}) "
                    f"overlap for {a.pet.name} — consider rescheduling one."
                )
            else:
                warnings.append(
                    f"Warning: '{a.name}' for {a.pet.name} ({a.scheduled_time}) and "
                    f"'{b.name}' for {b.pet.name} ({b.scheduled_time}) overlap — "
                    f"you can only attend one pet at a time."
                )
        return warnings

    def suggest_next_slot(self, task: Task, scheduled_tasks: List[Task],
                          day_start: str = "06:00", day_end: str = "22:00") -> Optional[str]:
        """Find the earliest available time slot for a task that avoids all conflicts.

        Scans the day from day_start to day_end, looking for the first gap between
        existing tasks that is large enough to fit the new task's duration. Considers
        all tasks on the same scheduled_date — both same-pet and cross-pet — since
        the owner can only attend one task at a time.

        Args:
            task: The Task to find a slot for (uses its duration_minutes and scheduled_date).
            scheduled_tasks: List of already-scheduled Tasks to avoid overlapping with.
            day_start: Earliest allowed start time ("HH:MM"). Defaults to "06:00".
            day_end: Latest allowed end time ("HH:MM"). Defaults to "22:00".

        Returns:
            A "HH:MM" string for the suggested start time, or None if no slot fits
            within the day window.

        Example:
            >>> scheduler.suggest_next_slot(training_task, existing_tasks)
            '07:30'  # first gap after existing 07:00-07:30 task
        """
        start_limit = self._to_minutes(day_start)
        end_limit = self._to_minutes(day_end)

        same_day = [t for t in scheduled_tasks
                    if t.scheduled_date == task.scheduled_date and t is not task]

        occupied = sorted(
            [(self._to_minutes(t.scheduled_time),
              self._to_minutes(t.scheduled_time) + t.duration_minutes)
             for t in same_day]
        )

        cursor = start_limit
        for occ_start, occ_end in occupied:
            if occ_start >= cursor + task.duration_minutes:
                break
            if occ_end > cursor:
                cursor = occ_end

        if cursor + task.duration_minutes <= end_limit:
            return f"{cursor // 60:02d}:{cursor % 60:02d}"
        return None

    def fits_in_budget(self, task: Task, time_remaining: int) -> bool:
        """Return True if the task's duration fits within the remaining time."""
        return task.duration_minutes <= time_remaining

    def get_skipped_tasks(self) -> List[Task]:
        """Return the list of tasks that were skipped due to time constraints."""
        return self.skipped_tasks
