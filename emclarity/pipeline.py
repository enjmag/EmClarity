"""Runs a preset chain on one media file."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import numpy as np
import yaml

from . import audio as A
from .paths import PRESETS_FILE

WET_ENGINES = {"sidon", "resemble"}


def load_presets(path: Path = PRESETS_FILE) -> tuple[dict, dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("defaults", {}), data["presets"]


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


def _blend(dry: np.ndarray, wet: np.ndarray, strength: float, sr: int) -> np.ndarray:
    # Engines compensate their own fixed latency, so wet and dry are already sample-aligned.
    # (Adaptive alignment was tried and is fooled by reverberant input.)
    if strength >= 0.999:
        return wet
    dry = dry * (_rms(wet) / _rms(dry))
    return (strength * wet + (1.0 - strength) * dry).astype(np.float32)


def _engine(name: str):
    if name == "sidon":
        from .engines import sidon as m
    elif name == "deepfilter":
        from .engines import deepfilter as m
    elif name == "resemble":
        from .engines import resemble as m
    elif name == "separate":
        from .engines import separate as m
    else:
        raise ValueError(f"Unknown engine '{name}'")
    return m


def output_paths(src: Path, preset: str, out_dir: Path | None = None) -> dict:
    d = out_dir or src.parent
    stem = f"{src.stem}_emclarity_{preset}"
    return {"wav": d / f"{stem}.wav", "background": d / f"{src.stem}_emclarity_background.wav",
            "video": d / f"{stem}.mp4"}


def process(src: Path, preset_name: str, out_dir: Path | None = None, log=print) -> dict:
    defaults, presets = load_presets()
    if preset_name not in presets:
        raise KeyError(f"Preset '{preset_name}' not found. Options: {', '.join(presets)}")
    cfg = {**defaults, **presets[preset_name]}
    sr = int(cfg.get("sample_rate", 48000))
    outs = output_paths(src, preset_name, out_dir)
    t0 = time.time()

    stereo = A.load(src, sr=sr, channels=2)
    voice = stereo.mean(axis=1).astype(np.float32)
    background = None
    if np.abs(voice).max() < 1e-5:
        raise RuntimeError("Input is silent")

    for step in cfg["steps"]:
        step = dict(step)
        name = step.pop("engine")
        strength = float(step.pop("strength", 1.0))
        ts = time.time()
        m = _engine(name)
        if name == "separate":
            vocals, background = m.run(stereo, sr, **step)
            voice = vocals.mean(axis=1)
        elif name in WET_ENGINES:
            wet = m.run(voice, sr, **step)
            voice = _blend(voice, wet, strength, sr)
        else:
            voice = m.run(voice, sr, **step)
        log(f"   {name:<10} {time.time() - ts:6.1f}s")

    bg_db = cfg.get("background_db")
    mix = voice
    if background is not None and bg_db is not None:
        bg = A.align(voice, background.mean(axis=1), sr) * (10 ** (float(bg_db) / 20))
        mix = voice + bg

    loud = cfg.get("loudness")
    with tempfile.TemporaryDirectory(prefix="emclarity_") as td:
        raw = Path(td) / "raw.wav"
        peak = float(np.abs(mix).max()) or 1.0
        A.save(raw, (mix / peak * 0.5).astype(np.float32), sr, subtype="FLOAT")
        if loud:
            A.loudnorm(raw, outs["wav"], loud.get("target_lufs", -16), loud.get("true_peak", -1.5),
                       loud.get("lra", 11), sr)
        else:
            A.save(outs["wav"], mix / peak * 0.89, sr)

    written = [outs["wav"]]
    if background is not None and cfg.get("save_background"):
        A.save(outs["background"], background, sr)
        written.append(outs["background"])
    if cfg.get("mux_video") and src.suffix.lower() in A.VIDEO_EXT:
        A.mux_video(src, outs["wav"], outs["video"])
        written.append(outs["video"])
    return {"written": written, "seconds": time.time() - t0, "duration": len(voice) / sr}
