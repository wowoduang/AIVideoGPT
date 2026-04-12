import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.utils.streamlit_compat import (
    collect_module_paths_without_side_effects,
    patch_streamlit_torch_watcher,
)


class _NamespacePath:
    def __init__(self, *paths):
        self._path = list(paths)


class ExplosiveModule(types.ModuleType):
    def __getattr__(self, name):
        if name == "__path__":
            raise RuntimeError("torch.classes path probe")
        raise AttributeError(name)


class StreamlitCompatTests(unittest.TestCase):
    def test_collect_module_paths_avoids_dynamic_getattr(self):
        module = ExplosiveModule("torch.classes")
        module.__file__ = os.path.join("tmp", "demo.py")
        module.__spec__ = SimpleNamespace(origin=os.path.join("tmp", "demo.py"))

        paths = collect_module_paths_without_side_effects(module, lambda value: bool(value))

        self.assertEqual({os.path.realpath(os.path.join("tmp", "demo.py"))}, paths)

    def test_collect_module_paths_reads_namespace_path_without_side_effects(self):
        module = types.ModuleType("pkg")
        module.__path__ = _NamespacePath(os.path.join("tmp", "a"), os.path.join("tmp", "b"))

        paths = collect_module_paths_without_side_effects(module, lambda value: bool(value))

        self.assertEqual(
            {
                os.path.realpath(os.path.join("tmp", "a")),
                os.path.realpath(os.path.join("tmp", "b")),
            },
            paths,
        )

    def test_patch_streamlit_torch_watcher_replaces_get_module_paths(self):
        fake_lsw = types.ModuleType("streamlit.watcher.local_sources_watcher")
        fake_lsw._is_valid_path = lambda value: bool(value)
        fake_lsw.get_module_paths = lambda module: {"old"}

        fake_streamlit = types.ModuleType("streamlit")
        fake_watcher = types.ModuleType("streamlit.watcher")
        fake_watcher.local_sources_watcher = fake_lsw
        fake_streamlit.watcher = fake_watcher

        with patch.dict(
            sys.modules,
            {
                "streamlit": fake_streamlit,
                "streamlit.watcher": fake_watcher,
                "streamlit.watcher.local_sources_watcher": fake_lsw,
            },
        ):
            patched = patch_streamlit_torch_watcher()

        self.assertTrue(patched)
        module = ExplosiveModule("torch.classes")
        module.__file__ = os.path.join("tmp", "demo.py")
        result = fake_lsw.get_module_paths(module)
        self.assertEqual({os.path.realpath(os.path.join("tmp", "demo.py"))}, result)


if __name__ == "__main__":
    unittest.main()
