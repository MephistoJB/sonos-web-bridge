"""Constants for Sonos Web Bridge."""

DOMAIN = "sonos_web_bridge"

CONF_PSONO_MCP_URL = "psono_mcp_url"
CONF_PSONO_BEARER_TOKEN = "psono_bearer_token"
CONF_PSONO_BEARER_TOKEN_FILE = "psono_bearer_token_file"
CONF_SONOS_EMAIL_KEY = "sonos_email_key"
CONF_SONOS_PASSWORD_KEY = "sonos_password_key"
CONF_REFRESH_INTERVAL_HOURS = "refresh_interval_hours"
CONF_REFRESH_THRESHOLD_HOURS = "refresh_threshold_hours"

DEFAULT_PSONO_MCP_URL = "http://192.168.1.151:8091/mcp"
DEFAULT_SONOS_EMAIL_KEY = "SONOS_ACCOUNT_EMAIL"
DEFAULT_SONOS_PASSWORD_KEY = "SONOS_ACCOUNT_PASSWORD"
DEFAULT_REFRESH_INTERVAL_HOURS = 24
DEFAULT_REFRESH_THRESHOLD_HOURS = 48

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.session"

PLAY_SONOS_BASE = "https://play.sonos.com"
PLAY_SONOS_WEB_APP = f"{PLAY_SONOS_BASE}/de-de/web-app"
LOGIN_SONOS_BASE = "https://login.sonos.com"

