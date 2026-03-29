"""DKN Cloud NA API client stub.

Real HTTP calls are implemented in a future phase. This stub defines the
interface and returns hardcoded data so the rest of the integration can be
developed and tested without live credentials.
"""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession

from .const import LOGGER


class DknAuthError(Exception):
    """Raised when authentication fails (401)."""


class DknConnectionError(Exception):
    """Raised when the API cannot be reached."""


class DknCloudNaClient:
    """Async client for the DKN Cloud NA REST API.

    Instantiated once per config entry. Password is cleared after login and
    never stored beyond the initial token exchange.
    """

    def __init__(
        self,
        username: str,
        session: ClientSession,
        *,
        password: str | None = None,
        token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._username = username
        self._session = session
        self._password = password
        self.token = token
        self.refresh_token = refresh_token

    def clear_password(self) -> None:
        """Discard password from memory after token exchange."""
        self._password = None

    async def login(self) -> None:
        """Exchange email+password for access and refresh tokens.

        Sets self.token and self.refresh_token on success.
        Raises DknAuthError on bad credentials, DknConnectionError on network failure.
        """
        # TODO: implement real POST to API_LOGIN
        LOGGER.debug("DknCloudNaClient.login() stub called for %s", self._username)
        raise NotImplementedError("login() not yet implemented")

    async def is_logged_in(self) -> bool:
        """Return True if the current token is still valid."""
        # TODO: implement real GET to API_IS_LOGGED_IN
        raise NotImplementedError("is_logged_in() not yet implemented")

    async def refresh_access_token(self) -> None:
        """Use the refresh token to obtain a new access token.

        Updates self.token on success.
        Raises DknAuthError if the refresh token is also expired.
        """
        # TODO: implement real GET to API_REFRESH_TOKEN
        raise NotImplementedError("refresh_access_token() not yet implemented")

    async def fetch_installations(self) -> list[dict[str, Any]]:
        """Return all installations and their devices.

        Each installation contains a list of DeviceInfo dicts.
        Returns stub data for scaffolding.
        """
        LOGGER.debug("DknCloudNaClient.fetch_installations() stub — returning fake data")
        return [
            {
                "_id": "stub-installation-1",
                "name": "My Home",
                "devices": [
                    {
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "name": "Living Room AC",
                        "power": False,
                        "mode": 1,
                        "real_mode": 1,
                        "work_temp": 22.0,
                        "ext_temp": 18.0,
                        "units": 0,
                        "setpoint_air_auto": 22.0,
                        "setpoint_air_cool": 24.0,
                        "setpoint_air_heat": 20.0,
                        "range_sp_auto_air_min": 16,
                        "range_sp_auto_air_max": 32,
                        "range_sp_cool_air_min": 16,
                        "range_sp_cool_air_max": 32,
                        "range_sp_hot_air_min": 16,
                        "range_sp_hot_air_max": 32,
                        "speed_state": 0,
                        "speed_available": [0, 2, 3, 4, 5, 6],
                        "slats_vertical_1": 0,
                        "machineready": True,
                        "isConnected": True,
                        "tsensor_error": False,
                        "stat_rssi": -65,
                        "stat_ssid": "MyWiFi",
                        "version": "1.0.0",
                        "error_value": 0,
                        "error_ascii1": "",
                        "error_ascii2": "",
                    }
                ],
            }
        ]

    def __repr__(self) -> str:
        first = self._username[0] if self._username else "?"
        token_state = "set" if self.token else "none"
        return f"DknCloudNaClient(u={first}***, token={token_state})"
