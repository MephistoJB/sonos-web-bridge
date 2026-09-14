# Sonos Web Bridge

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MephistoJB&repository=sonos-web-bridge&category=integration)

Sonos Web Bridge is a Home Assistant custom integration that exposes Apple Music content through the Sonos Web API used by `play.sonos.com`.

The integration is intentionally Sonos-only. It does not use the Apple Music API, MusicKit, Music Assistant, Sonos favorites, or an iframe. Apple Music access works through the Apple Music account that is already linked inside the user's Sonos household.

## Current Scope

This release is focused on Apple Music in Sonos.

Supported today:

- Browserless Sonos sign-in from the Home Assistant config flow.
- Periodic Sonos Web session refresh.
- Home Assistant media source named `Sonos Web Bridge`.
- Apple Music root view with `Personal Mediathek`, `Apple Music Library`, and Sonos browse entry points such as Browse Our Picks, Featured Playlists, Daily Top 100, radio, and genre stations.
- Personal library browsing for titles, albums, artists, and playlists where Sonos exposes those containers.
- Search through Sonos catalog search plus a bounded personal-library fallback.
- Playback of Sonos Apple Music track IDs on Home Assistant Sonos media players.

Not supported today:

- Music services other than Apple Music.
- Playback on non-Sonos players such as the Home Assistant web browser player.
- Direct Apple Music API or MusicKit access.
- Multi-factor or interactive Sonos login flows that cannot be completed by the browserless Okta flow.

## Installation

### HACS

1. Click the HACS button at the top of this README.
2. Open the repository in HACS and add it as category `Integration`.
3. Download `Sonos Web Bridge`.
4. Restart Home Assistant.
5. Go to **Settings > Devices & services > Add integration**.
6. Search for `Sonos Web Bridge`.
7. Enter the Sonos account credentials for the household where Apple Music is already configured.

### Manual

1. Copy `custom_components/sonos_web_bridge` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add `Sonos Web Bridge` from **Settings > Devices & services**.

## Configuration

The config flow asks for:

- Sonos email
- Sonos password
- Refresh interval in hours, default `24`
- Refresh threshold in hours, default `48`

The Sonos password is stored by Home Assistant as config-entry data and is used only by the integration backend for login and refresh. The frontend never stores Sonos credentials or Sonos Web cookies.

The options flow also contains Psono fields for private local test setups. They are optional and are not required for normal HACS installation.

## Session Refresh

At startup, and then every refresh interval, the integration checks whether the stored Sonos Web session is missing or close to expiry. If the session needs renewal, it logs in through Sonos again and stores the updated cookies in Home Assistant storage.

Every Sonos API call also has a reactive fallback: on an authorization failure, the integration forces one refresh and retries the original request once.

## Media Browser

Open **Media > Sonos Web Bridge > Apple Music**.

The first level contains:

- `Personal Mediathek`: direct shortcuts to personal titles, albums, artists, and playlists.
- `Apple Music Library`: the Sonos/Apple library root, including nodes such as `Recently Added`.
- Sonos browse pages such as `Browse Our Picks`, `Featured Playlists`, `Daily Top 100`, and radio/station views.

When a Sonos media player is selected in Home Assistant, track items are exposed as playable `audio/aac` media-source items. Home Assistant then resolves the media-source track ID to a Sonos playback URI before handing it to the Sonos player.

## Services

The integration registers these Home Assistant services:

- `sonos_web_bridge.login`
- `sonos_web_bridge.refresh`
- `sonos_web_bridge.discover`
- `sonos_web_bridge.search`
- `sonos_web_bridge.library_tracks`
- `sonos_web_bridge.library_resources`
- `sonos_web_bridge.play_media`

Example playback service data:

```yaml
entity_id: media_player.living_room_sonos
media_content_id: media-source://sonos_web_bridge/track/librarytrack%3Ai.example
```

## HTTP API

The integration also exposes authenticated Home Assistant HTTP endpoints for custom dashboards or cards:

- `GET /api/sonos_web_bridge/status`
- `POST /api/sonos_web_bridge/login`
- `GET /api/sonos_web_bridge/discover`
- `GET /api/sonos_web_bridge/search?q=Song&count=20`
- `GET /api/sonos_web_bridge/library/tracks?offset=0&count=100`
- `GET /api/sonos_web_bridge/library/resources?object_id=libraryfolder%3Af.3&offset=0&count=100`

## Development

Run the lightweight checks before publishing a release:

```bash
python -m compileall custom_components/sonos_web_bridge
python -m unittest discover -s tests
```

Release checklist:

1. Keep all work on `main`.
2. Update `manifest.json` version.
3. Run tests.
4. Push `main`.
5. Create a GitHub release for the matching tag so HACS can discover it.

Brand assets are intentionally present twice:

- `brand/icon.png` and `brand/logo.png` are used by HACS repository listings.
- `custom_components/sonos_web_bridge/brand/` is used by Home Assistant after installation.

## Notes

Sonos Web Bridge uses private Sonos Web endpoints that can change without notice. This integration should be treated as experimental until the Sonos Web flow has proven stable over time.
