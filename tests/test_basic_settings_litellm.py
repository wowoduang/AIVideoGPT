import importlib.util
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _Logger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_basic_settings_module():
    streamlit_module = _stub_module("streamlit")
    config_module = _stub_module(
        "app.config",
        config=SimpleNamespace(app={}, proxy={}, ui={}),
    )
    utils_module = _stub_module("app.utils.utils")
    app_utils_module = _stub_module("app.utils", utils=utils_module)
    unified_service_module = _stub_module(
        "app.services.llm.unified_service",
        UnifiedLLMService=type("UnifiedLLMService", (), {"clear_cache": staticmethod(lambda: None)}),
    )
    user_settings_module = _stub_module(
        "app.services.user_settings",
        apply_user_settings_to_config=lambda *_args, **_kwargs: None,
        save_runtime_settings=lambda *_args, **_kwargs: None,
    )
    loguru_module = _stub_module("loguru", logger=_Logger())

    repo_root = os.path.dirname(os.path.dirname(__file__))
    file_path = os.path.join(repo_root, "webui", "components", "basic_settings.py")
    spec = importlib.util.spec_from_file_location("test_basic_settings_module", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader

    with patch.dict(
        sys.modules,
        {
            "streamlit": streamlit_module,
            "app.config": config_module,
            "app.utils": app_utils_module,
            "app.utils.utils": utils_module,
            "app.services.llm.unified_service": unified_service_module,
            "app.services.user_settings": user_settings_module,
            "loguru": loguru_module,
        },
    ):
        spec.loader.exec_module(module)
    return module


class BasicSettingsLiteLLMTests(unittest.TestCase):
    def test_normalize_litellm_model_name_maps_doubao_to_volcengine(self):
        module = _load_basic_settings_module()

        self.assertEqual(
            "volcengine/ep-20260410-123456-abcd",
            module.normalize_litellm_model_name("doubao", "ep-20260410-123456-abcd"),
        )

    def test_build_base_url_help_for_doubao_uses_ark_endpoint(self):
        module = _load_basic_settings_module()

        help_text, requires_base, placeholder = module.build_base_url_help("doubao", "文案生成模型")

        self.assertTrue(requires_base)
        self.assertEqual("https://ark.cn-beijing.volces.com/api/v3", placeholder)
        self.assertIn("ark.cn-beijing.volces.com/api/v3", help_text)

    def test_build_base_url_help_for_volcengine_uses_ark_endpoint(self):
        module = _load_basic_settings_module()

        help_text, requires_base, placeholder = module.build_base_url_help("volcengine", "视频分析模型")

        self.assertTrue(requires_base)
        self.assertEqual("https://ark.cn-beijing.volces.com/api/v3", placeholder)
        self.assertIn("ark.cn-beijing.volces.com/api/v3", help_text)


if __name__ == "__main__":
    unittest.main()
