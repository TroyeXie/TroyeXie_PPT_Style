#!/usr/bin/env python3
"""Build a two-page A4 social-practice booklet from a short JSON brief.

Dependencies: reportlab; Pillow for photographs; pypdf only for a PDF logo.
No fonts, photos, identities, or project facts are bundled. Text, decorations and
an optional PDF logo remain vector objects. Photographs remain raster images.

Example:
  python build_booklet.py ../examples/brief.example.json --font-body /path/kaiti.ttf \
      --font-title /path/title.ttf --output booklet.pdf

All coordinates are points measured from the page top. The editable source is
the JSON brief plus this script. This is a deliberately bounded first-draft
layout: long copy fails with an actionable overflow error, rather than quietly
shrinking type or adding pages.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4
# Reuse these anchors for photographs, captions, text, and award cards.
X = {"left": 28.0, "middle": 226.0, "right_photo": 377.0, "right": 567.0}
PAGE_INNER_W = X["right"] - X["left"]
PRESETS = {
    "formal-red": {
        "paper": "#FFF9EF", "ink": "#382B21", "muted": "#6B5146",
        "primary": "#A92B23", "header": "#8F241E", "gold": "#BC9252",
        "tint": "#F4E7D0", "white": "#FFF9EF", "line": "#DCC6A3",
    },
    "university-blue": {
        "paper": "#FAFBFD", "ink": "#233246", "muted": "#526379",
        "primary": "#074591", "header": "#123C69", "gold": "#A58A5A",
        "tint": "#E8EFF7", "white": "#FAFBFD", "line": "#C7D4E3",
    },
}


class LayoutError(ValueError):
    """Copy, typography, or geometry does not fit the selected layout."""


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float
    label: str

    def check(self) -> None:
        vals = (self.x, self.y, self.w, self.h)
        if any(not math.isfinite(v) for v in vals) or self.w <= 0 or self.h <= 0:
            raise LayoutError(f"{self.label}: invalid rectangle {vals}")
        if self.x < -0.01 or self.y < -0.01 or self.x + self.w > PAGE_W + 0.01 or self.y + self.h > PAGE_H + 0.01:
            raise LayoutError(f"{self.label}: rectangle extends beyond A4 page: {vals}")


@dataclass(frozen=True)
class Glyph:
    char: str
    bold: bool = False
    highlight: bool = False
    group: int = -1


class Booklet:
    def __init__(self, brief: dict[str, Any], base: Path, fonts: dict[str, str | None], brief_path: Path | None = None):
        self.brief, self.base = brief, base
        self.source_paths: set[Path] = set()
        if brief_path is not None:
            self.source_paths.add(brief_path.resolve())
        # Protect all supplied inputs, including optional/unused assets and
        # JSON font entries overridden by command-line options.
        for value in list(fonts.values()) + list(brief.get("fonts", {}).values()):
            if isinstance(value, str) and value:
                self.source_paths.add(self.resolve(value))
        def collect_assets(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "path" and isinstance(child, str) and child:
                        self.source_paths.add(self.resolve(child))
                    collect_assets(child)
            elif isinstance(value, list):
                for child in value:
                    collect_assets(child)
        collect_assets(brief)
        preset = brief.get("preset", "formal-red")
        if preset not in PRESETS:
            raise LayoutError(f"Unknown preset {preset!r}; choose {', '.join(PRESETS)}")
        raw_colors = {**PRESETS[preset], **brief.get("colors", {})}
        for name, val in raw_colors.items():
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(val)):
                raise LayoutError(f"colors.{name}: expected #RRGGBB")
        self.colors = {k: HexColor(v) for k, v in raw_colors.items()}
        self.fonts: dict[str, str] = {}
        self.faces: dict[str, Any] = {}
        for kind, path in fonts.items():
            if not path:
                continue
            resolved = self.resolve(path)
            if not resolved.is_file():
                raise LayoutError(f"Font {kind}: file not found: {resolved}")
            name = f"Booklet_{kind}"
            try:
                font = TTFont(name, str(resolved))
                pdfmetrics.registerFont(font)
            except Exception as exc:
                raise LayoutError(f"Cannot load {kind} font {resolved}: {exc}. Use a TrueType-outline .ttf font.") from exc
            self.fonts[kind], self.faces[kind] = name, font.face
        if "body" not in self.fonts:
            raise LayoutError("Provide --font-body or fonts.body_regular in the JSON; fonts are never silently substituted.")
        self.fonts.setdefault("title", self.fonts["body"])
        self.faces.setdefault("title", self.faces["body"])
        self.fonts.setdefault("bold", self.fonts["body"])
        self.faces.setdefault("bold", self.faces["body"])
        self.synthetic_bold = not bool(fonts.get("bold"))
        self.cv: canvas.Canvas
        self.logo_places: list[dict[str, Any]] = []

    def resolve(self, value: str) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else (self.base / p).resolve()

    def col(self, key: str) -> Color:
        return self.colors[key]

    def rect(self, box: Box, fill: str = "tint", stroke: str | None = None, radius: float = 0) -> None:
        box.check()
        c = self.cv
        c.setFillColor(self.col(fill))
        if stroke:
            c.setStrokeColor(self.col(stroke))
            c.setLineWidth(0.55)
        fn = c.roundRect if radius else c.rect
        if radius:
            fn(box.x, PAGE_H - box.y - box.h, box.w, box.h, radius, fill=1, stroke=bool(stroke))
        else:
            fn(box.x, PAGE_H - box.y - box.h, box.w, box.h, fill=1, stroke=bool(stroke))

    def glyphs(self, text: str, bold: bool, highlights: list[str], bold_phrases: list[str], keep_together: list[str]) -> list[Glyph]:
        hi, bo = set(), set()
        for phrase, target in [(v, hi) for v in highlights] + [(v, bo) for v in bold_phrases]:
            if not phrase or phrase not in text:
                raise LayoutError(f"Requested emphasis phrase not found in text: {phrase!r}")
            start = 0
            while (pos := text.find(phrase, start)) >= 0:
                target.update(range(pos, pos + len(phrase)))
                start = pos + len(phrase)
        protected: dict[int, int] = {}
        group_id = 0
        for phrase in keep_together:
            if not phrase or phrase not in text or "\n" in phrase:
                raise LayoutError(f"Requested keep_together phrase is absent or invalid: {phrase!r}")
            start = 0
            while (pos := text.find(phrase, start)) >= 0:
                indices = range(pos, pos + len(phrase))
                if any(i in protected for i in indices):
                    raise LayoutError("keep_together phrases may not overlap")
                protected.update({i: group_id for i in indices})
                group_id += 1
                start = pos + len(phrase)
        return [Glyph(ch, bold or i in bo, i in hi, protected.get(i, -1)) for i, ch in enumerate(text)]

    def font_for(self, glyph: Glyph, font: str) -> str:
        return self.fonts["bold" if glyph.bold and font == "body" else font]

    def width(self, glyph: Glyph, font: str, size: float) -> float:
        face_key = "bold" if glyph.bold and font == "body" else font
        if glyph.char not in "\n\r\t" and ord(glyph.char) not in self.faces[face_key].charToGlyph:
            raise LayoutError(f"Font {face_key} is missing character {glyph.char!r} (U+{ord(glyph.char):04X}); provide a font with this glyph.")
        return pdfmetrics.stringWidth(glyph.char, self.font_for(glyph, font), size)

    def wrap(self, glyphs: list[Glyph], width: float, font: str, size: float, label: str) -> list[list[Glyph]]:
        # Character-aware wrapping works for CJK and Latin; prefer Latin spaces
        # when available and keep common closing punctuation with its phrase.
        lines: list[list[Glyph]] = []
        line: list[Glyph] = []
        used = 0.0
        closing = set("，。；：！？、）》】〉”’％%.,;:!?)]}")
        opening = set("（《【〈“‘([{")
        for g in glyphs:
            if g.char == "\r":
                continue
            if g.char == "\n":
                lines.append(line)
                line, used = [], 0.0
                continue
            w = self.width(g, font, size)
            if w > width + 0.01:
                raise LayoutError(f"{label}: one character exceeds the text box width")
            if line and used + w > width + 0.01:
                if g.group >= 0 and line[-1].group == g.group:
                    split_group = len(line) - 1
                    while split_group > 0 and line[split_group - 1].group == g.group:
                        split_group -= 1
                    if split_group == 0:
                        raise LayoutError(f"{label}: a keep_together phrase exceeds the box width; shorten it or widen the box")
                    lines.append(line[:split_group])
                    line = line[split_group:]
                    used = sum(self.width(v, font, size) for v in line)
                    if used + w > width + 0.01:
                        raise LayoutError(f"{label}: a keep_together phrase exceeds the box width")
                    line.append(g)
                    used += w
                    continue
                split = None
                spaces = [i for i, v in enumerate(line) if v.char == " "]
                if spaces and spaces[-1] >= len(line) * 0.55:
                    split = spaces[-1] + 1
                if split is not None:
                    lines.append(line[:split])
                    line = line[split:]
                elif g.char in closing or line[-1].char in opening:
                    if len(line) < 2:
                        raise LayoutError(f"{label}: punctuation cannot fit; widen the box")
                    tail = len(line) - 1
                    if line[-1].group >= 0:
                        while tail > 0 and line[tail - 1].group == line[-1].group:
                            tail -= 1
                    if tail == 0:
                        raise LayoutError(f"{label}: protected phrase plus punctuation cannot fit")
                    lines.append(line[:tail])
                    line = line[tail:]
                else:
                    lines.append(line)
                    line = []
                used = sum(self.width(v, font, size) for v in line)
            line.append(g)
            used += w
            if used > width + 0.01:
                raise LayoutError(f"{label}: text width overflow after punctuation wrapping")
        if line or not lines:
            lines.append(line)
        return lines

    def text(self, text: str, box: Box, size: float = 11.0, leading: float | None = None,
             font: str = "body", bold: bool = False, color: str = "ink", align: str = "left",
             max_lines: int | None = None, highlights: list[str] | None = None,
             bold_phrases: list[str] | None = None, keep_together: list[str] | None = None) -> None:
        box.check()
        if not isinstance(text, str) or not text:
            return
        if size < 9.5:
            raise LayoutError(f"{box.label}: size {size} is below this starter's readable minimum 9.5 pt")
        leading = leading or size * 1.35
        if leading < size:
            raise LayoutError(f"{box.label}: leading must be at least the font size")
        glyphs = self.glyphs(text, bold, highlights or [], bold_phrases or [], keep_together or [])
        lines = self.wrap(glyphs, box.w, font, size, box.label)
        face_keys = {"bold" if g.bold and font == "body" else font for g in glyphs}
        ascent = max(self.faces[k].ascent for k in face_keys) * size / 1000
        descent = min(self.faces[k].descent for k in face_keys) * size / 1000
        # Use supplied font metrics, not a guessed baseline or font substitution.
        needed = ascent - descent + (len(lines) - 1) * leading
        if needed > box.h + 0.01 or (max_lines is not None and len(lines) > max_lines):
            raise LayoutError(f"{box.label}: {len(lines)} lines need {needed:.1f} pt, available {box.h:.1f} pt"
                              f" (max {max_lines or 'unlimited'} lines). Shorten this field or revise the template explicitly.")
        c = self.cv
        for i, line in enumerate(lines):
            w = sum(self.width(g, font, size) for g in line)
            x = box.x + (box.w - w) * (0.5 if align == "center" else 1 if align == "right" else 0)
            baseline = PAGE_H - (box.y + ascent + i * leading)
            for g in line:
                c.saveState()
                c.setFillColor(self.col("primary" if g.highlight else color))
                c.setStrokeColor(self.col("primary" if g.highlight else color))
                t = c.beginText(x, baseline)
                t.setFont(self.font_for(g, font), size)
                if g.bold and self.synthetic_bold:
                    c.setLineWidth(max(0.3, size * 0.025))
                    t.setTextRenderMode(2)
                t.textOut(g.char)
                c.drawText(t)
                c.restoreState()
                x += self.width(g, font, size)

    def image(self, item: dict[str, Any] | None, box: Box, background: bool = True) -> None:
        """Complete image fit by default; no stretch, crop, or enlargement of faces."""
        box.check()
        if background:
            self.rect(box, "tint", "line")
        item = item or {}
        path = item.get("path")
        if not path:
            self.text(item.get("placeholder", "活动照片"), Box(box.x + 8, box.y + (box.h - 12) / 2, box.w - 16, 18, box.label + " placeholder"),
                      size=11, align="center", color="muted")
            return
        resolved = self.resolve(path)
        if not resolved.is_file():
            raise LayoutError(f"{box.label}: image not found: {resolved}")
        if item.get("fit", "contain") != "contain":
            raise LayoutError(f"{box.label}: only 'contain' is supported; prepare any intentional crop separately and supply it as a new asset")
        try:
            # ImageReader honors Pillow orientation normalization only after an
            # explicit transpose; use a copy and never modify the source file.
            from PIL import Image, ImageOps
            with Image.open(resolved) as source:
                oriented = ImageOps.exif_transpose(source)
                has_alpha = oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info
                im = oriented.convert("RGBA" if has_alpha else "RGB")
                iw, ih = im.size
                bio = BytesIO()
                if has_alpha:
                    im.save(bio, format="PNG")
                else:
                    im.save(bio, format="JPEG", quality=95)
                bio.seek(0)
                image = ImageReader(bio)
        except ImportError as exc:
            raise LayoutError("Pillow is required when the brief contains photographs") from exc
        except Exception as exc:
            raise LayoutError(f"{box.label}: cannot read {resolved}: {exc}") from exc
        scale = min(box.w / iw, box.h / ih)
        w, h = iw * scale, ih * scale
        self.cv.drawImage(image, box.x + (box.w - w) / 2, PAGE_H - box.y - (box.h + h) / 2,
                          w, h, preserveAspectRatio=True, mask="auto")

    def caption(self, text: str, x: float, y: float, w: float, label: str) -> None:
        self.text(text, Box(x, y, w, 15, label), 9.5, 12, bold=True, align="center", max_lines=1, color="muted")

    def section_bar(self, title: str, top: float, value: str = "") -> None:
        self.rect(Box(X["left"], top, PAGE_INNER_W, 25, title + " banner"), "primary")
        # Non-overlapping title/value boxes; both labels have explicit limits.
        tw = 327 if value else PAGE_INNER_W - 16
        self.text(title, Box(X["left"] + 8, top + 5, tw, 17, title), 13.1, bold=True, color="white", max_lines=1)
        if value:
            self.text(value, Box(X["right_photo"], top + 6, 182, 16, title + " value"), 10.5,
                      bold=True, color="white", align="right", max_lines=1)

    def logo(self, page_num: int, top: float) -> None:
        logo = self.brief.get("logo")
        if not logo:
            return
        path = self.resolve(logo["path"])
        width = float(logo.get("width", 110))
        height = float(logo.get("height", 31))
        # Same size and right anchor on both pages. Page 2 vertical centre is
        # shared with its title; page 1 has a separate reserved upper corner.
        box = Box(X["right"] - width, top, width, height, f"page {page_num} logo")
        box.check()
        if path.suffix.lower() == ".pdf":
            if not path.is_file():
                raise LayoutError(f"Logo PDF not found: {path}")
            self.logo_places.append({"page": page_num - 1, "path": path, "box": box, "source_page": int(logo.get("page", 1)) - 1})
        else:
            self.image({"path": str(path)}, box, background=False)

    def header(self, page_num: int) -> None:
        c = self.cv
        self.rect(Box(0, 0, PAGE_W, PAGE_H, "page background"), "paper")
        if page_num == 1:
            self.rect(Box(0, 0, PAGE_W, 162, "cover header"), "header")
            groups = self.brief["title"].get("groups")
            if groups:
                if len(groups) != 2:
                    raise LayoutError("title.groups must contain exactly two staggered title groups")
                self.text(groups[0], Box(X["left"], 47, 270, 50, "cover title group 1"), 36, font="title", bold=True, color="white", max_lines=1)
                self.text(groups[1], Box(173, 78, 270, 50, "cover title group 2"), 36, font="title", bold=True, color="white", max_lines=1)
            else:
                self.text(self.brief["title"]["text"], Box(X["left"], 68, PAGE_INNER_W, 52, "cover title"),
                          35, font="title", bold=True, color="white", max_lines=1)
            self.text(self.brief["team"], Box(X["left"], 137, PAGE_INNER_W, 16, "team name"),
                      10.5, bold=True, color="white", max_lines=1)
            self.logo(page_num, 17)
        else:
            self.rect(Box(0, 0, PAGE_W, 92, "second page header"), "header")
            self.text(self.brief.get("second_title", "四维实践·以行作答"),
                      Box(X["left"], 28, 410, 43, "second page title"), 27, font="title", bold=True, color="white", max_lines=1)
            height = float(self.brief.get("logo", {}).get("height", 31))
            self.logo(page_num, 47.5 - height / 2)
        c.setStrokeColor(self.col("gold"))
        c.setLineWidth(1.0)
        y = 156 if page_num == 1 else 84
        c.line(X["left"], PAGE_H - y, X["right"], PAGE_H - y)

    def page_one(self) -> None:
        b = self.brief
        self.header(1)
        hero = b.get("hero", {})
        self.image(hero, Box(X["left"], 178, 341, 125, "hero photo"))
        self.caption(hero.get("caption", "共建实践平台"), X["left"], 308, 341, "hero caption")
        self.rect(Box(X["right_photo"], 178, 190, 147, "project summary card"), "tint")
        intro = b.get("intro", {})
        self.text(intro.get("heading", "项目亮点"), Box(387, 189, 170, 20, "intro heading"), 14, bold=True, color="primary", max_lines=1)
        self.text(intro.get("body", "请填写项目缘起、实践定位与主要特色。"), Box(387, 219, 170, 94, "intro body"), 11.3, 15.2, max_lines=6)

        cursor = 338.0
        teachers = b.get("teachers", [])
        if teachers:
            if len(teachers) > 3:
                raise LayoutError("teachers: maximum three cards; summarize additional advisers in the brief")
            self.section_bar(b.get("teacher_heading", "专家领航，多学科协同育人"), cursor)
            cursor += 33
            width = (PAGE_INNER_W - 8 * (len(teachers) - 1)) / len(teachers)
            for i, t in enumerate(teachers):
                x = X["left"] + i * (width + 8)
                self.rect(Box(x, cursor, width, 88, f"teacher {i+1} card"), "tint")
                self.text(t["name"], Box(x+9, cursor+8, width-18, 20, f"teacher {i+1} name"), 14, bold=True, color="primary", max_lines=1)
                self.text(t.get("role", ""), Box(x+9, cursor+34, width-18, 29, f"teacher {i+1} role"), 10.5, 14, bold=True, max_lines=2)
                self.text(t.get("expertise", ""), Box(x+9, cursor+66, width-18, 16, f"teacher {i+1} expertise"), 10.5, bold=True, color="muted", max_lines=1)
            cursor += 102

        leaders = b.get("leaders", [])
        if leaders:
            if len(leaders) > 2:
                raise LayoutError("leaders: maximum two cards; edit the selection rather than making smaller labels")
            self.section_bar(b.get("leader_heading", "殷殷嘱托，厚植专业报国情怀"), cursor)
            cursor += 33
            width = (PAGE_INNER_W - 8 * (len(leaders) - 1)) / len(leaders)
            for i, t in enumerate(leaders):
                x = X["left"] + i * (width + 8)
                self.rect(Box(x, cursor, width, 88, f"leader {i+1} card"), "tint")
                self.text(t["name"], Box(x+10, cursor+8, width-20, 18, f"leader {i+1} name"), 12.5, bold=True, color="primary", max_lines=1)
                self.text(t["message"], Box(x+10, cursor+34, width-20, 46, f"leader {i+1} message"), 11, 15, max_lines=3)
            cursor += 102

        media = b.get("media", {})
        self.section_bar(media.get("heading", "主流媒体聚焦，记录实践成果"), cursor)
        cursor += 34
        available = 812 - cursor
        if available < 141:
            raise LayoutError(f"page 1 media: only {available:.1f} pt remains; reduce optional sections explicitly")
        # Use the available space for actual screenshots; no false giant numbers.
        h = min(available, 165 if teachers and leaders else 285)
        self.rect(Box(X["left"], cursor, 143, h, "media metrics card"), "tint")
        self.text(str(media.get("total", "—")), Box(38, cursor+9, 123, 43, "media total"), 34, bold=True, color="primary", max_lines=1)
        self.text(media.get("unit_label", "条媒体报道"), Box(38, cursor+56, 123, 18, "media total label"), 11.5, bold=True, max_lines=1)
        self.text(f"国家级 {media.get('national', '—')} 条", Box(38, cursor+87, 123, 18, "media national"), 11.5, bold=True, color="primary", max_lines=1)
        self.text(f"省级 {media.get('provincial', '—')} 条", Box(38, cursor+112, 123, 18, "media provincial"), 11.5, bold=True, color="primary", max_lines=1)
        cards = media.get("cards", [])
        if len(cards) > 3:
            raise LayoutError("media.cards: maximum three representative screenshots, prioritizing national/provincial sources")
        if not cards:
            cards = [{"label": "报道平台甲"}, {"label": "报道平台乙"}, {"label": "报道平台丙"}]
        n = len(cards)
        left = 179.0
        width = (X["right"] - left - 6 * (n - 1)) / n
        for i, card in enumerate(cards):
            x, offset = left + i * (width+6), (12 if i % 2 else 0)
            ih = h - offset - 23
            self.image(card, Box(x, cursor+offset, width, ih, f"media card {i+1}"))
            self.caption(card["label"], x, cursor+offset+ih+5, width, f"media card {i+1} caption")

    def page_two(self) -> None:
        b = self.brief
        self.header(2)
        modules = b.get("modules", [])
        if len(modules) != 4:
            raise LayoutError("modules: exactly four activity modules are required for the two-page layout")
        for i, m in enumerate(modules):
            top = 108 + i * 156
            self.section_bar(m["title"], top, m.get("value", ""))
            photos = m.get("photos", [])
            if len(photos) > 2:
                raise LayoutError(f"module {i+1}: at most two photographs")
            photos += [{} for _ in range(2 - len(photos))]
            if i % 2 == 0:
                text_x, text_w = X["left"], 190.0
                photo_cols = [(X["middle"], 143.0), (X["right_photo"], 190.0)]
            else:
                text_x, text_w = X["middle"], 143.0
                photo_cols = [(X["left"], 190.0), (X["right_photo"], 190.0)]
            self.text(m["body"], Box(text_x, top+36, text_w, 92, f"module {i+1} body"), 11, 15.1,
                      max_lines=6, highlights=m.get("highlights", []), bold_phrases=m.get("bold_phrases", []),
                      keep_together=m.get("keep_together", []))
            for j, (x, width) in enumerate(photo_cols):
                photo = photos[j]
                self.image(photo, Box(x, top+34, width, 91, f"module {i+1} photo {j+1}"))
                self.caption(photo.get("caption", "实践纪实"), x, top+131, width, f"module {i+1} photo {j+1} caption")

        awards = b.get("awards", [])
        if len(awards) > 2:
            raise LayoutError("awards: at most two cards; combine related honors without shrinking labels")
        if not awards:
            return
        for i, a in enumerate(awards):
            # The right award and rightmost photographs share X['right_photo'].
            x, w = (X["left"], 341.0) if i == 0 else (X["right_photo"], 190.0)
            self.rect(Box(x, 744, w, 74, f"award {i+1} card"), "tint")
            self.text(a["context"], Box(x+9, 752, w-18, 29, f"award {i+1} context"), 10.5, 13.5, bold=True, max_lines=2)
            self.text(a["name"], Box(x+9, 789, w-18, 22, f"award {i+1} name"), 14, bold=True, color="primary", max_lines=1)

    def merge_pdf_logos(self, source: BytesIO) -> bytes:
        try:
            from pypdf import PdfReader, PdfWriter, Transformation
        except ImportError as exc:
            raise LayoutError("pypdf is required for an optional vector PDF logo") from exc
        reader = PdfReader(source)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for entry in self.logo_places:
            lr = PdfReader(entry["path"])
            idx = entry["source_page"]
            if idx < 0 or idx >= len(lr.pages):
                raise LayoutError(f"Logo page {idx+1} is out of range")
            lp = lr.pages[idx]
            if lp.rotation:
                lp.transfer_rotation_to_content()
            mb, box = lp.cropbox, entry["box"]
            scale = min(box.w / float(mb.width), box.h / float(mb.height))
            dx = box.x + (box.w - float(mb.width)*scale)/2
            dy = PAGE_H - box.y - box.h + (box.h - float(mb.height)*scale)/2
            tf = Transformation().translate(-float(mb.left), -float(mb.bottom)).scale(scale).translate(dx, dy)
            writer.pages[entry["page"]].merge_transformed_page(lp, tf, over=True, expand=False)
        writer.add_metadata({"/Title": self.brief.get("document_title", "社会实践总结册"),
                             "/Creator": "social-practice-booklet configurable starter"})
        out = BytesIO()
        writer.write(out)
        return out.getvalue()

    def build(self, output: Path) -> None:
        output = output.resolve()
        for source in self.source_paths:
            same_file = output == source
            if not same_file and output.exists() and source.exists():
                same_file = output.samefile(source)
            if same_file:
                raise LayoutError(f"Output would overwrite a source input: {source}; choose a separate PDF output, even with --force")
        if not isinstance(self.brief.get("team"), str) or not self.brief["team"].strip():
            raise LayoutError("team: provide a verified team name")
        if "title" not in self.brief:
            raise LayoutError("title: provide text or two staggered groups")
        buf = BytesIO()
        self.cv = canvas.Canvas(buf, pagesize=A4, pageCompression=1)
        self.cv.setTitle(self.brief.get("document_title", "社会实践总结册"))
        self.cv.setAuthor(self.brief.get("author", ""))
        self.page_one()
        self.cv.showPage()
        self.page_two()
        self.cv.showPage()
        self.cv.save()
        buf.seek(0)
        data = self.merge_pdf_logos(buf) if self.logo_places else buf.getvalue()
        # Do not leave a partial deliverable when content validation fails.
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp: Path | None = None
        try:
            # A unique sibling avoids overwriting a user's existing .tmp file
            # and keeps the final replacement atomic on the same filesystem.
            with tempfile.NamedTemporaryFile(mode="wb", prefix=f".{output.name}.", suffix=".tmp",
                                             dir=output.parent, delete=False) as handle:
                tmp = Path(handle.name)
                handle.write(data)
                handle.flush()
            tmp.replace(output)
            tmp = None
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)


def main() -> int:
    # Keep missing-glyph and Chinese overflow diagnostics readable when stdout
    # is redirected on Windows, where the legacy system codec may be narrower.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("brief", type=Path, help="UTF-8 JSON brief; relative asset paths resolve against its directory")
    parser.add_argument("--output", type=Path, required=True, help="Output PDF; use a new staging path for review")
    parser.add_argument("--font-body", help="Local .ttf for body text; overrides fonts.body_regular")
    parser.add_argument("--font-bold", help="Optional local .ttf bold face; otherwise explicit vector stroke emphasis is used")
    parser.add_argument("--font-title", help="Optional local .ttf title/calligraphy face; defaults explicitly to body font")
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing output after review")
    args = parser.parse_args()
    try:
        brief_path = args.brief.expanduser().resolve()
        brief = json.loads(brief_path.read_text(encoding="utf-8-sig"))
        if not isinstance(brief, dict):
            raise LayoutError("JSON root must be an object")
        configured = brief.get("fonts", {})
        fonts = {"body": args.font_body or configured.get("body_regular"),
                 "bold": args.font_bold or configured.get("body_bold"),
                 "title": args.font_title or configured.get("title")}
        out = args.output.expanduser().resolve()
        if out.exists() and not args.force:
            raise LayoutError(f"Output already exists: {out}; use a fresh staging name or --force after review")
        booklet = Booklet(brief, brief_path.parent, fonts, brief_path=brief_path)
        booklet.build(out)
        print(f"Created two-page A4 PDF: {out}")
        if booklet.synthetic_bold:
            print("Emphasis: vector fill-and-stroke using the supplied body face (no separate bold font supplied).")
        print("Review both rendered pages before publication; photographs remain raster, text and decorations are vector.")
        return 0
    except (LayoutError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
