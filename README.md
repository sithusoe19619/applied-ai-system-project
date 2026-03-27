# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Smarter Scheduling

Beyond the basic priority-based planner, PawPal+ includes four algorithmic features:

- **Sort by time** -- `Scheduler.sort_by_time()` orders tasks chronologically by their `"HH:MM"` scheduled time using a lambda key that converts to minutes since midnight.
- **Filter by pet/status** -- `Scheduler.filter_tasks()` narrows a task list by completion status, pet name, or both (AND logic, case-insensitive).
- **Recurring tasks** -- `Task.mark_complete()` automatically generates the next occurrence for daily (+1 day) and weekly (+7 day) tasks using `timedelta`, while "as needed" tasks simply complete with no follow-up.
- **Conflict detection** -- `Scheduler.detect_conflicts()` compares every task pair for time-window overlaps and classifies each as `same_pet` or `cross_pet`. A lightweight `detect_conflicts_warnings()` wrapper returns plain English warnings safe to print directly.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.
