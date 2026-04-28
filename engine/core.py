from collections import defaultdict
from .parser import parse_timetable
from .scheduler import generate_timetables
from .scorer import calculate_score


def normalize_selected_courses(selected_courses):
    return {str(course).strip() for course in selected_courses if str(course).strip()}


def group_sections_by_course(parsed_sections, selected_courses):
    grouped = defaultdict(list)

    for section in parsed_sections:
        course = section.get("course", "").strip()
        if course in selected_courses:
            grouped[course].append(section)

    return grouped


def find_missing_courses(selected_courses, grouped):
    return sorted(course for course in selected_courses if not grouped.get(course))


def run_generator(text, selected_courses, constraints, top_n=3, return_debug=False):
    parsed_sections, parser_warnings = parse_timetable(text, return_warnings=True)

    selected_courses = normalize_selected_courses(selected_courses)
    grouped = group_sections_by_course(parsed_sections, selected_courses)
    missing_courses = find_missing_courses(selected_courses, grouped)

    if missing_courses:
        response = {
            "results": [],
            "warnings": parser_warnings,
            "missing_courses": missing_courses,
        }
        return response if return_debug else []

    scheduler_limit = constraints.get("scheduler_limit")
    timetables, scheduler_stats = generate_timetables(
        grouped,
        limit=scheduler_limit,
        return_stats=True,
    )

    results = []
    for timetable in timetables:
        score, violations, breakdown, priority_penalties = calculate_score(
            timetable,
            days_off=constraints.get("days_off"),
            avoid_slots=constraints.get("avoid_slots"),
            faculty_pref=constraints.get("faculty_pref"),
            priority_order=constraints.get("priority_order"),
            return_breakdown=True,
        )

        results.append({
            "score": score,
            "violations": violations,
            "breakdown": breakdown,
            "priority_penalties": priority_penalties,
            "timetable": timetable,
        })

    priority_order = constraints.get("priority_order") or ["days_off", "faculty", "time_slots", "compactness"]
    ranked_results = sorted(
        results,
        key=lambda item: (
            tuple(item["priority_penalties"].get(category, 0) for category in priority_order),
            sum(item["breakdown"].values()),
            len(item["violations"]),
            -item["score"],
        ),
    )[:top_n]

    if return_debug:
        return {
            "results": ranked_results,
            "warnings": parser_warnings,
            "missing_courses": missing_courses,
            "scheduler_stats": scheduler_stats,
        }

    return ranked_results
