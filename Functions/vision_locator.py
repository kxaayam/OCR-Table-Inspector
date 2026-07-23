"""Automatic table locator with strict lexical/numeric winner agreement."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import List, Optional

import Functions.llm_locator as llm_locator
import Functions.stage2_locate as stage2_locate
from Functions.finding import Finding
from Functions.vision_detection import TableCandidate, TableDetectors
from Functions.vision_matching import CandidateText, rank_candidates
from Functions.vision_ocr import GeneralOCR


@dataclass
class AutoLocateResult:
    finding: Finding
    status: str  # "located" | "unresolved"
    page: Optional[int] = None
    image_path: Optional[str] = None
    full_page_path: Optional[str] = None
    detail: str = ""
    diagnostics_path: Optional[str] = None


class AutomaticVisionLocator:
    """Owns and reuses the detector and OCR models for a pipeline run."""

    def __init__(self, detectors=None, ocr=None):
        self.detectors = detectors or TableDetectors()
        device = "gpu:0" if self.detectors.device == "cuda" else "cpu"
        self.ocr = ocr or GeneralOCR(device=device)

    def locate(self, finding: Finding, doc_id: str, image_dir: str,
               window: int = llm_locator.DEFAULT_WINDOW,
               collection: str = stage2_locate.DEFAULT_COLLECTION,
               template: str = stage2_locate.URL_TEMPLATE,
               debug: bool = False) -> AutoLocateResult:
        if finding.page_guess is None or finding.page_guess < 0:
            return AutoLocateResult(finding, "unresolved",
                                    detail="no usable page guess")
        pages = llm_locator._candidate_window(finding.page_guess, window)
        crop_dir = Path(image_dir) / "_table_crops" / \
            f"table_{finding.table_index}"
        all_candidates: List[TableCandidate] = []
        full_pages = {}
        errors = []
        for page in pages:
            page_path = Path(image_dir) / "_candidates" / f"cand_n{page}.jpg"
            try:
                got = stage2_locate.fetch_page_image(
                    doc_id, page, str(page_path), collection, template)
                if not got:
                    continue
                full_pages[page] = got
                all_candidates.extend(self.detectors.detect_and_crop(
                    got, page, str(crop_dir), debug=debug))
            except Exception as exc:
                errors.append(f"n{page}: {exc}")
        if not all_candidates:
            return AutoLocateResult(
                finding, "unresolved",
                detail="no table candidates" + (
                    f"; errors: {'; '.join(errors)}" if errors else ""))

        texts, ocr_errors = [], []
        for candidate in all_candidates:
            try:
                texts.append(CandidateText(
                    candidate.candidate_id, self.ocr.read(candidate.crop_path)))
            except Exception as exc:
                ocr_errors.append(f"{candidate.candidate_id}: {exc}")
        diagnostics = rank_candidates(finding.table_html, texts)
        diagnostics["candidates"] = [asdict(c) for c in all_candidates]
        diagnostics["ocr_text"] = {c.candidate_id: c.text for c in texts}
        diagnostics["errors"] = errors + ocr_errors
        diagnostics_path = crop_dir / "matching.json"
        crop_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_path.write_text(json.dumps(
            diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
        if diagnostics["status"] != "accepted":
            return AutoLocateResult(
                finding, "unresolved", detail="lexical/numeric winners did not "
                "agree or evidence was insufficient",
                diagnostics_path=str(diagnostics_path))
        selected = next(c for c in all_candidates
                        if c.candidate_id == diagnostics["selected"])
        return AutoLocateResult(
            finding, "located", page=selected.page,
            image_path=selected.crop_path,
            full_page_path=full_pages[selected.page],
            detail="automatic lexical/numeric winner agreement",
            diagnostics_path=str(diagnostics_path))
