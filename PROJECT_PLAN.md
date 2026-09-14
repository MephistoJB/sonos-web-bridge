# Sonos Web Bridge Project Plan

## Goal

Build a Home Assistant compatible bridge that exposes the Apple Music account registered in Sonos through Sonos Web only.

The bridge must not use MusicKit, the Apple Music API, Music Assistant, Sonos favorites, or iframes.

## Current Milestone

- Public GitHub repository: `MephistoJB/sonos-web-bridge`
- HACS custom integration layout
- Home Assistant config flow
- Sonos credential setup in the Home Assistant integration
- Optional Psono-backed credential lookup for existing local test setups
- Browserless Sonos Web login
- Periodic session refresh inside Home Assistant
- Home Assistant services and authenticated HTTP endpoints for:
  - status
  - login
  - discover
  - search
  - library tracks

## Proven Live Checks

- HACS installs the integration.
- Home Assistant loads the config entry.
- Sonos Web login works without Apple API credentials.
- Psono fallback was proven from `/config/secrets/psono_mcp_bearer_token` during local testing.
- Apple Music registration is discovered through Sonos:
  - `serviceId`: `52231`
  - `accountId`: `5`
  - `integrationId`: `com.apple.sonos-music`
- Library browsing returns the user's Apple Music library through Sonos.
- Search returns playable Apple Music tracks through Sonos.

## Next Milestone

Wire the custom Sonos card to this bridge:

- Show a Sonos Login button only when `/api/sonos_web_bridge/status` is unauthenticated.
- Prefer the Home Assistant integration setup credentials for login and refresh.
- Submit credentials to `/api/sonos_web_bridge/login` only as a manual fallback.
- List library tracks from `/api/sonos_web_bridge/library/tracks`.
- Search via `/api/sonos_web_bridge/search`.
- Keep credentials and cookies out of Lovelace config and browser storage.

## Playback Strategy

The bridge currently returns Sonos content objects with `ACTION_PLAY`. The next task is to verify the cleanest playback path:

- Prefer Home Assistant's native Sonos `media_player.play_media` path if it accepts the Sonos content identifiers returned by the bridge.
- If native playback cannot consume those identifiers, add a Sonos-Web-only playback endpoint to the bridge after tracing the matching `play.sonos.com` queue/play request.

## Release Notes

- `v0.1.1`: Mask Psono bearer token input in the config flow.
- `v0.1.2`: Read token file outside the HA event loop and accept JSON array responses.
- `v0.1.3`: Handle Sonos discovery arrays consistently.
- `v0.1.4`: Ask for Sonos credentials in the Home Assistant integration setup.
