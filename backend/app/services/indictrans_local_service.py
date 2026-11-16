"""Lazy, offline IndicTrans2 runtime.

This module never downloads a model.  The explicit download script places the
required files under ``backend/models``; this runtime refuses network access.
"""

import gc
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.config import get_settings


INDIC_LANGUAGE_CODES = {
    "as": ("Assamese", "asm_Beng"), "bn": ("Bengali", "ben_Beng"), "brx": ("Bodo", "brx_Deva"),
    "doi": ("Dogri", "doi_Deva"), "gu": ("Gujarati", "guj_Gujr"), "hi": ("Hindi", "hin_Deva"),
    "kn": ("Kannada", "kan_Knda"), "ks": ("Kashmiri", "kas_Arab"), "kok": ("Konkani", "gom_Deva"),
    "mai": ("Maithili", "mai_Deva"), "ml": ("Malayalam", "mal_Mlym"), "mni": ("Manipuri", "mni_Mtei"),
    "mr": ("Marathi", "mar_Deva"), "ne": ("Nepali", "npi_Deva"), "or": ("Odia", "ory_Orya"),
    "pa": ("Punjabi", "pan_Guru"), "sa": ("Sanskrit", "san_Deva"), "sat": ("Santali", "sat_Olck"),
    "sd": ("Sindhi", "snd_Arab"), "ta": ("Tamil", "tam_Taml"), "te": ("Telugu", "tel_Telu"),
    "ur": ("Urdu", "urd_Arab"),
}
SOURCE_LANGUAGE = "eng_Latn"


class LocalIndicTransUnavailable(RuntimeError):
    """The optional local runtime is not installed or its files are absent."""


class LocalIndicTransEngine:
    """Loads IndicTrans2 once, only when a cache miss needs translation."""

    def __init__(self):
        settings = get_settings()
        project_backend = Path(__file__).resolve().parents[2]
        configured_path = Path(settings.indictrans_model_path)
        self.model_path = configured_path if configured_path.is_absolute() else project_backend / configured_path
        self.device_preference = settings.indictrans_device.lower()
        self.batch_size = max(1, settings.indictrans_batch_size)
        self.num_beams = max(1, settings.indictrans_num_beams)
        self._model = self._tokenizer = self._processor = self._torch = self._device = None
        # FastAPI runs synchronous endpoints in a thread pool.  Serialize model
        # access: concurrent first-time locale requests otherwise compete for
        # the same model/GPU and can make every queued request look timed out.
        self._inference_lock = Lock()

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.is_dir():
            raise LocalIndicTransUnavailable(
                f"Local IndicTrans2 model is missing at {self.model_path}. "
                "Run scripts/download_indictrans_model.py explicitly; the API never downloads models."
            )
        missing_files = [name for name in ("model.safetensors", "model.SRC", "model.TGT") if not (self.model_path / name).is_file()]
        if missing_files:
            raise LocalIndicTransUnavailable(
                "Local IndicTrans2 model download is incomplete; missing "
                f"{', '.join(missing_files)}. Run scripts/download_indictrans_model.py again to resume."
            )
        try:
            import torch
            from IndicTransToolkit import IndicProcessor
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as error:
            raise LocalIndicTransUnavailable(
                "Local IndicTrans2 dependencies are missing. Install backend/requirements.txt first."
            ) from error

        if self.device_preference == "cuda" and not torch.cuda.is_available():
            raise LocalIndicTransUnavailable("INDICTRANS_DEVICE=cuda was selected but no CUDA GPU is available.")
        device = "cuda" if self.device_preference == "cuda" or (
            self.device_preference == "auto" and torch.cuda.is_available()
        ) else "cpu"
        self._auto_model_loader = AutoModelForSeq2SeqLM
        self._auto_tokenizer_loader = AutoTokenizer
        self._processor_factory = IndicProcessor
        self._torch = torch
        try:
            self._load_model(device)
        except RuntimeError as error:
            if device == "cuda" and self.device_preference == "auto" and self._is_cuda_oom(error):
                self._release_cuda_memory()
                try:
                    self._load_model("cpu")
                except Exception as fallback_error:
                    raise LocalIndicTransUnavailable(
                        "IndicTrans2 exhausted CUDA memory and could not be retried on CPU. "
                        "Close GPU-intensive applications or set INDICTRANS_DEVICE=cpu."
                    ) from fallback_error
            else:
                raise LocalIndicTransUnavailable(
                    "Local IndicTrans2 could not be loaded. Verify that the explicit download completed successfully."
                ) from error
        except Exception as error:
            raise LocalIndicTransUnavailable(
                "Local IndicTrans2 could not be loaded. Verify that the explicit download completed successfully."
            ) from error

    @staticmethod
    def _is_cuda_oom(error: RuntimeError) -> bool:
        return "cuda" in str(error).lower() and "out of memory" in str(error).lower()

    def _load_model(self, device: str) -> None:
        tokenizer = self._auto_tokenizer_loader.from_pretrained(
            self.model_path, trust_remote_code=True, local_files_only=True
        )
        model = self._auto_model_loader.from_pretrained(
            self.model_path, trust_remote_code=True, local_files_only=True
        ).to(device)
        model.eval()
        self._tokenizer, self._model = tokenizer, model
        self._processor, self._device = self._processor_factory(inference=True), device

    def _release_cuda_memory(self) -> None:
        self._model = self._tokenizer = self._processor = None
        gc.collect()
        if self._torch and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    def _retry_on_cpu_after_cuda_oom(self, error: RuntimeError) -> bool:
        if self._device != "cuda" or not self._is_cuda_oom(error):
            return False
        if self.device_preference != "auto":
            raise LocalIndicTransUnavailable(
                "IndicTrans2 exhausted CUDA memory. Close GPU-intensive applications, reduce "
                "INDICTRANS_BATCH_SIZE, or set INDICTRANS_DEVICE=cpu."
            ) from error
        self._release_cuda_memory()
        try:
            self._load_model("cpu")
        except Exception as fallback_error:
            raise LocalIndicTransUnavailable(
                "IndicTrans2 exhausted CUDA memory and could not be retried on CPU. "
                "Close GPU-intensive applications or set INDICTRANS_DEVICE=cpu."
            ) from fallback_error
        return True

    def _translate_chunk(self, texts: list[str], target_language: str) -> list[str]:
        prepared = self._processor.preprocess_batch(texts, src_lang=SOURCE_LANGUAGE, tgt_lang=target_language)
        encoded = self._tokenizer(
            prepared, padding="longest", truncation=True, max_length=256, return_tensors="pt"
        ).to(self._device)
        with self._torch.inference_mode():
            generated = self._model.generate(
                **encoded,
                num_beams=self.num_beams,
                num_return_sequences=1,
                max_new_tokens=128,
                use_cache=False,
            )
        decoded = self._tokenizer.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        return self._processor.postprocess_batch(decoded, lang=target_language)

    def translate_batch(self, texts: list[str], target_locale: str) -> list[str]:
        if target_locale == "en":
            return texts
        if target_locale not in INDIC_LANGUAGE_CODES:
            raise ValueError(f"Unsupported IndicTrans2 locale: {target_locale}")
        self._load()
        target_language = INDIC_LANGUAGE_CODES[target_locale][1]
        translated: list[str] = []
        with self._inference_lock:
            for start in range(0, len(texts), self.batch_size):
                chunk = texts[start:start + self.batch_size]
                try:
                    translated.extend(self._translate_chunk(chunk, target_language))
                except RuntimeError as error:
                    if not self._retry_on_cpu_after_cuda_oom(error):
                        raise
                    translated.extend(self._translate_chunk(chunk, target_language))
        return translated


@lru_cache(maxsize=1)
def get_local_indictrans_engine() -> LocalIndicTransEngine:
    return LocalIndicTransEngine()
