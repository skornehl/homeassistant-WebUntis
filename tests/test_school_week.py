"""A real school week, rebuilt with made-up teachers and group IDs.

The school only releases one week. Grade 7 has a WPI block of five courses
(Monday and Friday), 16 team projects for all grades on Wednesday, and some
subjects split into two groups (art, English, class council). The student
attends one course or group of each. Student groups are generated IDs like
"SG20260101000001_100", not names.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.webuntis.utils.course_choice import (
    CONF_COURSE_TEAM_PROJECT,
    CONF_COURSE_WPI,
    course_keys,
    course_label,
    courses_for_option,
    drop_parallel_courses,
    parallel_courses,
)

from .conftest import Element, Lesson

MONDAY = datetime(2026, 11, 16)
WPI_SLOTS = [(0, "08:00"), (0, "08:45"), (4, "09:50"), (4, "10:45")]
TEAM_SLOTS = [(2, "13:15"), (2, "14:10")]

WPI = [
    ("WPI 7 Frz", "WPI 7 Französisch", "L1"),
    ("WPI 7 NaWi", "WPI 7 Naturwissenschaften", "L2"),
    ("WPI 7 SN", "WPI 7 Spanisch", "L3"),
    ("WPI 7 Sp", "WPI 7 Sport", "L4"),
    ("WPI 7 WAT", "WPI 7 WAT", "L5"),
]
SPANISH_KEY = "WPI 7 SN|SG20260101000003_100"

TEAM_GROUPS = [
    "Teamprojekt_10a10b10c10d7a7b7c7d8a8b8c8d9a9b9c9d_1",
    "",
    *(f"SG2026020100{number:04d}_200" for number in range(1, 15)),
]
TEAM_TEACHERS = [f"T{number:02d}" for number in range(16, 0, -1)]
TEAM_TEACHERS[5] = "---"


def slot(weekday: int, start: str) -> tuple[datetime, datetime]:
    begin = (MONDAY + timedelta(days=weekday)).replace(
        hour=int(start[:2]), minute=int(start[3:])
    )
    return begin, begin + timedelta(minutes=45)


def school_week() -> list[Lesson]:
    lessons: list[Lesson] = []
    ids = iter(range(1, 10000))

    def add(slots, short, long_name, lsnumber, teacher, group="", **changes):
        for weekday, start in slots:
            begin, end = slot(weekday, start)
            lessons.append(
                Lesson(
                    start=begin,
                    end=end,
                    subjects=[Element(short, long_name, lsnumber)],
                    lsnumber=lsnumber,
                    id=next(ids),
                    teachers=[Element(teacher, teacher)],
                    studentGroup=group,
                    **changes,
                )
            )

    for number, (short, long_name, teacher) in enumerate(WPI, start=1):
        group = f"SG20260101{number:06d}_100"
        if short == "WPI 7 SN":
            # Spanish is cancelled on Monday, as on 16.11.
            add(WPI_SLOTS[:2], short, long_name, 2011, teacher, group, code="cancelled")
            add(WPI_SLOTS[2:], short, long_name, 2011, teacher, group)
        else:
            add(WPI_SLOTS, short, long_name, 2000 + number, teacher, group)

    for number, (group, teacher) in enumerate(
        zip(TEAM_GROUPS, TEAM_TEACHERS, strict=True), start=1
    ):
        add(TEAM_SLOTS, "Teamprojekt", "Teamprojekt", 3000 + number, teacher, group)

    # Subjects split into two groups of the class.
    add([(0, "09:50")], "KU", "Kunst", 4001, "A1")
    add([(0, "09:50")], "KU", "Kunst", 4002, "A2", "SG20260826000001_229")
    english = [(1, "08:00"), (1, "08:45"), (2, "09:50"), (4, "14:10")]
    add(english, "EN 7", "Englisch 7", 4011, "E1")
    add(english, "EN 7", "Englisch 7", 4012, "E2", "SG20260902000001_192")
    add([(1, "11:40")], "KR", "Klassenrat", 4021, "C1")
    add([(1, "11:40")], "KR", "Klassenrat", 4022, "C2", "SG20260113000001_399")

    # Regular lessons of the class.
    add([(0, "11:40"), (2, "08:00")], "DE", "Deutsch", 5001, "D1")
    add([(1, "09:50"), (3, "08:00")], "MA", "Mathematik", 5002, "M1")
    return lessons


def offered(option):
    return courses_for_option(parallel_courses(school_week()), option)


def test_wpi_dropdown_lists_the_five_wpi_courses() -> None:
    labels = [course_label(course, "de") for course in offered(CONF_COURSE_WPI)]

    assert labels == [
        "WPI 7 Französisch – L1 · Mo 08:00, Mo 08:45, Fr 09:50, Fr 10:45",
        "WPI 7 Naturwissenschaften – L2 · Mo 08:00, Mo 08:45, Fr 09:50, Fr 10:45",
        "WPI 7 Spanisch – L3 · Mo 08:00, Mo 08:45, Fr 09:50, Fr 10:45",
        "WPI 7 Sport – L4 · Mo 08:00, Mo 08:45, Fr 09:50, Fr 10:45",
        "WPI 7 WAT – L5 · Mo 08:00, Mo 08:45, Fr 09:50, Fr 10:45",
    ]


def test_team_project_dropdown_lists_the_16_team_projects_by_teacher() -> None:
    courses = offered(CONF_COURSE_TEAM_PROJECT)
    labels = [course_label(course, "de") for course in courses]

    assert len(labels) == 16
    assert labels[0] == "Teamprojekt · Mi 13:15, Mi 14:10"  # teacher "---"
    assert labels[1] == "Teamprojekt – T01 · Mi 13:15, Mi 14:10"
    assert labels[-1] == "Teamprojekt – T16 · Mi 13:15, Mi 14:10"
    assert len({course["value"] for course in courses}) == 16


def test_split_groups_are_in_neither_dropdown() -> None:
    names = {
        course["name"]
        for option in (CONF_COURSE_WPI, CONF_COURSE_TEAM_PROJECT)
        for course in offered(option)
    }
    assert names.isdisjoint({"Kunst", "Englisch 7", "Klassenrat", "Deutsch"})


def test_stored_key_format_stays_valid() -> None:
    """The WPI choice saved with v3.4.0 keeps matching."""
    keys = set(course_keys(school_week()))
    assert SPANISH_KEY in keys
    assert SPANISH_KEY in {course["value"] for course in offered(CONF_COURSE_WPI)}


def test_choices_leave_only_the_students_courses() -> None:
    robotics = next(
        course["value"]
        for course in offered(CONF_COURSE_TEAM_PROJECT)
        if course["teachers"] == ["T07"]
    )
    remaining, _ = drop_parallel_courses(school_week(), [SPANISH_KEY, robotics])

    wpi = {
        lesson.subjects[0].long_name
        for lesson in remaining
        if lesson.subjects[0].name.startswith("WPI")
    }
    team = [lesson for lesson in remaining if lesson.subjects[0].name == "Teamprojekt"]
    assert wpi == {"WPI 7 Spanisch"}
    assert {lesson.teachers[0].name for lesson in team} == {"T07"}
    assert len(team) == 2


def spanish_cancelled_all_week() -> list[Lesson]:
    return [
        lesson.but(code="cancelled")
        if lesson.subjects[0].name == "WPI 7 SN"
        else lesson
        for lesson in school_week()
    ]


def test_course_cancelled_all_week_keeps_its_place_and_label() -> None:
    """Spanish is cancelled in every lesson of the only week the school releases.

    It has no lesson that takes place, but it still runs in parallel to the
    WPI block, so it stays in the dropdown with its full label.
    """
    courses = courses_for_option(
        parallel_courses(spanish_cancelled_all_week()), CONF_COURSE_WPI
    )
    labels = {course["value"]: course_label(course, "de") for course in courses}

    assert len(labels) == 5
    assert labels[SPANISH_KEY] == (
        "WPI 7 Spanisch – L3 · Mo 08:00, Mo 08:45, Fr 09:50, Fr 10:45"
    )


def test_two_course_block_with_one_course_cancelled_all_week() -> None:
    lessons = [
        lesson.but(code="cancelled")
        if lesson.subjects[0].name == "WPI 7 SN"
        else lesson
        for lesson in school_week()
        if lesson.subjects[0].name not in ("WPI 7 Frz", "WPI 7 NaWi", "WPI 7 WAT")
    ]
    names = [
        course["name"]
        for course in courses_for_option(parallel_courses(lessons), CONF_COURSE_WPI)
    ]
    assert names == ["WPI 7 Spanisch", "WPI 7 Sport"]


def test_substitute_next_to_a_cancelled_lesson_leaves_the_dropdowns_alone() -> None:
    """One week only: art group A cancelled, a class council takes its place."""
    lessons = []
    for lesson in school_week():
        if lesson.lsnumber == 4001:  # art, group without ID
            lessons.append(lesson.but(code="cancelled"))
            lessons.append(
                lesson.but(subjects=[Element("KR", "Klassenrat", 4021)], lsnumber=4021)
            )
        else:
            lessons.append(lesson)
    courses = parallel_courses(lessons)

    def labels(found):
        return [(course["value"], course_label(course, "de")) for course in found]

    for option in (CONF_COURSE_WPI, CONF_COURSE_TEAM_PROJECT):
        assert labels(courses_for_option(courses, option)) == labels(offered(option))
