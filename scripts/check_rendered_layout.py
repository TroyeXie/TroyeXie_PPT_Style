#!/usr/bin/env python3
"""Read-only checks on supplied rendered bounds, using Python's standard library.

No PPTX parsing, rendering, font verification, OCR or asset upload is performed.
All coordinates must already be in points and use the same page origin.
See references/rendered-layout-checks.md for the measurement and contract format.
"""
import argparse
import json
import math
import sys
from pathlib import Path


class MeasurementError(ValueError):
    """Invalid measurements or an incomplete check contract."""


def number(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementError(label + " must be a finite number.")
    try:
        value = float(value)
    except OverflowError as exc:
        raise MeasurementError(label + " must be a finite number.") from exc
    if not math.isfinite(value):
        raise MeasurementError(label + " must be a finite number.")
    if minimum is not None and value < minimum:
        raise MeasurementError(label + " is below its minimum.")
    return value


def rectangle(value, label):
    if not isinstance(value, list) or len(value) != 4:
        raise MeasurementError(label + " must be [x, y, width, height].")
    x, y, w, h = [number(v, label) for v in value]
    if w <= 0 or h <= 0:
        raise MeasurementError(label + " must have positive width and height.")
    return (x, y, number(x + w, label), number(y + h, label))


def sequence(value, label, minimum=1):
    if not isinstance(value, list) or len(value) < minimum:
        raise MeasurementError(label + " has too few entries.")
    return value


def at_most(value, limit):
    number(value, "computed measurement")
    return value <= limit or math.isclose(value, limit, rel_tol=0, abs_tol=1e-9)


def same(values, tolerance):
    return at_most(max(values) - min(values), tolerance)


def audit(measurements, contracts):
    if not isinstance(measurements, dict) or measurements.get("unit") != "pt":
        raise MeasurementError("Measurements must declare unit: pt; do not guess pixel DPI.")
    if (type(measurements.get("schema_version")) is not int or measurements["schema_version"] != 1 or
            not isinstance(contracts, dict) or type(contracts.get("schema_version")) is not int or contracts["schema_version"] != 1):
        raise MeasurementError("Both inputs must use schema_version: 1.")
    objects = {}
    for obj in sequence(measurements.get("objects"), "objects"):
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not obj["id"]:
            raise MeasurementError("Every object requires a nonempty string id.")
        key = obj["id"]
        if key in objects:
            raise MeasurementError("Object ids must be unique.")
        page = obj.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise MeasurementError("Every object requires a positive integer page.")
        row = {"page": page, "frame": rectangle(obj.get("frame"), "frame")}
        if "ink" in obj:
            row["ink"] = rectangle(obj["ink"], "ink")
        objects[key] = row
    default_tolerance = number(contracts.get("tolerance_pt", 0.5), "tolerance_pt", 0)
    results, identifiers = [], set()
    for check in sequence(contracts.get("checks"), "checks"):
        if not isinstance(check, dict) or not isinstance(check.get("id"), str) or not check["id"] or check["id"] in identifiers:
            raise MeasurementError("Checks require unique nonempty string ids.")
        identifiers.add(check["id"])
        tolerance = number(check.get("tolerance_pt", default_tolerance), "tolerance_pt", 0)
        pages = set()

        def union(refs, field="ink"):
            rows = []
            for ref in sequence(refs, "object references"):
                if not isinstance(ref, str) or ref not in objects:
                    raise MeasurementError("A check references an unknown object id.")
                obj = objects[ref]
                if field not in obj:
                    raise MeasurementError("A visible-bounds check requires ink; frame is not a substitute.")
                pages.add(obj["page"])
                rows.append(obj[field])
            return (min(r[0] for r in rows), min(r[1] for r in rows),
                    max(r[2] for r in rows), max(r[3] for r in rows))

        def groups(minimum=2):
            return [union(refs) for refs in sequence(check.get("groups"), "groups", minimum)]

        def axis():
            value = check.get("axis", "y")
            if value not in ("x", "y"):
                raise MeasurementError("axis must be x or y.")
            return 0 if value == "x" else 1

        kind = check.get("kind")
        if kind == "align":
            edge = check.get("edge")
            indices = {"left": 0, "top": 1, "right": 2, "bottom": 3}
            if edge not in (*indices, "center_x", "center_y"):
                raise MeasurementError("Unknown alignment edge.")
            rects = groups()
            if edge in indices:
                values = [r[indices[edge]] for r in rects]
            else:
                i = 0 if edge == "center_x" else 1
                values = [(r[i] + r[i + 2]) / 2 for r in rects]
            measured, passed = {"positions": values}, same(values, tolerance)
        elif kind == "center":
            content = union(check.get("members"))
            container = union([check.get("container")], "frame")
            selected = check.get("axis", "both")
            if selected not in ("x", "y", "both"):
                raise MeasurementError("center axis must be x, y or both.")
            deltas = {a: (content[i] + content[i + 2] - container[i] - container[i + 2]) / 2
                      for a, i in [("x", 0), ("y", 1)] if selected in (a, "both")}
            measured, passed = {"center_deltas": deltas}, all(at_most(abs(v), tolerance) for v in deltas.values())
        elif kind == "pair_gaps":
            i, gaps = axis(), []
            for pair in sequence(check.get("pairs"), "pairs", 2):
                if not isinstance(pair, dict):
                    raise MeasurementError("A pair needs before and after reference lists.")
                first, second = union(pair.get("before")), union(pair.get("after"))
                gaps.append(second[i] - first[i + 2])
            minimum = number(check.get("min_pt", 0), "min_pt", 0)
            measured = {"gaps": gaps}
            passed = same(gaps, tolerance) and at_most(minimum - min(gaps), tolerance)
        elif kind == "distribute":
            i, rects = axis(), groups(3)
            gaps = [b[i] - a[i + 2] for a, b in zip(rects, rects[1:])]
            centers = [(r[i] + r[i + 2]) / 2 for r in rects]
            steps = [b - a for a, b in zip(centers, centers[1:])]
            mode = check.get("mode", "gaps")
            if mode not in ("gaps", "centers"):
                raise MeasurementError("distribution mode must be gaps or centers.")
            minimum = number(check.get("min_pt", 0), "min_pt", 0)
            measured = {"gaps": gaps, "center_steps": steps}
            passed = same(gaps if mode == "gaps" else steps, tolerance) and at_most(minimum - min(gaps), tolerance)
        elif kind == "padding":
            content, container = union(check.get("members")), union([check.get("container")], "frame")
            minimum = number(check.get("min_pt", 0), "min_pt", 0)
            pads = [content[0] - container[0], content[1] - container[1],
                    container[2] - content[2], container[3] - content[3]]
            measured, passed = {"padding_left_top_right_bottom": pads}, at_most(minimum - min(pads), tolerance)
        elif kind == "clearance":
            i = axis()
            first, second = union(check.get("before")), union(check.get("after"))
            gap = second[i] - first[i + 2]
            minimum = number(check.get("min_pt", 0), "min_pt", 0)
            measured, passed = {"gap": gap}, at_most(minimum - gap, tolerance)
        else:
            raise MeasurementError("Unknown check kind.")
        if len(pages) != 1:
            raise MeasurementError("A layout check cannot compare different pages.")
        for value in measured.values():
            scalars = value.values() if isinstance(value, dict) else value if isinstance(value, list) else [value]
            for scalar in scalars:
                number(scalar, "computed measurement")
        results.append({"id": check["id"], "kind": kind, "passed": passed, "measured_pt": measured})
    errors = sum(not r["passed"] for r in results)
    return {"schema_version": 1, "status": "pass" if not errors else "fail",
            "errors": errors, "checks": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("contracts", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and any(args.output.resolve() == p.resolve() or
                               (args.output.exists() and p.exists() and args.output.samefile(p))
                               for p in (args.measurements, args.contracts)):
            raise MeasurementError("Output must not replace either input file.")
        measurements = json.loads(args.measurements.read_text(encoding="utf-8-sig"))
        contracts = json.loads(args.contracts.read_text(encoding="utf-8-sig"))
        result = audit(measurements, contracts)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        else:
            print(encoded, end="")
        return 1 if result["errors"] else 0
    except (MeasurementError, OSError, ValueError) as exc:
        print("Rendered-layout check failed: " + (str(exc) if isinstance(exc, MeasurementError) else type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
