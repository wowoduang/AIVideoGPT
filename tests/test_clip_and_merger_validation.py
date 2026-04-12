import importlib
import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _Logger:
    def debug(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_clip_video_module():
    loguru_module = _stub_module("loguru", logger=_Logger())
    utils_module = _stub_module(
        "app.utils.utils",
        time_to_seconds=lambda value: 0.0,
        format_time=lambda value: "00:00:00,000",
    )
    ffmpeg_utils_module = _stub_module(
        "app.utils.ffmpeg_utils",
        get_resilient_decode_input_args=lambda **kwargs: [],
        get_ffmpeg_hwaccel_type=lambda: None,
        get_ffmpeg_hwaccel_args=lambda: [],
        get_ffmpeg_hwaccel_info=lambda: {},
        detect_hardware_acceleration=lambda: {},
        get_optimal_ffmpeg_encoder=lambda: "libx264",
        force_software_encoding=lambda: None,
    )
    app_utils_module = _stub_module("app.utils", ffmpeg_utils=ffmpeg_utils_module, utils=utils_module)
    working_copy_module = _stub_module(
        "app.services.video_working_copy",
        ensure_working_video_copy=lambda path, purpose="general": path,
    )

    stubbed_modules = {
        "loguru": loguru_module,
        "app.utils": app_utils_module,
        "app.utils.utils": utils_module,
        "app.utils.ffmpeg_utils": ffmpeg_utils_module,
        "app.services.video_working_copy": working_copy_module,
    }
    with patch.dict(sys.modules, stubbed_modules):
        sys.modules.pop("app.services.clip_video", None)
        return importlib.import_module("app.services.clip_video")


def _load_merger_video_module():
    loguru_module = _stub_module("loguru", logger=_Logger())
    ffmpeg_utils_module = _stub_module(
        "app.utils.ffmpeg_utils",
        get_ffmpeg_hwaccel_type=lambda: None,
        detect_hardware_acceleration=lambda: {},
        get_optimal_ffmpeg_encoder=lambda: "libx264",
        force_software_encoding=lambda: None,
    )
    app_utils_module = _stub_module("app.utils", ffmpeg_utils=ffmpeg_utils_module)

    stubbed_modules = {
        "loguru": loguru_module,
        "app.utils": app_utils_module,
        "app.utils.ffmpeg_utils": ffmpeg_utils_module,
    }
    with patch.dict(sys.modules, stubbed_modules):
        sys.modules.pop("app.services.merger_video", None)
        return importlib.import_module("app.services.merger_video")


class ClipAndMergerValidationTests(unittest.TestCase):
    def test_execute_ffmpeg_with_fallback_retries_when_primary_output_is_invalid(self):
        module = _load_clip_video_module()

        with (
            patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
            patch.object(module, "_has_valid_video_output", return_value=False),
            patch.object(module, "try_fallback_encoding", return_value=True) as fallback,
        ):
            ok = module.execute_ffmpeg_with_fallback_validated(
                cmd=["ffmpeg", "-i", "input.mp4", "output.mp4"],
                timestamp="00:00:01,000-00:00:03,000",
                input_path="input.mp4",
                output_path="output.mp4",
                start_time="00:00:01.000",
                end_time="00:00:03.000",
            )

        self.assertTrue(ok)
        fallback.assert_called_once()

    def test_execute_simple_command_validated_rejects_streamless_output(self):
        module = _load_clip_video_module()

        with (
            patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
            patch.object(module, "_has_valid_video_output", return_value=False),
        ):
            ok = module.execute_simple_command_validated(
                cmd=["ffmpeg", "-i", "input.mp4", "output.mp4"],
                timestamp="00:00:01,000-00:00:03,000",
                method_name="fallback",
            )

        self.assertFalse(ok)

    def test_process_single_video_rejects_invalid_input_segment(self):
        module = _load_merger_video_module()

        invalid_info = {"exists": True, "size_bytes": 2, "duration": 0.0, "has_video": False}
        with (
            patch.object(module.os.path, "exists", return_value=True),
            patch.object(module, "_probe_valid_video", return_value=(False, invalid_info)),
        ):
            with self.assertRaises(RuntimeError):
                module.process_single_video(
                    input_path="bad.mp4",
                    output_path="out.mp4",
                    target_width=1920,
                    target_height=1080,
                    keep_audio=False,
                    hwaccel=None,
                )

    def test_combine_clip_videos_skips_invalid_segments_when_valid_ones_remain(self):
        module = _load_merger_video_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = os.path.join(tmpdir, "bad.mp4")
            good_path = os.path.join(tmpdir, "good.mp4")
            output_path = os.path.join(tmpdir, "merged.mp4")
            for path in (bad_path, good_path):
                with open(path, "wb") as handle:
                    handle.write(b"seed")

            def fake_probe(path, include_audio=False):
                if path == bad_path:
                    return False, {
                        "exists": True,
                        "size_bytes": 2,
                        "duration": 0.0,
                        "has_video": False,
                        "has_audio": False,
                    }
                return True, {
                    "exists": True,
                    "size_bytes": 4096,
                    "duration": 3.2,
                    "has_video": True,
                    "has_audio": False,
                    "is_valid_video": True,
                }

            def fake_process_single_video(input_path, output_path, **kwargs):
                with open(output_path, "wb") as handle:
                    handle.write(b"processed")
                return output_path

            def fake_create_concat(video_paths, concat_file_path):
                with open(concat_file_path, "w", encoding="utf-8") as handle:
                    for video_path in video_paths:
                        handle.write(f"file '{video_path}'\n")
                return concat_file_path

            def fake_run(cmd, **kwargs):
                target = cmd[-1]
                if isinstance(target, str) and target.endswith(".mp4"):
                    with open(target, "wb") as handle:
                        handle.write(b"concat")
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

            with (
                patch.object(module, "check_ffmpeg_installation", return_value=True),
                patch.object(module, "get_hardware_acceleration_option", return_value=None),
                patch.object(module, "_probe_valid_video", side_effect=fake_probe),
                patch.object(module, "process_single_video", side_effect=fake_process_single_video) as process_single_video,
                patch.object(module, "create_ffmpeg_concat_file", side_effect=fake_create_concat),
                patch.object(module.subprocess, "run", side_effect=fake_run),
            ):
                result = module.combine_clip_videos(
                    output_video_path=output_path,
                    video_paths=[bad_path, good_path],
                    video_ost_list=[0, 0],
                    video_aspect=module.VideoAspect.landscape,
                    threads=1,
                )

                self.assertEqual(result, output_path)
                self.assertTrue(os.path.exists(output_path))
                process_single_video.assert_called_once()


if __name__ == "__main__":
    unittest.main()
