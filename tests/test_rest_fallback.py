"""The REST fallback must not mix up parallel lessons."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.webuntis.utils.web_untis_extended import ExtendedSession

START = datetime(2026, 11, 16, 8, 0)
END = datetime(2026, 11, 16, 8, 45)


def jsonrpc_lesson(subject_id, teacher_id, room_id, **data):
    return SimpleNamespace(
        start=START,
        end=END,
        _data={
            "su": [{"id": subject_id}] if subject_id else [],
            "te": [{"id": teacher_id}],
            "ro": [{"id": room_id}],
            **data,
        },
    )


def rest_lesson(subject_id, teacher_id, room_id, text=""):
    return {
        "start": START.isoformat(),
        "end": END.isoformat(),
        "subjects": [{"id": subject_id, "name": f"S{subject_id}", "long_name": ""}],
        "teachers": [{"id": teacher_id, "name": f"T{teacher_id}", "long_name": ""}],
        "rooms": [{"id": room_id, "name": f"R{room_id}", "long_name": ""}],
        "klassen": [],
        "lesson_text": text,
        "lesson_info": "",
        "substitution_text": "",
    }


def fill(lessons, rest_lessons):
    session = ExtendedSession(
        username="u", password="p", server="s", school="x", useragent="test"
    )
    session.login_result = {"personId": 1}
    with patch(
        "custom_components.webuntis.utils.web_untis_extended.get_rest_lessons",
        return_value=rest_lessons,
    ):
        session._add_rest_fallbacks(lessons, START.date(), END.date())


def ids(lesson, key):
    return [element["id"] for element in lesson._data[key]]


def test_parallel_lesson_keeps_its_own_data_when_rest_lists_one_course() -> None:
    """REST lists only the student's Spanish, JSON-RPC Spanish and Sport."""
    spanish = jsonrpc_lesson(101, 11, 21)
    sport = jsonrpc_lesson(102, 12, 22)

    fill([spanish, sport], [rest_lesson(101, 11, 21, text="Vokabeltest")])

    assert (ids(sport, "su"), ids(sport, "te"), ids(sport, "ro")) == (
        [102],
        [12],
        [22],
    )
    assert "lstext" not in sport._data
    assert spanish._data["lstext"] == "Vokabeltest"


def test_parallel_lessons_take_the_rest_lesson_with_their_subject() -> None:
    spanish = jsonrpc_lesson(101, 11, 21)
    sport = jsonrpc_lesson(102, 12, 22)

    fill(
        [spanish, sport],
        [rest_lesson(101, 11, 21, text="Spa"), rest_lesson(102, 12, 22, text="Spo")],
    )

    assert spanish._data["lstext"] == "Spa"
    assert sport._data["lstext"] == "Spo"
    assert ids(spanish, "te") == [11]
    assert ids(sport, "te") == [12]


def test_single_lesson_without_subject_is_still_filled() -> None:
    lesson = jsonrpc_lesson(None, 11, 21)

    fill([lesson], [rest_lesson(101, 11, 21)])

    assert ids(lesson, "su") == [101]


def test_lesson_without_subject_is_not_filled_from_parallel_lessons() -> None:
    lesson = jsonrpc_lesson(None, 11, 21)

    fill([lesson], [rest_lesson(101, 11, 21), rest_lesson(102, 12, 22)])

    assert ids(lesson, "su") == []


def test_single_lesson_with_its_subject_is_still_filled() -> None:
    lesson = jsonrpc_lesson(101, 11, 21)

    fill([lesson], [rest_lesson(101, 13, 21, text="Text")])

    assert lesson._data["lstext"] == "Text"
    assert ids(lesson, "te") == [11, 13]


def test_parallel_groups_of_one_subject_are_matched_by_teacher() -> None:
    robotics = jsonrpc_lesson(200, 31, 41)
    theatre = jsonrpc_lesson(200, 32, 42)

    fill(
        [robotics, theatre],
        [rest_lesson(200, 31, 41, text="Rob"), rest_lesson(200, 32, 42, text="The")],
    )

    assert robotics._data["lstext"] == "Rob"
    assert theatre._data["lstext"] == "The"
    assert ids(robotics, "ro") == [41]
    assert ids(theatre, "ro") == [42]


def test_indistinguishable_parallel_lessons_get_no_fallback() -> None:
    first = jsonrpc_lesson(200, 31, 41)

    fill(
        [first],
        [rest_lesson(200, 31, 41, text="A"), rest_lesson(200, 31, 42, text="B")],
    )

    assert "lstext" not in first._data


def test_rest_lesson_without_subject_still_fills_a_single_lesson() -> None:
    lesson = jsonrpc_lesson(101, 11, 21)
    rest = {**rest_lesson(101, 11, 21, text="Exkursion"), "subjects": []}

    fill([lesson], [rest])

    assert lesson._data["lstext"] == "Exkursion"
    assert ids(lesson, "su") == [101]
