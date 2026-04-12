import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _Logger:
    def warning(self, *args, **kwargs):
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


def _build_streamlit_module():
    module = types.ModuleType("streamlit")
    module.session_state = {}
    module.progress_values = []
    module.status_messages = []
    module.success_messages = []
    module.caption_messages = []
    module.error_messages = []

    def progress(initial):
        return _ProgressBar(module.progress_values, initial)

    def empty():
        return _StatusText(module.status_messages)

    def spinner(_message):
        return _Spinner()

    def success(message):
        module.success_messages.append(message)

    def caption(message):
        module.caption_messages.append(message)

    def error(message):
        module.error_messages.append(message)

    def stop():
        raise AssertionError("st.stop should not be called in this test")

    module.progress = progress
    module.empty = empty
    module.spinner = spinner
    module.success = success
    module.caption = caption
    module.error = error
    module.stop = stop
    return module


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_generate_highlight_edit_module(streamlit_module, pipeline_result):
    class InputValidationError(Exception):
        pass

    subtitle_text_module = _stub_module(
        "app.services.subtitle_text",
        decode_subtitle_bytes=lambda data: types.SimpleNamespace(text=data.decode("utf-8"), encoding="utf-8"),
    )
    upload_validation_module = _stub_module(
        "app.services.upload_validation",
        InputValidationError=InputValidationError,
        ensure_existing_file=lambda path, **kwargs: path,
    )
    job_runner_module = _stub_module(
        "webui.utils.job_runner",
        TRANSPORT_LOCAL_API="local_api",
        TRANSPORT_IN_PROCESS="in_process",
        start_highlight_script_job=lambda request: {
            "task_id": "highlight-task",
            "transport": "in_process",
            "task_dir": "D:/workspace/tasks/highlight-task",
        },
        get_job_status=lambda task_id, transport: {
            "task_id": task_id,
            "transport": transport,
            "status": "complete",
            "progress": 100,
            "result": pipeline_result,
        },
    )
    webui_utils_module = _stub_module("webui.utils", job_runner=job_runner_module)
    loguru_module = _stub_module("loguru", logger=_Logger())

    stubbed_modules = {
        "streamlit": streamlit_module,
        "loguru": loguru_module,
        "app.services.subtitle_text": subtitle_text_module,
        "app.services.upload_validation": upload_validation_module,
        "webui.utils": webui_utils_module,
        "webui.utils.job_runner": job_runner_module,
    }
    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_generate_highlight_edit"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/tools/generate_highlight_edit_api.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class GenerateHighlightEditTests(unittest.TestCase):
    def test_generated_subtitle_syncs_highlight_session_state(self):
        streamlit_module = _build_streamlit_module()
        streamlit_module.session_state.update(
            {
                "highlight_edit_mode": "highlight_recut",
                "highlight_target_minutes": 8,
                "highlight_movie_title": "Demo",
                "highlight_subtitle_path": "",
                "highlight_subtitle_source_mode": "auto_subtitle",
                "highlight_prefer_raw_audio": True,
                "highlight_visual_mode": "auto",
                "subtitle_asr_backend": "faster-whisper",
            }
        )

        subtitle_fd, subtitle_path = tempfile.mkstemp(suffix=".srt")
        os.close(subtitle_fd)
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\n测试字幕\n")

        pipeline_result = {
            "success": True,
            "script_items": [{"_id": 1}],
            "script_path": "script.json",
            "composition_plan": {"segments": []},
            "composition_plan_path": "plan.json",
            "candidate_clips": [],
            "plot_candidate_clips": [],
            "scene_candidate_clips": [],
            "candidate_stats": {},
            "selected_clips": [],
            "plot_chunks": [],
            "narration_units": [],
            "narration_matches": [],
            "subtitle_result": {
                "subtitle_path": subtitle_path,
            },
        }

        module = _load_generate_highlight_edit_module(streamlit_module, pipeline_result)
        params = types.SimpleNamespace(video_origin_path="demo.mp4")

        try:
            module.generate_highlight_edit(lambda text: text, params)
        finally:
            if os.path.exists(subtitle_path):
                os.remove(subtitle_path)

        subtitle_content = streamlit_module.session_state["subtitle_content"].replace("\r\n", "\n")
        highlight_subtitle_content = streamlit_module.session_state["highlight_subtitle_content"].replace("\r\n", "\n")
        self.assertEqual(streamlit_module.session_state["subtitle_path"], subtitle_path)
        self.assertEqual(streamlit_module.session_state["highlight_subtitle_path"], subtitle_path)
        self.assertEqual(subtitle_content, "1\n00:00:00,000 --> 00:00:01,000\n测试字幕\n")
        self.assertEqual(highlight_subtitle_content, "1\n00:00:00,000 --> 00:00:01,000\n测试字幕\n")
        self.assertTrue(streamlit_module.success_messages)


if __name__ == "__main__":
    unittest.main()
