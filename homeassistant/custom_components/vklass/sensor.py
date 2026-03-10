"""Sensor platform — one set of entities per child."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VklassCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VklassCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for child in coordinator.data.get("children", []):
        name = child["name"]
        slug = _to_slug(name)
        entities += [
            VklassMealSensor(coordinator, name, slug),
            VklassGymSensor(coordinator, name, slug),
            VklassNotificationSensor(coordinator, name, slug),
            VklassScheduleSensor(coordinator, name, slug),
        ]

    async_add_entities(entities, update_before_add=True)


def _to_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _find_child(coordinator: VklassCoordinator, name: str) -> dict | None:
    for child in (coordinator.data or {}).get("children", []):
        if child["name"] == name:
            return child
    return None


class _VklassBaseSensor(CoordinatorEntity[VklassCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VklassCoordinator, child_name: str, child_slug: str) -> None:
        super().__init__(coordinator)
        self._child_name = child_name
        self._child_slug = child_slug

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._child_slug)},
            "name": f"Vklass — {self._child_name}",
            "manufacturer": "Vklass",
        }

    def _child(self) -> dict:
        return _find_child(self.coordinator, self._child_name) or {}


class VklassMealSensor(_VklassBaseSensor):
    """Today's lunch/meal."""

    @property
    def unique_id(self) -> str:
        return f"vklass_{self._child_slug}_meal"

    @property
    def name(self) -> str:
        return "Meal"

    @property
    def icon(self) -> str:
        return "mdi:food"

    @property
    def native_value(self) -> str:
        return self._child().get("meal") or "Not listed"


class VklassGymSensor(_VklassBaseSensor):
    """Gym class indicator: today | tomorrow | none."""

    @property
    def unique_id(self) -> str:
        return f"vklass_{self._child_slug}_gym_class"

    @property
    def name(self) -> str:
        return "Gym class"

    @property
    def icon(self) -> str:
        return "mdi:run"

    @property
    def native_value(self) -> str:
        return self._child().get("gymclass", "none")


class VklassNotificationSensor(_VklassBaseSensor):
    """Unread notification count."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "notifications"

    @property
    def unique_id(self) -> str:
        return f"vklass_{self._child_slug}_notifications"

    @property
    def name(self) -> str:
        return "Notifications"

    @property
    def icon(self) -> str:
        return "mdi:bell"

    @property
    def native_value(self) -> int:
        return self._child().get("notifications", 0)


class VklassScheduleSensor(_VklassBaseSensor):
    """Number of events today; full schedule in attributes."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "events"

    @property
    def unique_id(self) -> str:
        return f"vklass_{self._child_slug}_schedule"

    @property
    def name(self) -> str:
        return "Schedule"

    @property
    def icon(self) -> str:
        return "mdi:calendar-today"

    @property
    def native_value(self) -> int:
        return len(self._child().get("calendar", []))

    @property
    def extra_state_attributes(self) -> dict:
        calendar = sorted(
            self._child().get("calendar", []),
            key=lambda e: e.get("start", ""),
        )
        events = []
        for ev in calendar:
            start = _fmt_time(ev.get("start", ""))
            end = _fmt_time(ev.get("end", ""))
            events.append({"start": start, "end": end, "text": ev.get("text", "")})

        next_event = None
        now_iso = datetime.now(timezone.utc).isoformat()
        for ev in events:
            if ev["start"] >= now_iso[:5]:  # rough HH:MM compare
                next_event = ev
                break

        return {"events": events, "next_event": next_event}


def _fmt_time(iso: str) -> str:
    """Convert ISO datetime string to HH:MM, return as-is on failure."""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except Exception:
        return iso
