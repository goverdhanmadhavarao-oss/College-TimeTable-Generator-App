import re
from .utils import DAYS

TIME_RANGE_PATTERN = re.compile(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})")
SECTION_PATTERN = re.compile(r"\b([A-Z]+\d*-[A-Z0-9]+)\b", re.IGNORECASE)
CREDITS_PATTERN = re.compile(r"\[(\d+)\s*Credits\]", re.IGNORECASE)

DAY_LOOKUP = {day.lower(): day for day in DAYS}
DAY_LINE_PATTERN = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s*:\s*(.+)$",
    re.IGNORECASE,
)


def normalize_space(text):
    return " ".join(text.strip().split())


def clean_faculty(name):
    name = re.sub(r"\(.*?\)", "", name)
    name = name.replace(".", " ")
    return normalize_space(name).upper()


def clean_course_name(name):
    return normalize_space(name)


def clean_slot(slot):
    return normalize_space(slot).upper()


def clean_day(day):
    return DAY_LOOKUP.get(day.strip().lower(), normalize_space(day))


def clean_time_string(time_str):
    blocks = []
    seen = set()

    for start, end in TIME_RANGE_PATTERN.findall(time_str):
        block = f"{start}-{end}"
        if block not in seen:
            seen.add(block)
            blocks.append(block)

    return blocks


def extract_section_info(line):
    slot_match = SECTION_PATTERN.search(line)
    if not slot_match:
        return None, ""

    slot = clean_slot(slot_match.group(1))

    remainder = line[slot_match.end():].strip(" -:\t")
    faculty = ""

    if remainder:
        parts = [part.strip() for part in remainder.split("-") if part.strip()]
        faculty_text = parts[-1] if parts else remainder
        faculty = clean_faculty(faculty_text)

    return slot, faculty


def extract_day_schedule(line):
    match = DAY_LINE_PATTERN.match(line)
    if not match:
        return None

    day = clean_day(match.group(1))
    time_str = match.group(2).strip()
    blocks = clean_time_string(time_str)

    if not blocks:
        return None

    return day, blocks


def is_course_boundary(line):
    return bool(CREDITS_PATTERN.search(line))


def extract_credits(line):
    match = CREDITS_PATTERN.search(line)
    if not match:
        return None
    return int(match.group(1))


def apply_course_credits(results, current_section, course_name, credits):
    if not course_name or credits is None:
        return

    for section in results:
        if section.get("course") == course_name:
            section["credits"] = credits

    if current_section and current_section.get("course") == course_name:
        current_section["credits"] = credits


def finalize_section(section, results, warnings):
    if not section:
        return

    if not section["course"]:
        warnings.append(f"Skipped section without course: {section}")
        return

    if not section["slot"]:
        warnings.append(f"Skipped section without slot: {section}")
        return

    if not section["schedule"]:
        warnings.append(f"Skipped section without schedule: {section['course']} / {section['slot']}")
        return

    deduped = []
    seen = set()
    for block in section["schedule"]:
        key = (block["day"], block["time"])
        if key not in seen:
            seen.add(key)
            deduped.append(block)

    section["schedule"] = deduped
    results.append(section)


def parse_timetable(text, return_warnings=False):
    lines = text.splitlines()

    results = []
    warnings = []

    current_course = None
    current_section = None
    waiting_for_course_name = False

    for raw_line in lines:
        line = normalize_space(raw_line)
        if not line:
            continue

        if is_course_boundary(line):
            credits = extract_credits(line)
            apply_course_credits(results, current_section, current_course, credits)
            finalize_section(current_section, results, warnings)
            current_section = None
            current_course = None
            waiting_for_course_name = False
            continue

        if line.lower() == "course overview":
            finalize_section(current_section, results, warnings)
            current_section = None
            waiting_for_course_name = True
            continue

        if waiting_for_course_name:
            current_course = clean_course_name(line)
            waiting_for_course_name = False
            continue

        if line.lower().startswith("date:"):
            continue

        day_info = extract_day_schedule(line)
        if day_info:
            if not current_section:
                warnings.append(f"Day schedule found without active section: {line}")
                continue

            day, blocks = day_info
            for block in blocks:
                current_section["schedule"].append({
                    "day": day,
                    "time": block,
                })
            continue

        slot, faculty = extract_section_info(line)
        if slot:
            finalize_section(current_section, results, warnings)

            if not current_course:
                warnings.append(f"Section found before course name: {line}")
                current_section = None
                continue

            current_section = {
                "course": current_course,
                "slot": slot,
                "faculty": faculty,
                "credits": None,
                "schedule": [],
            }
            continue

    finalize_section(current_section, results, warnings)

    if return_warnings:
        return results, warnings
    return results
