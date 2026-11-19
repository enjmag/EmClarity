"""Executed by envs/resemble python (torch 2.1.1).

  runner.py --fetch                                   download weights only
  runner.py in.wav out.wav mode nfe lambd tau solver  process one file
"""
import os
import sys
import types
from pathlib import Path


def _stub_deepspeed():
    """deepspeed is training-only and does not build on Windows. Provide inert stand-ins for
    the names resemble_enhance imports at module level; none are used during inference."""
    try:
        import deepspeed  # noqa: F401
        return
    except Exception:
        pass

    class _Inert:
        def __init__(self, *a, **k):
            pass

    def _mod(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m
        return m

    _mod("deepspeed", DeepSpeedConfig=_Inert, init_distributed=lambda *a, **k: None)
    _mod("deepspeed.accelerator", get_accelerator=lambda: None)
    _mod("deepspeed.runtime")
    _mod("deepspeed.runtime.engine", DeepSpeedEngine=_Inert)
    _mod("deepspeed.runtime.utils", clip_grad_norm_=lambda *a, **k: None)


def run_dir() -> Path:
    root = Path(os.environ.get("EMCLARITY_RESEMBLE_RUN_DIR", Path(__file__).resolve().parents[2] / "models" / "resemble"))
    rd = root / "enhancer_stage2"
    if not (rd / "hparams.yaml").exists():
        from huggingface_hub import snapshot_download

        snapshot_download("ResembleAI/resemble-enhance", allow_patterns=["enhancer_stage2/*", "enhancer_stage2/**"],
                          local_dir=str(root))
    return rd


def main():
    if sys.argv[1:2] == ["--fetch"]:
        print("Resemble Enhance weights:", run_dir())
        return
    _stub_deepspeed()
    if os.name == "nt":  # hparams.yaml was saved on Linux and contains !!python/object PosixPath tags
        import pathlib

        pathlib.PosixPath = pathlib.WindowsPath
    import soundfile as sf
    import torch
    from resemble_enhance.enhancer.inference import denoise, enhance

    src, dst, mode, nfe, lambd, tau, solver = sys.argv[1:8]
    rd = run_dir()
    wav, sr = sf.read(src, dtype="float32", always_2d=True)
    dwav = torch.from_numpy(wav.mean(axis=1))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if mode == "denoise":
        out, osr = denoise(dwav, sr, device, run_dir=rd)
    else:
        out, osr = enhance(dwav, sr, device, nfe=int(nfe), solver=solver, lambd=float(lambd),
                           tau=float(tau), run_dir=rd)
    sf.write(dst, out.cpu().numpy(), osr, subtype="FLOAT")


if __name__ == "__main__":
    main()
