# Sonos Web Bridge

Sonos Web Bridge is a Home Assistant custom integration for browsing Apple Music through the Sonos Web API used by `play.sonos.com`.

It does not use Apple Music APIs, MusicKit, Music Assistant, Sonos favorites, or iframes. Apple Music access is performed through the user's existing Apple Music account inside Sonos.

## Status

Experimental. The Sonos Web API used here is not the public Sonos Control API and may change.

## HACS Installation

1. Open HACS.
2. Open custom repositories.
3. Add this repository URL as category `Integration`.
4. Install `Sonos Web Bridge`.
5. Restart Home Assistant.
6. Add the integration from Settings > Devices & Services.

## Configuration

The integration can read Sonos credentials from a Psono MCP server or accept credentials through the `sonos_web_bridge.login` service and `/api/sonos_web_bridge/login` endpoint.

Recommended Psono keys:

- `SONOS_ACCOUNT_EMAIL`
- `SONOS_ACCOUNT_PASSWORD`

Recommended local configuration for Codex/Home Assistant hosts with an existing Psono MCP token file:

```text
Psono MCP URL: http://192.168.1.151:8091/mcp
Psono bearer token file: /config/secrets/psono_mcp_bearer_token
Sonos email key: SONOS_ACCOUNT_EMAIL
Sonos password key: SONOS_ACCOUNT_PASSWORD
Refresh interval: 24 hours
Refresh threshold: 48 hours
```

The bearer token value itself should not be stored in Lovelace YAML or exposed to the frontend.

## API

Authenticated Home Assistant HTTP endpoints:

- `GET /api/sonos_web_bridge/status`
- `POST /api/sonos_web_bridge/login`
- `GET /api/sonos_web_bridge/discover`
- `GET /api/sonos_web_bridge/search?q=Die%20Eine&count=20`
- `GET /api/sonos_web_bridge/library/tracks?offset=0&count=100`

## Services

- `sonos_web_bridge.login`
- `sonos_web_bridge.refresh`
- `sonos_web_bridge.discover`
- `sonos_web_bridge.search`
- `sonos_web_bridge.library_tracks`

## Session Refresh

The integration checks the Sonos Web session at startup, refreshes it periodically, and retries once after authorization failures.

The default refresh behavior is:

- At Home Assistant startup: refresh only if the session is missing or close to expiry.
- Every 24 hours: run the same refresh check.
- On Sonos authorization errors: force one refresh and retry the request once.

The relevant Sonos Web cookie currently expires after roughly 10 days, so the default 48-hour threshold avoids unnecessary daily logins while still renewing before expiry.

## Frontend Use

The custom card should call this integration through Home Assistant's authenticated HTTP API, for example:

```text
/api/sonos_web_bridge/status
/api/sonos_web_bridge/login
/api/sonos_web_bridge/search?q=Die%20Eine&count=20
/api/sonos_web_bridge/library/tracks?offset=0&count=100
```

The frontend should not store Sonos credentials or session cookies.
