import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class _Logger:
    def error(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
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


class _Spinner:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _Expander:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def _build_streamlit_module():
    module = types.ModuleType("streamlit")
    module.progress_values = []
    module.status_messages = []
    module.error_messages = []
    module.success_messages = []
    module.caption_messages = []
    module.write_messages = []
    module.session_state = {}

    module.progress = lambda initial: _ProgressBar(module.progress_values, initial)
    module.empty = lambda: _StatusText(module.status_messages)
    module.spinner = lambda _message: _Spinner()
    module.expander = lambda *args, **kwargs: _Expander()
    module.error = lambda message: module.error_messages.append(message)
    module.success = lambda message: module.success_messages.append(message)
    module.caption = lambda message: module.caption_messages.append(message)
    module.write = lambda *args: module.write_messages.append(args)
    return module


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_module(streamlit_module, *, review_mode: str, job_status: dict, legacy_mock: Mock, save_mock: Mock):
    short_summary_module = _stub_module(
        "webui.tools.generate_short_summary",
        _build_request=lambda params, subtitle_path, video_theme, temperature: {
            "video_path": params.video_origin_path,
            "subtitle_path": subtitle_path,
            "video_theme": video_theme,
            "temperature": temperature,
        },
        _normalize_subtitle_mode=lambda: "auto_subtitle",
        _normalize_subtitle_path=lambda subtitle_path, subtitle_mode: subtitle_path,
        _resolve_review_mode=lambda: review_mode,
        _save_pipeline_success=save_mock,
        generate_script_short_sunmmary=legacy_mock,
    )
    job_runner_module = _stub_module(
        "webui.utils.job_runner",
        TRANSPORT_LOCAL_API="local_api",
        TRANSPORT_IN_PROCESS="in_process",
        start_movie_story_script_job=lambda request: {
            "task_id": "movie-story-task",
            "transport": "in_process",
            "task_dir": "D:/workspace/tasks/movie-story-task",
        },
        get_job_status=lambda task_id, transport: job_status,
    )
    webui_utils_module = _stub_module("webui.utils", job_runner=job_runner_module)
    loguru_module = _stub_module("loguru", logger=_Logger())

    stubbed_modules = {
        "streamlit": streamlit_module,
        "loguru": loguru_module,
        "webui.tools.generate_short_summary": short_summary_module,
        "webui.utils": webui_utils_module,
        "webui.utils.job_runner": job_runner_module,
    }

    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_generate_short_summary_api"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/tools/generate_short_summary_api.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class GenerateShortSummaryApiTests(unittest.TestCase):
    def test_auto_subtitle_review_mode_falls_back_to_legacy_flow(self):
        streamlit_module = _build_streamlit_module()
        legacy_mock = Mock()
        save_mock = Mock()
        module = _load_module(
            streamlit_module,
            review_mode="review_suspicious",
            job_status={},
            legacy_mock=legacy_mock,
            save_mock=save_mock,
        )

        params = types.SimpleNamespace(video_origin_path="demo.mp4")
        module.generate_script_short_sunmmary(params, "", "Demo", 0.7)

        legacy_mock.assert_called_once_with(params, "", "Demo", 0.7)
        save_mock.assert_not_called()

    def test_non_review_flow_uses_job_runner_and_saves_pipeline_result(self):
        streamlit_module = _build_streamlit_module()
        legacy_mock = Mock()
        save_mock = Mock()
        pipeline_result = {
            "script_items": [{"timestamp": "00:00:00,000-00:00:05,000"}],
            "plot_chunks": [{"chunk_id": "chunk-1"}],
            "subtitle_path": "subtitle.srt",
        }
        module = _load_module(
            streamlit_module,
            review_mode="skip_review",
            job_status={
                "status": "complete",
                "progress": 100,
                "message": "",
                "result": pipeline_result,
            },
            legacy_mock=legacy_mock,
            save_mock=save_mock,
        )

        params = types.SimpleNamespace(video_origin_path="demo.mp4")
        module.generate_script_short_sunmmary(params, "", "Demo", 0.7)

        legacy_mock.assert_not_called()
        save_mock.assert_called_once_with(pipeline_result)
        self.assertTrue(streamlit_module.success_messages)


if __name__ == "__main__":
    unittest.main()
