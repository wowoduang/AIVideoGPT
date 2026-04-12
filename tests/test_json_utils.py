import unittest

from app.utils.json_utils import parse_and_fix_json


class JsonUtilsTests(unittest.TestCase):
    def test_parse_and_fix_json_accepts_plain_json(self):
        self.assertEqual({"a": 1}, parse_and_fix_json('{"a": 1}'))

    def test_parse_and_fix_json_accepts_markdown_fence(self):
        payload = """```json
{"items": [1, 2]}
```"""
        self.assertEqual({"items": [1, 2]}, parse_and_fix_json(payload))

    def test_parse_and_fix_json_repairs_double_braces(self):
        self.assertEqual({"a": 1}, parse_and_fix_json('{{"a": 1}}'))


if __name__ == "__main__":
    unittest.main()
