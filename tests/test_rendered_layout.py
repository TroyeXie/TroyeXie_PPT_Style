"""Synthetic point measurements only; no fonts, photographs or private decks."""
import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_rendered_layout.py"
SPEC = importlib.util.spec_from_file_location("rendered_layout", SCRIPT)
layout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(layout)


def obj(key, ink=None, frame=None, page=1):
    row = {"id": key, "page": page, "frame": frame or ink or [0, 0, 100, 50]}
    if ink is not None:
        row["ink"] = ink
    return row


def check(kind, **kwargs):
    return {"id": "synthetic", "kind": kind, **kwargs}


def measure(objects, contract, unit="pt"):
    return layout.audit({"schema_version": 1, "unit": unit, "objects": objects},
                        {"schema_version": 1, "tolerance_pt": 0.01, "checks": [contract]})


class RenderedLayoutTests(unittest.TestCase):
    def test_equal_frames_do_not_prove_equal_glyph_bottoms(self):
        objects = [obj("a", [0, 5, 30, 30], [0, 0, 100, 40]),
                   obj("b", [100, 12, 30, 15], [100, 0, 100, 40])]
        rule = check("align", edge="bottom", groups=[["a"], ["b"]])
        self.assertEqual(measure(objects, rule)["errors"], 1)
        objects[1]["ink"][1] += 8
        self.assertEqual(measure(objects, rule)["errors"], 0)

    def test_union_center_is_not_average_of_object_centers(self):
        objects = [obj("a", [0, 10, 20, 10]), obj("b", [40, 10, 60, 10]),
                   obj("panel", frame=[0, 0, 100, 40])]
        result = measure(objects, check("center", members=["a", "b"], container="panel", axis="x"))
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["checks"][0]["measured_pt"]["center_deltas"], {"x": 0})

    def test_center_detects_group_shift(self):
        objects = [obj("a", [10, 10, 20, 10]), obj("b", [50, 10, 60, 10]),
                   obj("panel", frame=[0, 0, 100, 40])]
        self.assertEqual(measure(objects, check("center", members=["a", "b"], container="panel", axis="x"))["errors"], 1)

    def test_pair_gaps_are_independent_of_text_heights(self):
        objects = [obj("a", [0, 0, 40, 20]), obj("b", [0, 26, 40, 10]),
                   obj("c", [0, 60, 40, 30]), obj("d", [0, 96, 40, 12])]
        pairs = [{"before": ["a"], "after": ["b"]}, {"before": ["c"], "after": ["d"]}]
        self.assertEqual(measure(objects, check("pair_gaps", pairs=pairs))["errors"], 0)
        objects[1]["ink"][1] -= 3
        self.assertEqual(measure(objects, check("pair_gaps", pairs=pairs))["errors"], 1)

    def test_equal_overlapping_pairs_do_not_pass(self):
        objects = [obj("a", [0, 0, 30, 20]), obj("b", [0, 15, 30, 10]),
                   obj("c", [0, 60, 30, 20]), obj("d", [0, 75, 30, 10])]
        pairs = [{"before": ["a"], "after": ["b"]}, {"before": ["c"], "after": ["d"]}]
        self.assertEqual(measure(objects, check("pair_gaps", pairs=pairs))["errors"], 1)

    def test_distribution_uses_whole_groups(self):
        objects = []
        for k, top in enumerate([0, 50, 100]):
            objects += [obj(f"n{k}", [0, top, 40, 20]), obj(f"l{k}", [0, top + 25, 40, 10])]
        groups = [[f"n{k}", f"l{k}"] for k in range(3)]
        self.assertEqual(measure(objects, check("distribute", groups=groups))["errors"], 0)
        objects[-1]["ink"][1] += 5
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="centers"))["errors"], 1)

    def test_gap_and_center_distribution_are_distinct(self):
        objects = [obj("a", [0, 0, 20, 20]), obj("b", [0, 50, 20, 40]), obj("c", [0, 120, 20, 20])]
        groups = [["a"], ["b"], ["c"]]
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="gaps"))["errors"], 0)
        objects[2]["ink"][1] = 130
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="gaps"))["errors"], 1)
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="centers"))["errors"], 1)
        objects = [obj("a", [0, 0, 20, 20]), obj("b", [0, 45, 20, 30]), obj("c", [0, 100, 20, 20])]
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="centers"))["errors"], 0)
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="gaps"))["errors"], 0)

    def test_center_distribution_can_allow_unequal_gaps(self):
        objects = [obj("a", [0, 0, 20, 20]), obj("b", [0, 50, 20, 20]), obj("c", [0, 90, 20, 40])]
        groups = [["a"], ["b"], ["c"]]
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="centers"))["errors"], 0)
        self.assertEqual(measure(objects, check("distribute", groups=groups, mode="gaps"))["errors"], 1)

    def test_padding_distinguishes_thin_and_roomy_band(self):
        objects = [obj("text", [10, 10, 80, 20]), obj("band", frame=[0, 7, 100, 26])]
        rule = check("padding", members=["text"], container="band", min_pt=8)
        self.assertEqual(measure(objects, rule)["errors"], 1)
        objects[1]["frame"] = [0, 0, 100, 40]
        self.assertEqual(measure(objects, rule)["errors"], 0)

    def test_clearance_and_horizontal_axis(self):
        objects = [obj("a", [0, 0, 20, 20]), obj("b", [25, 0, 20, 20])]
        self.assertEqual(measure(objects, check("clearance", before=["a"], after=["b"], axis="x", min_pt=6))["errors"], 1)
        self.assertEqual(measure(objects, check("clearance", before=["a"], after=["b"], axis="x", min_pt=5))["errors"], 0)

    def test_missing_ink_is_not_replaced_with_frame(self):
        with self.assertRaises(layout.MeasurementError):
            measure([obj("a"), obj("b")], check("align", edge="bottom", groups=[["a"], ["b"]]))

    def test_duplicate_object_ids_are_rejected(self):
        with self.assertRaises(layout.MeasurementError):
            measure([obj("same", [0, 0, 10, 10]), obj("same", [20, 0, 10, 10])], check("align", edge="top", groups=[["same"], ["same"]]))

    def test_cross_page_alignment_is_rejected(self):
        with self.assertRaises(layout.MeasurementError):
            measure([obj("a", [0, 0, 10, 10]), obj("b", [20, 0, 10, 10], page=2)], check("align", edge="top", groups=[["a"], ["b"]]))

    def test_pixels_require_explicit_conversion(self):
        with self.assertRaises(layout.MeasurementError):
            measure([obj("a", [0, 0, 10, 10])], check("padding", members=["a"], container="a"), unit="px")

    def test_nonfinite_and_invalid_sizes_are_rejected(self):
        for value in [float("nan"), float("inf"), 10 ** 400, True]:
            with self.subTest(value=str(value)[:20]), self.assertRaises(layout.MeasurementError):
                measure([obj("a", [value, 0, 10, 10])], check("padding", members=["a"], container="a"))
        for width in [0, -1]:
            with self.assertRaises(layout.MeasurementError):
                measure([obj("a", [0, 0, width, 10])], check("padding", members=["a"], container="a"))
        for bounds in [[1e308, 0, 1e308, 10], [0, 1e308, 10, 1e308]]:
            with self.assertRaises(layout.MeasurementError):
                measure([obj("a", bounds)], check("padding", members=["a"], container="a"))
        with self.assertRaises(layout.MeasurementError):
            measure([obj("a", [9e307, 0, 1e307, 10])], check("center", members=["a"], container="a"))

    def test_decimal_tolerance_boundary_is_inclusive(self):
        objects = [obj("a", [0, 1.0, 10, 10]), obj("b", [20, 1.1, 10, 10])]
        rule = check("align", edge="top", groups=[["a"], ["b"]], tolerance_pt=0.1)
        self.assertEqual(measure(objects, rule)["errors"], 0)
        objects[1]["ink"][1] = 1.1001
        self.assertEqual(measure(objects, rule)["errors"], 1)
        self.assertTrue(layout.at_most(1.1 - 1.0, 0.1))
        self.assertFalse(layout.at_most(0.1001, 0.1))

    def test_schema_version_requires_integer(self):
        for version in [True, 1.0, "1"]:
            for target in ["measurements", "contracts"]:
                payload = {"schema_version": 1, "unit": "pt", "objects": [obj("a", [0, 0, 10, 10])]}
                contracts = {"schema_version": 1, "checks": [check("padding", members=["a"], container="a")]}
                (payload if target == "measurements" else contracts)["schema_version"] = version
                with self.assertRaises(layout.MeasurementError):
                    layout.audit(payload, contracts)

    def test_unknown_reference_and_bad_tolerance_are_rejected(self):
        for rule in [check("align", edge="top", groups=[["a"], ["missing"]]),
                     check("padding", members=["a"], container="a", tolerance_pt=-1)]:
            with self.assertRaises(layout.MeasurementError):
                measure([obj("a", [0, 0, 10, 10])], rule)

    def test_audit_does_not_mutate_inputs_or_emit_text(self):
        payload = {"schema_version": 1, "unit": "pt", "objects": [obj("a", [0, 0, 10, 10])]}
        payload["objects"][0]["text"] = "not part of a diagnostic report"
        contracts = {"schema_version": 1, "checks": [check("padding", members=["a"], container="a")]}
        before = copy.deepcopy((payload, contracts))
        result = layout.audit(payload, contracts)
        self.assertEqual((payload, contracts), before)
        self.assertNotIn("not part of a diagnostic report", json.dumps(result))

    def test_cli_is_read_only_and_refuses_input_as_output(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "measurements.json", Path(folder) / "contracts.json"
            first.write_text(json.dumps({"schema_version": 1, "unit": "pt", "objects": [obj("a", [0, 0, 10, 10])]}), encoding="utf-8")
            second.write_text(json.dumps({"schema_version": 1, "checks": [check("padding", members=["a"], container="a")]}), encoding="utf-8")
            original = (first.read_bytes(), second.read_bytes())
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(layout.main([str(first), str(second)]), 0)
                self.assertEqual(layout.main([str(first), str(second), "--output", str(first)]), 2)
                self.assertEqual(layout.main([str(first), str(second), "--output", str(second)]), 2)
            self.assertEqual((first.read_bytes(), second.read_bytes()), original)


if __name__ == "__main__":
    unittest.main()
