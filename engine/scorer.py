from collections import defaultdict
from .utils import normalize_day, normalize_time_range, parse_time_range, ranges_overlap

CATEGORY_WEIGHTS = {
    1: 9,
    2: 6,
    3: 3,
    4: 1,
}

DEFAULT_CATEGORY_ORDER = ["days_off", "faculty", "time_slots", "compactness"]


def normalize_faculty(name):
    return " ".join(str(name).replace(".", " ").strip().split()).upper()


def get_category_weights(priority_order):
    order = priority_order or DEFAULT_CATEGORY_ORDER
    weights = {}

    for index, category in enumerate(order, start=1):
        weights[category] = CATEGORY_WEIGHTS.get(index, 1)

    for category in DEFAULT_CATEGORY_ORDER:
        weights.setdefault(category, 1)

    return weights


def normalize_faculty_preferences(faculty_pref):
    normalized = {}

    for course, preferred in (faculty_pref or {}).items():
        if isinstance(preferred, str):
            preferred = [preferred]

        normalized[course] = {normalize_faculty(name) for name in preferred}

    return normalized


def build_day_map(timetable):
    day_map = defaultdict(list)

    for section in timetable:
        for block in section.get("schedule", []):
            day = normalize_day(block["day"])
            time_range = normalize_time_range(block["time"])
            day_map[day].append(time_range)

    return day_map


def score_days_off(day_map, days_off, weight):
    penalty = 0
    violations = []

    for day in days_off or []:
        normalized_day = normalize_day(day)
        count = len(day_map.get(normalized_day, []))

        if count > 0:
            penalty += count * weight
            violations.append(f"{normalized_day}: {count} class block(s) scheduled")

    return penalty, violations


def score_faculty_preferences(timetable, faculty_pref, weight):
    penalty = 0
    violations = []

    for section in timetable:
        course = section.get("course", "")
        faculty = normalize_faculty(section.get("faculty", ""))
        preferred = faculty_pref.get(course, set())

        if preferred and faculty not in preferred:
            penalty += weight
            violations.append(
                f"{course}: assigned faculty '{faculty}' is not preferred"
            )

    return penalty, violations


def score_avoid_slots(timetable, avoid_slots, weight):
    penalty = 0
    violations_map = defaultdict(int)

    normalized_slots = [normalize_time_range(slot) for slot in (avoid_slots or [])]

    for section in timetable:
        for block in section.get("schedule", []):
            day = normalize_day(block["day"])
            time_range = normalize_time_range(block["time"])

            for avoided in normalized_slots:
                if ranges_overlap(time_range, avoided):
                    penalty += weight
                    violations_map[(day, avoided)] += 1

    violations = [
        f"{day}: avoided slot {slot} overlapped by {count} class block(s)"
        for (day, slot), count in sorted(violations_map.items())
    ]

    return penalty, violations


def score_compactness(day_map, weight):
    penalty = 0
    violations = []

    for day, blocks in day_map.items():
        if len(blocks) < 2:
            continue

        converted = sorted(parse_time_range(block) for block in blocks)

        first_start = converted[0][0]
        last_end = converted[-1][1]
        active_minutes = sum(end - start for start, end in converted)
        total_span = last_end - first_start
        idle_minutes = total_span - active_minutes

        if idle_minutes > 120:
            extra_idle_hours = ((idle_minutes - 120 - 1) // 60) + 1
            penalty += extra_idle_hours * weight
            violations.append(f"{day}: spread-out schedule with {idle_minutes} idle minute(s)")

    return penalty, violations


def calculate_score(
    timetable,
    days_off=None,
    avoid_slots=None,
    faculty_pref=None,
    priority_order=None,
    return_breakdown=False,
):
    priority_order = priority_order or DEFAULT_CATEGORY_ORDER
    weights = get_category_weights(priority_order)
    normalized_faculty_pref = normalize_faculty_preferences(faculty_pref)
    day_map = build_day_map(timetable)

    breakdown = {}
    violations = []

    days_penalty, days_violations = score_days_off(
        day_map,
        days_off,
        weights["days_off"],
    )
    breakdown["days_off"] = days_penalty
    violations.extend(days_violations)

    faculty_penalty, faculty_violations = score_faculty_preferences(
        timetable,
        normalized_faculty_pref,
        weights["faculty"],
    )
    breakdown["faculty"] = faculty_penalty
    violations.extend(faculty_violations)

    slot_penalty, slot_violations = score_avoid_slots(
        timetable,
        avoid_slots,
        weights["time_slots"],
    )
    breakdown["time_slots"] = slot_penalty
    violations.extend(slot_violations)

    compactness_penalty, compactness_violations = score_compactness(
        day_map,
        weights["compactness"],
    )
    breakdown["compactness"] = compactness_penalty
    violations.extend(compactness_violations)

    total_penalty = sum(breakdown.values())
    score = max(0, 100 - total_penalty)
    priority_penalties = {category: breakdown.get(category, 0) for category in priority_order}

    if return_breakdown:
        return score, violations, breakdown, priority_penalties

    return score, violations
