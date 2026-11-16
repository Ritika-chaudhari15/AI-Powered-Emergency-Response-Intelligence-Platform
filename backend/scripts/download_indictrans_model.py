"""Explicitly download only the local IndicTrans2 model files; never uses Git LFS."""

from pathlib import Path

from huggingface_hub import snapshot_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError


MODEL_ID = "ai4bharat/indictrans2-en-indic-dist-200M"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "indictrans2-en-indic-dist-200M"


def main() -> None:
    print("Downloading the required IndicTrans2 model files only. Git LFS is not used.")
    try:
        snapshot_download(
            repo_id=MODEL_ID,
            local_dir=MODEL_DIR,
            # The model card lists Safetensors, so do not download a duplicate .bin checkpoint.
            allow_patterns=["*.json", "*.py", "*.safetensors", "model.SRC", "model.TGT", "LICENSE"],
        )
    except GatedRepoError:
        print(
            "\nAccess was denied because IndicTrans2 is a gated Hugging Face model.\n"
            "1. Open https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M while signed in.\n"
            "2. Accept its access conditions.\n"
            "3. Create a new Hugging Face token with Read permission.\n"
            "4. In this PowerShell window only, run:\n"
            "   $env:HF_TOKEN='hf_your_new_read_token'\n"
            "   python scripts/download_indictrans_model.py\n"
            "   Remove-Item Env:HF_TOKEN\n"
            "The token is needed only for this one-time download and is not used by the running backend."
        )
        raise SystemExit(2)
    except HfHubHTTPError as error:
        print(f"\nIndicTrans2 download failed: {error}. Check your internet connection and try again.")
        raise SystemExit(1) from error
    print(f"Local model is ready at: {MODEL_DIR}")


if __name__ == "__main__":
    main()
