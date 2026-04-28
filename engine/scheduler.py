from .utils import normalize_day, normalize_time_range, parse_time_range


def preprocess_section(section):
    normalized_schedule = []
    day_map = {}

    for block in section.get("schedule", []):
        day = normalize_day(block["day"])
        time_range = normalize_time_range(block["time"])
        start, end = parse_time_range(time_range)

        normalized_block = {
            "day": day,
            "time": time_range,
            "start": start,
            "end": end,
        }
        normalized_schedule.append(normalized_block)
        day_map.setdefault(day, []).append(normalized_block)

    processed = dict(section)
    processed["schedule"] = normalized_schedule
    processed["_day_map"] = day_map
    return processed


def is_clash(section_a, section_b):
    days_a = section_a.get("_day_map", {})
    days_b = section_b.get("_day_map", {})

    common_days = set(days_a) & set(days_b)
    if not common_days:
        return False

    for day in common_days:
        for block_a in days_a[day]:
            for block_b in days_b[day]:
                if block_a["start"] < block_b["end"] and block_b["start"] < block_a["end"]:
                    return True

    return False


def can_add_section(section, current):
    return all(not is_clash(section, existing) for existing in current)


def get_ordered_courses(grouped):
    valid_courses = [course for course, sections in grouped.items() if sections]
    return sorted(valid_courses, key=lambda course: len(grouped[course]))


def get_ordered_sections(sections):
    def section_sort_key(section):
        day_count = len({block["day"] for block in section["schedule"]})
        block_count = len(section["schedule"])
        return (day_count, block_count, section.get("slot", ""))

    return sorted(sections, key=section_sort_key)


def generate_timetables(grouped, limit=None, return_stats=False):
    preprocessed = {
        course: [preprocess_section(section) for section in sections if section.get("schedule")]
        for course, sections in grouped.items()
    }

    if any(not sections for sections in preprocessed.values()):
        if return_stats:
            return [], {
                "branches_explored": 0,
                "clash_rejections": 0,
                "completed_timetables": 0,
            }
        return []

    courses = get_ordered_courses(preprocessed)
    results = []
    stats = {
        "branches_explored": 0,
        "clash_rejections": 0,
        "completed_timetables": 0,
    }

    def backtrack(index, current):
        if index == len(courses):
            results.append([strip_internal_fields(section) for section in current])
            stats["completed_timetables"] += 1
            return

        course = courses[index]
        for section in get_ordered_sections(preprocessed[course]):
            if limit is not None and len(results) >= limit:
                return

            stats["branches_explored"] += 1

            if can_add_section(section, current):
                current.append(section)
                backtrack(index + 1, current)
                current.pop()
            else:
                stats["clash_rejections"] += 1

    backtrack(0, [])

    if return_stats:
        return results, stats
    return results


def strip_internal_fields(section):
    cleaned = dict(section)
    cleaned.pop("_day_map", None)
    return cleaned
