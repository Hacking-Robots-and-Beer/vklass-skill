"""Config flow — lets users set up Vklass via the HA UI."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from bs4 import BeautifulSoup
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import AUTH_BASE, CONF_PASSWORD, CONF_USERNAME, DOMAIN, USER_AGENT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _test_credentials(hass: HomeAssistant, username: str, password: str) -> str | None:
    """Return None on success, or an error key string on failure."""
    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(
        cookie_jar=jar,
        headers={"User-Agent": USER_AGENT},
    ) as session:
        try:
            # Fetch login page for token
            async with session.get(
                f"{AUTH_BASE}/credentials", timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                resp.raise_for_status()
                html = await resp.text()

            soup = BeautifulSoup(html, "html.parser")
            token_input = soup.find("input", {"name": "__RequestVerificationToken"})
            if not token_input:
                return "cannot_connect"

            token = token_input["value"]

            async with session.post(
                f"{AUTH_BASE}/credentials/signin",
                data={
                    "username": username,
                    "password": password,
                    "__RequestVerificationToken": token,
                },
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status not in (302, 200):
                    return "invalid_auth"

        except aiohttp.ClientError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during Vklass credential test")
            return "unknown"

    return None


class VklassConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Vklass config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            error_key = await _test_credentials(self.hass, username, password)
            if error_key:
                errors["base"] = error_key
            else:
                return self.async_create_entry(
                    title=f"Vklass ({username})",
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
