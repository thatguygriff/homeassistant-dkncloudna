"""DKN Cloud NA API client."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ContentTypeError

from .const import (
    API_INSTALLATIONS,
    API_IS_LOGGED_IN,
    API_LOGIN,
    API_REFRESH_TOKEN,
    BASE_URL,
    LOGGER,
    REQUEST_TIMEOUT,
    USER_AGENT,
)


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
        """Exchange email+password for access and refresh tokens."""
        if not self._password:
            raise DknAuthError("Missing password")

        data = await self._request(
            "POST",
            API_LOGIN,
            json_body={"email": self._username, "password": self._password},
            auth_error_statuses={400, 401, 403},
        )
        self._store_tokens(data)

    async def is_logged_in(self) -> bool:
        """Return True if the current token is still valid."""
        try:
            await self._request(
                "GET",
                API_IS_LOGGED_IN,
                require_auth=True,
                auth_error_statuses={401, 403},
            )
        except DknAuthError:
            return False

        return True

    async def refresh_access_token(self) -> None:
        """Use the refresh token to obtain a new access token."""
        if not self.refresh_token:
            raise DknAuthError("Missing refresh token")

        data = await self._request(
            "GET",
            API_REFRESH_TOKEN.format(refresh_token=self.refresh_token),
            require_auth=bool(self.token),
            auth_error_statuses={400, 401, 403},
        )
        self._store_tokens(data)

    async def fetch_installations(self) -> list[dict[str, Any]]:
        """Return all installations and their devices."""
        data = await self._request(
            "GET",
            API_INSTALLATIONS,
            require_auth=True,
            retry_on_auth=True,
            auth_error_statuses={401, 403},
        )
        if not isinstance(data, list):
            raise DknConnectionError("Unexpected installations response")
        return data

    def _store_tokens(self, data: Any) -> None:
        """Persist access and refresh tokens from an API response."""
        if not isinstance(data, dict):
            raise DknConnectionError("Unexpected authentication response")

        token = data.get("token")
        refresh_token = data.get("refreshToken")
        if not isinstance(token, str) or not token:
            raise DknConnectionError("Authentication response missing token")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise DknConnectionError("Authentication response missing refresh token")

        self.token = token
        self.refresh_token = refresh_token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        require_auth: bool = False,
        retry_on_auth: bool = False,
        auth_error_statuses: set[int] | None = None,
    ) -> Any:
        """Perform an API request and decode the response body."""
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if require_auth:
            if not self.token:
                raise DknAuthError("Missing access token")
            headers["Authorization"] = f"Bearer {self.token}"

        url = f"{BASE_URL}{path}"
        safe_body = {
            key: ("***" if key == "password" else value)
            for key, value in (json_body or {}).items()
        }
        LOGGER.debug("DKN request %s %s body=%s", method, url, safe_body or None)

        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                data = await self._read_response(response)
        except asyncio.TimeoutError as err:
            raise DknConnectionError("Request timed out") from err
        except ClientError as err:
            raise DknConnectionError(str(err) or type(err).__name__) from err

        LOGGER.debug("DKN response %s %s status=%s", method, url, response.status)

        if response.status in (auth_error_statuses or set()):
            if retry_on_auth and self.refresh_token:
                await self.refresh_access_token()
                return await self._request(
                    method,
                    path,
                    json_body=json_body,
                    require_auth=require_auth,
                    retry_on_auth=False,
                    auth_error_statuses=auth_error_statuses,
                )
            raise DknAuthError(self._error_message(data, response))

        if response.status >= 400:
            raise DknConnectionError(self._error_message(data, response))

        return data

    async def _read_response(self, response: ClientResponse) -> Any:
        """Decode a JSON response body, falling back to text."""
        try:
            return await response.json(content_type=None)
        except ContentTypeError:
            return await response.text()

    def _error_message(self, data: Any, response: ClientResponse) -> str:
        """Build a useful error message from an API response."""
        if isinstance(data, dict):
            for key in ("message", "error", "detail"):
                value = data.get(key)
                if isinstance(value, str) and value:
                    return value
        if isinstance(data, str) and data:
            return data
        return f"HTTP {response.status}: {response.reason}"

    def __repr__(self) -> str:
        first = self._username[0] if self._username else "?"
        token_state = "set" if self.token else "none"
        return f"DknCloudNaClient(u={first}***, token={token_state})"
