"""Optional: Resemble Enhance (MIT). Runs in its own env (envs/resemble) because it pins torch 2.1.1.

Install with:  install.bat -WithResemble
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from ..paths import MODELS, RESEMBLE_PY, ROOT

RUNNER = ROOT / "emclarity" / "engines" / "_resemble_runner.py"


def available() -> bool:
    return RESEMBLE_PY.exists()


def run(audio: np.ndarray, sr: int, mode: str = "enhance", nfe: int = 64, lambd: float = 0.9,
        tau: float = 0.5, solver: str = "midpoint", **_) -> np.ndarray:
    """audio 1-D float32 at `sr`; returns 1-D float32 at `sr`. mode: 'enhance' or 'denoise'."""
    if not available():
        raise FileNotFoundError("Resemble Enhance env not installed - run: install.bat -WithResemble")
    import os

    with tempfile.TemporaryDirectory(prefix="emclarity_re_") as td:
        src, dst = Path(td) / "in.wav", Path(td) / "out.wav"
        sf.write(str(src), audio, sr, subtype="FLOAT")
        env = dict(os.environ, HF_HOME=str(MODELS / "hf"), TORCH_HOME=str(MODELS / "torch"),
                   EMCLARITY_RESEMBLE_RUN_DIR=str(MODELS / "resemble"))
        cmd = [str(RESEMBLE_PY), str(RUNNER), str(src), str(dst), mode, str(nfe), str(lambd),
               str(tau), solver]
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", env=env)
        if p.returncode != 0 or not dst.exists():
            raise RuntimeError(f"Resemble Enhance failed:\n{p.stderr[-2000:]}")
        y, ysr = sf.read(str(dst), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if ysr != sr:
        from scipy.signal import resample_poly
        from math import gcd

        g = gcd(sr, ysr)
        y = resample_poly(y, sr // g, ysr // g).astype(np.float32)
    n = len(audio)
    return y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)))
