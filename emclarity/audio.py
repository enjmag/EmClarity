"""Audio I/O through ffmpeg: decode anything (wav/mp3/m4a/mp4/mov...) and loudness-master the result."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff", ".wma"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mxf"}
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({p.returncode}):\n{p.stderr[-2000:]}")
    return p


def load(path: Path, sr: int = 48000, channels: int = 1) -> np.ndarray:
    """Decode the first audio stream of any media file to float32, shape (samples, channels)."""
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-vn", "-map", "0:a:0",
           "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"Could not decode {path.name}: {p.stderr.decode(errors='replace')[-800:]}")
    a = np.frombuffer(p.stdout, dtype=np.float32).copy()
    return a.reshape(-1, channels)


def save(path: Path, audio: np.ndarray, sr: int = 48000, subtype: str = "PCM_24") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(audio, -1.0, 1.0), sr, subtype=subtype)


def loudnorm(src: Path, dst: Path, target_lufs: float = -16.0, true_peak: float = -1.5,
             lra: float = 11.0, sr: int = 48000) -> dict:
    """Two-pass EBU R128 loudness normalisation. Returns the measured input stats."""
    f = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}"
    p = _run([ffmpeg_exe(), "-hide_banner", "-nostats", "-i", str(src), "-af", f + ":print_format=json",
              "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    stats = json.loads(m.group(0)) if m else {}
    if stats and stats.get("input_i") not in (None, "-inf"):
        f += (f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
              f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
              f":offset={stats['target_offset']}:linear=true")
    _run([ffmpeg_exe(), "-hide_banner", "-y", "-i", str(src), "-af", f, "-ar", str(sr),
          "-c:a", "pcm_s24le", str(dst)])
    return stats


def mux_video(video: Path, wav: Path, dst: Path) -> None:
    """Copy the video stream and replace its audio with the enhanced WAV (AAC 320k)."""
    _run([ffmpeg_exe(), "-hide_banner", "-y", "-i", str(video), "-i", str(wav),
          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
          "-shortest", str(dst)])


def align(ref: np.ndarray, x: np.ndarray, sr: int, max_shift_ms: float = 100.0) -> np.ndarray:
    """Shift x (1-D) so it lines up with ref (1-D); used before wet/dry blending."""
    from scipy.signal import correlate

    lag = estimate_lag(ref, x, sr, max_shift_ms)
    if lag > 0:
        x = x[lag:]
    elif lag < 0:
        x = np.concatenate([np.zeros(-lag, dtype=x.dtype), x])
    return _fit(x, len(ref))


def _envelope(x: np.ndarray, hop: int) -> np.ndarray:
    n = len(x) // hop * hop
    e = np.log(np.sqrt(np.square(x[:n]).reshape(-1, hop).mean(1)) + 1e-4)
    return e - e.mean()


def estimate_lag(ref: np.ndarray, x: np.ndarray, sr: int, max_shift_ms: float = 100.0) -> int:
    """Samples by which x lags ref (positive = x is late).

    Uses log-energy envelopes at 0.5 ms hops rather than raw waveforms: generative engines
    (Sidon, Resemble) re-synthesise phase, so waveform correlation is unreliable for them.
    """
    from scipy.signal import correlate

    hop = max(1, sr // 2000)
    n = min(len(ref), len(x), sr * 30)
    if n < sr // 4:
        return 0
    a, b = _envelope(ref[:n], hop), _envelope(x[:n], hop)
    c = correlate(b, a, mode="full", method="fft")
    lags = np.arange(-len(a) + 1, len(b))
    lim = int(max_shift_ms / 1000 * sr / hop)
    win = np.abs(lags) <= lim
    return int(lags[win][np.argmax(c[win])]) * hop


def _fit(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x), dtype=x.dtype)])
