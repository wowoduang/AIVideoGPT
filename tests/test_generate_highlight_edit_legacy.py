import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_legacy_module(api_mock: Mock):
    api_module = _stub_module("webui.tools.generate_highlight_edit_api", generate_highlight_edit=api_mock)

    with patch.dict(sys.modules, {"webui.tools.generate_highlight_edit_api": api_module}):
        module_name = "_test_generate_highlight_edit_legacy"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/tools/generate_highlight_edit.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class GenerateHighlightEditLegacyTests(unittest.TestCase):
    def test_legacy_module_reexports_api_entrypoint(self):
        api_mock = Mock()
        module = _load_legacy_module(api_mock)
        params = types.SimpleNamespace(video_origin_path="demo.mp4")

        module.generate_highlight_edit(lambda text: text, params)

        api_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
