from dataclasses import dataclass, field
from typing import List


@dataclass
class Pet:
    name: str
    species: str
    age: int
    special_needs: str

    def has_special_needs(self) -> bool:
        pass


@dataclass
class Task:
    name: str
    duration_minutes: int
    priority: str
    category: str
    notes: str
    status: str

    def is_high_priority(self) -> bool:
        pass

    def __repr__(self) -> str:
        pass


class Owner:
    def __init__(self, name: str, available_minutes: int):
        self.name = name
        self.available_minutes = available_minutes

    def add_task(self, task: Task) -> None:
        pass

    def remove_task(self, task: Task) -> None:
        pass


class Scheduler:
    def __init__(self, owner: Owner):
        self.owner = owner

    def generate_plan(self) -> None:
        pass

    def fits_in_budget(self, task: Task, time_remaining: int) -> bool:
        pass

    def get_skipped_tasks(self) -> List[Task]:
        pass
