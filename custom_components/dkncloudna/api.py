"""DKN Cloud NA API client."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ContentTypeError
import socketio

from .const import (
    API_INSTALLATIONS,
    API_IS_LOGGED_IN,
    API_LOGIN,
    API_REFRESH_TOKEN,
    API_SOCKET_PATH,
    API_USERS_NAMESPACE,
    BASE_URL,
    LOGGER,
    REQUEST_TIMEOUT,
    SOCKET_RECONNECT_ATTEMPTS,
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
        self._socket: socketio.AsyncClient | None = None
        self._socket_installations: set[str] = set()
        self._desired_socket_installations: set[str] = set()
        self._socket_token: str | None = None
        self._socket_lock = asyncio.Lock()
        self._socket_data_callback: (
            Callable[[str, dict[str, Any]], Awaitable[None]] | None
        ) = None
        self._socket_refresh_callback: Callable[[], Awaitable[None]] | None = None
        self._last_command_ack: dict[str, Any] | None = None
        self._recent_socket_events: deque[dict[str, Any]] = deque(maxlen=20)

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
                auth_error_statuses={401, 403, 404},
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
            auth_error_statuses={400, 401, 403, 404},
        )
        self._store_tokens(data)

    async def fetch_installations(self) -> list[dict[str, Any]]:
        """Return all installations and their devices."""
        data = await self._request(
            "GET",
            API_INSTALLATIONS,
            require_auth=True,
            retry_on_auth=True,
            auth_error_statuses={401, 403, 404},
        )
        if not isinstance(data, list):
            raise DknConnectionError("Unexpected installations response")
        return data

    async def ensure_socket_connection(
        self,
        installations: list[dict[str, Any]],
        data_callback: Callable[[str, dict[str, Any]], Awaitable[None]],
        refresh_callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Connect Socket.IO listeners for installation device-data updates."""
        installation_ids = {
            str(installation.get("_id") or "").strip()
            for installation in installations
            if installation.get("_id")
        }
        async with self._socket_lock:
            self._socket_data_callback = data_callback
            self._socket_refresh_callback = refresh_callback
            self._desired_socket_installations = installation_ids

            if not installation_ids:
                await self._disconnect_socket_locked()
                return

            reconnect_required = (
                self._socket is None
                or not self._socket.connected
                or self._socket_token != self.token
                or self._socket_installations != installation_ids
            )
            if not reconnect_required:
                return

            await self._disconnect_socket_locked()

            await self._connect_socket_locked(installation_ids)

    async def _connect_socket_locked(self, installation_ids: set[str]) -> bool:
        """Connect a Socket.IO client while holding the socket lock."""
        if not installation_ids:
            return False

        if not self.token:
            raise DknAuthError("Missing access token")

        sio = socketio.AsyncClient(
            logger=False,
            engineio_logger=False,
            reconnection=True,
            reconnection_attempts=SOCKET_RECONNECT_ATTEMPTS,
        )

        self._register_socket_handlers(sio, installation_ids)

        namespaces = [
            API_USERS_NAMESPACE,
            *self._installation_namespaces(installation_ids),
        ]
        try:
            await sio.connect(
                BASE_URL,
                headers={"Authorization": f"Bearer {self.token}"},
                transports=["polling", "websocket"],
                socketio_path=API_SOCKET_PATH.strip("/"),
                namespaces=namespaces,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("DKN socket connect failed: %s", err)
            await sio.disconnect()
            return False

        self._socket = sio
        self._socket_installations = installation_ids
        self._socket_token = self.token
        return True

    async def _ensure_socket_ready_for_write_locked(self, installation_id: str) -> None:
        """Reconnect Socket.IO on demand before sending a control event."""
        namespace = self._installation_namespace(installation_id)
        socket = self._socket
        if socket is not None and socket.connected and namespace in socket.namespaces:
            return

        desired_installations = set(self._desired_socket_installations)
        desired_installations.add(installation_id)
        self._desired_socket_installations = desired_installations

        await self._disconnect_socket_locked()
        await self._connect_socket_locked(desired_installations)

    async def disconnect_socket(self) -> None:
        """Disconnect the Socket.IO client if it is connected."""
        async with self._socket_lock:
            await self._disconnect_socket_locked()

    async def async_send_machine_event(
        self,
        installation_id: str,
        mac: str,
        property_name: str,
        value: Any,
    ) -> None:
        """Send a device control event over Socket.IO."""
        async with self._socket_lock:
            namespace = self._installation_namespace(installation_id)
            await self._ensure_socket_ready_for_write_locked(installation_id)

            socket = self._socket
            if socket is None or not socket.connected:
                raise DknConnectionError("Socket not connected")
            if namespace not in socket.namespaces:
                raise DknConnectionError(
                    f"Socket namespace unavailable for installation {installation_id}"
                )

            payload = {"mac": mac, "property": property_name, "value": value}
            LOGGER.debug("DKN socket send %s %s", namespace, payload)
            try:
                ack = None
                await socket.emit("create-machine-event", payload, namespace=namespace)
                self._last_command_ack = {
                    "namespace": namespace,
                    "payload": payload,
                    "ack": ack,
                }
                LOGGER.debug("DKN socket ack %s %s", namespace, ack)
            except Exception as err:  # noqa: BLE001
                raise DknConnectionError(str(err) or type(err).__name__) from err

    def pop_last_command_debug(self) -> dict[str, Any] | None:
        """Return and clear the latest command ack plus recent socket events."""
        if self._last_command_ack is None and not self._recent_socket_events:
            return None
        debug = {
            "last_command_ack": self._last_command_ack,
            "recent_socket_events": list(self._recent_socket_events),
        }
        self._last_command_ack = None
        self._recent_socket_events.clear()
        return debug

    async def _disconnect_socket_locked(self) -> None:
        """Disconnect the Socket.IO client while holding the socket lock."""
        socket = self._socket
        self._socket = None
        self._socket_installations = set()
        self._socket_token = None
        if socket is not None:
            try:
                await socket.disconnect()
            except Exception:  # noqa: BLE001
                pass

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

    def _register_socket_handlers(
        self,
        sio: socketio.AsyncClient,
        installation_ids: set[str],
    ) -> None:
        """Register Socket.IO event handlers for the active installations."""

        @sio.on("control-new-device", namespace=API_USERS_NAMESPACE)
        async def _on_new_device(_: Any) -> None:
            self._record_socket_event(API_USERS_NAMESPACE, "control-new-device", _)
            await self._request_socket_refresh()

        @sio.on("control-deleted-device", namespace=API_USERS_NAMESPACE)
        async def _on_deleted_device(_: Any) -> None:
            self._record_socket_event(API_USERS_NAMESPACE, "control-deleted-device", _)
            await self._request_socket_refresh()

        @sio.on("control-deleted-installation", namespace=API_USERS_NAMESPACE)
        async def _on_deleted_installation(_: Any) -> None:
            self._record_socket_event(
                API_USERS_NAMESPACE, "control-deleted-installation", _
            )
            await self._request_socket_refresh()

        for installation_id in installation_ids:
            namespace = self._installation_namespace(installation_id)

            @sio.on("device-data", namespace=namespace)
            async def _on_device_data(
                message: Any, *, _namespace: str = namespace
            ) -> None:
                self._record_socket_event(_namespace, "device-data", message)
                if not isinstance(message, dict):
                    return
                mac = str(message.get("mac") or "").strip().lower()
                data = message.get("data")
                if not mac or not isinstance(data, dict):
                    return
                installation_id = _namespace.split("/", 1)[1].split("::", 1)[0]
                if self._socket_data_callback is not None:
                    await self._socket_data_callback(
                        mac, {**data, "_installation_id": installation_id}
                    )

    async def _request_socket_refresh(self) -> None:
        """Request a coordinator refresh after a socket topology change."""
        if self._socket_refresh_callback is not None:
            await self._socket_refresh_callback()

    def _installation_namespaces(self, installation_ids: set[str]) -> list[str]:
        """Return sorted Socket.IO namespaces for installations."""
        return [
            self._installation_namespace(installation_id)
            for installation_id in sorted(installation_ids)
        ]

    def _installation_namespace(self, installation_id: str) -> str:
        """Return the Socket.IO namespace for one installation."""
        return f"/{installation_id}::dknUsa"

    def _record_socket_event(self, namespace: str, event: str, payload: Any) -> None:
        """Track recent socket events for write debugging."""
        self._recent_socket_events.append(
            {"namespace": namespace, "event": event, "payload": payload}
        )

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

        if response.status >= 400:
            LOGGER.warning(
                "DKN API error %s %s status=%s body=%s",
                method,
                url,
                response.status,
                data if not isinstance(data, str) or len(data) < 200 else data[:200],
            )
        else:
            LOGGER.debug("DKN response %s %s status=%s", method, url, response.status)

        if response.status in (auth_error_statuses or set()):
            if retry_on_auth and self.refresh_token:
                LOGGER.info("DKN token expired, attempting refresh")
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
