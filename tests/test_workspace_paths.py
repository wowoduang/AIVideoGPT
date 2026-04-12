import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import config as app_config
from app.utils import utils
from app.utils import workspace
from webui.config import settings as webui_settings


class WorkspacePathTests(unittest.TestCase):
    def test_default_workspace_uses_storage_directory(self):
        with patch.object(workspace, "config") as mock_config:
            mock_config.root_dir = r"F:\demo-project"
            mock_config.app = {}

            result = workspace.cache_dir("tts_cache")

        expected = os.path.abspath(r"F:\demo-project-workspace\cache\tts_cache")
        self.assertEqual(expected, result)

    def test_relative_workspace_root_resolves_from_project_root(self):
        with patch.object(workspace, "config") as mock_config:
            mock_config.root_dir = r"F:\demo-project"
            mock_config.app = {"workspace_root": r"..\workspace-data"}

            result = workspace.temp_dir("subtitles")

        expected = os.path.abspath(r"F:\demo-project\..\workspace-data\temp\subtitles")
        self.assertEqual(expected, result)

    def test_explicit_workspace_root_argument_overrides_config(self):
        with patch.object(workspace, "config") as mock_config:
            mock_config.root_dir = r"F:\demo-project"
            mock_config.app = {"workspace_root": r"..\workspace-data"}

            result = workspace.task_dir("demo", workspace_root=r"D:\custom-workspace")

        expected = os.path.abspath(r"D:\custom-workspace\tasks\demo")
        self.assertEqual(expected, result)

    def test_cleanup_targets_collect_repo_junk_and_vendor_runtime(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            appdata_dir = os.path.join(tmp_dir, "AppData")
            vendor_work_dir = os.path.join(tmp_dir, "vendor", "VideoCaptioner", "work-dir")
            os.makedirs(appdata_dir, exist_ok=True)
            os.makedirs(vendor_work_dir, exist_ok=True)

            with patch.object(workspace, "config") as mock_config:
                mock_config.root_dir = tmp_dir
                mock_config.app = {}
                groups = workspace.cleanup_target_groups(include_vendor_runtime=True)

        self.assertIn(os.path.abspath(appdata_dir), groups["repo_junk"])
        self.assertIn(os.path.abspath(vendor_work_dir), groups["vendor_runtime"])

    def test_cleanup_targets_collect_model_vcs_from_repo_and_workspace(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_model_git = os.path.join(tmp_dir, "app", "models", "faster-whisper-large-v2", ".git")
            workspace_root = os.path.join(tmp_dir, "workspace")
            workspace_model_git = os.path.join(workspace_root, "models", "faster-whisper-large-v2", ".git")
            os.makedirs(repo_model_git, exist_ok=True)
            os.makedirs(workspace_model_git, exist_ok=True)

            with patch.object(workspace, "config") as mock_config:
                mock_config.root_dir = tmp_dir
                mock_config.app = {"workspace_root": workspace_root}
                groups = workspace.cleanup_target_groups(include_model_vcs=True)

        self.assertIn(os.path.abspath(repo_model_git), groups["model_vcs"])
        self.assertIn(os.path.abspath(workspace_model_git), groups["model_vcs"])

    def test_utils_media_dirs_follow_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(workspace, "config") as mock_workspace_config:
                mock_workspace_config.root_dir = r"F:\demo-project"
                mock_workspace_config.app = {"workspace_root": tmp_dir}

                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "videos")),
                    utils.video_dir(),
                )
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "subtitles")),
                    utils.subtitle_dir(),
                )
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "scripts")),
                    utils.script_dir(),
                )
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "models")),
                    utils.model_dir(),
                )
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "fonts")),
                    utils.font_dir(),
                )
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "songs")),
                    utils.song_dir(),
                )
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "analysis", "json")),
                    utils.analysis_dir("json"),
                )

    def test_workspace_layout_paths_follow_workspace_root(self):
        with patch.object(workspace, "config") as mock_config:
            mock_config.root_dir = r"F:\demo-project"
            mock_config.app = {}

            layout = workspace.workspace_layout_paths()

        self.assertEqual(
            os.path.abspath(r"F:\demo-project-workspace\videos"),
            layout["videos"],
        )
        self.assertEqual(
            os.path.abspath(r"F:\demo-project-workspace\analysis\json"),
            layout["analysis/json"],
        )
        self.assertEqual(
            os.path.abspath(r"F:\demo-project-workspace\state"),
            layout["state"],
        )

    def test_app_config_defaults_to_workspace_state_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"NARRATO_WORKSPACE_ROOT": tmp_dir}, clear=False):
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "state", "config.toml")),
                    app_config.resolve_config_file(),
                )

    def test_webui_config_defaults_to_workspace_state_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"NARRATO_WORKSPACE_ROOT": tmp_dir}, clear=False):
                self.assertEqual(
                    os.path.abspath(os.path.join(tmp_dir, "state", "webui.toml")),
                    webui_settings.resolve_config_path(),
                )


if __name__ == "__main__":
    unittest.main()
