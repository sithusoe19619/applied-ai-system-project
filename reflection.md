# PawPal+ Project Reflection

## 1. System Design
The three core actions a user should be able to perform in PawPal+ are:

1. **Enter owner and pet info** — The user provides basic context about themselves and their pet, including the owner's name, the pet's name and type, and how much time is available in the day. This information gives the scheduler the constraints it needs to build a realistic plan.

2. **Add and manage care tasks** — The user creates tasks representing pet care responsibilities (such as walks, feeding, medications, grooming, or enrichment). Each task includes at minimum a name, an estimated duration, and a priority level. Users can also edit or remove tasks as their pet's needs change.

3. **Generate and view a daily plan** — The user triggers the scheduler to produce a prioritized, constraint-aware daily schedule. The app displays the resulting plan clearly and explains the reasoning behind it — for example, why certain tasks were included, deferred, or ordered the way they were.

**a. Initial design**
The system is built around four core classes:

- **`Pet`** — A dataclass that holds information about the pet, including name, species, age, and any special needs (such as required medication). It is responsible for representing the pet's profile and exposing a `has_special_needs()` method that the scheduler can use to prioritize certain tasks.

- **`Task`** — A dataclass that represents a single pet care responsibility. It stores the task name, estimated duration in minutes, priority level (low/medium/high), category (e.g. walk, feeding, grooming), notes, and a status field to track whether it was scheduled or skipped. It provides `is_high_priority()` as a convenience method for scheduling logic.

- **`Owner`** — Holds the owner's name, their daily time budget (`available_minutes`), a reference to their `Pet`, and a list of `Task` objects. It is responsible for managing the task list through `add_task()` and `remove_task()`, making it the single source of truth for all scheduling inputs.

- **`Scheduler`** — Takes an `Owner` as its only input and accesses the pet and tasks through it. Responsible for generating a daily care plan via `generate_plan()`, checking whether a task fits within the remaining time budget via `fits_in_budget()`, and returning any tasks that couldn't be scheduled via `get_skipped_tasks()`.

**b. Design changes**
Yes, the design changed several times during the skeleton review phase. The most significant changes were:

- **Removed `Pet` from `Scheduler`** — The initial UML had `Scheduler` holding both `owner` and `pet` as separate attributes. Since `pet` is already accessible via `owner.pet`, this was redundant. Removing it made `Owner` the single entry point into the model, which is cleaner and avoids the two getting out of sync.

- **Added `Priority` enum** — The original design used a plain `str` for `Task.priority`. This was replaced with a `Priority` enum (`LOW`, `MEDIUM`, `HIGH`) to prevent invalid values like `"HIGH"` or `"urgent"` from silently breaking scheduling logic.

- **Added `Task.pet` reference** — Tasks initially had no link back to the `Pet` they belonged to. A `pet: Optional[Pet]` field was added so the scheduler can inspect pet-specific constraints (like `special_needs`) directly from a task. `Owner.add_task()` automatically sets this link when a task is added.

- **Added `status` default and `Scheduler` state** — `Task.status` originally had no default, requiring callers to always pass it. It now defaults to `"pending"`. Similarly, `Scheduler` was given `scheduled_tasks` and `skipped_tasks` lists so that `get_skipped_tasks()` has persistent state to return after `generate_plan()` runs.

- **Gave `generate_plan()` a defined return structure** — The method originally returned `None`. It now returns a `dict` with keys `"scheduled"`, `"skipped"`, and `"reasoning"` so the UI layer knows exactly what to expect.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

The scheduler uses a greedy algorithm — it sorts all tasks by priority (HIGH → MEDIUM → LOW) and schedules them one by one until the time budget runs out. Once a task is skipped because it doesn't fit, the algorithm moves on and never revisits that decision. This means it can leave time on the table: if a 25-minute MEDIUM task is skipped with 20 minutes remaining, a 10-minute LOW task that comes later in the list is also skipped, even though it would have fit.

The tradeoff is **simplicity and predictability over optimal time usage**. A more sophisticated approach (like a knapsack algorithm) could pack the schedule tighter, but it would be harder to explain to the user *why* a lower-priority task was chosen over a higher-priority one. For a pet owner glancing at their daily plan, "high-priority tasks go first" is an intuitive rule that builds trust in the output — even if it occasionally wastes a few minutes of available time.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
