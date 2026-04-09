import json
import re
from typing import Any, Dict, List


REQUIRED_FIELDS = ["_id", "timestamp", "picture", "narration", "OST"]
TIMESTAMP_PATTERN = r"^\d{2}:\d{2}:\d{2},\d{3}-\d{2}:\d{2}:\d{2},\d{3}$"


def _load_script_data(script_content: Any) -> List[Dict[str, Any]]:
    if isinstance(script_content, list):
        return script_content
    if isinstance(script_content, dict):
        if isinstance(script_content.get("items"), list):
            return script_content["items"]
        raise ValueError('脚本必须是JSON数组格式')
    if isinstance(script_content, str):
        data = json.loads(script_content)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            data = data["items"]
        if not isinstance(data, list):
            raise ValueError('脚本必须是JSON数组格式')
        return data
    raise TypeError(f"不支持的脚本内容类型: {type(script_content).__name__}")


def _narration_required(clip: Dict[str, Any]) -> bool:
    try:
        ost = int(clip.get("OST", 2))
    except Exception:
        ost = 2
    return ost in {0, 2}


def check_format(script_content: Any) -> Dict[str, Any]:
    """检查脚本格式。

    支持传入 JSON 字符串、脚本列表，或包含 `items` 的字典。
    """
    try:
        data = _load_script_data(script_content)

        if len(data) == 0:
            return {
                "success": False,
                "message": "脚本数组不能为空",
                "details": "至少需要包含一个脚本片段",
            }

        for i, clip in enumerate(data, start=1):
            if not isinstance(clip, dict):
                return {
                    "success": False,
                    "message": f"第{i}个元素必须是对象类型",
                    "details": f"当前类型: {type(clip).__name__}",
                }

            for field in REQUIRED_FIELDS:
                if field not in clip:
                    return {
                        "success": False,
                        "message": f"第{i}个片段缺少必需字段: {field}",
                        "details": f"必需字段: {', '.join(REQUIRED_FIELDS)}",
                    }

            if not isinstance(clip["_id"], int) or clip["_id"] <= 0:
                return {
                    "success": False,
                    "message": f"第{i}个片段的_id必须是正整数",
                    "details": f"当前值: {clip['_id']} (类型: {type(clip['_id']).__name__})",
                }

            if not isinstance(clip["timestamp"], str) or not re.match(TIMESTAMP_PATTERN, clip["timestamp"]):
                return {
                    "success": False,
                    "message": f"第{i}个片段的timestamp格式错误",
                    "details": '正确格式: "HH:MM:SS,mmm-HH:MM:SS,mmm"，示例: "00:00:00,600-00:00:07,559"',
                }

            if not isinstance(clip["picture"], str) or not clip["picture"].strip():
                return {
                    "success": False,
                    "message": f"第{i}个片段的picture必须是非空字符串",
                    "details": f"当前值: {clip.get('picture', '未定义')}",
                }

            if _narration_required(clip) and (not isinstance(clip["narration"], str) or not clip["narration"].strip()):
                return {
                    "success": False,
                    "message": f"第{i}个片段的narration必须是非空字符串",
                    "details": f"当前值: {clip.get('narration', '未定义')}",
                }

            if not isinstance(clip["OST"], int):
                return {
                    "success": False,
                    "message": f"第{i}个片段的OST必须是整数",
                    "details": f"当前值: {clip['OST']} (类型: {type(clip['OST']).__name__})，常用值: 0, 1, 2",
                }

        return {
            "success": True,
            "message": "脚本格式检查通过",
            "details": f"共验证 {len(data)} 个脚本片段，格式正确",
        }

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "message": f"JSON格式错误: {str(e)}",
            "details": "请检查JSON语法，确保所有括号、引号、逗号正确",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"检查过程中发生错误: {str(e)}",
            "details": "请联系技术支持",
        }


def check_script(script_content: Any, total_duration: float = 0.0) -> Dict[str, Any]:
    """兼容旧调用方的脚本检查入口。"""
    result = check_format(script_content)
    if not result.get("success"):
        raise ValueError(result.get("message") or "脚本格式检查失败")
    return result
