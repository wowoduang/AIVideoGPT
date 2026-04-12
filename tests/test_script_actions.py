import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def _build_streamlit_module():
    module = types.ModuleType("streamlit")
    module.session_state = {}
    module.error_messages = []
    module.error = lambda message: module.error_messages.append(message)
    return module


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_script_actions_module(streamlit_module, *, highlight_mock: Mock, summary_mock: Mock):
    class VideoClipParams:
        def __init__(self):
            self.video_clip_json_path = ""
            self.video_origin_path = ""

    schema_module = _stub_module("app.models.schema", VideoClipParams=VideoClipParams)
    highlight_module = _stub_module("webui.tools.generate_highlight_edit_api", generate_highlight_edit=highlight_mock)
    summary_module = _stub_module("webui.tools.generate_short_summary_api", generate_script_short_sunmmary=summary_mock)
    persistence_module = _stub_module("webui.services.script_persistence", load_script=Mock())

    stubbed_modules = {
        "streamlit": streamlit_module,
        "app.models.schema": schema_module,
        "webui.services.script_persistence": persistence_module,
        "webui.tools.generate_highlight_edit_api": highlight_module,
        "webui.tools.generate_short_summary_api": summary_module,
    }

    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_script_actions"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/services/script_actions.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class ScriptActionsTests(unittest.TestCase):
    def test_get_script_action_label_uses_auto_subtitle_variant(self):
        streamlit_module = _build_streamlit_module()
        streamlit_module.session_state["subtitle_source_mode"] = "auto_subtitle"
        module = _load_script_actions_module(
            streamlit_module,
            highlight_mock=Mock(),
            summary_mock=Mock(),
        )

        label = module.get_script_action_label(lambda text: text, module.MODE_SUBTITLE_FIRST)
        self.assertEqual("Auto Generate Subtitle and Script", label)

    def test_run_script_action_dispatches_highlight_generation(self):
        streamlit_module = _build_streamlit_module()
        streamlit_module.session_state.update(
            {
                "video_origin_path": "demo.mp4",
                "highlight_subtitle_source_mode": "existing_subtitle",
                "highlight_subtitle_path": "",
                "highlight_subtitle_content": "subtitle-text",
            }
        )
        highlight_mock = Mock()
        module = _load_script_actions_module(
            streamlit_module,
            highlight_mock=highlight_mock,
            summary_mock=Mock(),
        )

        module.run_script_action(
            lambda text: text,
            module.MODE_HIGHLIGHT_EDIT,
            lazy_import_short_mix_generator=Mock(),
        )

        highlight_mock.assert_called_once()
        args = highlight_mock.call_args.args
        self.assertEqual("highlight_edit", args[1].video_clip_json_path)
        self.assertEqual("demo.mp4", args[1].video_origin_path)
        self.assertEqual("", streamlit_module.session_state["subtitle_path"])
        self.assertEqual("subtitle-text", streamlit_module.session_state["subtitle_content"])

    def test_run_script_action_validates_short_summary_subtitle(self):
        streamlit_module = _build_streamlit_module()
        streamlit_module.session_state.update(
            {
                "video_origin_path": "demo.mp4",
                "short_summary_subtitle_path": "",
            }
        )
        summary_mock = Mock()
        module = _load_script_actions_module(
            streamlit_module,
            highlight_mock=Mock(),
            summary_mock=summary_mock,
        )

        module.run_script_action(
            lambda text: text,
            module.MODE_SHORT_SUMMARY,
            lazy_import_short_mix_generator=Mock(),
        )

        summary_mock.assert_not_called()
        self.assertEqual(["Short drama summary requires subtitle file"], streamlit_module.error_messages)


if __name__ == "__main__":
    unittest.main()
