import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class _Logger:
    def error(self, *args, **kwargs):
        return None


def _build_streamlit_module():
    module = types.ModuleType("streamlit")
    module.session_state = {}
    module.success_messages = []
    module.error_messages = []
    module.warning_messages = []
    module.success = lambda message: module.success_messages.append(message)
    module.error = lambda message: module.error_messages.append(message)
    module.warning = lambda message: module.warning_messages.append(message)
    return module


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_script_persistence_module(streamlit_module, *, save_json_file=None, check_format=None, script_dir=None):
    loguru_module = _stub_module("loguru", logger=_Logger())
    check_script_module = _stub_module(
        "app.utils.check_script",
        check_format=check_format or (lambda _items: {"success": True}),
    )
    utils_module = _stub_module(
        "app.utils.utils",
        script_dir=script_dir or (lambda: tempfile.gettempdir()),
    )
    file_utils_module = _stub_module(
        "webui.utils.file_utils",
        save_json_file=save_json_file or (lambda *args, **kwargs: ""),
    )
    webui_utils_module = _stub_module("webui.utils", file_utils=file_utils_module)

    stubbed_modules = {
        "streamlit": streamlit_module,
        "loguru": loguru_module,
        "app.utils.check_script": check_script_module,
        "app.utils.utils": utils_module,
        "webui.utils": webui_utils_module,
        "webui.utils.file_utils": file_utils_module,
    }

    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_script_persistence"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/services/script_persistence.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class ScriptPersistenceTests(unittest.TestCase):
    def test_normalize_script_payload_supports_items_wrapper(self):
        module = _load_script_persistence_module(_build_streamlit_module())
        payload = {"items": [{"timestamp": "00:00:00,000-00:00:05,000"}]}

        result = module.normalize_script_payload(payload)

        self.assertEqual(payload["items"], result)

    def test_load_script_updates_session_state(self):
        streamlit_module = _build_streamlit_module()
        module = _load_script_persistence_module(streamlit_module)

        fd, script_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(script_path, "w", encoding="utf-8") as file_obj:
                json.dump([{"timestamp": "00:00:00,000-00:00:05,000"}], file_obj, ensure_ascii=False)

            result = module.load_script(lambda text: text, script_path)
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)

        self.assertTrue(result)
        self.assertEqual([{"timestamp": "00:00:00,000-00:00:05,000"}], streamlit_module.session_state["video_clip_json"])
        self.assertTrue(streamlit_module.success_messages)

    def test_save_script_with_validation_updates_script_paths(self):
        streamlit_module = _build_streamlit_module()
        save_json_file = Mock(return_value="D:/workspace/scripts/script.json")
        module = _load_script_persistence_module(
            streamlit_module,
            save_json_file=save_json_file,
        )

        save_path = module.save_script_with_validation(
            lambda text: text,
            [{"timestamp": "00:00:00,000-00:00:05,000"}],
        )

        self.assertEqual("D:/workspace/scripts/script.json", save_path)
        self.assertEqual("D:/workspace/scripts/script.json", streamlit_module.session_state["video_clip_json_path"])
        self.assertEqual("D:/workspace/scripts/script.json", streamlit_module.session_state["video_clip_json_path_selected"])
        self.assertTrue(streamlit_module.success_messages)


if __name__ == "__main__":
    unittest.main()
