#!/usr/bin/env python3
"""Read-only PPTX inventory using only Python's standard library.

Usage: python inspect_pptx.py deck.pptx [--include-text] [--output inventory.json]

Default output contains counts and explicit font declarations, not slide text.
Notes bodies, media contents, absolute paths, and relationship URLs are never
included. This is a structural inventory, not a fact, privacy, layout, or visual
acceptance check. It does not render slides or resolve inherited formatting.
"""

import argparse
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


MAX_XML_BYTES = 32 * 1024 * 1024
PRESENTATION_NS = {
    "http://schemas.openxmlformats.org/presentationml/2006/main",
    "http://purl.oclc.org/ooxml/presentationml/main",
}
DRAWING_NS = {
    "http://schemas.openxmlformats.org/drawingml/2006/main",
    "http://purl.oclc.org/ooxml/drawingml/main",
}
RELATIONSHIP_NS = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "http://purl.oclc.org/ooxml/officeDocument/relationships",
}


class InventoryError(Exception):
    """A concise, path-safe error that can be shown to the caller."""


def tag_parts(tag):
    if tag.startswith("{"):
        return tag[1:].split("}", 1)
    return "", tag


def is_tag(element, namespaces, name):
    namespace, local = tag_parts(element.tag)
    return namespace in namespaces and local == name


def rels_part(part):
    if not part:
        return "_rels/.rels"
    return posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")


def resolve_part(source, target):
    """Resolve an internal OPC target without allowing escape from the ZIP."""
    if not target or "\\" in target or "\x00" in target or re.search(r"[?#%:]", target):
        raise InventoryError("Unsupported or invalid internal relationship target.")
    if target.startswith("//"):
        raise InventoryError("Invalid absolute relationship target.")
    combined = target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(source), target)
    result = posixpath.normpath(combined)
    if result in ("", ".", "..") or result.startswith("../"):
        raise InventoryError("An internal relationship escapes the package root.")
    return result


class Package:
    def __init__(self, archive):
        self.archive = archive
        self.members = {}
        for info in archive.infolist():
            name = info.filename
            if (not name or name.startswith("/") or "\\" in name or "\x00" in name
                    or ":" in name or any(p in (".", "..") for p in name.split("/"))):
                raise InventoryError("The ZIP contains an invalid package member path.")
            if name in self.members:
                raise InventoryError("The ZIP contains duplicate package member names.")
            self.members[name] = info

    def xml(self, part):
        info = self.members.get(part)
        if info is None or info.is_dir():
            raise InventoryError("A required XML part is missing.")
        if info.file_size > MAX_XML_BYTES:
            raise InventoryError("An XML part exceeds the 32 MiB inventory limit.")
        try:
            raw = self.archive.read(info)
        except (RuntimeError, OSError, zipfile.BadZipFile, NotImplementedError) as exc:
            raise InventoryError("An XML part could not be read from the ZIP.") from exc
        # No DTD/entity processing is needed by Office Open XML.
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise InventoryError("DTD or entity declarations are not supported.")
        try:
            return ET.fromstring(raw)
        except (ET.ParseError, ValueError) as exc:
            raise InventoryError("The package contains malformed XML.") from exc

    def relationships(self, part, required=False):
        name = rels_part(part)
        if name not in self.members:
            if required:
                raise InventoryError("A required relationship part is missing.")
            return {}
        root = self.xml(name)
        if tag_parts(root.tag)[1] != "Relationships":
            raise InventoryError("Invalid relationship XML root.")
        result = {}
        for item in root:
            if tag_parts(item.tag)[1] != "Relationship":
                continue
            rid, kind, target = (item.get(k) for k in ("Id", "Type", "Target"))
            if not rid or not kind or not target or rid in result:
                raise InventoryError("A relationship is incomplete or has a duplicate ID.")
            external = item.get("TargetMode", "Internal").lower() == "external"
            result[rid] = {"type": kind.rsplit("/", 1)[-1], "external": external,
                           "part": None if external else resolve_part(part, target)}
        return result


def visible_xml_nodes(element):
    """Exclude explicitly hidden shape subtrees, but do not infer rendering."""
    for child in element:
        if tag_parts(child.tag)[1].startswith("nv"):
            for prop in child:
                if tag_parts(prop.tag)[1] == "cNvPr" and prop.get("hidden", "").lower() in ("1", "true"):
                    return
    yield element
    for child in element:
        yield from visible_xml_nodes(child)


def positive_int(value, description):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise InventoryError("Invalid " + description + ".") from exc
    if number <= 0:
        raise InventoryError("Invalid " + description + ".")
    return number


def inventory(pptx_path, include_text=False):
    try:
        digest = hashlib.sha256()
        with pptx_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            handle.seek(0)
            with zipfile.ZipFile(handle) as archive:
                package = Package(archive)
                offices = [r for r in package.relationships("", required=True).values()
                           if r["type"] == "officeDocument" and not r["external"]]
                if len(offices) != 1:
                    raise InventoryError("Exactly one internal officeDocument relationship is required.")
                presentation_part = offices[0]["part"]
                presentation = package.xml(presentation_part)
                if not is_tag(presentation, PRESENTATION_NS, "presentation"):
                    raise InventoryError("The officeDocument part is not a presentation.")
                size = next((c for c in presentation if is_tag(c, PRESENTATION_NS, "sldSz")), None)
                slide_ids = next((c for c in presentation if is_tag(c, PRESENTATION_NS, "sldIdLst")), None)
                if size is None or slide_ids is None:
                    raise InventoryError("Presentation size or logical slide list is missing.")
                width = positive_int(size.get("cx"), "slide width")
                height = positive_int(size.get("cy"), "slide height")
                relationships = package.relationships(presentation_part, required=True)
                slides = []
                seen_ids = set()
                for entry in slide_ids:
                    if not is_tag(entry, PRESENTATION_NS, "sldId"):
                        continue
                    sid = entry.get("id")
                    rid = next((entry.get("{" + ns + "}id") for ns in RELATIONSHIP_NS
                                if entry.get("{" + ns + "}id") is not None), None)
                    rel = relationships.get(rid)
                    if not sid or sid in seen_ids or not rel or rel["type"] != "slide" or rel["external"]:
                        raise InventoryError("The logical slide list contains an invalid reference or duplicate ID.")
                    seen_ids.add(sid)
                    slide = package.xml(rel["part"])
                    if not is_tag(slide, PRESENTATION_NS, "sld"):
                        raise InventoryError("A slide relationship points to a non-slide XML part.")
                    nodes = list(visible_xml_nodes(slide))
                    texts = [n.text or "" for n in nodes if is_tag(n, DRAWING_NS, "t")]
                    faces = sorted({n.get("typeface") for n in nodes
                                    if tag_parts(n.tag)[0] in DRAWING_NS
                                    and tag_parts(n.tag)[1] in ("latin", "ea", "cs", "sym")
                                    and n.get("typeface")})
                    sizes = sorted({positive_int(n.get("sz"), "explicit font size") / 100
                                    for n in nodes if tag_parts(n.tag)[0] in DRAWING_NS
                                    and tag_parts(n.tag)[1] in ("rPr", "defRPr", "endParaRPr")
                                    and n.get("sz") is not None})
                    srels = package.relationships(rel["part"])
                    note_rels = [r for r in srels.values() if r["type"] == "notesSlide" and not r["external"]]
                    image_rels = [r for r in srels.values() if r["type"] == "image"]
                    record = {
                        "logical_position": len(slides) + 1,
                        "presentation_slide_id": sid,
                        "part": rel["part"],
                        "hidden_slide": slide.get("show", "1").lower() in ("0", "false"),
                        "native_table_count": sum(is_tag(n, DRAWING_NS, "tbl") for n in nodes),
                        "picture_shape_count": sum(is_tag(n, PRESENTATION_NS, "pic") for n in nodes),
                        "text_node_count": len(texts),
                        "text_character_count": sum(map(len, texts)),
                        "explicit_typefaces": faces,
                        "explicit_font_sizes_pt": sizes,
                        "notes_relationship_present": bool(note_rels),
                        "notes_part_present": any(r["part"] in package.members for r in note_rels),
                        "internal_image_relationship_count": sum(not r["external"] for r in image_rels),
                        "external_image_relationship_count": sum(r["external"] for r in image_rels),
                        "missing_internal_image_part_count": sum(not r["external"] and r["part"] not in package.members for r in image_rels),
                    }
                    if include_text:
                        record["text"] = texts
                    slides.append(record)
                media_count = sum(not info.is_dir() and "media" in name.split("/")[:-1]
                                  for name, info in package.members.items())
                notes_count = sum(not info.is_dir() and "notesSlides" in name.split("/")[:-1]
                                  and name.endswith(".xml") for name, info in package.members.items())
                return {
                    "schema": "pptx-structure-inventory/1",
                    "sha256": digest.hexdigest(),
                    "slide_count": len(slides),
                    "slide_size": {"width_emu": width, "height_emu": height,
                                   "width_inches": round(width / 914400, 6), "height_inches": round(height / 914400, 6)},
                    "text_included": include_text,
                    "media_part_count": media_count,
                    "notes_slide_part_count": notes_count,
                    "slides": slides,
                    "limitations": [
                        "Logical order follows presentation.xml, not slide filenames.",
                        "Slide-local XML only; inherited master/layout text, themes, charts and image OCR are not resolved.",
                        "Text and counts exclude explicitly hidden shape subtrees; actual rendered visibility is not determined.",
                        "Explicit font declarations may include theme tokens or unused defaults; they are not rendered font measurements.",
                        "Notes bodies, media contents, absolute input paths and relationship URLs are not emitted.",
                        "No assessment of factual correctness, adequate redaction, actual glyphs, overflow or visual acceptance is made.",
                    ],
                }
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise InventoryError("The input is unreadable or is not a valid PPTX ZIP package.") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pptx", type=Path, help="PPTX file to inspect without modification")
    parser.add_argument("--include-text", action="store_true", help="include slide-local text; may contain sensitive content")
    parser.add_argument("--output", type=Path, help="write JSON to this file instead of stdout")
    args = parser.parse_args(argv)
    try:
        if args.output is not None:
            same_path = args.output.resolve() == args.pptx.resolve()
            same_file = args.output.exists() and args.pptx.exists() and args.output.samefile(args.pptx)
            if same_path or same_file:
                raise InventoryError("The output must not overwrite the input PPTX.")
        result = json.dumps(inventory(args.pptx, args.include_text), ensure_ascii=False, indent=2) + "\n"
        if args.output is None:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            sys.stdout.write(result)
        else:
            args.output.write_text(result, encoding="utf-8")
        return 0
    except (InventoryError, OSError, ValueError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, InventoryError) else "The requested input/output path or package structure could not be processed."
        print("inspect_pptx: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
