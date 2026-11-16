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
import re
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

# Student groups longer than this or with a long run of digits are generated
# IDs, not names.
_MAX_GROUP_LENGTH = 24
_GENERATED_ID = re.compile(r"\d{6}")

# A course belongs to an elective block when at least this share of its
# lessons runs in parallel to another course. Substitutions and one-off events
# overlap a lesson now and then, an elective block every week.
PARALLEL_SHARE = 0.5

# Names that mark the block of an option, searched in subject and student group.
_MARKERS = {
    CONF_COURSE_WPI: re.compile(r"wp|wahlpflicht|elective", re.IGNORECASE),
    CONF_COURSE_TEAM_PROJECT: re.compile(
        r"team|projekt|project|(?<![a-z])tp(?![a-z])", re.IGNORECASE
    ),
}


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
    """Return the courses of elective blocks, grouped by block.

    Only lessons that take place as planned count: a cancelled lesson next to
    its substitute, or an irregular event, is no elective block. A course that
    is cancelled in all its lessons counts with those instead. A course
    belongs to a block when at least ``PARALLEL_SHARE`` of its lessons run in
    parallel to another course of the block, so a one-off overlap does not
    turn a regular subject into a choice.

    Each course is a dict with ``value`` (the course key), ``short``, ``name``,
    ``group``, ``teachers``, ``times`` (weekly ``(weekday, "HH:MM")`` slots)
    and ``block`` (blocks numbered by their first lesson). The courses of one
    block stay together, sorted by name.
    """
    lessons = list(lessons)
    keys = course_keys(lessons)
    # A course cancelled in every lesson of the fetched timetable (some schools
    # release only one week) has no lesson that takes place. Its cancelled
    # lessons count instead, so it keeps its place in the block.
    taking_place = {
        key
        for lesson, key in zip(lessons, keys, strict=True)
        if key is not None and _code(lesson) is None
    }
    regular = sorted(
        (
            (lesson, key)
            for lesson, key in zip(lessons, keys, strict=True)
            if key is not None
            and (
                _code(lesson) is None
                or (_code(lesson) == "cancelled" and key not in taking_place)
            )
        ),
        key=lambda item: (item[0].start, item[0].end),
    )

    occurrences: dict[str, int] = {}
    in_parallel: dict[str, set[int]] = {}
    links: dict[str, set[str]] = {}
    for index, (lesson, key) in enumerate(regular):
        occurrences[key] = occurrences.get(key, 0) + 1
        for other_index in range(index + 1, len(regular)):
            other, other_key = regular[other_index]
            if other.start >= lesson.end:
                break
            if other_key == key:
                continue
            in_parallel.setdefault(key, set()).add(index)
            in_parallel.setdefault(other_key, set()).add(other_index)
            links.setdefault(key, set()).add(other_key)
            links.setdefault(other_key, set()).add(key)

    elective = {
        key
        for key, found in in_parallel.items()
        if len(found) >= PARALLEL_SHARE * occurrences[key]
    }

    # Blocks: elective courses connected by running in parallel.
    block_of: dict[str, int] = {}
    blocks = 0
    for _, key in regular:
        if key not in elective or key in block_of:
            continue
        members = []
        stack = [key]
        while stack:
            current = stack.pop()
            if current in block_of:
                continue
            block_of[current] = blocks
            members.append(current)
            stack.extend(
                other
                for other in links.get(current, ())
                if other in elective and other not in block_of
            )
        if len(members) < 2:
            for member in members:
                del block_of[member]
            continue
        blocks += 1

    # Weekly times and teachers also from cancelled lessons, so a course that
    # is cancelled this week still shows its usual slots.
    courses: dict[str, dict[str, Any]] = {}
    planned = sorted(
        (
            (lesson, key)
            for lesson, key in zip(lessons, keys, strict=True)
            if key in block_of and _code(lesson) != "irregular"
        ),
        key=lambda item: (item[0].start, item[0].end),
    )
    for lesson, key in planned:
        course = courses.get(key)
        if course is None:
            subject = _primary_subject(lesson)
            short, name = subject if subject else (key, key)
            course = courses[key] = {
                "value": key,
                "short": short,
                "name": name,
                "group": _student_group(lesson),
                "teachers": set(),
                "times": set(),
                "block": block_of[key],
            }
        course["times"].add((lesson.start.weekday(), lesson.start.strftime("%H:%M")))
        course["teachers"].update(_teacher_names(lesson))

    result = []
    for course in courses.values():
        course["teachers"] = sorted(course["teachers"])
        course["times"] = sorted(course["times"])
        result.append(course)
    # Parallel groups of one subject (e.g. 16 team projects) by teacher.
    result.sort(
        key=lambda course: (course["block"], course["name"], course["teachers"])
    )
    return result


def courses_for_option(
    courses: Sequence[dict[str, Any]], option: str
) -> list[dict[str, Any]]:
    """Return the courses offered for one option (WPI or team project).

    A block is offered for an option when one of its courses carries the
    option's marker in its subject or student group ("WPI", "Wahlpflicht",
    "TP", "Teamprojekt", ...). Blocks without any marker are offered for an
    option that has no marked block; without any marker every block is offered.
    """

    def text(course: dict[str, Any]) -> str:
        return " ".join(
            (course.get("short", ""), course.get("name", ""), course.get("group", ""))
        )

    marked = {
        name: {course["block"] for course in courses if pattern.search(text(course))}
        for name, pattern in _MARKERS.items()
    }
    if marked.get(option):
        blocks = marked[option]
    else:
        taken = set().union(
            *(found for name, found in marked.items() if name != option)
        )
        blocks = {course["block"] for course in courses} - taken
    return [course for course in courses if course["block"] in blocks]


def course_label(course: dict[str, Any], language: str | None = None) -> str:
    """Return a dropdown label like ``Spanisch WPI – Hub · Mo 08:00, Do 09:50``."""
    weekdays = _WEEKDAYS.get((language or "en").split("-")[0], _WEEKDAYS["en"])
    label = course["name"]
    group = _readable_group(course.get("group") or "")
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
    group = _readable_group(rest.split(KEY_SEPARATOR)[0])
    return f"{subject} ({group})" if group else subject


def _readable_group(group: str) -> str:
    """Return the student group if it is a name, not an internal Untis ID.

    Some schools name groups like "WPI Spanisch 7", others leave generated IDs
    such as "SG20260123120354_525" or long class lists; those only clutter
    the label.
    """
    if len(group) > _MAX_GROUP_LENGTH or _GENERATED_ID.search(group):
        return ""
    return group
