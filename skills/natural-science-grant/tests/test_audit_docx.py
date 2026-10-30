"""Synthetic OOXML checks; these do not certify rendered pagination."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_docx.py"
spec = importlib.util.spec_from_file_location("audit_docx", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def picture(kind="inline"):
    return f'<w:p><w:r><w:drawing><wp:{kind}><a:graphic><a:blip r:embed="rImage1"/></a:graphic></wp:{kind}></w:drawing></w:r></w:p>'


class AuditDocxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "synthetic.docx"

    def tearDown(self):
        self.temp.cleanup()

    def make(self, body, extra=None):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("word/document.xml", f'<w:document {NS}><w:body>{body}</w:body></w:document>')
            for name, content in (extra or {}).items():
                archive.writestr(name, content)

    def test_default_redacts_text_and_preserves_input(self):
        secret = "Synthetic Person Unpublished Result"
        self.make(f'<w:p><w:r><w:t>{secret}</w:t></w:r></w:p>')
        before = self.path.read_bytes()
        report = module.audit(self.path)
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn("paragraph_text", report)
        self.assertEqual(report["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(module.audit(self.path, True)["paragraph_text"][0]["text"], secret)

    def test_explicit_false_unspecified_and_inheritance_stay_distinct(self):
        self.make('<w:p><w:pPr><w:pStyle w:val="Kept"/></w:pPr><w:r><w:t>A</w:t></w:r></w:p>'
                  '<w:p><w:pPr><w:keepNext w:val="0"/><w:keepLines/><w:pageBreakBefore w:val="false"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>',
                  {"word/styles.xml": f'<w:styles {NS}><w:style w:styleId="Kept"><w:pPr><w:keepNext/></w:pPr></w:style></w:styles>'})
        report = module.audit(self.path)
        self.assertEqual(len(report["pagination_candidates"]), 1)
        item = report["pagination_candidates"][0]
        self.assertEqual(item["index"], 2)
        self.assertEqual(item["pagination_explicit"], {"keepNext": False, "keepLines": True, "pageBreakBefore": False})
        self.assertEqual(item["manual_page_breaks"], 1)
        self.assertIsNone(report["font_settings_explicit"]["embedTrueTypeFonts"])

    def test_inline_anchor_caption_and_empty_candidates_are_not_page_claims(self):
        long_caption = "图4 示例图注。" + "仅用于合成测试。" * 80
        self.make(picture() + f'<w:p><w:r><w:t>{long_caption}</w:t></w:r></w:p>'
                  '<w:p/>' + picture("anchor") + '<w:p><w:r><w:t>Figure 5 Example</w:t></w:r></w:p>')
        report = module.audit(self.path)
        self.assertEqual(report["image_counts"], {"inline": 1, "anchored": 1, "legacy_vml": 0})
        self.assertEqual(report["empty_paragraph_candidates"], [3])
        self.assertEqual([c["index"] for c in report["caption_candidates"]], [2, 5])
        self.assertTrue(all(c["previous_paragraph_has_image"] for c in report["caption_candidates"]))
        self.assertNotIn("page_count", report)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(module.main([str(self.path)]), 0)

    def test_embedded_missing_relation_and_missing_part(self):
        table = f'<w:fonts {NS}><w:font w:name="Synthetic Serif"><w:embedRegular r:id="rMissing"/><w:embedBold r:id="rAbsentPart"/><w:embedItalic r:id="rPresent" w:subsetted="1"/></w:font></w:fonts>'
        rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rAbsentPart" Target="fonts/missing.odttf"/><Relationship Id="rPresent" Target="fonts/present.odttf"/></Relationships>'
        settings = f'<w:settings {NS}><w:embedTrueTypeFonts/><w:saveSubsetFonts w:val="false"/></w:settings>'
        self.make('<w:p/>', {"word/fontTable.xml": table, "word/_rels/fontTable.xml.rels": rels,
                             "word/settings.xml": settings, "word/fonts/present.odttf": b"synthetic-not-real-font"})
        report = module.audit(self.path)
        faces = report["fonts"]["embedded_faces"]
        self.assertEqual([(x["relationship_exists"], x["part_exists"]) for x in faces], [(False, False), (True, False), (True, True)])
        self.assertTrue(faces[2]["subsetted_explicit"])
        self.assertEqual(report["font_settings_explicit"]["embedTrueTypeFonts"], True)
        self.assertEqual(report["font_settings_explicit"]["saveSubsetFonts"], False)

    def test_output_cannot_overwrite_resolved_input(self):
        self.make('<w:p/>')
        before = self.path.read_bytes()
        alias = self.root / "nonexistent" / ".." / self.path.name
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main([str(self.path), "--output", str(alias)]), 2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_zip_and_missing_document_part_fail_cleanly(self):
        self.path.write_bytes(b"not a zip")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main([str(self.path)]), 2)
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("unrelated.xml", "<root/>")
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(module.main([str(self.path)]), 2)
        self.assertIn("word/document.xml", errors.getvalue())

    def test_nested_textbox_text_is_not_duplicated(self):
        self.make('<w:p><w:r><w:t>Outer</w:t></w:r><w:r><w:pict><w:txbxContent><w:p><w:r><w:t>Inner</w:t></w:r></w:p></w:txbxContent></w:pict></w:r></w:p>')
        report = module.audit(self.path, True)
        self.assertEqual(report["paragraph_text"], [{"index": 1, "text": "Outer"}, {"index": 2, "text": "Inner"}])

    def test_font_declarations_and_output_json(self):
        self.make('<w:p><w:r><w:rPr><w:rFonts w:ascii="Example Serif" w:eastAsia="Example CJK" w:hAnsiTheme="minorHAnsi"/></w:rPr><w:t>Private words</w:t></w:r></w:p>')
        output = self.root / "inventory.json"
        self.assertEqual(module.main([str(self.path), "--output", str(output)]), 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["fonts"]["explicit_font_declarations"], {"Example CJK": 1, "Example Serif": 1})
        self.assertEqual(report["fonts"]["theme_font_slots"], {"hAnsiTheme:minorHAnsi": 1})
        self.assertNotIn("Private words", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
