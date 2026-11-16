"""Elective courses of other students must not show up as changes.

Reported case: the student attends Spanish in the WPI block (Wahlpflicht),
Sport and Computer Science run at the same time for other students. Spanish
was cancelled, and the family got "instead of Spanish: Sport", because the
automation looks up the calendar for the cancelled slot and found the Sport
course of other students there.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.webuntis.utils.course_choice import (
    CONF_COURSE_TEAM_PROJECT,
    CONF_COURSE_WPI,
)
from custom_components.webuntis.utils.utils import compact_list

from .conftest import Element, make_entry, make_server
from .timetable import (
    COMPUTING,
    MATH,
    SPANISH,
    SPANISH_KEY,
    SPORT_WPI,
    TEAM_ROBOTICS_KEY,
    WPI_PERIODS,
    changed,
    week,
)

pytestmark = pytest.mark.freeze_time("2026-11-16 06:30:00+01:00")


async def poll(server, lessons):
    """Run one update cycle and return the lesson change events it fired."""
    events = []
    server.lesson_change_callback = lambda change, data: events.append((change, data))
    server.timetable = lessons
    server.calendar_events = sorted(
        compact_list(server._get_events(), "calendar", timedelta(0), False),
        key=lambda event: event.start,
    )
    await server.update_notify()
    return events


def replacement(server, data):
    """Return what the "lesson cancelled" automation reports as the substitute.

    Like ``sophie_unterricht_faellt_aus``: 15 minutes after the cancellation it
    asks calendar.get_events for the time of the cancelled lesson and reports
    the first event there as "instead now: ...".
    """
    start = data["old_lesson"]["start"]
    end = data["old_lesson"]["end"]
    found = [
        event
        for event in server.calendar_events
        if event.start.isoformat() < end and event.end.isoformat() > start
    ]
    return found[0].summary.replace("Irregular: ", "") if found else None


def calendar_names(server):
    return {event.summary for event in server.calendar_events}


def morning_block():
    """This morning's WPI block: Spanish for the student, Sport for others."""
    return [lesson for lesson in week() if lesson.subjects != [COMPUTING]]


async def test_without_choice_sport_is_reported_instead_of_spanish(hass) -> None:
    """Reproduces the wrong message: Sport WPI 'instead of' Spanish WPI."""
    server = make_server(hass, make_entry(), morning_block())
    assert await poll(server, morning_block()) == []

    events = await poll(server, changed(morning_block(), SPANISH, code="cancelled"))

    assert [change for change, _ in events] == ["cancelled", "cancelled"]
    assert {data["new_lesson"]["name"] for _, data in events} == {
        "Spanisch Wahlpflicht"
    }
    assert {replacement(server, data) for _, data in events} == {"Sport Wahlpflicht"}


async def test_with_choice_no_other_course_is_reported(hass) -> None:
    """With Spanish chosen, the cancellation stands alone."""
    entry = make_entry({CONF_COURSE_WPI: SPANISH_KEY})
    server = make_server(hass, entry, morning_block())
    assert await poll(server, morning_block()) == []
    assert "Sport Wahlpflicht" not in calendar_names(server)
    assert {"Spanisch Wahlpflicht", "Sport", "Deutsch"} <= calendar_names(server)

    events = await poll(server, changed(morning_block(), SPANISH, code="cancelled"))

    assert [change for change, _ in events] == ["cancelled", "cancelled"]
    assert {data["new_lesson"]["name"] for _, data in events} == {
        "Spanisch Wahlpflicht"
    }
    assert {replacement(server, data) for _, data in events} == {None}


@pytest.mark.parametrize(
    "change",
    [
        {"code": "cancelled"},
        {"teachers": [Element("---")]},
        {"rooms": [Element("R99", "Raum 99")]},
    ],
    ids=["cancelled", "teacher", "room"],
)
@pytest.mark.parametrize("course", [SPORT_WPI, COMPUTING], ids=["sport", "computing"])
async def test_changes_of_other_courses_fire_no_event(hass, change, course) -> None:
    server = make_server(hass, make_entry({CONF_COURSE_WPI: SPANISH_KEY}), week())
    await poll(server, week())

    assert await poll(server, changed(week(), course, **change)) == []


async def test_changes_of_other_courses_fired_events_before(hass) -> None:
    server = make_server(hass, make_entry(), week())
    await poll(server, week())

    events = await poll(server, changed(week(), SPORT_WPI, code="cancelled"))

    assert {data["new_lesson"]["name"] for _, data in events} == {"Sport Wahlpflicht"}


async def test_changes_of_the_chosen_course_still_fire(hass) -> None:
    server = make_server(hass, make_entry({CONF_COURSE_WPI: SPANISH_KEY}), week())
    await poll(server, week())

    events = await poll(server, changed(week(), SPANISH, teachers=[Element("Neu")]))

    assert [change for change, _ in events] == ["teachers", "teachers"]
    assert {data["new_lesson"]["name"] for _, data in events} == {
        "Spanisch Wahlpflicht"
    }


async def test_substitute_lesson_in_the_slot_is_kept(hass) -> None:
    """Spanish cancelled, Math instead in the first period: Math is kept."""
    server = make_server(hass, make_entry({CONF_COURSE_WPI: SPANISH_KEY}), week())
    await poll(server, week())

    later = changed(week(), SPANISH, code="cancelled")
    start, end = WPI_PERIODS[0]
    later.append(
        later[0].but(
            start=start,
            end=end,
            subjects=[MATH],
            lsnumber=99,
            id=5000,
            code="irregular",
        )
    )
    events = await poll(server, later)

    by_start = {
        (change, data["old_lesson"]["start"][11:16]): data for change, data in events
    }
    assert sorted(by_start) == [("cancelled", "08:45"), ("replacement", "08:00")]
    swap = by_start[("replacement", "08:00")]
    assert swap["old_lesson"]["name"] == "Spanisch Wahlpflicht"
    assert swap["new_lesson"]["name"] == "Mathematik"
    assert replacement(server, swap) == "Mathematik"
    assert replacement(server, by_start[("cancelled", "08:45")]) is None


async def test_coupled_block_reports_no_phantom_changes(hass) -> None:
    """All WPI courses in one coupled lesson number.

    The change detection matches lessons by lesson number and start, so
    without a course choice the parallel courses are compared with each other
    and every poll reports changes that never happened.
    """
    unchosen = make_server(hass, make_entry(), week(coupled=True))
    await poll(unchosen, week(coupled=True))
    assert await poll(unchosen, week(coupled=True)) != []

    server = make_server(
        hass,
        make_entry({CONF_COURSE_WPI: SPANISH_KEY}, unique_id="chosen"),
        week(coupled=True),
    )
    await poll(server, week(coupled=True))
    assert await poll(server, week(coupled=True)) == []


async def test_team_project_choice(hass) -> None:
    server = make_server(
        hass,
        make_entry(
            {CONF_COURSE_WPI: SPANISH_KEY, CONF_COURSE_TEAM_PROJECT: TEAM_ROBOTICS_KEY}
        ),
        week(),
    )
    await poll(server, week())

    team = [event for event in server.calendar_events if event.summary == "Teamprojekt"]
    assert [event.location for event in team] == ["R20"]

    theatre_cancelled = [
        lesson.but(code="cancelled") if lesson.lsnumber == 302 else lesson
        for lesson in week()
    ]
    assert await poll(server, theatre_cancelled) == []


async def test_options_list_the_parallel_courses(hass) -> None:
    """The unfiltered timetable feeds the dropdowns, also after a choice."""
    server = make_server(hass, make_entry({CONF_COURSE_WPI: SPANISH_KEY}), week())
    await poll(server, week())

    assert {course["name"] for course in server.parallel_courses} == {
        "Spanisch Wahlpflicht",
        "Sport Wahlpflicht",
        "Informatik Wahlpflicht",
        "Teamprojekt",
    }
    assert len(server.parallel_courses) == 5


async def test_service_without_filter_shows_all_courses(hass) -> None:
    server = make_server(hass, make_entry({CONF_COURSE_WPI: SPANISH_KEY}), week())
    start, end = WPI_PERIODS[0]

    filtered = server._get_events_in_timerange(start, end, True, True, False)
    unfiltered = server._get_events_in_timerange(start, end, False, True, False)

    assert "Spanisch Wahlpflicht" in {lesson["name"] for lesson in filtered}
    assert "Sport Wahlpflicht" not in {lesson["name"] for lesson in filtered}
    assert {"Spanisch Wahlpflicht", "Sport Wahlpflicht"} <= {
        lesson["name"] for lesson in unfiltered
    }
