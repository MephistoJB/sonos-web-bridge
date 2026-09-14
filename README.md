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

The integration asks for the Sonos account credentials during setup:

```text
Sonos email: your Sonos account email
Sonos password: your Sonos account password
Refresh interval: 24 hours
Refresh threshold: 48 hours
```

The password is entered through a Home Assistant password selector. It is used only by the backend integration for the browserless Sonos Web login and refresh.

Psono-backed credential lookup remains available as a fallback for existing local test setups, but it is not the normal installation path.

## API

Authenticated Home Assistant HTTP endpoints:

- `GET /api/sonos_web_bridge/status`
- `POST /api/sonos_web_bridge/login`
- `GET /api/sonos_web_bridge/discover`
- `GET /api/sonos_web_bridge/search?q=Die%20Eine&count=20`
- `GET /api/sonos_web_bridge/library/tracks?offset=0&count=100`
- `GET /api/sonos_web_bridge/library/resources?object_id=libraryfolder%3Af.3&offset=0&count=100`

## Home Assistant Media Browser

The integration also exposes a Home Assistant media source named `Sonos Web Bridge`.

The media source currently supports:

- Browsing Apple Music through a native Home Assistant media source.
- Showing an Apple Music > Mediathek structure.
- Browsing Sonos library containers such as titles, albums, artists, and playlists where Sonos exposes them.
- Paginating through large library containers.
- Searching Apple Music through Sonos.
- Playing library tracks on Home Assistant Sonos media players by resolving Sonos content IDs to Sonos playback URIs.

## Services

- `sonos_web_bridge.login`
- `sonos_web_bridge.refresh`
- `sonos_web_bridge.discover`
- `sonos_web_bridge.search`
- `sonos_web_bridge.library_tracks`
- `sonos_web_bridge.library_resources`
- `sonos_web_bridge.play_media`

`sonos_web_bridge.play_media` accepts a Home Assistant Sonos `media_player` entity and a Sonos Web Bridge track id, including a full `media-source://sonos_web_bridge/track/...` id from the media browser.

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

For playback, call the Home Assistant service `sonos_web_bridge.play_media` with the selected player entity and the selected media source track id. The frontend should not store Sonos credentials or session cookies.

For a Home Assistant-native browsing experience, prefer the `Sonos Web Bridge` media source in the Home Assistant Media Browser.
