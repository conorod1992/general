# Smart Reminders

This custom component allows you to schedule one-off or recurring reminders in Home Assistant.

Use the `smart_reminders.add_reminder` service to create reminders that can announce messages via TTS or send notifications.

## Service call example

```yaml
service: smart_reminders.add_reminder
data:
  message: "Take out the trash"
  start: "2025-06-05 19:00:00"
  actions:
    - type: tts
      entity_id: media_player.kitchen_speaker
    - type: notify
      service: notify.mobile_app_my_phone
      data:
        title: "Trash day"
  rrule: "FREQ=WEEKLY;BYDAY=FR"
```

### Required fields
- `message`: Text that will be spoken or included in the notification.
- `start`: Date and time for the first reminder occurrence.
- `actions`: List of actions to run when the reminder triggers.

### Optional fields
- `rrule`: [iCalendar recurrence rule](https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html) describing how the reminder repeats.
