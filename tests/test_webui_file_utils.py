import json
import os
import tempfile
import unittest

from webui.utils import file_utils


class _FakeUpload:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self._cursor = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._payload) - self._cursor
        start = self._cursor
        end = min(len(self._payload), self._cursor + size)
        self._cursor = end
        return self._payload[start:end]

    def seek(self, offset: int, whence: int = 0) -> None:
        if whence == 0:
            self._cursor = offset
        elif whence == 1:
            self._cursor += offset
        elif whence == 2:
            self._cursor = len(self._payload) + offset


class FileUtilsTests(unittest.TestCase):
    def test_build_unique_file_path_sanitizes_name(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = file_utils.build_unique_file_path(tmp_dir, "../demo.json")
            self.assertEqual(os.path.join(tmp_dir, "demo.json"), path)

    def test_save_uploaded_file_persists_content_and_resets_cursor(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            upload = _FakeUpload("clip.mp4", b"hello world")
            saved_path = file_utils.save_uploaded_file(
                upload,
                tmp_dir,
                allowed_types=[".mp4"],
                chunk_size=4,
                default_stem="video",
            )

            self.assertTrue(saved_path)
            with open(saved_path, "rb") as f:
                self.assertEqual(b"hello world", f.read())

            self.assertEqual(0, upload._cursor)

    def test_save_text_and_json_file_use_unique_workspace_friendly_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            text_path = file_utils.save_text_file("abc", tmp_dir, "note.txt")
            json_path = file_utils.save_json_file({"ok": True}, tmp_dir, "data.json")

            self.assertTrue(os.path.exists(text_path))
            self.assertTrue(os.path.exists(json_path))

            with open(text_path, "r", encoding="utf-8") as f:
                self.assertEqual("abc", f.read())

            with open(json_path, "r", encoding="utf-8") as f:
                self.assertEqual({"ok": True}, json.load(f))


if __name__ == "__main__":
    unittest.main()
