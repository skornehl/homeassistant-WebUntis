## Optional Configurations

### Filter Options

Control which lessons or subjects are included or excluded.

| Option             | Description                                              | Example/Default  |
| :----------------- | :------------------------------------------------------- | :--------------- |
| filter_mode        | Filter mode, e.g., `Blacklist` or `Whitelist`.           | `Blacklist`      |
| filter_subjects    | Subjects to exclude from any data.                       | `["Math", "PE"]` |
| filter_description | Exclude lessons containing specific text in description. | `"Online"`       |
| invalid_subjects   | Allow lessons without subjects.                          | `False`          |

### Course Choice Options

Some schools put every course of an elective block (e.g. WPI/Wahlpflicht or
team projects) into each student's timetable, so the calendar shows several
lessons at the same time and changes of other students' courses trigger events
and notifications. Under **Options → Course choice (WPI, team project)** pick
the course the student attends in each block.

| Option              | Description                                                   | Default |
| :------------------ | :------------------------------------------------------------ | :------ |
| course_wpi          | The student's course in the elective block (WPI/Wahlpflicht). | `None`  |
| course_team_project | The student's team project.                                   | `None`  |

The dropdowns list every course that runs in parallel to another course in the
fetched timetable (current week and the next 30 days), with teacher and weekly
times, e.g. `Spanisch Wahlpflicht – Hub · Mo 08:00, Mo 08:45`. In the holidays
the list is empty; a stored choice stays selected.

Once a course is chosen, every other course that runs at the same time is left
out of the calendar, the sensors, the `webuntis.get_timetable` and
`webuntis.count_lessons` services (unless `apply_filter` is off) and the lesson
change detection, so it fires no events and sends no notifications. Substitute
lessons of a new subject in the slot (e.g. "Math instead of Spanish") are
kept. Changes of the chosen course itself are reported as before.

A course is identified by its subject and student group, not by teacher or
room, so a substitution or cancellation does not break the choice. Two
parallel courses with the same subject (e.g. all team projects share the
subject "Teamprojekt") are told apart by their Untis lesson number; that
number may change with a new timetable, then choose the course again. Clear a
field to show all courses again.

### Calendar Options

Customize what is shown in calendar entities.

| Option                          | Description                                  | Default          |
| :------------------------------ | :------------------------------------------- | :--------------- |
| calendar_show_cancelled_lessons | Show cancelled lessons in calendar.          | `False`          |
| calendar_description            | Display format for event description.        | `JSON`           |
| calendar_room                   | Specify location display.                    | `Room long name` |
| calendar_show_room_change       | Show room changes in calendar.               | `False`          |
| calendar_replace_name           | Replace words in event name.                 | `None`           |


### Lesson Options

Control how the lesson name is displayed.

| Option                        | Description                                    | Default |
| :---------------------------- | :--------------------------------------------- | :------ |
| lesson_long_name              | Show the full lesson name.                     | `True`  |
| lesson_replace_name           | Replace lesson names based on mapping.         | `None`  |
| lesson_add_teacher            | Show the teacher's name for selected subjects. | `None`  |
| lesson_compacting_tolerance   | Break (in minutes) between lessons for merge.  |  `0`    |
| lesson_compacting_parallel    | Compact parallel lessons that overlap or share the same time. | `False` |

### Notification Options

Configure how lesson change notifications are sent.

| Option           | Description                                                   | Default         |
| :--------------- | :------------------------------------------------------------ | :-------------- |
| name             | Name of the Notify device.                                    | `entity_id`     |
| notify_entity_id | Home Assistant notification service, e.g., `notify.telegram`. | `None`          |
| target           | Additional targets for the notification.                      | `None`          |
| data             | Additional data for the notification service.                 | `None`          |
| template         | Notification template to use.                                 | `message_title` |
| options          | Options that trigger the notification.                        | `None`          |

### Live Timetable Options

Show your current lessons as Live Activities directly on your Lock Screen.

| Option        | Description                                                   | Default.    |
| :------------ | :------------------------------------------------------------ | :---------- |
| name          | Name of the Notify device.                                    | `entity_id` |
| platform      | Device platform for this target.                              | `None`      |
| entity_id     | Mobile App notify service, e.g., `notify.iphone_von_max`.     | `None`      |
| start_offset  | Minutes before the first lesson to start the live activity.   | `10`        |
| end_offset    | Minutes after the last lesson to stop the live activity.      | `10`        |

### Backend Options

Control backend behavior and data generation.

| Option         | Description                                                 | Default |
| :------------- | :---------------------------------------------------------- | :------ |
| keep_logged_in | Keep the client logged in (Beta).                           | `False` |
| generate_json  | Generate JSON in sensor attributes for templates.           | `False` |
| exclude_data   | Automatically exclude data if the user lacks access rights. | `None`  |
