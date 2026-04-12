import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import subtitle_external


class SubtitleExternalTests(unittest.TestCase):
    def test_augment_env_without_winreg_still_builds_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ffmpeg_dir = os.path.join(tmp_dir, "ffmpeg-bin")
            os.makedirs(ffmpeg_dir, exist_ok=True)
            with patch.object(subtitle_external, "winreg", None):
                with patch.object(subtitle_external, "config") as mock_config:
                    mock_config.app = {"ffmpeg_path": ffmpeg_dir}
                    env = subtitle_external._augment_env_with_windows_paths({"PATH": ffmpeg_dir})

            self.assertIn(ffmpeg_dir, env["PATH"])

    def test_videocaptioner_runtime_env_clears_proxy_env(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(subtitle_external, "config") as mock_config:
                mock_config.root_dir = tmp_dir
                mock_config.app = {"workspace_root": tmp_dir}
                env = subtitle_external._videocaptioner_runtime_env(
                    {
                        "PATH": "",
                        "HTTP_PROXY": "http://127.0.0.1:9",
                        "HTTPS_PROXY": "http://127.0.0.1:9",
                        "ALL_PROXY": "http://127.0.0.1:9",
                    }
                )

            self.assertNotIn("HTTP_PROXY", env)
            self.assertNotIn("HTTPS_PROXY", env)
            self.assertNotIn("ALL_PROXY", env)
            self.assertTrue(env["LOCALAPPDATA"].startswith(tmp_dir))
            self.assertTrue(env["APPDATA"].startswith(tmp_dir))

    def test_videocaptioner_prefix_prefers_repo_python_module(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = os.path.join(tmp_dir, "VideoCaptioner")
            src_dir = os.path.join(repo_dir, "src")
            python_exe = os.path.join(repo_dir, ".runtime_venv", "Scripts", "python.exe")
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(os.path.dirname(python_exe), exist_ok=True)
            with open(python_exe, "wb") as f:
                f.write(b"")

            with patch.object(subtitle_external, "config") as mock_config:
                mock_config.root_dir = tmp_dir
                mock_config.app = {"workspace_root": tmp_dir}
                with patch.object(subtitle_external, "_find_repo_candidate", return_value=repo_dir):
                    prefix, env, cwd = subtitle_external._videocaptioner_command_prefix()

            self.assertEqual([python_exe, "-m", "videocaptioner"], prefix)
            self.assertEqual(repo_dir, cwd)
            self.assertIn(src_dir, env.get("PYTHONPATH", ""))

    def test_videocaptioner_prefix_supports_posix_venv_python(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = os.path.join(tmp_dir, "VideoCaptioner")
            src_dir = os.path.join(repo_dir, "src")
            python_bin = os.path.join(repo_dir, ".runtime_venv", "bin", "python")
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(os.path.dirname(python_bin), exist_ok=True)
            with open(python_bin, "wb") as f:
                f.write(b"")

            with patch.object(subtitle_external, "os") as mock_os:
                mock_os.name = "posix"
                mock_os.path = os.path
                mock_os.pathsep = os.pathsep
                mock_os.environ = os.environ
                mock_os.makedirs = os.makedirs
                with patch.object(subtitle_external, "config") as mock_config:
                    mock_config.root_dir = tmp_dir
                    mock_config.app = {"workspace_root": tmp_dir}
                    with patch.object(subtitle_external, "_find_repo_candidate", return_value=repo_dir):
                        prefix, env, cwd = subtitle_external._videocaptioner_command_prefix()

            self.assertEqual([python_bin, "-m", "videocaptioner"], prefix)
            self.assertEqual(repo_dir, cwd)
            self.assertIn(src_dir, env.get("PYTHONPATH", ""))

    def test_videocaptioner_prefix_ignores_windows_python_on_posix(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = os.path.join(tmp_dir, "VideoCaptioner")
            python_exe = os.path.join(repo_dir, ".runtime_venv", "Scripts", "python.exe")
            os.makedirs(os.path.dirname(python_exe), exist_ok=True)
            with open(python_exe, "wb") as f:
                f.write(b"")

            with patch.object(subtitle_external, "os") as mock_os:
                mock_os.name = "posix"
                mock_os.path = os.path
                mock_os.pathsep = os.pathsep
                mock_os.environ = os.environ
                mock_os.makedirs = os.makedirs
                with patch.object(subtitle_external, "config") as mock_config:
                    mock_config.root_dir = tmp_dir
                    mock_config.app = {"workspace_root": tmp_dir}
                    with patch.object(subtitle_external, "_find_repo_candidate", return_value=repo_dir):
                        prefix, env, cwd = subtitle_external._videocaptioner_command_prefix()

            self.assertEqual([subtitle_external.sys.executable, "-m", "videocaptioner"], prefix)
            self.assertEqual(repo_dir, cwd)
            self.assertIsNotNone(env)

    def test_run_videocaptioner_uses_cli_and_expected_args(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "demo.mp4")
            subtitle_path = os.path.join(tmp_dir, "demo.srt")
            with open(video_path, "wb") as f:
                f.write(b"fake")
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:01,000 --> 00:00:02,000\n你好\n")

            with patch.object(subtitle_external, "config") as mock_config:
                mock_config.whisper = {
                    "videocaptioner_asr": "bijian",
                    "videocaptioner_language": "auto",
                }
                mock_config.app = {"workspace_root": tmp_dir}
                with patch.object(subtitle_external, "_find_repo_candidate", return_value=""):
                    with patch("app.services.subtitle_external.shutil.which", return_value=r"C:\tools\videocaptioner.exe"):
                        with patch(
                            "app.services.subtitle_external.subprocess.run",
                            return_value=SimpleNamespace(returncode=0, stdout=subtitle_path, stderr=""),
                        ) as mock_run:
                            result = subtitle_external.run_external_subtitle_backend(
                                "videocaptioner_shell",
                                video_file=video_path,
                                audio_file=os.path.join(tmp_dir, "demo.wav"),
                                subtitle_file=subtitle_path,
                            )

            self.assertEqual(os.path.abspath(subtitle_path), result)
            argv = mock_run.call_args.args[0]
            self.assertEqual(argv[0], r"C:\tools\videocaptioner.exe")
            self.assertIn("transcribe", argv)
            self.assertIn("--format", argv)
            self.assertIn("srt", argv)
            self.assertIn("--quiet", argv)
            self.assertIn(os.path.abspath(subtitle_path), argv)


if __name__ == "__main__":
    unittest.main()
