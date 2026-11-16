"""A week of a student timetable with two elective blocks.

The school lists every course of an elective block in each student's
timetable. The student attends Spanish in the WPI block (Wahlpflicht); Sport
and Computer Science run at the same time for other students. In the team
project block all groups share one subject and are told apart by their lesson
number.
"""

from __future__ import annotations

from datetime import datetime

from .conftest import Element, Lesson

MONDAY = datetime(2026, 11, 16)
THURSDAY = datetime(2026, 11, 19)

SPANISH = Element("SpaWP", "Spanisch Wahlpflicht", 101)
SPORT_WPI = Element("SpoWP", "Sport Wahlpflicht", 102)
COMPUTING = Element("InfWP", "Informatik Wahlpflicht", 103)
GERMAN = Element("De", "Deutsch", 1)
MATH = Element("Ma", "Mathematik", 2)
SPORT = Element("Sp", "Sport", 3)
TEAM_PROJECT = Element("TP", "Teamprojekt", 200)

SPANISH_KEY = "SpaWP|"
SPORT_WPI_KEY = "SpoWP|"
TEAM_ROBOTICS_KEY = "TP||301"
TEAM_THEATRE_KEY = "TP||302"


def at(day: datetime, start: str, end: str) -> tuple[datetime, datetime]:
    """Return start and end of a period on ``day``."""
    begin = day.replace(hour=int(start[:2]), minute=int(start[3:]))
    finish = day.replace(hour=int(end[:2]), minute=int(end[3:]))
    return begin, finish


WPI_PERIODS = [at(MONDAY, "08:00", "08:45"), at(MONDAY, "08:45", "09:30")]
TEAM_PERIODS = [at(THURSDAY, "11:40", "12:25"), at(THURSDAY, "12:25", "13:10")]


def week(*, coupled: bool = False) -> list[Lesson]:
    """Return the timetable of the week.

    ``coupled`` gives all WPI courses one lesson number, as Untis does for a
    coupled lesson (Kopplung).
    """
    lessons: list[Lesson] = []
    next_id = iter(range(1000, 2000))
    wpi = [
        (SPANISH, 11, Element("Hub", "Huber"), Element("R12", "Raum 12")),
        (SPORT_WPI, 12, Element("Kra", "Kraft"), Element("TH", "Turnhalle")),
        (COMPUTING, 13, Element("Bit", "Bitter"), Element("PC1", "PC-Raum 1")),
    ]
    for start, end in WPI_PERIODS:
        for subject, lsnumber, teacher, room in wpi:
            lessons.append(
                Lesson(
                    start=start,
                    end=end,
                    subjects=[subject],
                    lsnumber=10 if coupled else lsnumber,
                    id=next(next_id),
                    teachers=[teacher],
                    rooms=[room],
                )
            )

    regular = [
        (at(MONDAY, "09:50", "10:35"), GERMAN, 21, "Mül", "R08"),
        (at(MONDAY, "11:40", "12:25"), SPORT, 23, "Kra", "TH"),
        (at(THURSDAY, "08:00", "08:45"), MATH, 22, "Sch", "R08"),
    ]
    for (start, end), subject, lsnumber, teacher, room in regular:
        lessons.append(
            Lesson(
                start=start,
                end=end,
                subjects=[subject],
                lsnumber=lsnumber,
                id=next(next_id),
                teachers=[Element(teacher, teacher)],
                rooms=[Element(room, room)],
            )
        )

    for start, end in TEAM_PERIODS:
        for lsnumber, teacher, room in ((301, "Rob", "R20"), (302, "The", "Aula")):
            lessons.append(
                Lesson(
                    start=start,
                    end=end,
                    subjects=[TEAM_PROJECT],
                    lsnumber=lsnumber,
                    id=next(next_id),
                    teachers=[Element(teacher, teacher)],
                    rooms=[Element(room, room)],
                )
            )
    return lessons


def changed(lessons: list[Lesson], subject: Element, **changes) -> list[Lesson]:
    """Return a later poll in which all lessons of ``subject`` changed."""
    return [
        lesson.but(**changes) if lesson.subjects == [subject] else lesson
        for lesson in lessons
    ]
