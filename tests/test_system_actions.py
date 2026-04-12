import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _Logger:
    def error(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_system_actions_module(layout=None, layout_dirs=None):
    workspace_module = _stub_module(
        "app.utils.workspace",
        workspace_layout_paths=lambda create=False: layout or {},
        WORKSPACE_LAYOUT_DIRS=layout_dirs or tuple((layout or {}).keys()),
    )
    app_utils_module = _stub_module("app.utils", workspace=workspace_module)
    loguru_module = _stub_module("loguru", logger=_Logger())

    stubbed_modules = {
        "app.utils": app_utils_module,
        "app.utils.workspace": workspace_module,
        "loguru": loguru_module,
    }

    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_system_actions"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/services/system_actions.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class SystemActionsTests(unittest.TestCase):
    def test_get_workspace_layout_rows_keeps_declared_order(self):
        layout = {
            "temp": "D:/workspace/temp",
            "cache": "D:/workspace/cache",
        }
        module = _load_system_actions_module(layout=layout, layout_dirs=("temp", "cache"))

        rows = module.get_workspace_layout_rows()

        self.assertEqual([("temp", "D:/workspace/temp"), ("cache", "D:/workspace/cache")], rows)

    def test_clear_directory_removes_files_and_subdirs(self):
        module = _load_system_actions_module()
        root_dir = tempfile.mkdtemp()
        nested_dir = os.path.join(root_dir, "nested")
        os.makedirs(nested_dir, exist_ok=True)
        with open(os.path.join(root_dir, "demo.txt"), "w", encoding="utf-8") as file_obj:
            file_obj.write("demo")
        with open(os.path.join(nested_dir, "child.txt"), "w", encoding="utf-8") as file_obj:
            file_obj.write("child")

        try:
            status, message = module.clear_directory(root_dir)
            remaining = os.listdir(root_dir)
        finally:
            shutil.rmtree(root_dir, ignore_errors=True)

        self.assertEqual("success", status)
        self.assertEqual("Directory cleared", message)
        self.assertEqual([], remaining)

    def test_clear_directory_returns_warning_for_missing_path(self):
        module = _load_system_actions_module()

        status, message = module.clear_directory("Z:/path/does/not/exist")

        self.assertEqual(("warning", "Directory does not exist"), (status, message))


if __name__ == "__main__":
    unittest.main()
