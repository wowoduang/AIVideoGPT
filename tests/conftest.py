import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

os.environ.setdefault("NARRATO_CONFIG_FILE", str(ROOT / "config.toml"))
os.environ.setdefault("NARRATO_WEBUI_CONFIG_FILE", str(ROOT / "config.toml"))
