#!/usr/bin/env python3
"""Read-only structural PDF preflight; it does not certify visual quality.

Python 3.10+ and pypdf are required. Optional rendering needs pypdfium2 and
Pillow. No files are uploaded. Reports omit extracted text and URI contents.
Exit codes: 0 = checks pass (warnings possible), 1 = failed checks,
2 = unreadable input, invalid arguments, or unavailable dependency.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit


STANDARD_14 = {
    "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
    "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    "Symbol", "ZapfDingbats",
}
PAINT_OPS = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"sh"}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def resolved(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def object_key(value: Any) -> str:
    ref = getattr(value, "indirect_reference", None)
    if ref is None and hasattr(value, "idnum"):
        ref = value
    return (f"ref:{ref.idnum}:{ref.generation}" if ref is not None
            else f"direct:{id(value)}")


def has_font_program(descriptor: Any) -> bool:
    descriptor = resolved(descriptor)
    for key in ("/FontFile", "/FontFile2", "/FontFile3"):
        if key in descriptor:
            stream = resolved(descriptor[key])
            if hasattr(stream, "get_data") and len(stream.get_data()) > 0:
                return True
    return False


def font_details(raw_font: Any) -> dict[str, Any]:
    font = resolved(raw_font)
    subtype = str(font.get("/Subtype", "unknown"))
    name = str(font.get("/BaseFont", "unnamed")).lstrip("/")
    standard = name in STANDARD_14  # A subset prefix does not make a Standard 14 font.
    if subtype == "/Type3":
        status = "embedded_type3" if font.get("/CharProcs") else "missing"
    elif subtype == "/Type0":
        descendants = resolved(font.get("/DescendantFonts", []))
        embedded = []
        for child in descendants:
            descriptor = resolved(resolved(child).get("/FontDescriptor", {}))
            embedded.append(has_font_program(descriptor))
        status = "embedded" if embedded and all(embedded) else "missing"
    elif subtype in ("/TrueType", "/Type1", "/MMType1", "/CIDFontType0", "/CIDFontType2"):
        descriptor = resolved(font.get("/FontDescriptor", {}))
        embedded = has_font_program(descriptor)
        status = "embedded" if embedded else ("standard14_allowed" if standard else "missing")
    else:
        status = "unknown"
    return {"name": name, "subtype": subtype, "embedding": status,
            "standard14": standard, "used": False}


def image_digest(image: Any) -> str:
    """Hash decoded payload; do not write image data into the JSON report."""
    return digest(resolved(image).get_data())


def inspect_pdf(path: Path, reader_class: Any, content_class: Any) -> tuple[dict, dict]:
    reader = reader_class(str(path), strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Encrypted PDF requires a password; input was not modified.")
    if not reader.pages:
        raise ValueError("PDF has no readable pages.")

    fonts: dict[str, dict] = {}
    inventory_seen: set[str] = set()
    resource_seen: set[str] = set()
    images: dict[str, str] = {}
    warnings: list[str] = []
    failures: list[str] = []
    private_pages: list[dict] = []
    public_pages: list[dict] = []

    def inventory(resources: Any, depth: int = 0) -> None:
        if resources is None:
            return
        if depth > 64:
            warnings.append("Resource nesting exceeds 64 levels; inventory may be incomplete.")
            return
        resources = resolved(resources)
        rkey = object_key(resources)
        if rkey in resource_seen:
            return
        resource_seen.add(rkey)
        for raw in resolved(resources.get("/Font", {})).values():
            key = object_key(raw)
            if key not in fonts:
                fonts[key] = font_details(raw)
        for raw_state in resolved(resources.get("/ExtGState", {})).values():
            state_font = resolved(raw_state).get("/Font")
            if state_font:
                raw = resolved(state_font)[0]
                key = object_key(raw)
                if key not in fonts:
                    fonts[key] = font_details(raw)
        for raw in resolved(resources.get("/XObject", {})).values():
            key = object_key(raw)
            if key in inventory_seen:
                continue
            inventory_seen.add(key)
            obj = resolved(raw)
            if obj.get("/Subtype") == "/Image":
                images[key] = image_digest(obj)
            elif obj.get("/Subtype") == "/Form":
                inventory(obj.get("/Resources", resources), depth + 1)

    def inspect_stream(stream: Any, resources: Any, stats: Counter,
                       page_images: list[str], active: set[str], depth: int = 0) -> None:
        if stream is None:
            return
        if depth > 64:
            warnings.append("Content nesting exceeds 64 levels; operator counts may be incomplete.")
            return
        resources = resolved(resources or {})
        font_map = resolved(resources.get("/Font", {}))
        state_map = resolved(resources.get("/ExtGState", {}))
        xobjects = resolved(resources.get("/XObject", {}))
        cs = content_class(stream, reader)
        for operands, op in cs.operations:
            if op in PAINT_OPS:
                stats["vector_paint_operators"] += 1
            elif op == b"Tf" and operands:
                raw = font_map.get(operands[0])
                if raw is None:
                    failures.append("A used font resource is missing from its resource dictionary.")
                else:
                    key = object_key(raw)
                    if key not in fonts:
                        fonts[key] = font_details(raw)
                    fonts[key]["used"] = True
            elif op == b"gs" and operands:
                state_font = resolved(state_map.get(operands[0], {})).get("/Font")
                if state_font:
                    raw = resolved(state_font)[0]
                    key = object_key(raw)
                    if key not in fonts:
                        fonts[key] = font_details(raw)
                    fonts[key]["used"] = True
            elif op in (b"Tj", b"TJ", b"'", b'"'):
                stats["text_show_operators"] += 1
            elif op == b"INLINE IMAGE":
                stats["image_draw_operators"] += 1
                data = operands.get("data", b"")
                page_images.append(digest(data))
            elif op == b"Do" and operands:
                raw = xobjects.get(operands[0])
                if raw is None:
                    warnings.append("A drawn XObject is absent from its resource dictionary.")
                    continue
                obj, key = resolved(raw), object_key(raw)
                if obj.get("/Subtype") == "/Image":
                    stats["image_draw_operators"] += 1
                    page_images.append(images.get(key) or image_digest(obj))
                elif obj.get("/Subtype") == "/Form":
                    if key in active:
                        warnings.append("Cyclic Form XObject reference skipped.")
                        continue
                    inspect_stream(obj, obj.get("/Resources", resources), stats,
                                   page_images, active | {key}, depth + 1)

    for number, page in enumerate(reader.pages, 1):
        resources = page.get("/Resources", {})
        inventory(resources)
        text = page.extract_text() or ""
        stats: Counter = Counter()
        page_images: list[str] = []
        inspect_stream(page.get_contents(), resources, stats, page_images, set())
        rect = page.mediabox
        width, height = float(rect.width), float(rect.height)
        if width <= 0 or height <= 0:
            failures.append(f"Page {number}: non-positive page dimensions.")
        if not text.strip():
            failures.append(f"Page {number}: no extractable text; check for raster-only or outlined text.")
        bad_count = text.count("\ufffd")
        square_count = text.count("\u25a0") + text.count("\u25a1")
        control_count = sum(ord(c) < 32 and c not in "\t\r\n" for c in text)
        if bad_count:
            failures.append(f"Page {number}: contains {bad_count} replacement characters (U+FFFD).")
        if square_count:
            warnings.append(f"Page {number}: {square_count} square characters require visual inspection; they may be intentional.")
        if control_count:
            warnings.append(f"Page {number}: {control_count} unusual control characters in extracted text require glyph inspection.")
        links: list[dict] = []
        unsafe_count = 0
        for raw in page.get("/Annots", []):
            annot = resolved(raw)
            action = resolved(annot.get("/A", {}))
            if action.get("/S") != "/URI":
                continue
            uri = str(action.get("/URI", ""))
            link_rect = [round(float(v), 5) for v in annot.get("/Rect", [])]
            links.append({"uri": uri, "rect": link_rect})
            try:
                scheme = urlsplit(uri).scheme.lower()
            except ValueError:
                scheme = ""
            if scheme not in ("https", "http", "mailto", "tel"):
                unsafe_count += 1
        if unsafe_count:
            warnings.append(f"Page {number}: {unsafe_count} URI links have missing or unusual schemes; inspect destinations locally.")
        public_pages.append({
            "page": number, "width_pt": round(width, 4), "height_pt": round(height, 4),
            "rotation": int(page.get("/Rotate", 0)), "text_character_count": len(text),
            "text_sha256": digest(text.encode("utf-8")), "replacement_character_count": bad_count,
            "square_character_count": square_count, "uri_link_count": len(links),
            "unusual_control_character_count": control_count,
            "uri_links_sha256": digest(canonical(sorted(links, key=lambda x: canonical(x)))),
            "image_draw_count": stats["image_draw_operators"],
            "image_payload_sha256": sorted(page_images),
            "vector_paint_operator_count": stats["vector_paint_operators"],
            "text_show_operator_count": stats["text_show_operators"],
        })
        private_pages.append({"text": text, "images": Counter(page_images),
                              "links": sorted(canonical(item) for item in links)})

    for item in fonts.values():
        if item["used"] and item["embedding"] == "missing":
            failures.append(f"Used nonstandard font lacks embedded font data: {item['name']}.")
        if item["used"] and item["embedding"] == "unknown":
            warnings.append(f"Used font subtype could not be certified structurally: {item['name']}.")
    used_fonts = sorted((f for f in fonts.values() if f["used"]),
                        key=lambda f: (f["name"], f["subtype"]))
    report = {
        "pdf": str(path), "file_sha256": digest(path.read_bytes()),
        "page_count": len(reader.pages), "pages": public_pages,
        "fonts": used_fonts, "unused_font_resource_count": sum(not f["used"] for f in fonts.values()),
        "unique_image_resource_count": len(images),
        "all_image_resource_payload_sha256": sorted(images.values()),
        "warnings": sorted(set(warnings)), "failures": sorted(set(failures)),
        "limits": [
            "Structural checks and optional previews do not certify visual quality.",
            "Vector operator counts do not prove that every object is vector artwork.",
            "Extractable text does not guarantee that every glyph renders correctly.",
            "Image hashes compare decoded payloads, not visual equivalence.",
        ],
    }
    return report, {"pages": private_pages}


def render_previews(pdf: Path, output: Path, protected_inputs: set[Path]) -> dict:
    import pypdfium2 as pdfium
    from PIL import Image, ImageOps, ImageDraw

    output.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    thumbs = []
    names = []
    try:
        proposed = [output / f"page_{i + 1:03}.png" for i in range(len(doc))]
        proposed.append(output / "contact_sheet.jpg")
        if any(p.resolve() in protected_inputs for p in proposed):
            raise ValueError("Preview output would overwrite an input PDF.")
        for index in range(len(doc)):
            page = doc[index]
            bitmap = page.render(scale=1.5)
            try:
                img = bitmap.to_pil().convert("RGB")
                name = output / f"page_{index + 1:03}.png"
                img.save(name)
                names.append(str(name))
                thumb = ImageOps.contain(img, (360, 500))
                tile = Image.new("RGB", (380, 530), "#eeeeee")
                tile.paste(thumb, ((380 - thumb.width) // 2, 10))
                ImageDraw.Draw(tile).text((10, 512), str(index + 1), fill="black")
                thumbs.append(tile)
            finally:
                bitmap.close()
                page.close()
    finally:
        doc.close()
    columns = min(4, len(thumbs))
    sheet = Image.new("RGB", (380 * columns, 530 * ((len(thumbs) + columns - 1) // columns)), "white")
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % columns) * 380, (index // columns) * 530))
    contact = output / "contact_sheet.jpg"
    sheet.save(contact, quality=90)
    return {"scale": 1.5, "pages": names, "contact_sheet": str(contact),
            "visual_review": "pending_human_or_agent_inspection"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--expected-pages", type=int)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--report", type=Path, help="Optional internal JSON report; no document text or URI values.")
    parser.add_argument("--baseline", type=Path, help="Compare text, image payloads, and URI/rectangle invariants.")
    parser.add_argument("--require-same-text", action="store_true", help="Fail if baseline text differs (otherwise warn).")
    args = parser.parse_args()
    if args.expected_pages is not None and args.expected_pages < 1:
        parser.error("--expected-pages must be positive")
    if args.require_same_text and not args.baseline:
        parser.error("--require-same-text requires --baseline")
    inputs = {args.pdf.resolve()}
    if args.baseline:
        inputs.add(args.baseline.resolve())
    if args.report and args.report.resolve() in inputs:
        parser.error("--report must not overwrite an input PDF")
    if args.render_dir and args.render_dir.resolve() in inputs:
        parser.error("--render-dir must be a directory separate from input PDFs")
    try:
        from pypdf import PdfReader
        from pypdf.generic import ContentStream
        if args.render_dir:
            import pypdfium2  # noqa: F401
            import PIL  # noqa: F401
    except ImportError as exc:
        print(json.dumps({"status": "ERROR", "error": f"Missing dependency: {exc.name}"}))
        return 2
    try:
        report, private = inspect_pdf(args.pdf.resolve(), PdfReader, ContentStream)
        if args.expected_pages is not None and report["page_count"] != args.expected_pages:
            report["failures"].append(f"Expected {args.expected_pages} pages; found {report['page_count']}.")
        if args.baseline:
            baseline, base_private = inspect_pdf(args.baseline.resolve(), PdfReader, ContentStream)
            text_same = [p["text"] for p in private["pages"]] == [p["text"] for p in base_private["pages"]]
            image_same = (report["all_image_resource_payload_sha256"] == baseline["all_image_resource_payload_sha256"]
                          and [p["images"] for p in private["pages"]] == [p["images"] for p in base_private["pages"]])
            links_same = [p["links"] for p in private["pages"]] == [p["links"] for p in base_private["pages"]]
            report["baseline_comparison"] = {
                "baseline_sha256": baseline["file_sha256"], "same_page_count": report["page_count"] == baseline["page_count"],
                "exact_extracted_text_equal": text_same, "image_payloads_and_occurrences_equal": image_same,
                "link_uris_and_rectangles_equal": links_same,
                "text_changes_are_failures": args.require_same_text,
            }
            if not text_same:
                report["failures" if args.require_same_text else "warnings"].append("Extracted text differs from baseline.")
            if not image_same:
                report["failures"].append("Image payloads or drawing occurrences differ from baseline.")
            if not links_same:
                report["failures"].append("URI links or their rectangles differ from baseline.")
        if args.render_dir:
            report["previews"] = render_previews(args.pdf, args.render_dir, inputs)
        report["status"] = "FAIL" if report["failures"] else "PASS"
        output = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 1 if report["failures"] else 0
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
