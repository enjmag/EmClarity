"""EmClarity command line.

  python -m emclarity <files or folders...> [--preset vo_clean] [--out DIR]
  python -m emclarity --list
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from . import paths  # noqa: F401  (pins model caches before torch / HF imports)
from .audio import MEDIA_EXT
from .pipeline import load_presets, process


def collect(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        p = Path(raw.strip('"'))
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in MEDIA_EXT)
        elif p.is_file():
            files.append(p)
        else:
            print(f"!! not found: {p}")
    # never re-process our own outputs
    return [f for f in files if "_emclarity_" not in f.stem]


def main(argv: list[str] | None = None) -> int:
    defaults, presets = load_presets()
    ap = argparse.ArgumentParser(prog="emclarity", description="Local studio-voice enhancement")
    ap.add_argument("inputs", nargs="*", help="audio/video files or folders")
    ap.add_argument("-p", "--preset", default="vo_clean", choices=list(presets))
    ap.add_argument("-o", "--out", type=Path, help="output folder (default: next to each file)")
    ap.add_argument("--list", action="store_true", help="list presets")
    a = ap.parse_args(argv)

    if a.list or not a.inputs:
        print("Presets:")
        for k, v in presets.items():
            print(f"  {k:<14} {v.get('label', '')}")
        return 0 if a.list else 2

    files = collect(a.inputs)
    if not files:
        print("No audio/video files found.")
        return 1
    print(f"EmClarity | preset: {a.preset} | {len(files)} file(s)")
    failed = 0
    for i, f in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {f.name}")
        try:
            r = process(f, a.preset, a.out)
            for w in r["written"]:
                print(f"   -> {w}")
            print(f"   done: {r['duration']:.1f}s of audio in {r['seconds']:.1f}s")
        except Exception as e:  # keep going on batch jobs
            failed += 1
            print(f"   !! failed: {e}")
            traceback.print_exc(limit=2, file=sys.stdout)
    print(f"\nFinished: {len(files) - failed} ok, {failed} failed.")
    return 1 if failed else 0
