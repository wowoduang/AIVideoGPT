import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class _Logger:
    def error(self, *args, **kwargs):
        return None


class _ProgressBar:
    def __init__(self, values, initial):
        self._values = values
        self._values.append(initial)

    def progress(self, value):
        self._values.append(value)


class _StatusText:
    def __init__(self, messages):
        self._messages = messages

    def text(self, value):
        self._messages.append(value)


def _build_streamlit_module():
    module = types.ModuleType("streamlit")
    module.progress_values = []
    module.status_messages = []
    module.success_messages = []
    module.error_messages = []
    module.caption_messages = []
    module.progress = lambda initial: _ProgressBar(module.progress_values, initial)
    module.empty = lambda: _StatusText(module.status_messages)
    module.success = lambda message: module.success_messages.append(message)
    module.error = lambda message: module.error_messages.append(message)
    module.caption = lambda message: module.caption_messages.append(message)
    return module


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_video_actions_module(streamlit_module, *, job_runner_module):
    class VideoClipParams:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    schema_module = _stub_module("app.models.schema", VideoClipParams=VideoClipParams)
    loguru_module = _stub_module("loguru", logger=_Logger())
    webui_utils_module = _stub_module("webui.utils", job_runner=job_runner_module)

    stubbed_modules = {
        "streamlit": streamlit_module,
        "loguru": loguru_module,
        "app.models.schema": schema_module,
        "webui.utils": webui_utils_module,
        "webui.utils.job_runner": job_runner_module,
    }

    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_video_actions"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/services/video_actions.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class VideoActionsTests(unittest.TestCase):
    def test_build_video_clip_params_merges_all_sections(self):
        job_runner_module = _stub_module(
            "webui.utils.job_runner",
            TRANSPORT_LOCAL_API="local_api",
            TRANSPORT_IN_PROCESS="in_process",
        )
        module = _load_video_actions_module(
            _build_streamlit_module(),
            job_runner_module=job_runner_module,
        )

        params = module.build_video_clip_params(
            script_params={"video_clip_json_path": "script.json"},
            video_params={"video_origin_path": "demo.mp4"},
            audio_params={"voice_name": "test-voice"},
            subtitle_params={"subtitle_enabled": True},
        )

        self.assertEqual("script.json", params.video_clip_json_path)
        self.assertEqual("demo.mp4", params.video_origin_path)
        self.assertEqual("test-voice", params.voice_name)
        self.assertTrue(params.subtitle_enabled)

    def test_run_video_generation_renders_completed_videos(self):
        streamlit_module = _build_streamlit_module()
        job_runner_module = _stub_module(
            "webui.utils.job_runner",
            TRANSPORT_LOCAL_API="local_api",
            TRANSPORT_IN_PROCESS="in_process",
            start_video_job=lambda params: {"task_id": "video-task", "transport": "in_process"},
            get_job_status=lambda task_id, transport: {
                "status": "complete",
                "progress": 100,
                "videos": ["video.mp4"],
            },
        )
        module = _load_video_actions_module(
            streamlit_module,
            job_runner_module=job_runner_module,
        )
        render_mock = Mock()
        params = types.SimpleNamespace(video_origin_path="demo.mp4")

        module.run_video_generation(lambda text: text, params, render_generated_videos=render_mock)

        render_mock.assert_called_once_with(["video.mp4"])
        self.assertTrue(streamlit_module.success_messages)
        self.assertTrue(streamlit_module.caption_messages)


if __name__ == "__main__":
    unittest.main()
