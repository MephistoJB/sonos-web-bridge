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

APPLE_MUSIC = "apple_music"
LIBRARY = "apple_music/library"
RESOURCE = "apple_music/library/resource"
SEARCH = "search"
PAGE_SIZE = 48
SONOS_THUMBNAIL = "/api/brands/integration/sonos/logo.png"

LIBRARY_FOLDERS = (
    ("Titel", "libraryfolder:f.3", MediaClass.TRACK),
    ("Alben", "libraryfolder:f.2", MediaClass.ALBUM),
    ("Kuenstler", "libraryfolder:f.1", MediaClass.ARTIST),
    ("Playlists", "libraryfolder:f.4", MediaClass.PLAYLIST),
)


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
        if identifier == APPLE_MUSIC:
            return self._apple_music()
        if identifier == LIBRARY:
            return self._library()
        if identifier.startswith(RESOURCE):
            return await self._resource_folder(identifier)
        if identifier.startswith(SEARCH):
            return await self._search_folder(identifier)
        raise BrowseError(f"Unknown Sonos Web Bridge media identifier: {identifier}")

    async def async_search_media(self, item: MediaSourceItem, query: SearchMediaQuery) -> SearchMedia:
        """Search Apple Music content through Sonos."""
        runtime = async_get_runtime(self.hass)
        results = await runtime.async_search(query.search_query, PAGE_SIZE)
        return SearchMedia(result=_search_result_items(results))

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media for playback."""
        identifier = item.identifier or ""
        if not identifier.startswith("track/"):
            raise Unresolvable("Only Sonos Web Bridge tracks can be played")
        runtime = async_get_runtime(self.hass)
        return PlayMedia(await runtime.async_resolve_playback_uri(identifier), "audio/aac")

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
                    identifier=APPLE_MUSIC,
                    media_class=MediaClass.APP,
                    media_content_type=MediaType.MUSIC,
                    title="Apple Music",
                    can_play=False,
                    can_expand=True,
                    can_search=True,
                    search_media_classes=[MediaClass.TRACK, MediaClass.ARTIST, MediaClass.ALBUM, MediaClass.PLAYLIST],
                    thumbnail=SONOS_THUMBNAIL,
                )
            ],
            thumbnail=SONOS_THUMBNAIL,
        )

    def _apple_music(self) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=APPLE_MUSIC,
            media_class=MediaClass.APP,
            media_content_type=MediaType.MUSIC,
            title="Apple Music",
            can_play=False,
            can_expand=True,
            can_search=True,
            search_media_classes=[MediaClass.TRACK, MediaClass.ARTIST, MediaClass.ALBUM, MediaClass.PLAYLIST],
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=LIBRARY,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="Mediathek",
                    can_play=False,
                    can_expand=True,
                    can_search=True,
                    search_media_classes=[MediaClass.TRACK, MediaClass.ARTIST, MediaClass.ALBUM, MediaClass.PLAYLIST],
                    thumbnail=SONOS_THUMBNAIL,
                )
            ],
            thumbnail=SONOS_THUMBNAIL,
        )

    def _library(self) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=LIBRARY,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title="Mediathek",
            can_play=False,
            can_expand=True,
            can_search=True,
            search_media_classes=[MediaClass.TRACK, MediaClass.ARTIST, MediaClass.ALBUM, MediaClass.PLAYLIST],
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=_resource_identifier(object_id, 0, title),
                    media_class=media_class,
                    media_content_type=MediaType.MUSIC,
                    title=title,
                    can_play=False,
                    can_expand=True,
                    can_search=True,
                    search_media_classes=[media_class],
                    thumbnail=SONOS_THUMBNAIL,
                )
                for title, object_id, media_class in LIBRARY_FOLDERS
            ],
            thumbnail=SONOS_THUMBNAIL,
        )

    async def _resource_folder(self, identifier: str) -> BrowseMediaSource:
        object_id = _object_id_from_identifier(identifier)
        offset = _offset_from_identifier(identifier)
        label = _label_from_identifier(identifier)
        runtime = async_get_runtime(self.hass)
        payload = await runtime.async_library_resources(object_id, offset, PAGE_SIZE)
        resources, total = _resources_from_payload(payload)
        items = [_resource_item(resource) for resource in resources]
        next_offset = offset + len(items)
        if next_offset < total:
            items.append(_next_page_item(object_id, next_offset, label))

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=_resource_identifier(object_id, offset, label),
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=label or "Mediathek",
            can_play=False,
            can_expand=True,
            can_search=True,
            search_media_classes=[MediaClass.TRACK, MediaClass.ARTIST, MediaClass.ALBUM, MediaClass.PLAYLIST],
            children_media_class=_children_media_class(items),
            children=items,
            not_shown=max(total - next_offset, 0),
            thumbnail=SONOS_THUMBNAIL,
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


def _resource_identifier(object_id: str, offset: int, label: str) -> str:
    return f"{RESOURCE}/{quote(object_id, safe='')}?{urlencode({'offset': offset, 'label': label})}"


def _object_id_from_identifier(identifier: str) -> str:
    encoded = identifier.removeprefix(f"{RESOURCE}/").partition("?")[0]
    return unquote(encoded)


def _offset_from_identifier(identifier: str) -> int:
    query = parse_qs(identifier.partition("?")[2])
    value = query.get("offset", ["0"])[0]
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def _label_from_identifier(identifier: str) -> str:
    query = parse_qs(identifier.partition("?")[2])
    return query.get("label", [""])[0]


def _next_page_item(object_id: str, offset: int, label: str) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=_resource_identifier(object_id, offset, label),
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.MUSIC,
        title="Naechste Seite",
        can_play=False,
        can_expand=True,
    )


def _resource_item(item: dict[str, Any]) -> BrowseMediaSource:
    object_id = _object_id(item)
    media_class = _media_class(item)
    can_expand = media_class != MediaClass.TRACK and bool(object_id)
    title = _title(item)
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=_resource_identifier(object_id, 0, title) if can_expand else f"track/{quote(str(item.get('id') or object_id or title), safe='')}",
        media_class=media_class,
        media_content_type=MediaType.MUSIC,
        title=title,
        can_play=media_class == MediaClass.TRACK,
        can_expand=can_expand,
        thumbnail=_thumbnail(item),
    )


def _search_result_items(payload: dict[str, Any]) -> list[BrowseMedia]:
    tracks = payload.get("TRACKS", {}).get("resources", [])
    return [_resource_item(track) for track in tracks]


def _resources_from_payload(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    direct_items = payload.get("items")
    if isinstance(direct_items, list):
        return direct_items, int(payload.get("total") or len(direct_items))

    for key in ("resources", "tracks"):
        collection = payload.get(key)
        if isinstance(collection, dict) and isinstance(collection.get("items"), list):
            items = collection["items"]
            return items, int(collection.get("total") or len(items))

    sections = payload.get("sections")
    if isinstance(sections, dict):
        for section in sections.get("items", []):
            items = section.get("items")
            if isinstance(items, list):
                return items, int(section.get("total") or len(items))

    return [], 0


def _object_id(item: dict[str, Any]) -> str:
    resource_id = item.get("resource", {}).get("id", {})
    return unquote(str(resource_id.get("objectId") or item.get("objectId") or ""))


def _media_class(item: dict[str, Any]) -> MediaClass:
    resource_type = str(item.get("resource", {}).get("type") or item.get("type") or "").upper()
    if "ARTIST" in resource_type:
        return MediaClass.ARTIST
    if "ALBUM" in resource_type:
        return MediaClass.ALBUM
    if "PLAYLIST" in resource_type:
        return MediaClass.PLAYLIST
    if "CONTAINER" in resource_type:
        return MediaClass.DIRECTORY
    return MediaClass.TRACK


def _children_media_class(items: list[BrowseMediaSource]) -> MediaClass | None:
    for item in items:
        if item.title != "Naechste Seite":
            return item.media_class
    return None


def _title(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("name") or "Untitled")
    subtitle = str(item.get("subtitle") or _artist_summary(item) or "")
    if subtitle and _media_class(item) == MediaClass.TRACK:
        return f"{title} - {subtitle}"
    return title


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
