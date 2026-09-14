"""Unit tests for media source parsing helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.sonos_web_bridge"


def _install_homeassistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    media_player = types.ModuleType("homeassistant.components.media_player")
    media_source = types.ModuleType("homeassistant.components.media_source")
    core = types.ModuleType("homeassistant.core")

    class BrowseMedia:
        pass

    class BrowseMediaSource:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.media_content_id = f"media-source://{kwargs['domain']}/{kwargs['identifier']}"

    class BrowseError(Exception):
        pass

    class Unresolvable(Exception):
        pass

    class MediaClass:
        ALBUM = "album"
        APP = "app"
        ARTIST = "artist"
        DIRECTORY = "directory"
        PLAYLIST = "playlist"
        TRACK = "track"

    class MediaType:
        APP = "app"
        MUSIC = "music"

    class HomeAssistant:
        pass

    media_player.BrowseError = BrowseError
    media_player.BrowseMedia = BrowseMedia
    media_player.MediaClass = MediaClass
    media_player.MediaType = MediaType
    media_player.SearchMedia = object
    media_player.SearchMediaQuery = object
    media_source.BrowseMediaSource = BrowseMediaSource
    media_source.MediaSource = object
    media_source.MediaSourceItem = object
    media_source.PlayMedia = object
    media_source.Unresolvable = Unresolvable
    core.HomeAssistant = HomeAssistant

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.media_player"] = media_player
    sys.modules["homeassistant.components.media_source"] = media_source
    sys.modules["homeassistant.core"] = core


def _load_module(module_name: str, file_name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "custom_components" / "sonos_web_bridge" / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_media_source() -> types.ModuleType:
    _install_homeassistant_stubs()
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "sonos_web_bridge")]
    package.async_get_runtime = lambda hass: None
    sys.modules[PACKAGE] = package
    _load_module(f"{PACKAGE}.const", "const.py")
    return _load_module(f"{PACKAGE}.media_source", "media_source.py")


class MediaSourceHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.media_source = _load_media_source()

    def test_reads_single_section_payloads(self) -> None:
        payload = {"section": {"items": [{"title": "Recently Added Album"}], "total": 100}}

        items, total = self.media_source._resources_from_payload(payload)

        self.assertEqual(items, [{"title": "Recently Added Album"}])
        self.assertEqual(total, 100)

    def test_reads_multi_section_payloads(self) -> None:
        payload = {
            "sections": {
                "items": [
                    {"items": [{"title": "One"}], "total": 1},
                    {"items": [{"title": "Two"}], "total": 1},
                ]
            }
        }

        items, total = self.media_source._resources_from_payload(payload)

        self.assertEqual([item["title"] for item in items], ["One", "Two"])
        self.assertEqual(total, 2)

    def test_renames_sonos_library_root_for_display(self) -> None:
        item = {
            "title": "Library",
            "resource": {"id": {"objectId": "browseviewlibraryroot:libraryroot"}, "type": "CONTAINER"},
        }

        result = self.media_source._resource_item(item)

        self.assertEqual(result.title, "Apple Music Library")
        self.assertIn("label=Apple+Music+Library", result.identifier)

    def test_library_tracks_are_marked_playable_audio(self) -> None:
        item = {
            "title": "Song",
            "subtitle": "Artist",
            "resource": {"id": {"objectId": "librarytrack:i.123"}, "type": "TRACK"},
        }

        result = self.media_source._resource_item(item)

        self.assertTrue(result.can_play)
        self.assertFalse(result.can_expand)
        self.assertEqual(result.media_content_type, "audio/aac")
        self.assertEqual(result.title, "Song - Artist")


if __name__ == "__main__":
    unittest.main()
