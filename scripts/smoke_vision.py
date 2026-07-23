"""Load all optional localization models; optionally run them on one image."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Functions.vision_detection import TableDetectors
from Functions.vision_ocr import GeneralOCR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="real page image for inference smoke test")
    parser.add_argument("--output", default=".vision-smoke")
    args = parser.parse_args()

    detectors = TableDetectors()
    ocr = GeneralOCR("gpu:0" if detectors.device == "cuda" else "cpu")
    print(f"Table Transformer loaded on {detectors.device}")
    print("PP-DocLayout_plus-L loaded")
    print("general OCR loaded")
    if args.image:
        image = Path(args.image)
        candidates = detectors.detect_and_crop(
            str(image), 0, args.output, debug=True)
        print(f"detected {len(candidates)} canonical table candidate(s)")
        for candidate in candidates:
            text = ocr.read(candidate.crop_path)
            print(f"{candidate.candidate_id}: {len(text)} OCR character(s)")


if __name__ == "__main__":
    main()
