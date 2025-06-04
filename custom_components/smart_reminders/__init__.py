"""Smart Reminders custom component."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import dateparser
from dateutil.rrule import rrulestr

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.helpers.event import async_track_point_in_utc_time

DOMAIN = "smart_reminders"
SERVICE_ADD_REMINDER = "add_reminder"
EVENT_REMINDER_TRIGGERED = "reminder_triggered"

_LOGGER = logging.getLogger(__name__)

@dataclass
class ReminderAction:
    type: str
    service: Optional[str] = None
    entity_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Reminder:
    message: str
    start: datetime
    rrule: Optional[str] = None
    actions: List[ReminderAction] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _cancel: Optional[Callable[[], None]] = field(default=None, init=False, repr=False)
    _rrule: Optional[Any] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.start, str):
            parsed = dateparser.parse(self.start)
            if parsed is None:
                raise ValueError(f"Could not parse start datetime: {self.start}")
            self.start = parsed
        if self.rrule:
            self._rrule = rrulestr(self.rrule, dtstart=self.start)

    def next_occurrence(self) -> Optional[datetime]:
        if self._rrule:
            return self._rrule.after(datetime.utcnow(), inc=False)
        return None

class ReminderManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._reminders: Dict[str, Reminder] = {}

    @callback
    def add(self, reminder: Reminder) -> None:
        self._reminders[reminder.id] = reminder
        self._schedule(reminder, reminder.start)
        _LOGGER.debug("Added reminder %s", reminder)

    def _schedule(self, reminder: Reminder, when: datetime) -> None:
        reminder._cancel = async_track_point_in_utc_time(
            self.hass, lambda _: self._handle_trigger(reminder), when
        )
        _LOGGER.debug("Scheduled reminder %s at %s", reminder.id, when)

    @callback
    def _handle_trigger(self, reminder: Reminder) -> None:
        _LOGGER.debug("Triggering reminder %s", reminder.id)
        for action in reminder.actions:
            if action.type == "tts" and action.entity_id:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "tts",
                        "google_translate_say",
                        {
                            "entity_id": action.entity_id,
                            "message": reminder.message,
                        },
                        blocking=True,
                    )
                )
            elif action.type == "notify" and action.service:
                service_domain, service_name = action.service.split(".", 1)
                data = {"message": reminder.message}
                data.update(action.data)
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        service_domain,
                        service_name,
                        data,
                        blocking=True,
                    )
                )

        self.hass.bus.async_fire(
            EVENT_REMINDER_TRIGGERED,
            {"id": reminder.id, "message": reminder.message},
        )

        next_time = reminder.next_occurrence()
        if next_time:
            _LOGGER.debug("Rescheduling recurring reminder %s for %s", reminder.id, next_time)
            self._schedule(reminder, next_time)
        else:
            _LOGGER.debug("Removing one-off reminder %s", reminder.id)
            self._reminders.pop(reminder.id, None)

async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    manager = ReminderManager(hass)

    async def handle_add(call: ServiceCall) -> None:
        data = call.data
        actions = [ReminderAction(**a) for a in data.get("actions", [])]
        reminder = Reminder(
            message=data["message"],
            start=data["start"],
            rrule=data.get("rrule"),
            actions=actions,
        )
        manager.add(reminder)

    hass.services.async_register(DOMAIN, SERVICE_ADD_REMINDER, handle_add)

    async def startup(event):
        _LOGGER.debug("smart_reminders component ready")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, startup)
    hass.data[DOMAIN] = manager
    return True
