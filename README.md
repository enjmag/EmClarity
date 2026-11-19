# EmClarity

Local, offline studio-voice enhancement for voiceovers, podcasts and video dialogue — the same job as
Adobe Podcast *Enhance Speech*, running on your own GPU with open models. No upload limits, no daily caps,
batch whole folders.

**Drag files (or a folder) onto `Enhance.bat` → pick a preset → `<name>_emclarity_<preset>.wav` appears next to each file.**

## How it works

Each preset is a chain of steps (edit them in [`presets.yaml`](presets.yaml)):

| Step | Engine | What it does |
|---|---|---|
| `separate` | Demucs v4 (`htdemucs`) | Splits the voice from music / TV / crowd. The background can be saved or mixed back in. |
| `deepfilter` | DeepFilterNet 3 | Fast noise removal. `atten_limit_db` caps how much noise is removed (lower = more natural). |
| `sidon` | Sidon v0.1 | Rebuilds a clean 48 kHz studio voice from w2v-BERT 2.0 speech features (the "Adobe-like" step). |
| `resemble` | Resemble Enhance | Alternative rebuild engine for A/B listening (optional install). |
| master | ffmpeg `loudnorm` | Two-pass EBU R128 to −16 LUFS, −1.5 dBTP, 24-bit WAV. |

`strength` on `sidon` / `resemble` works like Adobe's slider: `1.0` = fully rebuilt voice,
`0.7` = 70 % rebuilt + 30 % of the voice as it was before that step (level-matched).

Output is **sample-aligned with the input** — Sidon's fixed ~7.75 ms vocoder delay is compensated —
so you can drop the WAV straight onto the timeline in place of the original and stay frame-exact.

## Presets

| # | Preset | Chain | Use for |
|---|---|---|---|
| 1 | `vo_clean` (default) | deepfilter → sidon 90 % | Voiceover, talking head, HeyGen/CK takes |
| 2 | `podcast` | deepfilter (−24 dB cap) → sidon 70 % | Natural sound, keeps a little room |
| 3 | `noisy_room` | separate → deepfilter → sidon 100 % | Music/TV/crowd behind the voice; also saves `_background.wav` |
| 4 | `denoise_only` | deepfilter (−18 dB cap) | Light clean-up, no voice rebuild |
| 5 | `resemble` | deepfilter → Resemble Enhance 90 % | Second opinion for A/B |
| 6 | *Compare* | runs 1, 2 and 4 | Side-by-side listening |

## Install (Windows + NVIDIA GPU)

Requirements: Windows 10/11, Python 3.10+ on PATH, an NVIDIA GPU (CPU works, just slower).

```
install.bat                 # main engines (~8.5 GB: PyTorch/CUDA ~7.3 GB + models ~1 GB)
install.bat -WithResemble   # also the optional Resemble Enhance engine (+~6 GB)
```

Everything installs inside this folder (`.venv`, `envs\`, `bin\`, `models\`). Delete the folder to uninstall.

## Command line

```
.venv\Scripts\python -m emclarity --list
.venv\Scripts\python -m emclarity "D:\VO\take3.wav" -p podcast
.venv\Scripts\python -m emclarity "D:\VO\Hook 2" -p vo_clean -o "D:\VO\Hook 2\clean"
```

Inputs: wav, mp3, m4a, flac, aac, ogg, mp4, mov, mkv … (first audio stream). Files already named
`*_emclarity_*` are skipped, so re-running on a folder is safe. Set `mux_video: true` in `presets.yaml`
to also get an `.mp4` with the enhanced audio.

## Measured on a real VO (33 s Hook 1 take, RTX 4070 Ti SUPER)

Test file = the clean take with added pink noise, 60 Hz hum and a 3-tap room echo.

| File | Noise floor vs speech | Similarity to the clean original |
|---|---|---|
| noisy input | −17 dB | 0.67 |
| `denoise_only` | −30 dB | 0.78 |
| `podcast` | −42 dB | 0.875 |
| `vo_clean` | −46 dB | 0.875 |
| `noisy_room` | −49 dB | 0.84 |
| `resemble` | −43 dB | 0.73 |

Speed: ~10–17 s per 33 s clip (about 2–3× faster than real time), all presets.

## Licences

All engines allow commercial use. Model weights are downloaded at install time and are not part of this repo.

| Component | Licence |
|---|---|
| EmClarity code | MIT (see below) |
| Sidon v0.1 weights — `sarulab-speech/sidon-v0.1` | MIT |
| w2v-BERT 2.0 feature extractor — `facebook/w2v-bert-2.0` | MIT |
| DeepFilterNet 3 (binary + model) | MIT or Apache-2.0 (dual) |
| Demucs v4 / htdemucs | MIT |
| Resemble Enhance (optional) | MIT |
| PyTorch | BSD-3-Clause |
| ffmpeg (via `imageio-ffmpeg`) | GPL/LGPL — run as a separate program, not linked |

Do **not** swap in `DialogueSidon` or other CC BY-NC checkpoints for client work — non-commercial only.

## Repo layout

```
Enhance.bat            drag-and-drop entry point (preset menu)
install.bat/.ps1       one-click installer
presets.yaml           preset chains — edit freely
emclarity/
  cli.py               command line / batch runner
  pipeline.py          runs a preset chain, blend + master
  audio.py             ffmpeg decode, loudnorm, video mux, alignment
  engines/             sidon, deepfilter, separate (demucs), resemble (+ isolated runner)
  fetch_models.py      pre-downloads weights into models/
```

## Notes

- Resemble Enhance runs in its own environment (`envs\resemble`, torch 2.1.1) because it pins old
  versions. Its training-only DeepSpeed dependency is replaced by an inert stub, so no compiler is needed.
- `Enhance.bat` runs with `HF_HUB_OFFLINE=1`; after install, nothing leaves your machine.
