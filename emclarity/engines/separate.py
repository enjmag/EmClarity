"""Demucs v4 (htdemucs, MIT) voice / background separation."""
from __future__ import annotations

import numpy as np

from .. import paths  # noqa: F401

_cache: dict = {}


def _model(name: str):
    if name not in _cache:
        from demucs.pretrained import get_model

        m = get_model(name)
        m.eval()
        _cache[name] = m
    return _cache[name]


def run(audio_stereo: np.ndarray, sr: int, model: str = "htdemucs", device: str | None = None,
        shifts: int = 1, **_) -> tuple[np.ndarray, np.ndarray]:
    """audio_stereo: (samples, 2) float32 at `sr`. Returns (vocals, background) each (samples, 2) at `sr`."""
    import torch
    import torchaudio.functional as AF
    from demucs.apply import apply_model

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    m = _model(model)
    x = torch.from_numpy(np.ascontiguousarray(audio_stereo.T)).float()
    if sr != m.samplerate:
        x = AF.resample(x, sr, m.samplerate)
    ref = x.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    with torch.inference_mode():
        stems = apply_model(m, ((x - mean) / std)[None], device=device, shifts=shifts,
                            split=True, overlap=0.25, progress=False)[0]
    stems = stems * std + mean
    vi = m.sources.index("vocals")
    vocals = stems[vi]
    background = stems.sum(0) - vocals
    if sr != m.samplerate:
        vocals = AF.resample(vocals, m.samplerate, sr)
        background = AF.resample(background, m.samplerate, sr)
    n = audio_stereo.shape[0]

    def fit(t):
        a = t.cpu().numpy().T
        return a[:n] if a.shape[0] >= n else np.pad(a, ((0, n - a.shape[0]), (0, 0)))

    return fit(vocals).astype(np.float32), fit(background).astype(np.float32)
