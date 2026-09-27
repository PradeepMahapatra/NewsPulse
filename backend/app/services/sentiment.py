from dataclasses import dataclass
from typing import Any


MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
LABELS = {"LABEL_0": "negative", "LABEL_1": "neutral", "LABEL_2": "positive"}


@dataclass(frozen=True)
class SentimentResult:
    label: str
    confidence: float


class SentimentAnalyzer:
    def __init__(self, pipeline_factory: Any = None) -> None:
        self._pipeline_factory = pipeline_factory
        self._pipeline: Any = None

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            if self._pipeline_factory is None:
                from transformers import pipeline

                self._pipeline_factory = pipeline
            self._pipeline = self._pipeline_factory(
                "sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME, top_k=None
            )
        return self._pipeline

    def analyze(self, text: str) -> SentimentResult:
        if not text.strip():
            raise ValueError("cannot analyze empty text")
        result = self._get_pipeline()(text, truncation=True, max_length=512)
        scores = result[0] if result and isinstance(result[0], list) else result
        best = max(scores, key=lambda item: float(item["score"]))
        raw_label = str(best["label"]).upper()
        label = LABELS.get(raw_label, raw_label.lower())
        if label not in {"positive", "neutral", "negative"}:
            raise ValueError("sentiment model returned an unsupported label")
        return SentimentResult(label=label, confidence=float(best["score"]))