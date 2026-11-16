"""Fixtures and fake WebUntis lessons for the tests."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.webuntis import WebUntis
from custom_components.webuntis.const import (
    CONFIG_ENTRY_VERSION,
    DEFAULT_OPTIONS,
    DOMAIN,
)

UNIQUE_ID = "korsop@school"


@pytest.fixture(autouse=True)
async def setup_hass(hass, enable_custom_integrations):
    """Load custom_components/webuntis and run in the school's time zone.

    The frontend and http dependencies count as set up: the tests need
    neither, and the frontend package is not installed.
    """
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.components.update({"frontend", "http"})
    yield


@dataclass(frozen=True)
class Element:
    """A subject, teacher, room or class as python-webuntis returns it."""

    name: str
    long_name: str = ""
    id: int = 0


@dataclass
class Lesson:
    """The attributes of a python-webuntis PeriodObject the integration reads."""

    start: datetime
    end: datetime
    subjects: list[Element]
    lsnumber: int
    id: int
    teachers: list[Element] = field(default_factory=list)
    rooms: list[Element] = field(default_factory=list)
    klassen: list[Element] = field(default_factory=lambda: [Element("8b", "8b")])
    original_teachers: list[Element] = field(default_factory=list)
    original_rooms: list[Element] = field(default_factory=list)
    code: str | None = None
    type: str = "ls"
    info: str = ""
    lstext: str = ""
    substText: str = ""
    studentGroup: str = ""

    def but(self, **changes: Any) -> Lesson:
        """Return a copy with some attributes changed (a later poll)."""
        return replace(self, **changes)


def make_entry(
    options: dict[str, Any] | None = None, unique_id: str = UNIQUE_ID
) -> MockConfigEntry:
    """Return a config entry for a student timetable."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sophie",
        unique_id=unique_id,
        version=CONFIG_ENTRY_VERSION,
        data={
            "server": "school.webuntis.com",
            "school": "school",
            "username": "KorSop",
            "password": "test",
            "timetable_source": "personal",
            "timetable_source_id": "",
        },
        options={**copy.deepcopy(DEFAULT_OPTIONS), **(options or {})},
    )


def make_server(hass, entry: MockConfigEntry, timetable: list[Lesson]) -> WebUntis:
    """Return a WebUntis client that reads ``timetable`` instead of the server."""
    entry.add_to_hass(hass)
    server = WebUntis(hass, entry.unique_id, entry)
    server.current_schoolyear = SimpleNamespace(
        start=datetime(2026, 8, 1), end=datetime(2027, 7, 31)
    )
    server.timetable = timetable

    def my_timetable(start, end):
        return [
            lesson for lesson in server.timetable if start <= lesson.start.date() <= end
        ]

    server.session.my_timetable = my_timetable
    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = server
    return server
