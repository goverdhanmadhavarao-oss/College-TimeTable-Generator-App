DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

DAY_LOOKUP = {day.lower(): day for day in DAYS}


def normalize_space(text):
    return " ".join(str(text).strip().split())


def normalize_day(day):
    day = normalize_space(day).lower()
    if day not in DAY_LOOKUP:
        raise ValueError(f"Invalid day: {day}")
    return DAY_LOOKUP[day]


def time_to_minutes(value):
    value = normalize_space(value)
    hour, minute = map(int, value.split(":"))

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time value: {value}")

    return hour * 60 + minute


def minutes_to_time(minutes):
    if minutes < 0:
        raise ValueError(f"Invalid minute value: {minutes}")
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_time_range(time_range):
    cleaned = str(time_range).replace(" ", "")
    start_text, end_text = cleaned.split("-")

    start = time_to_minutes(start_text)
    end = time_to_minutes(end_text)

    if start >= end:
        raise ValueError(f"Invalid time range: {time_range}")

    return start, end


def normalize_time_range(time_range):
    start, end = parse_time_range(time_range)
    return f"{minutes_to_time(start)}-{minutes_to_time(end)}"


def ranges_overlap(first, second):
    first_start, first_end = parse_time_range(first)
    second_start, second_end = parse_time_range(second)
    return first_start < second_end and second_start < first_end
