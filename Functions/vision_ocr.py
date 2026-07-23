"""General OCR adapter used only to match candidate table crops."""

import json
from typing import Any, Iterable, List

from Functions.vision_detection import VisionDependencyError


def _collect_rec_texts(value: Any) -> List[str]:
    """Collect PaddleX/PaddleOCR 3.x rec_texts without binding to result class."""
    if hasattr(value, "json"):
        value = value.json
        value = value() if callable(value) else value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
    if isinstance(value, dict):
        direct = value.get("rec_texts")
        if isinstance(direct, list):
            return [str(item) for item in direct if item]
        texts = []
        for nested in value.values():
            texts.extend(_collect_rec_texts(nested))
        return texts
    if isinstance(value, (list, tuple)):
        texts = []
        for nested in value:
            texts.extend(_collect_rec_texts(nested))
        return texts
    return []


class GeneralOCR:
    def __init__(self, device: str = "cpu"):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise VisionDependencyError(
                "PaddleOCR unavailable; install requirements-vision.txt") from exc
        self.pipeline = PaddleOCR(
            device=device,
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def read(self, image_path: str) -> str:
        return "\n".join(_collect_rec_texts(self.pipeline.predict(image_path)))
