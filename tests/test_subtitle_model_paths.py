import os
import tempfile
import unittest
from unittest.mock import patch

from app.services import subtitle


class SubtitleModelPathTests(unittest.TestCase):
    def test_candidate_model_dirs_prefers_workspace_models(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_models = os.path.join(tmp_dir, "models")
            with patch.object(subtitle, "_base_dirs", return_value=[tmp_dir]):
                with patch.object(subtitle.utils, "root_dir", return_value=tmp_dir):
                    with patch.object(subtitle.utils, "model_dir", return_value=workspace_models):
                        result = subtitle._candidate_model_dirs(["faster-whisper-large-v2"])

        self.assertIn(os.path.abspath(os.path.join(workspace_models, "faster-whisper-large-v2")), result)
        self.assertIn(os.path.abspath(os.path.join(tmp_dir, "app", "models", "faster-whisper-large-v2")), result)

    def test_candidate_model_dirs_supports_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_dir = os.path.join(tmp_dir, "fw-large-v2")
            with patch.object(subtitle, "_base_dirs", return_value=[tmp_dir]):
                with patch.object(subtitle.utils, "root_dir", return_value=tmp_dir):
                    with patch.object(subtitle.utils, "model_dir", return_value=os.path.join(tmp_dir, "models")):
                        result = subtitle._candidate_model_dirs([model_dir])

        self.assertEqual([os.path.abspath(model_dir)], result)

    def test_resolve_local_model_path_accepts_workspace_model_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_models = os.path.join(tmp_dir, "models")
            target_dir = os.path.join(workspace_models, "faster-whisper-large-v2")
            os.makedirs(target_dir, exist_ok=True)
            with open(os.path.join(target_dir, "model.bin"), "wb") as f:
                f.write(b"demo")

            with patch.object(subtitle, "_base_dirs", return_value=[tmp_dir]):
                with patch.object(subtitle.utils, "root_dir", return_value=tmp_dir):
                    with patch.object(subtitle.utils, "model_dir", return_value=workspace_models):
                        resolved, searched = subtitle._resolve_local_model_path(
                            ["faster-whisper-large-v2"],
                            require_ctranslate2=True,
                        )

        self.assertEqual(os.path.abspath(target_dir), resolved)
        self.assertIn(os.path.abspath(target_dir), searched)


if __name__ == "__main__":
    unittest.main()
