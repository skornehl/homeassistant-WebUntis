"""Options flow step for the course choice (WPI, team project)."""

from __future__ import annotations

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.webuntis.utils.course_choice import (
    CONF_COURSE_TEAM_PROJECT,
    CONF_COURSE_WPI,
    parallel_courses,
)

from .conftest import Element, make_entry, make_server
from .timetable import (
    SPANISH_KEY,
    SPORT_WPI_KEY,
    TEAM_ROBOTICS_KEY,
    TEAM_THEATRE_KEY,
    week,
)


async def open_courses_step(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert "courses" in result["menu_options"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "courses"}
    )


def select_options(result, field):
    for key, value in result["data_schema"].schema.items():
        if key == field:
            return {
                option["value"]: option["label"] for option in value.config["options"]
            }
    raise KeyError(field)


@pytest.fixture
def entry(hass):
    entry = make_entry()
    server = make_server(hass, entry, week())
    server.parallel_courses = parallel_courses(week())
    hass.config.language = "de"
    return entry


async def test_each_dropdown_lists_its_own_block(hass, entry) -> None:
    result = await open_courses_step(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "courses"
    assert result["description_placeholders"] == {"count": "5"}
    assert select_options(result, CONF_COURSE_WPI) == {
        "InfWP|": "Informatik Wahlpflicht – Bit · Mo 08:00, Mo 08:45",
        SPANISH_KEY: "Spanisch Wahlpflicht – Hub · Mo 08:00, Mo 08:45",
        SPORT_WPI_KEY: "Sport Wahlpflicht – Kra · Mo 08:00, Mo 08:45",
    }
    assert select_options(result, CONF_COURSE_TEAM_PROJECT) == {
        TEAM_ROBOTICS_KEY: "Teamprojekt – Rob · Do 11:40, Do 12:25",
        TEAM_THEATRE_KEY: "Teamprojekt – The · Do 11:40, Do 12:25",
    }


async def test_choice_is_saved(hass, entry) -> None:
    result = await open_courses_step(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_COURSE_WPI: SPANISH_KEY, CONF_COURSE_TEAM_PROJECT: TEAM_ROBOTICS_KEY},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_COURSE_WPI] == SPANISH_KEY
    assert entry.options[CONF_COURSE_TEAM_PROJECT] == TEAM_ROBOTICS_KEY
    # The other options are kept.
    assert entry.options["filter_mode"] == "None"


async def test_cleared_field_saves_no_course(hass, entry) -> None:
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_COURSE_WPI: SPANISH_KEY}
    )
    result = await open_courses_step(hass, entry)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_COURSE_WPI] == ""
    assert entry.options[CONF_COURSE_TEAM_PROJECT] == ""


async def test_same_course_twice_is_refused(hass, entry) -> None:
    """Without names that mark the blocks both dropdowns offer every block."""
    unmarked = [
        lesson.but(subjects=[Element(f"K{lesson.lsnumber}", f"Kurs {lesson.lsnumber}")])
        for lesson in week()
    ]
    hass.data["webuntis"][entry.unique_id].parallel_courses = parallel_courses(unmarked)
    result = await open_courses_step(hass, entry)
    assert select_options(result, CONF_COURSE_WPI) == select_options(
        result, CONF_COURSE_TEAM_PROJECT
    )
    sport_wpi_key = "K12|"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_COURSE_WPI: sport_wpi_key, CONF_COURSE_TEAM_PROJECT: sport_wpi_key},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_course"}


async def test_stored_choice_stays_selectable_in_the_holidays(hass, entry) -> None:
    """No lessons, no parallel courses: the stored choice is still offered."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_COURSE_WPI: SPANISH_KEY}
    )
    hass.data["webuntis"][entry.unique_id].parallel_courses = []

    result = await open_courses_step(hass, entry)

    assert result["description_placeholders"] == {"count": "0"}
    assert select_options(result, CONF_COURSE_WPI) == {SPANISH_KEY: "SpaWP"}
    suggested = {
        str(key): key.description.get("suggested_value")
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested == {CONF_COURSE_WPI: SPANISH_KEY}
