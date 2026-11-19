"""Project paths. Importing this module pins model caches inside the EmClarity folder."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
BIN = ROOT / "bin"
ENVS = ROOT / "envs"
PRESETS_FILE = ROOT / "presets.yaml"

os.environ.setdefault("HF_HOME", str(MODELS / "hf"))
os.environ.setdefault("TORCH_HOME", str(MODELS / "torch"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

DEEP_FILTER_EXE = BIN / "deep-filter.exe"
RESEMBLE_PY = ENVS / "resemble" / "Scripts" / "python.exe"
