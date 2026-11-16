"""Unit tests for the course choice of elective blocks."""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.webuntis.utils.course_choice import (
    CONF_COURSE_TEAM_PROJECT,
    CONF_COURSE_WPI,
    course_keys,
    course_label,
    courses_for_option,
    drop_parallel_courses,
    key_label,
    parallel_courses,
)

from .conftest import Element, Lesson
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


class BrokenLesson:
    """A lesson whose master data the server does not hand out.

    python-webuntis raises when a lesson refers to a subject, teacher or room
    the account may not read ("no right for getTeachers()").
    """

    def __init__(self, lesson):
        self._lesson = lesson

    def __getattr__(self, name):
        if name in ("start", "end"):
            return getattr(self._lesson, name)
        raise KeyError(name)


def test_unreadable_lesson_is_never_part_of_a_choice() -> None:
    broken = BrokenLesson(week()[0])

    assert course_keys([broken]) == [None]
    remaining, _ = drop_parallel_courses([*week(), broken], [SPANISH_KEY])
    assert broken in remaining
    assert parallel_courses([broken]) == []


def test_unreadable_details_do_not_break_the_course() -> None:
    class NoTeachers:
        def __init__(self, lesson):
            self.__dict__.update(vars(lesson))

        @property
        def teachers(self):
            raise KeyError("te")

        @property
        def studentGroup(self):
            raise KeyError("sg")

    lessons = [NoTeachers(lesson) for lesson in week()]
    spanish = next(c for c in parallel_courses(lessons) if c["value"] == SPANISH_KEY)
    assert spanish["teachers"] == []
    assert spanish["group"] == ""


def test_missing_lesson_number_and_code() -> None:
    class Bare:
        def __init__(self, lesson):
            self.__dict__.update(vars(lesson))

        @property
        def lsnumber(self):
            raise KeyError("lsnumber")

        @property
        def code(self):
            raise KeyError("code")

    team = [Bare(lesson) for lesson in week() if lesson.subjects[0].name == "TP"]
    # Without lesson numbers the two team projects cannot be told apart.
    assert set(course_keys(team)) == {"TP|"}
    assert {course["value"] for course in parallel_courses(team)} == set()
    # A lesson number of -1 means "none sent".
    assert course_keys([week()[0].but(lsnumber=-1)]) == [SPANISH_KEY]


def test_subject_without_names_has_no_key() -> None:
    nameless = week()[0].but(subjects=[Element("", "", 999)])
    assert course_keys([nameless]) == [None]


def test_long_label_is_shortened() -> None:
    course = {
        "name": "Sport Wahlpflicht",
        "group": "",
        "teachers": [],
        "times": [(day, "08:00") for day in range(5)],
    }
    assert course_label(course, "de") == (
        "Sport Wahlpflicht · Mo 08:00, Di 08:00, Mi 08:00, Do 08:00, …"
    )


def weekly(subject, lsnumber, weekday, start, end, weeks=4, **changes):
    """Return one lesson per week, like a regular timetable entry."""
    first = MONDAY_8 + timedelta(days=weekday)
    begin = first.replace(hour=int(start[:2]), minute=int(start[3:]))
    finish = first.replace(hour=int(end[:2]), minute=int(end[3:]))
    return [
        Lesson(
            start=begin + timedelta(weeks=week),
            end=finish + timedelta(weeks=week),
            subjects=[subject],
            lsnumber=lsnumber,
            id=lsnumber * 100 + week,
            **changes,
        )
        for week in range(weeks)
    ]


MONDAY_8 = datetime(2026, 11, 16)
ART = Element("Ku", "Kunst", 40)
MUSIC = Element("Mu", "Musik", 41)
CLASS_COUNCIL = Element("KR", "Klassenrat", 42)


def test_cancelled_lesson_next_to_its_substitute_is_no_block() -> None:
    art = weekly(ART, 40, 1, "10:00", "10:45")
    art[1] = art[1].but(code="cancelled")
    council = art[1].but(subjects=[CLASS_COUNCIL], lsnumber=42, id=1, code=None)

    assert parallel_courses([*art, council]) == []


def test_one_off_overlap_is_no_block() -> None:
    """Class council once during art: no choice between them."""
    art = weekly(ART, 40, 1, "10:00", "10:45")
    council = art[2].but(subjects=[CLASS_COUNCIL], lsnumber=42, id=1)

    assert parallel_courses([*art, council]) == []


def test_weekly_split_is_its_own_block() -> None:
    lessons = [
        *week(),
        *weekly(ART, 40, 1, "10:00", "10:45", weeks=1),
        *weekly(MUSIC, 41, 1, "10:00", "10:45", weeks=1),
    ]
    courses = parallel_courses(lessons)

    blocks = {}
    for course in courses:
        blocks.setdefault(course["block"], []).append(course["name"])
    assert list(blocks.values()) == [
        ["Informatik Wahlpflicht", "Spanisch Wahlpflicht", "Sport Wahlpflicht"],
        ["Kunst", "Musik"],
        ["Teamprojekt", "Teamprojekt"],
    ]

    def names(option):
        return [course["name"] for course in courses_for_option(courses, option)]

    assert names(CONF_COURSE_WPI) == [
        "Informatik Wahlpflicht",
        "Spanisch Wahlpflicht",
        "Sport Wahlpflicht",
    ]
    assert names(CONF_COURSE_TEAM_PROJECT) == ["Teamprojekt", "Teamprojekt"]


def test_unmarked_blocks_go_to_the_option_without_a_marked_block() -> None:
    """WPI courses without "WP" in the name, team projects named "TP"."""
    lessons = [
        lesson.but(subjects=[Element(lesson.subjects[0].name[:3], "Kurs")])
        if "Wahlpflicht" in lesson.subjects[0].long_name
        else lesson
        for lesson in week()
    ]
    lessons += [
        *weekly(ART, 40, 1, "10:00", "10:45", weeks=1),
        *weekly(MUSIC, 41, 1, "10:00", "10:45", weeks=1),
    ]
    courses = parallel_courses(lessons)

    wpi = {course["value"] for course in courses_for_option(courses, CONF_COURSE_WPI)}
    assert wpi == {"Spa|", "Spo|", "Inf|", "Ku|", "Mu|"}
    team = courses_for_option(courses, CONF_COURSE_TEAM_PROJECT)
    assert {course["value"] for course in team} == {TEAM_ROBOTICS_KEY, TEAM_THEATRE_KEY}


def test_markers() -> None:
    def offered(name, group=""):
        course = {"short": name, "name": name, "group": group, "block": 0}
        other = {"short": "X", "name": "X", "group": "", "block": 1}
        return {
            option: [c["block"] for c in courses_for_option([course, other], option)]
            for option in (CONF_COURSE_WPI, CONF_COURSE_TEAM_PROJECT)
        }

    assert offered("WPI Spanisch") == {
        CONF_COURSE_WPI: [0],
        CONF_COURSE_TEAM_PROJECT: [1],
    }
    assert offered("Spa", "Wahlpflicht 8") == {
        CONF_COURSE_WPI: [0],
        CONF_COURSE_TEAM_PROJECT: [1],
    }
    assert offered("TP Robotik") == {
        CONF_COURSE_WPI: [1],
        CONF_COURSE_TEAM_PROJECT: [0],
    }
    assert offered("Teamprojekt") == {
        CONF_COURSE_WPI: [1],
        CONF_COURSE_TEAM_PROJECT: [0],
    }
    # "tp" only as a word of its own, not inside another word.
    assert offered("Stpk") == {
        CONF_COURSE_WPI: [0, 1],
        CONF_COURSE_TEAM_PROJECT: [0, 1],
    }
