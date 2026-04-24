from pawpal_system import Owner, Pet, Task, Priority, Scheduler
from tabulate import tabulate

DATA_FILE = "data.json"

# ── ANSI color codes ──────────────────────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

# ── Helpers ───────────────────────────────────────────────────────────────────
PRIORITY_BADGE = {
    "high":   f"{RED}🔴 High{RESET}",
    "medium": f"{YELLOW}🟡 Medium{RESET}",
    "low":    f"{GREEN}🟢 Low{RESET}",
}

CATEGORY_EMOJI = {
    "exercise":   "🏃",
    "health":     "💊",
    "grooming":   "✂️ ",
    "nutrition":  "🍽️ ",
    "enrichment": "🎾",
    "general":    "📋",
}

STATUS_BADGE = {
    "pending":   f"{YELLOW}⏳ pending{RESET}",
    "completed": f"{GREEN}✅ done{RESET}",
}

SPECIES_EMOJI = {"dog": "🐶", "cat": "🐱", "other": "🐾"}

def priority_badge(p):   return PRIORITY_BADGE.get(p, p)
def category_emoji(c):   return CATEGORY_EMOJI.get(c, "📋")
def status_badge(s):     return STATUS_BADGE.get(s, s)
def species_emoji(sp):   return SPECIES_EMOJI.get(sp, "🐾")

def section(title):
    print(f"\n{BOLD}{CYAN}{'─' * 52}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 52}{RESET}")

# ── Setup: Load from file or create fresh ─────────────────────────────────────
owner = Owner.load_from_json(DATA_FILE)

if owner:
    print(f"{GREEN}✅ Loaded saved data from {DATA_FILE}{RESET}")
else:
    print(f"{YELLOW}⚠️  No saved data found — creating fresh demo data{RESET}")
    owner = Owner("Alex")

    dog = Pet("Rex", "dog", 3)
    cat = Pet("Luna", "cat", 5, special_needs="kidney diet")

    dog.add_task(Task("Flea Treatment",  15, Priority.MEDIUM, "health",    "Apply monthly drops",       scheduled_time="14:00", frequency="weekly"))
    dog.add_task(Task("Morning Walk",    30, Priority.HIGH,   "exercise",  "Go around the block twice", scheduled_time="07:00", frequency="daily"))
    dog.add_task(Task("Brush Teeth",      5, Priority.LOW,    "grooming",  "Use dog toothpaste",        scheduled_time="21:00", frequency="daily"))
    cat.add_task(Task("Playtime",        20, Priority.LOW,    "enrichment","Feather wand session",      scheduled_time="16:30", frequency="as needed"))
    cat.add_task(Task("Special Feeding", 10, Priority.HIGH,   "nutrition", "Kidney diet wet food only", scheduled_time="08:00", frequency="daily"))
    cat.add_task(Task("Grooming",        25, Priority.MEDIUM, "grooming",  "Brush coat and check ears", scheduled_time="11:00", frequency="weekly"))
    dog.add_task(Task("Training",        20, Priority.MEDIUM, "exercise",  "Practice sit and stay",     scheduled_time="07:00", frequency="daily"))
    cat.add_task(Task("Vet Call",        15, Priority.HIGH,   "health",    "Phone check-in with vet",   scheduled_time="07:00", frequency="as needed"))

    owner.add_pet(dog)
    owner.add_pet(cat)

# ── Run Scheduler ─────────────────────────────────────────────────────────────
scheduler = Scheduler(owner)
plan = scheduler.generate_plan()
all_tasks = owner.get_all_tasks()

# ── Daily Schedule ────────────────────────────────────────────────────────────
section("🐾 PAWPAL+ DAILY SCHEDULE")
print(f"  {BOLD}Owner :{RESET} {owner.name}")
print()

for pet in owner.pets:
    pet_tasks = [t for t in plan["scheduled"] if t.pet == pet]
    if not pet_tasks:
        continue
    print(f"  {BOLD}{species_emoji(pet.species)} {pet.name} ({pet.species}){RESET}")
    rows = [
        [category_emoji(t.category), t.scheduled_time, t.name, f"{t.duration_minutes} min", priority_badge(t.priority.value)]
        for t in pet_tasks
    ]
    print(tabulate(rows, headers=["", "Time", "Task", "Duration", "Priority"],
                   tablefmt="rounded_outline"))
    print()

time_used = sum(t.duration_minutes for t in plan["scheduled"])
print(f"\n  {BOLD}📊 Summary{RESET}")
summary = [
    ["✅ Scheduled", len(plan["scheduled"])],
    ["⏱️  Total Care Time",  f"{time_used} min"],
]
print(tabulate(summary, tablefmt="simple"))

# ── Sort by priority then time ─────────────────────────────────────────────────
section("📋 All Tasks — Priority then Time")
priority_sorted = scheduler.sort_by_priority_then_time(all_tasks)
rows = [
    [priority_badge(t.priority.value), t.scheduled_time,
     category_emoji(t.category), t.name, t.pet.name]
    for t in priority_sorted
]
print(tabulate(rows, headers=["Priority", "Time", "", "Task", "Pet"],
               tablefmt="rounded_outline"))

# ── Filter: Luna's tasks ───────────────────────────────────────────────────────
section("🔍 Filter — Luna's Tasks")
luna_tasks = scheduler.filter_tasks(all_tasks, pet_name="Luna")
rows = [
    [t.scheduled_time, category_emoji(t.category), t.name,
     f"{t.duration_minutes} min", status_badge(t.status)]
    for t in luna_tasks
]
print(tabulate(rows, headers=["Time", "", "Task", "Duration", "Status"],
               tablefmt="rounded_outline"))

# ── Filter: Rex's pending tasks sorted by time ────────────────────────────────
section("🔍 Filter — Rex's Pending Tasks (by time)")
rex_pending = scheduler.filter_tasks(all_tasks, status="pending", pet_name="Rex")
rows = [
    [t.scheduled_time, category_emoji(t.category), t.name,
     priority_badge(t.priority.value), t.frequency]
    for t in scheduler.sort_by_time(rex_pending)
]
print(tabulate(rows, headers=["Time", "", "Task", "Priority", "Frequency"],
               tablefmt="rounded_outline"))

# ── Conflict Detection ────────────────────────────────────────────────────────
section("⚠️  Conflict Detection")
pending_today = scheduler.filter_tasks(all_tasks, status="pending")
conflicts = scheduler.detect_conflicts(pending_today)
if conflicts:
    for c in conflicts:
        a, b = c["task_a"], c["task_b"]
        tag = f"{RED}same-pet{RESET}" if c["type"] == "same_pet" else f"{YELLOW}cross-pet{RESET}"
        print(f"  🚨 {tag} conflict")
        rows = [
            [a.pet.name, a.scheduled_time, f"{a.duration_minutes} min", a.name],
            [b.pet.name, b.scheduled_time, f"{b.duration_minutes} min", b.name],
        ]
        print(tabulate(rows, headers=["Pet", "Time", "Duration", "Task"],
                       tablefmt="rounded_outline"))
        print()
else:
    print(f"  {GREEN}✅ No conflicts found.{RESET}")

# ── Conflict Warnings ─────────────────────────────────────────────────────────
section("💬 Conflict Warnings")
warnings = scheduler.detect_conflicts_warnings(pending_today)
for w in warnings:
    print(f"  ⚠️  {w}")
if not warnings:
    print(f"  {GREEN}No warnings.{RESET}")

# ── Suggest Next Slot ─────────────────────────────────────────────────────────
section("🕐 Suggest Next Slot")
if conflicts:
    task_b = conflicts[0]["task_b"]
    slot = scheduler.suggest_next_slot(task_b, pending_today)
    print(f"  '{task_b.name}' ({task_b.duration_minutes} min) conflicts at {task_b.scheduled_time}")
    print(f"  {GREEN}→ Suggested slot: {slot}{RESET}")

big_task = Task("Deep Clean", 180, Priority.LOW, "grooming", "", scheduled_time="06:00")
slot2 = scheduler.suggest_next_slot(big_task, pending_today)
print(f"\n  'Deep Clean' (180 min) — next available slot:")
print(f"  {GREEN}→ {slot2 if slot2 else 'No slot available today'}{RESET}")

# ── Save ──────────────────────────────────────────────────────────────────────
owner.save_to_json(DATA_FILE)
section(f"💾 Saved to {DATA_FILE}")
