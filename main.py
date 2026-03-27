from pawpal_system import Owner, Pet, Task, Priority, Scheduler


# --- Setup ---
owner = Owner("Alex", available_minutes=90)

dog = Pet("Rex", "dog", 3)
cat = Pet("Luna", "cat", 5, special_needs="kidney diet")

# Tasks added deliberately OUT OF chronological order, with mixed frequencies
dog.add_task(Task("Flea Treatment",  15, Priority.MEDIUM, "health",    "Apply monthly drops",        scheduled_time="14:00", frequency="weekly"))
dog.add_task(Task("Morning Walk",    30, Priority.HIGH,   "exercise",  "Go around the block twice",  scheduled_time="07:00", frequency="daily"))
dog.add_task(Task("Brush Teeth",      5, Priority.LOW,    "grooming",  "Use dog toothpaste",         scheduled_time="21:00", frequency="daily"))
cat.add_task(Task("Playtime",        20, Priority.LOW,    "enrichment","Feather wand session",       scheduled_time="16:30", frequency="as needed"))
cat.add_task(Task("Special Feeding", 10, Priority.HIGH,   "nutrition", "Kidney diet wet food only",  scheduled_time="08:00", frequency="daily"))
cat.add_task(Task("Grooming",        25, Priority.MEDIUM, "grooming",  "Brush coat and check ears",  scheduled_time="11:00", frequency="weekly"))

# Deliberate conflicts for testing
dog.add_task(Task("Training",       20, Priority.MEDIUM, "exercise",  "Practice sit and stay",      scheduled_time="07:00", frequency="daily"))   # SAME time as Rex's Morning Walk (same_pet)
cat.add_task(Task("Vet Call",       15, Priority.HIGH,   "health",    "Phone check-in with vet",    scheduled_time="07:00", frequency="as needed"))  # SAME time as Rex's Morning Walk (cross_pet)

owner.add_pet(dog)
owner.add_pet(cat)

# Mark tasks completed to test recurring logic
# Flea Treatment is weekly  -> should create next occurrence 7 days out
# Brush Teeth is daily      -> should create next occurrence 1 day out
# Playtime is "as needed"   -> should NOT create a next occurrence
# NOTE: Morning Walk left pending so it conflicts with Training at 07:00 (same_pet test)
flea_next = dog.tasks[0].mark_complete()   # Flea Treatment (weekly)
brush_next = dog.tasks[2].mark_complete()  # Brush Teeth (daily)
play_next = cat.tasks[0].mark_complete()   # Playtime (as needed)

# --- Run Scheduler ---
scheduler = Scheduler(owner)
plan = scheduler.generate_plan()

# === Print Today's Schedule ===
print("=" * 50)
print("           PAWPAL+ DAILY SCHEDULE")
print("=" * 50)
print(f"Owner  : {owner.name}")
print(f"Budget : {owner.available_minutes} min")

# Group scheduled tasks by pet
for pet in owner.pets:
    pet_tasks = [t for t in plan["scheduled"] if t.pet == pet]
    if not pet_tasks:
        continue
    print(f"\n--- {pet.name} ({pet.species}) ---")
    for task in pet_tasks:
        print(f"  [{task.priority.value.upper():<6}] {task.name:<20} {task.duration_minutes} min")

# Skipped tasks (if any)
if plan["skipped"]:
    print("\n--- Skipped ---")
    for task in plan["skipped"]:
        print(f"  [{task.priority.value.upper():<6}] {task.name:<20} {task.duration_minutes} min  ({task.pet.name})")

# Summary footer
time_used = sum(t.duration_minutes for t in plan["scheduled"])
print("\n" + "." * 50)
print(f"  {'Scheduled':<10}: {len(plan['scheduled'])} tasks")
print(f"  {'Time Used':<10}: {time_used} / {owner.available_minutes} min")
print(f"  {'Remaining':<10}: {owner.available_minutes - time_used} min")
print("=" * 50)

# === Test: sort_by_time ===
all_tasks = owner.get_all_tasks()
print("\n" + "=" * 50)
print("  TEST: sort_by_time (all tasks, chronological)")
print("=" * 50)
sorted_tasks = scheduler.sort_by_time(all_tasks)
for t in sorted_tasks:
    print(f"  {t.scheduled_time}  {t.name:<20} ({t.pet.name})")

# === Test: filter_tasks by pet name ===
print("\n" + "=" * 50)
print("  TEST: filter_tasks (pet_name='Luna')")
print("=" * 50)
luna_tasks = scheduler.filter_tasks(all_tasks, pet_name="Luna")
for t in luna_tasks:
    print(f"  {t.scheduled_time}  {t.name:<20} [{t.status}]")

# === Test: filter_tasks by status ===
print("\n" + "=" * 50)
print("  TEST: filter_tasks (status='pending')")
print("=" * 50)
pending_tasks = scheduler.filter_tasks(all_tasks, status="pending")
for t in pending_tasks:
    print(f"  {t.scheduled_time}  {t.name:<20} ({t.pet.name})")

# === Test: filter + sort combined ===
print("\n" + "=" * 50)
print("  TEST: Rex's pending tasks, sorted by time")
print("=" * 50)
rex_pending = scheduler.filter_tasks(all_tasks, status="pending", pet_name="Rex")
rex_pending_sorted = scheduler.sort_by_time(rex_pending)
for t in rex_pending_sorted:
    print(f"  {t.scheduled_time}  {t.name:<20} [{t.priority.value}]")

# === Test: Recurring Tasks ===
print("\n" + "=" * 50)
print("  TEST: Recurring task auto-creation")
print("=" * 50)
print(f"  Flea Treatment (weekly)  -> next: {flea_next.scheduled_date if flea_next else 'None'}")
print(f"  Brush Teeth    (daily)   -> next: {brush_next.scheduled_date if brush_next else 'None'}")
print(f"  Playtime       (as needed)-> next: {play_next}")
print()
print(f"  Rex now has {len(dog.tasks)} tasks (was 3, +2 recurring copies):")
for t in dog.tasks:
    print(f"    {t.scheduled_date}  {t.name:<20} [{t.status}] ({t.frequency})")
print()
print(f"  Luna now has {len(cat.tasks)} tasks (was 3, +0 from 'as needed'):")
for t in cat.tasks:
    print(f"    {t.scheduled_date}  {t.name:<20} [{t.status}] ({t.frequency})")

# === Test: Conflict Detection ===
print("\n" + "=" * 50)
print("  TEST: detect_conflicts")
print("=" * 50)
all_tasks = owner.get_all_tasks()
pending_today = scheduler.filter_tasks(all_tasks, status="pending")
conflicts = scheduler.detect_conflicts(pending_today)
if conflicts:
    for c in conflicts:
        a, b = c["task_a"], c["task_b"]
        print(f"  CONFLICT ({c['type']}):")
        print(f"    {a.name:<20} ({a.pet.name})  {a.scheduled_time} - {a.duration_minutes} min")
        print(f"    {b.name:<20} ({b.pet.name})  {b.scheduled_time} - {b.duration_minutes} min")
        print()
else:
    print("  No conflicts found.")

# === Test: Lightweight Conflict Warnings ===
print("\n" + "=" * 50)
print("  TEST: detect_conflicts_warnings")
print("=" * 50)
warnings = scheduler.detect_conflicts_warnings(pending_today)
if warnings:
    for w in warnings:
        print(f"  {w}")
else:
    print("  No warnings.")
