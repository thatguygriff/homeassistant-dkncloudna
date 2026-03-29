"""Config flow for DKN Cloud NA."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DknAuthError, DknCloudNaClient, DknConnectionError
from .const import (
    CONF_EXPOSE_PII,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
        vol.Optional(CONF_EXPOSE_PII, default=False): cv.boolean,
    }
)


class DknConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for DKN Cloud NA.

    Steps:
      user → (optionally) token_display → entry created
    Reauth: reauth_confirm → updates token in options
    """

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._expose_pii: bool = False
        self._token: str = ""
        self._refresh_token: str = ""

    @staticmethod
    def async_get_options_flow(
        entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return DknOptionsFlow(entry)

    # ------------------------------------------------------------------
    # Step 1: credentials
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL, "")).strip()
            password = str(user_input.get(CONF_PASSWORD, ""))

            if not email or not password:
                errors["base"] = "invalid_auth"
            else:
                normalized = email.casefold()
                await self.async_set_unique_id(normalized)
                self._abort_if_unique_id_configured()

                session = async_get_clientsession(self.hass)
                client = DknCloudNaClient(email, session, password=password, token=None)
                try:
                    await asyncio.wait_for(client.login(), timeout=60.0)
                except TimeoutError:
                    errors["base"] = "timeout"
                except DknAuthError:
                    errors["base"] = "invalid_auth"
                except DknConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during login")
                    errors["base"] = "unknown"
                finally:
                    client.clear_password()

                if not errors:
                    self._email = email
                    self._scan_interval = int(
                        user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    )
                    self._expose_pii = bool(user_input.get(CONF_EXPOSE_PII, False))
                    self._token = client.token or ""
                    self._refresh_token = client.refresh_token or ""

                    if self._expose_pii:
                        return await self.async_step_token_display()
                    return self._create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2 (optional): show tokens to user
    # ------------------------------------------------------------------

    async def async_step_token_display(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show retrieved tokens read-only, then create the entry."""
        if user_input is not None:
            return self._create_entry()

        schema = vol.Schema(
            {
                vol.Optional("access_token_display", default=self._token): cv.string,
                vol.Optional(
                    "refresh_token_display", default=self._refresh_token
                ): cv.string,
            }
        )
        return self.async_show_form(
            step_id="token_display",
            data_schema=schema,
            errors={},
        )

    def _create_entry(self) -> config_entries.FlowResult:
        return self.async_create_entry(
            title=self._email,
            data={"username": self._email},
            options={
                CONF_USER_TOKEN: self._token,
                CONF_REFRESH_TOKEN: self._refresh_token,
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_EXPOSE_PII: self._expose_pii,
            },
        )

    # ------------------------------------------------------------------
    # Reauth
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.FlowResult:
        self._reauth_entry_id = (self.context or {}).get("entry_id")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        entry = None
        if getattr(self, "_reauth_entry_id", None):
            entry = self.hass.config_entries.async_get_entry(self._reauth_entry_id)
        if entry is None:
            entries = self.hass.config_entries.async_entries(DOMAIN)
            entry = entries[0] if len(entries) == 1 else None
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        username = entry.data.get("username", "")
        schema = vol.Schema({vol.Required(CONF_PASSWORD): cv.string})
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = DknCloudNaClient(
                username, session, password=str(user_input[CONF_PASSWORD])
            )
            try:
                await asyncio.wait_for(client.login(), timeout=60.0)
            except TimeoutError:
                errors["base"] = "timeout"
            except DknAuthError:
                errors["base"] = "invalid_auth"
            except DknConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            finally:
                client.clear_password()

            if not errors:
                new_opts = dict(entry.options)
                new_opts[CONF_USER_TOKEN] = client.token or ""
                new_opts[CONF_REFRESH_TOKEN] = client.refresh_token or ""
                self.hass.config_entries.async_update_entry(entry, options=new_opts)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"username": username},
        )


class DknOptionsFlow(config_entries.OptionsFlow):
    """Options flow: scan interval + PII toggle."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        opts = self._entry.options
        defaults = {
            CONF_SCAN_INTERVAL: int(
                opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            CONF_EXPOSE_PII: bool(opts.get(CONF_EXPOSE_PII, False)),
        }
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Optional(
                    CONF_EXPOSE_PII, default=defaults[CONF_EXPOSE_PII]
                ): cv.boolean,
            }
        )

        if user_input is not None:
            # Preserve hidden keys (tokens) when updating options
            next_opts = dict(self._entry.options)
            next_opts[CONF_SCAN_INTERVAL] = int(
                user_input.get(CONF_SCAN_INTERVAL, defaults[CONF_SCAN_INTERVAL])
            )
            next_opts[CONF_EXPOSE_PII] = bool(
                user_input.get(CONF_EXPOSE_PII, defaults[CONF_EXPOSE_PII])
            )
            return self.async_create_entry(title="", data=next_opts)

        return self.async_show_form(step_id="init", data_schema=schema, errors={})
