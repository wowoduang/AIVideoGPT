from __future__ import annotations

import json
import re
from typing import Any


def parse_and_fix_json(json_string: str) -> Any:
    if not json_string or not str(json_string).strip():
        return None

    normalized = str(json_string).strip()

    try:
        return json.loads(normalized)
    except Exception:
        pass

    try:
        fixed_braces = normalized.replace("{{", "{").replace("}}", "}")
        return json.loads(fixed_braces)
    except Exception:
        pass

    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", normalized, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1).strip())
    except Exception:
        pass

    return None
