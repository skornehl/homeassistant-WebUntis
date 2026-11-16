"""Unit tests for the course choice of elective blocks."""

from __future__ import annotations

from custom_components.webuntis.utils.course_choice import (
    course_keys,
    course_label,
    drop_parallel_courses,
    key_label,
    parallel_courses,
)

from .conftest import Element
from .timetable import (
    GERMAN,
    MATH,
    SPANISH,
    SPANISH_KEY,
    SPORT,
    SPORT_WPI,
    SPORT_WPI_KEY,
    TEAM_ROBOTICS_KEY,
    TEAM_THEATRE_KEY,
    WPI_PERIODS,
    week,
)


def names(lessons):
    return sorted({lesson.subjects[0].long_name for lesson in lessons})


def test_keys_use_subject_and_student_group() -> None:
    lessons = week()
    keys = dict(zip((id(lesson) for lesson in lessons), course_keys(lessons)))
    spanish = next(lesson for lesson in lessons if lesson.subjects == [SPANISH])
    assert keys[id(spanish)] == SPANISH_KEY

    grouped = spanish.but(studentGroup="WPI Spanisch 8")
    assert course_keys([grouped]) == ["SpaWP|WPI Spanisch 8"]


def test_same_subject_in_parallel_is_told_apart_by_lesson_number() -> None:
    keys = set(course_keys(week()))
    assert {TEAM_ROBOTICS_KEY, TEAM_THEATRE_KEY} <= keys
    assert "TP|" not in keys


def test_key_ignores_teacher_room_and_code() -> None:
    lesson = week()[0]
    substituted = lesson.but(
        teachers=[Element("---")], rooms=[Element("R99")], code="cancelled"
    )
    assert course_keys([lesson]) == course_keys([substituted])


def test_key_uses_the_lessons_own_subject_first() -> None:
    """The REST fallback can append the subject of a parallel lesson."""
    lesson = week()[0].but(subjects=[SPORT_WPI, SPANISH])
    lesson._data = {"su": [{"id": SPANISH.id}, {"id": SPORT_WPI.id}]}
    assert course_keys([lesson]) == [SPANISH_KEY]


def test_lesson_without_subject_has_no_key() -> None:
    event = week()[0].but(subjects=[], lstext="Wandertag")
    assert course_keys([event]) == [None]


def test_nothing_is_dropped_without_a_choice() -> None:
    lessons = week()
    assert drop_parallel_courses(lessons, []) == (lessons, set())
    assert drop_parallel_courses(lessons, [""]) == (lessons, set())


def test_parallel_courses_of_the_chosen_one_are_dropped() -> None:
    remaining, found = drop_parallel_courses(week(), [SPANISH_KEY])

    assert "Sport Wahlpflicht" not in names(remaining)
    assert "Informatik Wahlpflicht" not in names(remaining)
    assert {"Spanisch Wahlpflicht", "Sport", "Deutsch", "Teamprojekt"} <= set(
        names(remaining)
    )
    assert found == {SPORT_WPI_KEY, "InfWP|"}


def test_regular_lesson_with_the_same_key_elsewhere_stays() -> None:
    """WPI Sport and the class's Sport share subject and group."""
    lessons = [
        lesson.but(subjects=[SPORT]) if lesson.subjects == [SPORT_WPI] else lesson
        for lesson in week()
    ]
    remaining, _ = drop_parallel_courses(lessons, [SPANISH_KEY])

    sport = [lesson for lesson in remaining if lesson.subjects == [SPORT]]
    assert [lesson.start.hour for lesson in sport] == [11]


def test_irregular_new_course_in_the_slot_stays() -> None:
    start, end = WPI_PERIODS[0]
    math = week()[0].but(
        start=start, end=end, subjects=[MATH], lsnumber=99, code="irregular"
    )
    remaining, found = drop_parallel_courses([*week(), math], [SPANISH_KEY])

    assert math in remaining
    assert "Ma|" not in found


def test_irregular_lesson_of_a_known_other_course_is_dropped() -> None:
    """E.g. today's timetable, with Sport WPI moved and marked irregular."""
    start, _ = WPI_PERIODS[0]
    spanish = [
        lesson
        for lesson in week()
        if lesson.start == start and lesson.subjects == [SPANISH]
    ]
    moved = week()[1].but(code="irregular")
    assert moved.subjects == [SPORT_WPI]
    assert moved.start == start
    lessons = spanish

    remaining, _ = drop_parallel_courses([*lessons, moved], [SPANISH_KEY])
    assert moved in remaining

    remaining, _ = drop_parallel_courses(
        [*lessons, moved], [SPANISH_KEY], known_alternatives={SPORT_WPI_KEY}
    )
    assert moved not in remaining


def test_choice_missing_from_the_timetable_drops_nothing() -> None:
    lessons = week()
    remaining, found = drop_parallel_courses(lessons, ["Gone|"])
    assert remaining == lessons
    assert found == set()


def test_parallel_courses_offers_only_elective_courses() -> None:
    courses = parallel_courses(week())

    assert [course["value"] for course in courses] == [
        "InfWP|",
        SPANISH_KEY,
        SPORT_WPI_KEY,
        TEAM_ROBOTICS_KEY,
        TEAM_THEATRE_KEY,
    ]
    spanish = courses[1]
    assert spanish["name"] == "Spanisch Wahlpflicht"
    assert spanish["teachers"] == ["Hub"]
    assert spanish["times"] == [(0, "08:00"), (0, "08:45")]
    assert GERMAN.long_name not in {course["name"] for course in courses}


def test_parallel_courses_ignore_substitute_teachers() -> None:
    lessons = [
        lesson.but(teachers=[Element("Ver")], code="irregular")
        if lesson.subjects == [SPANISH] and lesson.start.minute == 45
        else lesson
        for lesson in week()
    ]
    spanish = next(c for c in parallel_courses(lessons) if c["value"] == SPANISH_KEY)
    assert spanish["teachers"] == ["Hub"]


def test_course_label() -> None:
    spanish = next(c for c in parallel_courses(week()) if c["value"] == SPANISH_KEY)

    assert (
        course_label(spanish, "de") == "Spanisch Wahlpflicht – Hub · Mo 08:00, Mo 08:45"
    )
    assert course_label(spanish, "en-GB").endswith("· Mon 08:00, Mon 08:45")
    assert course_label({**spanish, "group": "WPI 8"}, "de").startswith(
        "Spanisch Wahlpflicht (WPI 8) – Hub"
    )


def test_key_label() -> None:
    assert key_label(SPANISH_KEY) == "SpaWP"
    assert key_label("SpaWP|WPI 8") == "SpaWP (WPI 8)"
    assert key_label(TEAM_ROBOTICS_KEY) == "TP"
