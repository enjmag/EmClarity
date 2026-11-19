"""DeepFilterNet 3 noise suppression via the official standalone binary (MIT / Apache-2.0)."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from ..paths import DEEP_FILTER_EXE

SR = 48_000


def run(audio: np.ndarray, sr: int, atten_limit_db: float | None = None, **_) -> np.ndarray:
    """audio: 1-D float32 at 48 kHz. atten_limit_db caps how much noise is removed (e.g. 12 = gentle)."""
    if sr != SR:
        raise ValueError("DeepFilterNet expects 48 kHz input")
    if not DEEP_FILTER_EXE.exists():
        raise FileNotFoundError(f"{DEEP_FILTER_EXE} missing - run install.bat")
    with tempfile.TemporaryDirectory(prefix="emclarity_df_") as td:
        src = Path(td) / "in.wav"
        out_dir = Path(td) / "out"
        out_dir.mkdir()
        sf.write(str(src), audio, SR, subtype="FLOAT")
        cmd = [str(DEEP_FILTER_EXE), "--compensate-delay", "-o", str(out_dir)]
        if atten_limit_db:
            cmd += ["--atten-lim-db", str(atten_limit_db)]
        cmd.append(str(src))
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        outs = list(out_dir.glob("*.wav"))
        if p.returncode != 0 or not outs:
            raise RuntimeError(f"deep-filter failed:\n{p.stderr[-1500:]}")
        y, ysr = sf.read(str(outs[0]), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if len(y) >= len(audio):
        return y[: len(audio)]
    return np.pad(y, (0, len(audio) - len(y)))
