"""Constants for DKN Cloud NA integration."""

from __future__ import annotations

import logging

DOMAIN = "dkncloudna"
LOGGER = logging.getLogger(__package__)
MANUFACTURER = "Daikin"

# API
BASE_URL = "https://dkncloudna.com"
API_BASE = "/api/v1"
API_LOGIN = f"{API_BASE}/auth/login/dknUsa"
API_IS_LOGGED_IN = f"{API_BASE}/users/isLoggedIn/dknUsa"
API_REFRESH_TOKEN = f"{API_BASE}/auth/refreshToken/{{refresh_token}}/dknUsa"
API_INSTALLATIONS = f"{API_BASE}/installations/dknUsa"
API_SOCKET_PATH = f"{API_BASE}/devices/socket.io/"
API_USERS_NAMESPACE = "/users"

# The DKN Cloud NA API requires a mobile-like User-Agent.
# This matches what the official DKN Cloud NA iOS app sends.
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)

REQUEST_TIMEOUT = 30  # seconds
SOCKET_RECONNECT_ATTEMPTS = 5

# Config/options keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_EXPOSE_PII = "expose_pii"
CONF_USER_TOKEN = "user_token"
CONF_REFRESH_TOKEN = "refresh_token"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 300

# Optimistic overlay: how long to hold a locally-set value before trusting
# the next coordinator refresh. Must exceed the write→cloud→poll round-trip.
OPTIMISTIC_TTL_SEC: float = 2.5

# Post-write coordinator refresh: coalesced delay after a device command.
POST_WRITE_REFRESH_DELAY_SEC: float = 1.0

# Device modes (from homebridge plugin src/types.ts)
# DeviceMode: 1=Auto, 2=Cool, 3=Heat, 4=Fan, 5=Dry
DEVICE_MODE_AUTO = 1
DEVICE_MODE_COOL = 2
DEVICE_MODE_HEAT = 3
DEVICE_MODE_FAN = 4
DEVICE_MODE_DRY = 5

# Fan speeds (SpeedState)
SPEED_AUTO = 0
SPEED_20 = 2
SPEED_40 = 3
SPEED_60 = 4
SPEED_80 = 5
SPEED_100 = 6

# Temperature units
TEMP_CELSIUS = 0
TEMP_FAHRENHEIT = 1
