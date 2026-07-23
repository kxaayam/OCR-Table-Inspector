"""Complementary PP-DocLayout and Table Transformer table detection."""

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BBox = Tuple[float, float, float, float]

PP_MODEL = "PP-DocLayout_plus-L"
TT_MODEL = "microsoft/table-transformer-detection"
PP_THRESHOLD = 0.5
TT_THRESHOLD = 0.7
DEDUP_IOU = 0.5
CROP_PADDING = 8


class VisionDependencyError(RuntimeError):
    pass


@dataclass
class Detection:
    detector: str
    label: str
    score: float
    raw_bbox: BBox


@dataclass
class TableCandidate:
    candidate_id: str
    page: int
    raw_bbox: BBox
    crop_bbox: Tuple[int, int, int, int]
    sources: List[str] = field(default_factory=list)
    detector_scores: Dict[str, float] = field(default_factory=dict)
    raw_detections: List[dict] = field(default_factory=list)
    crop_path: Optional[str] = None


def valid_intersection(box: BBox, width: int, height: int) -> bool:
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        return False
    x1, y1, x2, y2 = box
    return x1 < x2 and y1 < y2 and x2 > 0 and y2 > 0 and x1 < width and y1 < height


def clamp_box(box: BBox, width: int, height: int,
              padding: int = CROP_PADDING) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return (max(0, math.floor(x1 - padding)),
            max(0, math.floor(y1 - padding)),
            min(width, math.ceil(x2 + padding)),
            min(height, math.ceil(y2 + padding)))


def iou(a: BBox, b: BBox) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), \
        min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def canonicalize(detections: Sequence[Detection], page: int, width: int,
                 height: int, threshold: float = DEDUP_IOU) -> List[TableCandidate]:
    valid = [d for d in detections if valid_intersection(d.raw_bbox, width, height)]
    valid.sort(key=lambda d: (-d.score, d.detector, d.raw_bbox))
    groups: List[List[Detection]] = []
    for detection in valid:
        group = next((g for g in groups if any(
            iou(detection.raw_bbox, existing.raw_bbox) >= threshold
            for existing in g)), None)
        if group is None:
            groups.append([detection])
        else:
            group.append(detection)
    candidates = []
    for index, group in enumerate(groups):
        # Highest-score member supplies the canonical box; all raw boxes remain.
        representative = group[0]
        candidates.append(TableCandidate(
            candidate_id=f"n{page}_table_{index:03d}",
            page=page,
            raw_bbox=representative.raw_bbox,
            crop_bbox=clamp_box(representative.raw_bbox, width, height),
            sources=sorted({d.detector for d in group}),
            detector_scores={d.detector: max(
                x.score for x in group if x.detector == d.detector) for d in group},
            raw_detections=[asdict(d) for d in group],
        ))
    return candidates


class TableDetectors:
    """Models are loaded once, on construction, and reused."""

    def __init__(self, device: Optional[str] = None):
        try:
            import torch
            from transformers import AutoImageProcessor, \
                TableTransformerForObjectDetection
            from paddlex import create_model
        except ImportError as exc:
            raise VisionDependencyError(
                "vision dependencies unavailable; install requirements-vision.txt"
            ) from exc
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tt_processor = AutoImageProcessor.from_pretrained(TT_MODEL)
        self.tt_model = TableTransformerForObjectDetection.from_pretrained(
            TT_MODEL).to(self.device).eval()
        if self.device == "cpu":
            # PaddleX defaults to oneDNN on CPU, but PP-DocLayout_plus-L fails
            # there on Windows with ConvertPirAttribute2RuntimeAttribute.
            self.pp_model = create_model(
                model_name=PP_MODEL, device="cpu",
                engine_config={"run_mode": "paddle"})
        else:
            self.pp_model = create_model(model_name=PP_MODEL)

    def detect_tt(self, image) -> List[Detection]:
        inputs = self.tt_processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with self.torch.no_grad():
            outputs = self.tt_model(**inputs)
        target = self.torch.tensor([image.size[::-1]], device=self.device)
        result = self.tt_processor.post_process_object_detection(
            outputs, threshold=TT_THRESHOLD, target_sizes=target)[0]
        found = []
        for score, label, box in zip(
                result["scores"], result["labels"], result["boxes"]):
            name = self.tt_model.config.id2label[int(label)]
            if name.casefold() in {"table", "table rotated"}:
                found.append(Detection("table_transformer", name, float(score),
                                       tuple(float(v) for v in box)))
        return found

    def detect_pp(self, image_path: str) -> List[Detection]:
        found = []
        for result in self.pp_model.predict(image_path, threshold=PP_THRESHOLD):
            data = getattr(result, "json", result)
            if callable(data):
                data = data()
            if isinstance(data, str):
                data = json.loads(data)
            data = data.get("res", data) if isinstance(data, dict) else data
            for box in data.get("boxes", []) if isinstance(data, dict) else []:
                label = str(box.get("label", box.get("label_name", "")))
                if "table" not in label.casefold():
                    continue
                coords = box.get("coordinate", box.get("bbox"))
                found.append(Detection("pp_doclayout", label,
                                       float(box.get("score", 0)), tuple(coords)))
        return found

    def detect_and_crop(self, image_path: str, page: int, output_dir: str,
                        debug: bool = False) -> List[TableCandidate]:
        try:
            from PIL import Image
        except ImportError as exc:
            raise VisionDependencyError("Pillow is required") from exc
        image = Image.open(image_path).convert("RGB")
        detections = self.detect_pp(image_path) + self.detect_tt(image)
        candidates = canonicalize(detections, page, *image.size)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for candidate in candidates:
            path = out / f"{candidate.candidate_id}.jpg"
            image.crop(candidate.crop_bbox).save(path, quality=95)
            candidate.crop_path = str(path)
        if debug:
            (out / f"n{page}_detections.json").write_text(json.dumps(
                {"detections": [asdict(d) for d in detections],
                 "candidates": [asdict(c) for c in candidates]}, indent=2),
                encoding="utf-8")
        return candidates
