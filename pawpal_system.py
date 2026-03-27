from dataclasses import dataclass, field, replace
from typing import List, Optional
from enum import Enum
from datetime import date, timedelta


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Task:
    name: str
    duration_minutes: int
    priority: Priority
    category: str
    notes: str
    scheduled_time: str = "00:00"  # "HH:MM" format, e.g. "08:30"
    scheduled_date: str = ""       # "YYYY-MM-DD" format, defaults to today at runtime
    frequency: str = "daily"       # "daily", "weekly", or "as needed"
    status: str = "pending"
    pet: Optional["Pet"] = None

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

        frequency_delta = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
        delta = frequency_delta.get(self.frequency)
        if delta is None:
            return None

        next_date = date.fromisoformat(self.scheduled_date) + delta
        next_task = replace(self, scheduled_date=next_date.isoformat(), status="pending", pet=None)

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


class Scheduler:
    def __init__(self, owner: Owner):
        self.owner = owner
        self.scheduled_tasks: List[Task] = []
        self.skipped_tasks: List[Task] = []

    def generate_plan(self) -> dict:
        """
        Returns: {"scheduled": List[Task], "skipped": List[Task], "reasoning": List[str]}
        Schedules high-priority tasks first, fitting within the owner's available minutes.
        """
        self.scheduled_tasks = []
        self.skipped_tasks = []
        reasoning = []

        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        all_tasks = sorted(
            self.owner.get_all_tasks(),
            key=lambda t: priority_order[t.priority]
        )

        time_remaining = self.owner.available_minutes

        for task in all_tasks:
            if self.fits_in_budget(task, time_remaining):
                self.scheduled_tasks.append(task)
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

    def fits_in_budget(self, task: Task, time_remaining: int) -> bool:
        """Return True if the task's duration fits within the remaining time."""
        return task.duration_minutes <= time_remaining

    def get_skipped_tasks(self) -> List[Task]:
        """Return the list of tasks that were skipped due to time constraints."""
        return self.skipped_tasks
