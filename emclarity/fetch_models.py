"""Pre-download all model weights into ./models so the first real run is fast (and works offline)."""
from . import paths  # noqa: F401


def main() -> int:
    import torch
    import transformers
    from huggingface_hub import hf_hub_download

    tag = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {tag} ({torch.cuda.get_device_name(0) if tag == 'cuda' else 'no NVIDIA GPU found'})")
    for f in (f"feature_extractor_{tag}.pt", f"decoder_{tag}.pt"):
        print("Sidon:", hf_hub_download("sarulab-speech/sidon-v0.1", filename=f))
    transformers.SeamlessM4TFeatureExtractor.from_pretrained("facebook/w2v-bert-2.0")
    print("w2v-BERT 2.0 feature extractor config: ok")
    from demucs.pretrained import get_model

    get_model("htdemucs")
    print("Demucs htdemucs: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
