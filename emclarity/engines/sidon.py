"""Sidon v0.1 speech restoration (MIT) - w2v-BERT 2.0 features -> neural vocoder, 48 kHz out.

Follows the reference inference in the official demo Space (sarulab-speech/sidon_demo_beta).
"""
from __future__ import annotations

import numpy as np

from .. import paths  # noqa: F401  (pins model caches)

REPO = "sarulab-speech/sidon-v0.1"
SR_OUT = 48_000
CHUNK_S = 96
# Measured constant output delay of the Sidon v0.1 vocoder at 48 kHz (~7.75 ms, stable across
# clip length/content). Trimmed so output is frame-exact with the input.
LATENCY_48K = 372

_cache: dict = {}


def _models(device: str):
    if device in _cache:
        return _cache[device]
    import torch
    import transformers
    from huggingface_hub import hf_hub_download

    tag = "cuda" if device.startswith("cuda") else "cpu"
    fe_path = hf_hub_download(REPO, filename=f"feature_extractor_{tag}.pt")
    dec_path = hf_hub_download(REPO, filename=f"decoder_{tag}.pt")
    fe = torch.jit.load(fe_path, map_location=device).to(device).eval()
    dec = torch.jit.load(dec_path, map_location=device).to(device).eval()
    pre = transformers.SeamlessM4TFeatureExtractor.from_pretrained("facebook/w2v-bert-2.0")
    _cache[device] = (fe, dec, pre)
    return _cache[device]


def device_default() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def run(audio: np.ndarray, sr: int, device: str | None = None, **_) -> np.ndarray:
    """audio: 1-D float32 at `sr`. Returns 1-D float32 at 48 kHz, same duration."""
    import torch
    import torchaudio.functional as AF

    device = device or device_default()
    fe, dec, pre = _models(device)

    peak = float(np.abs(audio).max()) or 1.0
    target_n = int(round(SR_OUT / sr * len(audio)))
    wav = torch.from_numpy((0.9 * audio / peak).astype(np.float32)).view(1, -1)

    with torch.inference_mode():
        wav = AF.highpass_biquad(wav, sr, 50)
        wav16 = AF.resample(wav, sr, 16_000)
        wav16 = torch.nn.functional.pad(wav16, (0, 24_000))
        out, cache = [], None
        for chunk in wav16.view(-1).split(16_000 * CHUNK_S):
            inputs = pre(torch.nn.functional.pad(chunk, (160, 160)), return_tensors="pt",
                         sampling_rate=16_000)
            feat = fe(inputs["input_features"].to(device))["last_hidden_state"]
            if cache is not None:
                feat = torch.cat([cache, feat], dim=1)
            out.append(dec(feat.transpose(1, 2)).view(-1)[:-960])
            cache = feat[:, -1:]
        restored = torch.cat(out).float().cpu().numpy()

    restored = restored[LATENCY_48K:LATENCY_48K + target_n]
    if len(restored) < target_n:
        restored = np.pad(restored, (0, target_n - len(restored)))
    return restored.astype(np.float32)
