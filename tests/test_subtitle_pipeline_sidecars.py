import json
import os
import tempfile
import unittest

from app.services.subtitle_pipeline import _derive_family_paths, _write_generated_sidecars


class SubtitlePipelineSidecarTests(unittest.TestCase):
    def test_derive_family_paths_reuses_existing_clean_suffix(self):
        family = _derive_family_paths(os.path.join("tmp", "demo_clean.srt"))

        self.assertEqual(os.path.join("tmp", "demo.srt"), family["main"])
        self.assertEqual(os.path.join("tmp", "demo_raw.srt"), family["raw"])
        self.assertEqual(os.path.join("tmp", "demo_clean.srt"), family["clean"])
        self.assertEqual(os.path.join("tmp", "demo_segments.json"), family["segments"])

    def test_write_generated_sidecars_creates_standard_family(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            subtitle_path = os.path.join(tmp_dir, "demo.srt")
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:01,000 --> 00:00:02,000\n你好\n")

            sidecars = _write_generated_sidecars(
                subtitle_path,
                [
                    {
                        "seg_id": "sub_0001",
                        "start": 1.0,
                        "end": 2.0,
                        "text": "你好",
                        "source": "generated_clean",
                        "backend": "videocaptioner_shell",
                        "confidence": None,
                    }
                ],
            )

            self.assertTrue(os.path.exists(sidecars["raw"]))
            self.assertTrue(os.path.exists(sidecars["clean"]))
            self.assertTrue(os.path.exists(sidecars["segments"]))

            with open(sidecars["segments"], "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload[0]["text"], "你好")
            self.assertEqual(payload[0]["backend"], "videocaptioner_shell")


if __name__ == "__main__":
    unittest.main()
