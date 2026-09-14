"""Unit tests for Sonos Web helper functions."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.sonos_web_bridge"


def _install_dependency_stubs() -> None:
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientResponse = object
    aiohttp.ClientSession = object
    yarl = types.ModuleType("yarl")

    class URL:
        def __init__(self, value: str) -> None:
            from urllib.parse import urlparse

            parsed = urlparse(value)
            self.host = parsed.hostname
            self.path = parsed.path or "/"

    yarl.URL = URL
    sys.modules["aiohttp"] = aiohttp
    sys.modules["yarl"] = yarl


def _load_module(module_name: str, file_name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "custom_components" / "sonos_web_bridge" / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_sonos_web() -> types.ModuleType:
    _install_dependency_stubs()
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "sonos_web_bridge")]
    sys.modules[PACKAGE] = package
    _load_module(f"{PACKAGE}.const", "const.py")
    return _load_module(f"{PACKAGE}.sonos_web", "sonos_web.py")


class SonosWebHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sonos_web = _load_sonos_web()

    def test_playback_uri_accepts_media_source_track_ids(self) -> None:
        uri = self.sonos_web._playback_uri("media-source://sonos_web_bridge/track/librarytrack%3Ai.abc", "42")

        self.assertEqual(uri, "x-sonos-http:librarytrack%3ai.abc.mp4?sid=204&flags=8232&sn=42")

    def test_track_object_id_accepts_sonos_srn_ids(self) -> None:
        object_id = self.sonos_web._track_object_id("srn:content:audio:track:song%3A123#library")

        self.assertEqual(object_id, "song:123")

    def test_track_object_id_rejects_non_track_ids(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Unsupported Sonos media id"):
            self.sonos_web._track_object_id("libraryalbum:l.123")

    def test_library_root_uses_container_resources_path(self) -> None:
        path = self.sonos_web._library_resource_path("hh", "svc", "acct", "root", 0, 48)

        self.assertEqual(
            path,
            "/api/content/v2/households/hh/services/svc/accounts/acct/containers/root/resources?count=48&offset=0&filterExplicit=false&muse2=true",
        )

    def test_personal_library_folders_use_playlist_resources_path(self) -> None:
        path = self.sonos_web._library_resource_path("hh", "svc", "acct", "libraryfolder:f.3", 48, 100)

        self.assertEqual(
            path,
            "/api/content/v2/households/hh/services/svc/accounts/acct/playlists/libraryfolder%3Af.3/resources?count=100&offset=48&filterExplicit=false&muse2=true",
        )


if __name__ == "__main__":
    unittest.main()
