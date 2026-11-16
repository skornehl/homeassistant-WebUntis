"""Course choice for elective blocks such as WPI (Wahlpflicht) or team projects.

Many schools publish an elective block as several lessons in the same time
slot, one per course, and put all of them into every student's timetable.
Untis does not say which of them the student really attends. Once the
student's course is chosen, every other course that runs in parallel to it
belongs to other students and is dropped from the calendar, the sensors and
the change detection.

Lessons are matched by a course key built from the short name of the lesson's
own subject and its student group. Both stay the same when Untis substitutes a
teacher or room or cancels the lesson, so a chosen course keeps matching. Two
parallel courses with the same subject and student group are told apart by
their lesson number.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Sequence
from typing import Any

CONF_COURSE_WPI = "course_wpi"
CONF_COURSE_TEAM_PROJECT = "course_team_project"

# One dropdown per elective block in which a student has exactly one course.
COURSE_OPTIONS = (CONF_COURSE_WPI, CONF_COURSE_TEAM_PROJECT)

# Stored when no course is chosen.
NO_COURSE = ""

KEY_SEPARATOR = "|"

_WEEKDAYS = {
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}

_MAX_TIMES_IN_LABEL = 4


def _primary_subject(lesson: Any) -> tuple[str, str] | None:
    """Return short and long name of the lesson's own subject.

    The REST fallback can append the subject of a parallel lesson, so the first
    subject of the JSON-RPC data wins over the order of ``lesson.subjects``.
    """
    try:
        subjects = list(lesson.subjects or [])
    except Exception:
        return None
    if not subjects:
        return None

    primary = subjects[0]
    raw = getattr(lesson, "_data", None)
    if isinstance(raw, dict):
        with contextlib.suppress(IndexError, KeyError, TypeError):
            first_id = raw["su"][0]["id"]
            primary = next(
                (s for s in subjects if getattr(s, "id", None) == first_id), primary
            )

    name = str(getattr(primary, "name", "") or "").strip()
    long_name = str(getattr(primary, "long_name", "") or "").strip()
    if not name and not long_name:
        return None
    return name or long_name, long_name or name


def _student_group(lesson: Any) -> str:
    with contextlib.suppress(Exception):
        return str(lesson.studentGroup or "").strip()
    return ""


def _lsnumber(lesson: Any) -> int | None:
    with contextlib.suppress(Exception):
        number = int(lesson.lsnumber)
        # python-webuntis returns -1 when the server sends no lesson number
        return number if number >= 0 else None
    return None


def _code(lesson: Any) -> str | None:
    with contextlib.suppress(Exception):
        return lesson.code
    return None


def _teacher_names(lesson: Any) -> set[str]:
    with contextlib.suppress(Exception):
        return {
            str(teacher.name)
            for teacher in lesson.teachers
            if getattr(teacher, "name", None) and str(teacher.name) != "---"
        }
    return set()


def _overlaps(first: Any, second: Any) -> bool:
    return first.start < second.end and second.start < first.end


def course_keys(lessons: Sequence[Any]) -> list[str | None]:
    """Return the course key of every lesson, in the same order.

    Lessons without a subject (events, notes) get ``None`` and are never part
    of a course choice.
    """
    bases: list[str | None] = []
    for lesson in lessons:
        subject = _primary_subject(lesson)
        bases.append(
            None
            if subject is None
            else f"{subject[0]}{KEY_SEPARATOR}{_student_group(lesson)}"
        )

    # A subject and student group that two lesson numbers share in one slot
    # needs the lesson number to tell the two courses apart.
    numbers: dict[tuple[Any, Any, str], set[int | None]] = {}
    for lesson, base in zip(lessons, bases, strict=True):
        if base is not None:
            numbers.setdefault((lesson.start, lesson.end, base), set()).add(
                _lsnumber(lesson)
            )
    ambiguous = {base for (_, _, base), found in numbers.items() if len(found) > 1}

    return [
        f"{base}{KEY_SEPARATOR}{_lsnumber(lesson)}" if base in ambiguous else base
        for lesson, base in zip(lessons, bases, strict=True)
    ]


def drop_parallel_courses(
    lessons: Iterable[Any],
    chosen: Iterable[str],
    known_alternatives: set[str] | None = None,
) -> tuple[list[Any], set[str]]:
    """Drop the lessons of courses that run in parallel to a chosen course.

    A lesson is dropped when it overlaps a lesson of a chosen course and its
    course regularly runs at the same time (any code except ``irregular``).
    An irregular lesson of a new course in that slot, e.g. "Math instead of
    Spanish", is kept because it may be the student's substitute lesson.

    ``known_alternatives`` are courses found in parallel in earlier fetches, so
    an irregular lesson of another student's course is dropped as well.

    Returns the remaining lessons and the courses found in parallel this time.
    """
    lessons = list(lessons)
    chosen_keys = {key for key in chosen if key}
    if not chosen_keys or not lessons:
        return lessons, set()

    keys = course_keys(lessons)
    own = [
        lesson for lesson, key in zip(lessons, keys, strict=True) if key in chosen_keys
    ]
    if not own:
        return lessons, set()

    parallel = [
        index
        for index, (lesson, key) in enumerate(zip(lessons, keys, strict=True))
        if key is not None
        and key not in chosen_keys
        and any(_overlaps(lesson, other) for other in own)
    ]
    found = {keys[index] for index in parallel if _code(lessons[index]) != "irregular"}
    alternatives = found | (known_alternatives or set())
    drop = {index for index in parallel if keys[index] in alternatives}

    remaining = [lesson for index, lesson in enumerate(lessons) if index not in drop]
    return remaining, {key for key in found if key is not None}


def parallel_courses(lessons: Iterable[Any]) -> list[dict[str, Any]]:
    """Return every course that runs in parallel to another course.

    Each course is a dict with ``value`` (the course key), ``name``, ``group``,
    ``teachers`` and ``times`` (weekly ``(weekday, "HH:MM")`` slots). Courses
    are sorted by their first weekly slot, so the courses of one elective block
    stay together in a dropdown.
    """
    lessons = list(lessons)
    keys = course_keys(lessons)
    regular = sorted(
        (
            (lesson, key)
            for lesson, key in zip(lessons, keys, strict=True)
            if key is not None and _code(lesson) != "irregular"
        ),
        key=lambda item: (item[0].start, item[0].end),
    )

    parallel_keys: set[str] = set()
    for index, (lesson, key) in enumerate(regular):
        for other, other_key in regular[index + 1 :]:
            if other.start >= lesson.end:
                break
            if other_key != key:
                parallel_keys.update((key, other_key))

    courses: dict[str, dict[str, Any]] = {}
    for lesson, key in regular:
        if key not in parallel_keys:
            continue
        course = courses.get(key)
        if course is None:
            subject = _primary_subject(lesson)
            course = courses[key] = {
                "value": key,
                "name": subject[1] if subject else key,
                "group": _student_group(lesson),
                "teachers": set(),
                "times": set(),
            }
        course["times"].add((lesson.start.weekday(), lesson.start.strftime("%H:%M")))
        if _code(lesson) is None:
            course["teachers"].update(_teacher_names(lesson))

    result = []
    for course in courses.values():
        course["teachers"] = sorted(course["teachers"])
        course["times"] = sorted(course["times"])
        result.append(course)
    result.sort(key=lambda course: (course["times"][:1], course["name"]))
    return result


def course_label(course: dict[str, Any], language: str | None = None) -> str:
    """Return a dropdown label like ``Spanisch WPI – Hub · Mo 08:00, Do 09:50``."""
    weekdays = _WEEKDAYS.get((language or "en").split("-")[0], _WEEKDAYS["en"])
    label = course["name"]
    group = course.get("group")
    if group and group.lower() not in label.lower():
        label += f" ({group})"
    if course.get("teachers"):
        label += " – " + ", ".join(course["teachers"])
    times = course.get("times") or []
    if times:
        shown = [f"{weekdays[day]} {time}" for day, time in times[:_MAX_TIMES_IN_LABEL]]
        if len(times) > _MAX_TIMES_IN_LABEL:
            shown.append("…")
        label += " · " + ", ".join(shown)
    return label


def key_label(key: str) -> str:
    """Return a readable label for a stored key that is not in the timetable."""
    subject, _, rest = key.partition(KEY_SEPARATOR)
    group = rest.split(KEY_SEPARATOR)[0]
    return f"{subject} ({group})" if group else subject
