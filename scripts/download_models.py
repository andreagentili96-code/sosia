"""Download the optional local NER model used by Sosia (GLiNER multi PII + the mDeBERTa-v3 tokenizer).

The models are NOT part of this repository and Sosia never downloads anything while it runs. Run this script once,
on purpose, to fetch them from Hugging Face into a local folder; afterwards Sosia loads them offline.

    pip install huggingface_hub
    python scripts/download_models.py                 # default folder (see below)
    python scripts/download_models.py --dest ./models

Default folder: $SOSIA_MODELLI if set, otherwise %LOCALAPPDATA%/sosia/modelli-origine on Windows and
~/.local/share/sosia/modelli-origine elsewhere, which is where `sosia --ner gliner` looks first.

Licences (accept them before use):
- urchade/gliner_multi_pii-v1: Apache License 2.0, about 1.16 GB
- microsoft/mdeberta-v3-base (only spm.model, config.json, tokenizer_config.json, about 4.3 MB): MIT License
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MODELLI = {
    "gliner_multi_pii-v1": ("urchade/gliner_multi_pii-v1", ["gliner_config.json", "pytorch_model.bin", "README.md"]),
    "mdeberta-v3-base": ("microsoft/mdeberta-v3-base", ["spm.model", "config.json", "tokenizer_config.json", "README.md"]),
}


def cartella_predefinita() -> Path:
    if os.environ.get("SOSIA_MODELLI"):
        return Path(os.environ["SOSIA_MODELLI"])
    base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / ".local" / "share"
    return base / "sosia" / "modelli-origine"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", type=Path, default=cartella_predefinita(), help="destination folder")
    ap.add_argument("--revision", default=None, help="optional Hugging Face revision (commit hash) to pin")
    a = ap.parse_args()
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("This script needs huggingface_hub:  pip install huggingface_hub", file=sys.stderr)
        return 2
    for cartella, (repo, file) in MODELLI.items():
        dest = a.dest / cartella
        dest.mkdir(parents=True, exist_ok=True)
        for f in file:
            print(f"{repo}/{f} -> {dest}")
            hf_hub_download(repo_id=repo, filename=f, local_dir=dest, revision=a.revision)
    print("\nDone. Sosia will find the models automatically in the default folder; otherwise set")
    print(f"  SOSIA_GLINER={a.dest / 'gliner_multi_pii-v1'}")
    print(f"  SOSIA_MDEBERTA={a.dest / 'mdeberta-v3-base'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
