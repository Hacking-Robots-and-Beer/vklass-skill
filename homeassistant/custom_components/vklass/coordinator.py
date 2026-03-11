"""Data coordinator — authenticates with Vklass and refreshes every 30 min."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import aiohttp
from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AUTH_BASE, CUSTODIAN_BASE, DOMAIN, UPDATE_INTERVAL_MINUTES, USER_AGENT

_LOGGER = logging.getLogger(__name__)


class VklassCoordinator(DataUpdateCoordinator):
    """Fetches and caches Vklass data for all children."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._username = username
        self._password = password

    async def _async_update_data(self) -> dict:
        """Fetch fresh data from Vklass. Called by the coordinator framework."""
        jar = aiohttp.CookieJar()
        connector = aiohttp.TCPConnector(ssl=True)
        async with aiohttp.ClientSession(
            cookie_jar=jar,
            connector=connector,
            headers={"User-Agent": USER_AGENT},
        ) as session:
            try:
                await self._authenticate(session)
                students = await self._parse_students(session)
                notifications = await self._fetch_notifications(session)
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Network error: {err}") from err
            except ValueError as err:
                raise UpdateFailed(str(err)) from err

            children = []
            for student in students:
                student_id = student["id"]
                calendar = await self._fetch_calendar(session, student_id) if student_id else []
                children.append(
                    {
                        "name": student["name"],
                        "meal": student["meal"],
                        "gymclass": self._detect_gymclass(calendar),
                        "calendar": calendar,
                        "notifications": notifications,
                    }
                )

            return {"children": children}

    # ------------------------------------------------------------------ auth

    async def _get_verification_token(self, session: aiohttp.ClientSession) -> str:
        async with session.get(f"{AUTH_BASE}/credentials", timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token_input:
            raise ValueError("Could not find __RequestVerificationToken in Vklass login page")
        return token_input["value"]

    async def _authenticate(self, session: aiohttp.ClientSession) -> None:
        token = await self._get_verification_token(session)
        async with session.post(
            f"{AUTH_BASE}/credentials/signin",
            data={
                "username": self._username,
                "password": self._password,
                "__RequestVerificationToken": token,
            },
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status not in (200, 302):
                raise ValueError(f"Authentication failed (HTTP {resp.status}). Check your credentials.")

    # --------------------------------------------------------------- parsing

    async def _parse_students(self, session: aiohttp.ClientSession) -> list[dict]:
        # The Absence/Notify page reliably lists all wards with IDs and names in a
        # server-rendered JSON blob used to populate the student picker form.
        # Pattern: "fullName":"Sam","disabled":false,...,"value":"348307"
        async with session.get(
            f"{CUSTODIAN_BASE}/Absence/Notify", timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            resp.raise_for_status()
            html = await resp.text()

        students: list[dict] = []
        seen_ids: set[str] = set()

        for m in re.finditer(r'"fullName"\s*:\s*"([^"]+)"[^}]{0,300}"value"\s*:\s*"(\d{4,})"', html):
            name, sid = m.group(1), m.group(2)
            if sid not in seen_ids:
                seen_ids.add(sid)
                students.append({"id": sid, "name": name, "meal": ""})

        return students

    async def _fetch_calendar(self, session: aiohttp.ClientSession, student_id: str) -> list[dict]:
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=2)

        async with session.post(
            f"{CUSTODIAN_BASE}/Events/FullCalendar",
            data={
                "students": student_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if not resp.ok:
                return []
            try:
                events_raw = await resp.json(content_type=None)
            except Exception:
                return []

        if not isinstance(events_raw, list):
            return []

        return [
            {
                "start": ev.get("start", ""),
                "end": ev.get("end", ""),
                "text": ev.get("title", ev.get("text", ev.get("name", ""))),
            }
            for ev in events_raw
        ]

    async def _fetch_notifications(self, session: aiohttp.ClientSession) -> int:
        async with session.get(
            f"{CUSTODIAN_BASE}/Account/Scoreboard",
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if not resp.ok:
                return 0
            try:
                data = await resp.json(content_type=None)
            except Exception:
                return 0

        if isinstance(data, int):
            return data
        if isinstance(data, dict):
            return int(data.get("notifications", data.get("unread", data.get("count", 0))))
        return 0

    # ----------------------------------------------------------------- utils

    @staticmethod
    def _detect_gymclass(calendar: list[dict]) -> str:
        gym_keywords = ["idrott", "gym", "pe ", "sport", "idrottslektion"]
        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)

        for ev in calendar:
            if any(kw in ev.get("text", "").lower() for kw in gym_keywords):
                try:
                    ev_date = datetime.fromisoformat(ev["start"]).date()
                    if ev_date == today:
                        return "today"
                    if ev_date == tomorrow:
                        return "tomorrow"
                except Exception:
                    pass
        return "none"
