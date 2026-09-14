"""Media source support for Sonos Web Bridge."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_source import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia, Unresolvable
from homeassistant.core import HomeAssistant

from . import async_get_runtime
from .const import DOMAIN

LIBRARY_TRACKS = "library/tracks"
SEARCH = "search"
PAGE_SIZE = 48


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up the Sonos Web Bridge media source."""
    return SonosWebBridgeMediaSource(hass)


class SonosWebBridgeMediaSource(MediaSource):
    """Expose Sonos Apple Music content in Home Assistant's media browser."""

    name = "Sonos Web Bridge"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse Sonos Apple Music content."""
        identifier = item.identifier or ""
        if not identifier:
            return self._root()
        if identifier.startswith(LIBRARY_TRACKS):
            return await self._library_tracks(identifier)
        if identifier.startswith(SEARCH):
            return await self._search_folder(identifier)
        raise BrowseError(f"Unknown Sonos Web Bridge media identifier: {identifier}")

    async def async_search_media(self, item: MediaSourceItem, query: SearchMediaQuery) -> SearchMedia:
        """Search Sonos Apple Music content."""
        runtime = async_get_runtime(self.hass)
        results = await runtime.async_search(query.search_query, PAGE_SIZE)
        return SearchMedia(result=_search_result_items(results))

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media for playback."""
        raise Unresolvable("Sonos Web Bridge playback is not implemented yet")

    def _root(self) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type=MediaType.APP,
            title=self.name,
            can_play=False,
            can_expand=True,
            can_search=True,
            search_media_classes=[MediaClass.TRACK, MediaClass.ARTIST, MediaClass.ALBUM, MediaClass.PLAYLIST],
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=_library_identifier(0),
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="Apple Music Library Tracks",
                    can_play=False,
                    can_expand=True,
                    can_search=True,
                    search_media_classes=[MediaClass.TRACK],
                    thumbnail="/api/brands/integration/sonos/logo.png",
                )
            ],
            thumbnail="/api/brands/integration/sonos/logo.png",
        )

    async def _library_tracks(self, identifier: str) -> BrowseMediaSource:
        offset = _offset_from_identifier(identifier)
        runtime = async_get_runtime(self.hass)
        payload = await runtime.async_library_tracks(offset, PAGE_SIZE)
        items = [_track_item(track) for track in payload.get("items", [])]
        total = int(payload.get("total") or 0)
        next_offset = offset + len(items)
        if next_offset < total:
            items.append(_next_page_item(next_offset))

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=_library_identifier(offset),
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title="Apple Music Library Tracks",
            can_play=False,
            can_expand=True,
            can_search=True,
            search_media_classes=[MediaClass.TRACK],
            children=items,
            not_shown=max(total - next_offset, 0),
            thumbnail="/api/brands/integration/sonos/logo.png",
        )

    async def _search_folder(self, identifier: str) -> BrowseMediaSource:
        query = unquote(identifier.removeprefix(f"{SEARCH}/"))
        runtime = async_get_runtime(self.hass)
        payload = await runtime.async_search(query, PAGE_SIZE)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=f"Search: {query}",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.TRACK,
            children=_search_result_items(payload),
        )


def _library_identifier(offset: int) -> str:
    return f"{LIBRARY_TRACKS}?{urlencode({'offset': offset})}"


def _offset_from_identifier(identifier: str) -> int:
    query = parse_qs(identifier.partition("?")[2])
    value = query.get("offset", ["0"])[0]
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def _next_page_item(offset: int) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=_library_identifier(offset),
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.MUSIC,
        title="Next page",
        can_play=False,
        can_expand=True,
    )


def _track_item(track: dict[str, Any]) -> BrowseMediaSource:
    title = str(track.get("title") or track.get("name") or "Untitled")
    subtitle = str(track.get("subtitle") or _artist_summary(track) or "")
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"track/{quote(str(track.get('id') or track.get('resource', {}).get('id', {}).get('objectId') or title), safe='')}",
        media_class=MediaClass.TRACK,
        media_content_type=MediaType.MUSIC,
        title=f"{title} - {subtitle}" if subtitle else title,
        can_play=False,
        can_expand=False,
        thumbnail=_thumbnail(track),
    )


def _search_result_items(payload: dict[str, Any]) -> list[BrowseMedia]:
    tracks = payload.get("TRACKS", {}).get("resources", [])
    return [_track_item(track) for track in tracks]


def _artist_summary(item: dict[str, Any]) -> str:
    artists = item.get("artists")
    if isinstance(artists, list) and artists:
        return ", ".join(str(artist.get("name")) for artist in artists if artist.get("name"))
    summary = item.get("summary")
    if isinstance(summary, dict):
        return str(summary.get("content") or "")
    return ""


def _thumbnail(item: dict[str, Any]) -> str | None:
    images = item.get("images")
    if isinstance(images, dict):
        return images.get("tile1x1")
    if isinstance(images, list) and images:
        image = images[0]
        if isinstance(image, dict):
            return image.get("url")
    return None
