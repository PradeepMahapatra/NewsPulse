import re
from typing import Any

from langdetect import DetectorFactory, LangDetectException, detect


DetectorFactory.seed = 0
SUPPORTED_LANGUAGES = {"en", "hi", "fr", "de", "es", "pt", "it", "nl", "ru", "ar", "ja", "ko", "zh"}
MAX_ANALYSIS_CHARS = 4000


def build_analysis_text(title: Any, description: Any) -> str:
    parts = [value.strip() for value in (title, description) if isinstance(value, str) and value.strip()]
    return re.sub(r"\s+", " ", " ".join(parts))[:MAX_ANALYSIS_CHARS]


def normalize_language(language: Any) -> str | None:
    if not isinstance(language, str) or not language.strip():
        return None
    code = language.strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else None


def detect_language(text: str, metadata: Any = None) -> str:
    metadata_language = normalize_language(metadata)
    if metadata_language:
        return metadata_language
    if not text:
        return "unknown"
    try:
        detected = normalize_language(detect(text))
    except LangDetectException:
        detected = None
    return detected or "unknown"