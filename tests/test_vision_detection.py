import math
import unittest

from Functions.vision_detection import (
    Detection, canonicalize, clamp_box, valid_intersection,
)


class DetectionGeometryTests(unittest.TestCase):
    def test_out_of_bounds_box_is_valid_and_clamped(self):
        box = (-3.2, -2.1, 105.4, 90)
        self.assertTrue(valid_intersection(box, 100, 80))
        self.assertEqual(clamp_box(box, 100, 80), (0, 0, 100, 80))

    def test_invalid_boxes(self):
        self.assertFalse(valid_intersection((1, 1, 1, 2), 100, 100))
        self.assertFalse(valid_intersection((math.nan, 1, 2, 3), 100, 100))
        self.assertFalse(valid_intersection((-5, 0, -1, 4), 100, 100))

    def test_dedup_is_deterministic_and_preserves_provenance(self):
        detections = [
            Detection("pp_doclayout", "table", .8, (0, 0, 50, 50)),
            Detection("table_transformer", "table", .9, (1, 1, 51, 51)),
            Detection("pp_doclayout", "table", .7, (70, 70, 90, 90)),
        ]
        candidates = canonicalize(detections, 4, 100, 100)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].candidate_id, "n4_table_000")
        self.assertEqual(candidates[0].raw_bbox, (1, 1, 51, 51))
        self.assertEqual(candidates[0].sources,
                         ["pp_doclayout", "table_transformer"])


if __name__ == "__main__":
    unittest.main()
