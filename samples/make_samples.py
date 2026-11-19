"""Rebuild the README before/after samples from a public-domain LibriVox recording.

  .venv\\Scripts\\python samples\\make_samples.py

Source: "Eratosthenes", LibriVox Short Nonfiction Collection Vol. 083 (Public Domain Mark 1.0)
https://archive.org/details/snf083_2106_librivox
Each scenario damages the clean excerpt in a typical way, runs an EmClarity preset on it, and writes
MP3 previews + a before/after spectrogram into samples/.
"""
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from emclarity.audio import ffmpeg_exe  # noqa: E402
from emclarity.pipeline import process  # noqa: E402

SRC_URL = ("https://archive.org/download/snf083_2106_librivox/"
           "snf083_eratosthenes_encyclopediabritannica_pn81.mp3")
OUT = ROOT / "samples"
WORK = OUT / "_work"
START, DUR = 40, 15  # seconds of the source used

# name: (ffmpeg filter that damages the clean voice, preset to fix it, caption)
SCENARIOS = {
    "1_home_office": (
        "[0:a]aformat=sample_rates=48000:channel_layouts=mono[v];"
        "anoisesrc=color=brown:amplitude=0.05:sample_rate=48000[n];"
        "sine=frequency=50:sample_rate=48000,volume=0.015[h];"
        "[v][n][h]amix=inputs=3:duration=first:normalize=0",
        "vo_clean", "Fan rumble + 50 Hz hum"),
    "2_loud_ac": (
        "[0:a]aformat=sample_rates=48000:channel_layouts=mono[v];"
        "anoisesrc=color=pink:amplitude=0.06:sample_rate=48000[n];"
        "[v][n]amix=inputs=2:duration=first:normalize=0",
        "strong_denoise", "Loud air-con hiss"),
    "3_bad_phone_echo": (
        "[0:a]aformat=sample_rates=48000:channel_layouts=mono,"
        "highpass=f=300,lowpass=f=3400,aecho=0.8:0.8:60|130|210:0.45|0.3|0.2[v];"
        "anoisesrc=color=white:amplitude=0.01:sample_rate=48000[n];"
        "[v][n]amix=inputs=2:duration=first:normalize=0",
        "rescue", "Phone-quality, echoey room"),
}


def ff(*args):
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-v", "error", "-y", *args], check=True)


def spectrogram(wav: Path, png: Path, title: str):
    ff("-i", str(wav), "-lavfi",
       f"showspectrumpic=s=900x240:legend=0:color=magma:scale=log:fscale=log:drange=75:stop=16000,"
       f"drawtext=text='{title}':x=12:y=10:fontsize=22:fontcolor=white", str(png))


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    src = WORK / "librivox_src.mp3"
    if not src.exists():
        urllib.request.urlretrieve(SRC_URL, src)
    clean = WORK / "clean.wav"
    ff("-ss", str(START), "-t", str(DUR), "-i", str(src), "-ac", "1", "-ar", "48000", str(clean))
    ff("-i", str(clean), "-b:a", "192k", str(OUT / "0_clean_original.mp3"))

    for name, (filt, preset, caption) in SCENARIOS.items():
        noisy = WORK / f"{name}.wav"
        ff("-i", str(clean), "-filter_complex", filt, str(noisy))
        r = process(noisy, preset, out_dir=WORK, log=lambda *_: None)
        fixed = r["written"][0]
        ff("-i", str(noisy), "-af", "loudnorm=I=-16:TP=-1.5", "-ar", "48000", "-b:a", "192k",
           str(OUT / f"{name}_before.mp3"))
        ff("-i", str(fixed), "-b:a", "192k", str(OUT / f"{name}_after_{preset}.mp3"))
        b, a = WORK / f"{name}_b.png", WORK / f"{name}_a.png"
        spectrogram(noisy, b, f"BEFORE - {caption}")
        spectrogram(fixed, a, f"AFTER - {preset}")
        ff("-i", str(b), "-i", str(a), "-filter_complex", "vstack", str(OUT / f"{name}.png"))
        print(f"{name}: {preset} ok")

    if "--keep-work" not in sys.argv:
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
