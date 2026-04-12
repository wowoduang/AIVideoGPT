import unittest
from types import SimpleNamespace
from unittest.mock import patch

from webui.utils import job_runner
from webui.utils import local_api_client


class LocalApiClientTests(unittest.TestCase):
    def test_local_api_base_url_uses_loopback_for_wildcard_host(self):
        with patch.object(local_api_client, "config") as mock_config:
            mock_config.app = {
                "local_api_host": "0.0.0.0",
                "local_api_port": 19000,
            }
            self.assertEqual(
                "http://127.0.0.1:19000",
                local_api_client.get_local_api_base_url(),
            )


class JobRunnerTests(unittest.TestCase):
    def test_start_video_job_prefers_local_api_when_available(self):
        params = SimpleNamespace()
        with patch.object(local_api_client, "is_local_api_available", return_value=True), patch.object(
            local_api_client,
            "submit_video_job",
            return_value={"task_id": "api-task", "task_dir": "D:/workspace/tasks/api-task"},
        ):
            result = job_runner.start_video_job(params)

        self.assertEqual("api-task", result["task_id"])
        self.assertEqual(job_runner.TRANSPORT_LOCAL_API, result["transport"])

    def test_start_video_job_falls_back_to_in_process_runner(self):
        params = SimpleNamespace()
        with patch.object(local_api_client, "is_local_api_available", return_value=False), patch(
            "webui.utils.job_runner.start_local_video_job",
            return_value="local-task",
        ), patch(
            "webui.utils.job_runner.get_task_snapshot",
            return_value={"task_dir": "D:/workspace/tasks/local-task"},
        ):
            result = job_runner.start_video_job(params)

        self.assertEqual("local-task", result["task_id"])
        self.assertEqual(job_runner.TRANSPORT_IN_PROCESS, result["transport"])

    def test_start_highlight_script_job_prefers_local_api_when_available(self):
        request = {"video_path": "demo.mp4"}
        with patch.object(local_api_client, "is_local_api_available", return_value=True), patch.object(
            local_api_client,
            "submit_highlight_script_job",
            return_value={"task_id": "highlight-api-task", "task_dir": "D:/workspace/tasks/highlight-api-task"},
        ):
            result = job_runner.start_highlight_script_job(request)

        self.assertEqual("highlight-api-task", result["task_id"])
        self.assertEqual(job_runner.TRANSPORT_LOCAL_API, result["transport"])

    def test_start_highlight_script_job_falls_back_to_in_process_runner(self):
        request = {"video_path": "demo.mp4"}
        with patch.object(local_api_client, "is_local_api_available", return_value=False), patch(
            "webui.utils.job_runner.start_local_highlight_script_job",
            return_value="highlight-local-task",
        ), patch(
            "webui.utils.job_runner.get_task_snapshot",
            return_value={"task_dir": "D:/workspace/tasks/highlight-local-task"},
        ):
            result = job_runner.start_highlight_script_job(request)

        self.assertEqual("highlight-local-task", result["task_id"])
        self.assertEqual(job_runner.TRANSPORT_IN_PROCESS, result["transport"])

    def test_start_movie_story_script_job_prefers_local_api_when_available(self):
        request = {"video_path": "demo.mp4"}
        with patch.object(local_api_client, "is_local_api_available", return_value=True), patch.object(
            local_api_client,
            "submit_movie_story_script_job",
            return_value={"task_id": "movie-story-api-task", "task_dir": "D:/workspace/tasks/movie-story-api-task"},
        ):
            result = job_runner.start_movie_story_script_job(request)

        self.assertEqual("movie-story-api-task", result["task_id"])
        self.assertEqual(job_runner.TRANSPORT_LOCAL_API, result["transport"])

    def test_start_movie_story_script_job_falls_back_to_in_process_runner(self):
        request = {"video_path": "demo.mp4"}
        with patch.object(local_api_client, "is_local_api_available", return_value=False), patch(
            "webui.utils.job_runner.start_local_movie_story_script_job",
            return_value="movie-story-local-task",
        ), patch(
            "webui.utils.job_runner.get_task_snapshot",
            return_value={"task_dir": "D:/workspace/tasks/movie-story-local-task"},
        ):
            result = job_runner.start_movie_story_script_job(request)

        self.assertEqual("movie-story-local-task", result["task_id"])
        self.assertEqual(job_runner.TRANSPORT_IN_PROCESS, result["transport"])


if __name__ == "__main__":
    unittest.main()
