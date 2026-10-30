#!/usr/bin/env python3
"""Read-only DOCX structure inventory; candidates are not layout defects.

Python 3.10+, standard library only. No text is included unless requested.
This does not render Word pages, resolve inherited formatting, count abstract
words, validate scientific content, or grant font embedding permission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}
W = "{" + NS["w"] + "}"
R = "{" + NS["r"] + "}"
CAPTION = re.compile(r"^(?:图\s*[A-Za-z]?\d+[A-Za-z]?|Figure\s+[A-Za-z]?\d+[A-Za-z]?)(?=\s|[：:.、．]|[\u3400-\u9fff]|$)", re.I)
PAGINATION = ("keepNext", "keepLines", "pageBreakBefore")
FONT_FACES = ("embedRegular", "embedBold", "embedItalic", "embedBoldItalic")


def _xml(archive: zipfile.ZipFile, name: str, required: bool = False):
    if name not in archive.namelist():
        if required:
            raise ValueError(f"Required DOCX part is missing: {name}")
        return None
    try:
        return ET.fromstring(archive.read(name))
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML in DOCX part: {name}") from exc


def _on_off(element):
    """None is unspecified, not False; style inheritance remains unresolved."""
    if element is None:
        return None
    value = element.get(W + "val", "true").lower()
    if value in {"1", "true", "on"}:
        return True
    if value in {"0", "false", "off"}:
        return False
    return "unknown"


def _own_elements(paragraph):
    """Do not count a text-box paragraph's text again in its outer paragraph."""
    yield paragraph
    for child in paragraph:
        if child.tag == W + "p":
            continue
        yield from _without_paragraphs(child)


def _without_paragraphs(element):
    yield element
    for child in element:
        if child.tag != W + "p":
            yield from _without_paragraphs(child)


def _paragraph_record(paragraph, index):
    elements = list(_own_elements(paragraph))
    text = "".join(e.text or "" for e in elements if e.tag == W + "t")
    images = {"inline": 0, "anchored": 0, "legacy_vml": 0}
    for element in elements:
        if element.tag in {"{" + NS["wp"] + "}inline", "{" + NS["wp"] + "}anchor"}:
            if element.find(".//a:blip", NS) is not None:
                key = "inline" if element.tag.endswith("}inline") else "anchored"
                images[key] += 1
        elif element.tag == "{" + NS["v"] + "}imagedata":
            images["legacy_vml"] += 1
    properties = paragraph.find("w:pPr", NS)
    flags = {name: _on_off(properties.find("w:" + name, NS) if properties is not None else None)
             for name in PAGINATION}
    manual_breaks = sum(e.tag == W + "br" and e.get(W + "type") == "page" for e in elements)
    nontext_tags = {W + name for name in ("drawing", "pict", "object", "fldChar", "sym")}
    nontext_tags.add("{" + NS["m"] + "}oMath")
    record = {
        "index": index,
        "images": images,
        "pagination_explicit": flags,
        "manual_page_breaks": manual_breaks,
        "cached_rendered_page_breaks": sum(e.tag == W + "lastRenderedPageBreak" for e in elements),
        "empty_candidate": not text.strip() and not any(e.tag in nontext_tags for e in elements),
        "section_boundary": properties is not None and properties.find("w:sectPr", NS) is not None,
    }
    return record, text


def _font_inventory(archive):
    fonts = Counter()
    themes = Counter()
    parts = [n for n in archive.namelist() if re.fullmatch(
        r"word/(?:document|styles|numbering|header\d+|footer\d+)\.xml", n)]
    for name in parts:
        root = _xml(archive, name)
        for declaration in root.iter(W + "rFonts"):
            for key, value in declaration.attrib.items():
                local = key.rsplit("}", 1)[-1]
                if local in {"ascii", "hAnsi", "eastAsia", "cs"}:
                    fonts[value] += 1
                elif local in {"asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme", "csTheme"}:
                    themes[local + ":" + value] += 1
    embedded = []
    table = _xml(archive, "word/fontTable.xml")
    rels = _xml(archive, "word/_rels/fontTable.xml.rels")
    relationships = {} if rels is None else {r.get("Id"): r for r in rels}
    if table is not None:
        for font in table.findall("w:font", NS):
            for face in FONT_FACES:
                item = font.find("w:" + face, NS)
                if item is None:
                    continue
                rid = item.get(R + "id")
                relation = relationships.get(rid)
                external = relation is not None and relation.get("TargetMode") == "External"
                target = relation.get("Target", "") if relation is not None else ""
                part = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "word/" + target)
                embedded.append({
                    "font": font.get(W + "name", ""), "face": face,
                    "relationship_id": rid,
                    "relationship_exists": relation is not None,
                    "external_relationship": external,
                    "part_exists": bool(target) and not external and part in archive.namelist(),
                    "subsetted_explicit": _on_off_attribute(item, W + "subsetted"),
                })
    return {"explicit_font_declarations": dict(sorted(fonts.items())),
            "theme_font_slots": dict(sorted(themes.items())),
            "font_scan_parts": sorted(parts), "embedded_faces": embedded}


def _on_off_attribute(element, attribute):
    value = element.get(attribute)
    if value is None:
        return None
    if value.lower() in {"1", "true", "on"}:
        return True
    if value.lower() in {"0", "false", "off"}:
        return False
    return "unknown"


def audit(path: Path, include_text: bool = False) -> dict:
    data = Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = _xml(archive, "word/document.xml", required=True)
        body = document.find("w:body", NS)
        if body is None:
            raise ValueError("Required DOCX body is missing")
        records, texts = [], []
        for index, paragraph in enumerate(body.iter(W + "p"), start=1):
            record, text = _paragraph_record(paragraph, index)
            records.append(record)
            texts.append(text)
        image_indices = {p["index"] for p in records if any(p["images"].values())}
        captions = []
        for record, text in zip(records, texts):
            index = record["index"]
            if CAPTION.match(text.lstrip()):
                captions.append({"index": index,
                                 "same_paragraph_has_image": index in image_indices,
                                 "previous_paragraph_has_image": index - 1 in image_indices,
                                 "next_paragraph_has_image": index + 1 in image_indices})
        settings = _xml(archive, "word/settings.xml")
        setting_values = {key: _on_off(settings.find("w:" + key, NS) if settings is not None else None)
                          for key in ("embedTrueTypeFonts", "saveSubsetFonts", "embedSystemFonts")}
        report = {
            "schema_version": 1,
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "paragraph_indexing": "1-based XML body order, including tables and text boxes; not page numbers",
            "paragraph_count": len(records),
            "image_counts": {key: sum(p["images"][key] for p in records)
                             for key in ("inline", "anchored", "legacy_vml")},
            "image_paragraphs": sorted(image_indices),
            "caption_candidates": captions,
            "empty_paragraph_candidates": [p["index"] for p in records if p["empty_candidate"]],
            "pagination_candidates": [p for p in records if any(v is not None for v in p["pagination_explicit"].values())
                                      or p["manual_page_breaks"] or p["cached_rendered_page_breaks"] or p["section_boundary"]],
            "font_settings_explicit": setting_values,
            "fonts": _font_inventory(archive),
            "limitations": [
                "Candidates are not errors. Empty paragraphs and pagination controls may be intentional.",
                "Unspecified properties are null; style inheritance, table layout and effective formatting are not resolved.",
                "XML adjacency does not prove a picture and caption first line share a rendered page.",
                "Anchored pictures may render away from their XML anchor. Compatibility fallback branches may duplicate objects.",
                "An embedded relationship/part does not prove valid font data, glyph coverage, embedding permission or cross-computer fidelity.",
                "No actual pagination, word-limit compliance, scientific accuracy, headers alignment or visual quality is certified.",
            ],
        }
        if include_text:
            report["paragraph_text"] = [{"index": p["index"], "text": text} for p, text in zip(records, texts)]
        return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON destination, relative to the current directory")
    parser.add_argument("--include-text", action="store_true", help="Opt in to potentially private paragraph text")
    args = parser.parse_args(argv)
    try:
        if args.output is not None:
            same = args.output.resolve() == args.docx.resolve()
            if not same and args.output.exists() and args.docx.exists():
                same = args.output.samefile(args.docx)
            if same:
                raise ValueError("Output must not overwrite the input DOCX")
        report = audit(args.docx, args.include_text)
        result = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is None:
            print(result, end="")
        else:
            args.output.write_text(result, encoding="utf-8")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        print(f"DOCX inventory failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
