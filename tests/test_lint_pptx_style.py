"""Synthetic OOXML fixtures only: no private presentations or licensed assets."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/lint_pptx_style.py'
spec = importlib.util.spec_from_file_location('lint_style', SCRIPT)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)
NS = ' '.join(f'xmlns:{k}="{v}"' for k, v in lint.NS.items())
URL = 'https://example.org/paper'

def run_xml(value, linked=False, underline='none', bold='1', size=900):
    link = '<a:hlinkClick r:id="rRef"/>' if linked else ''
    return f'<a:r><a:rPr sz="{size}" b="{bold}" u="{underline}">{link}</a:rPr><a:t>{escape(value)}</a:t></a:r>'

class StyleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'synthetic.pptx'
    def tearDown(self):
        self.tmp.cleanup()
    def make(self, runs=None, shape_action=False, order=(1,), wrong_page=False, relation=True):
        if runs is None:
            runs = run_xml('Paper title | ') + run_xml('Example Journal', True) + run_xml(', 2026.')
        prs = ''.join(f'<p:sldId id="{255+n}" r:id="s{n}"/>' for n in order)
        relationships = ''.join(f'<Relationship Id="s{n}" Target="slides/slide{n}.xml"/>' for n in order)
        with ZipFile(self.path, 'w') as z:
            z.writestr('ppt/presentation.xml', f'<p:presentation {NS}><p:sldIdLst>{prs}</p:sldIdLst></p:presentation>')
            z.writestr('ppt/_rels/presentation.xml.rels', f'<Relationships>{relationships}</Relationships>')
            for position, n in enumerate(order, 1):
                action = '<a:hlinkClick r:id="rRef"/>' if shape_action else ''
                page = 99 if wrong_page else position
                xml = f'<p:sld {NS}><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr name="ReferenceFooter">{action}</p:cNvPr></p:nvSpPr><p:txBody><a:p>{runs}</a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:cNvPr name="Page"/></p:nvSpPr><p:txBody><a:p>{run_xml(f"{page:02d}")}</a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
                z.writestr(f'ppt/slides/slide{n}.xml', xml)
                r = f'<Relationship Id="rRef" Target="{URL}" TargetMode="External"/>' if relation else ''
                z.writestr(f'ppt/slides/_rels/slide{n}.xml.rels', f'<Relationships>{r}</Relationships>')
    def codes(self, **kwargs):
        return {x['code'] for x in lint.audit(self.path, **kwargs)['issues']}
    def test_good_exact_anchor(self):
        self.make()
        expected = {'1:ReferenceFooter:1': [{'text': 'Example Journal', 'url': URL}]}
        self.assertEqual(lint.audit(self.path, expected=expected)['errors'], 0)
    def test_title_link(self):
        self.make(run_xml('Paper title | ', True) + run_xml('Example Journal', True))
        self.assertIn('title_or_prefix_linked', self.codes())
    def test_status_must_not_be_linked(self):
        self.make(run_xml('Paper | ') + run_xml('Example Journal Reviewed Preprint v2', True))
        self.assertIn('date_or_status_linked', self.codes())
    def test_shape_action(self):
        self.make(shape_action=True)
        self.assertIn('shape_level_reference_link', self.codes())
    def test_underlined(self):
        self.make(run_xml('Paper | ') + run_xml('Example Journal', True, underline='sng'))
        self.assertIn('underlined_reference_link', self.codes())
    def test_logical_order_not_filenames(self):
        self.make(order=(3, 1, 2))
        report = lint.audit(self.path, profile={'page_number_shape_name': 'Page'})
        self.assertEqual(report['slide_count'], 3)
        self.assertEqual(report['errors'], 0)
    def test_page_number(self):
        self.make(wrong_page=True)
        self.assertIn('page_number_mismatch', self.codes(profile={'page_number_shape_name': 'Page'}))
    def test_size(self):
        self.make(run_xml('Paper | ') + run_xml('Example Journal', True, size=870))
        self.assertIn('font_size_mismatch', self.codes(profile={'reference_pt': 9}))
    def test_wrong_target(self):
        self.make()
        expected = {'1:ReferenceFooter:1': [{'text': 'Example Journal', 'url': 'https://example.org/other'}]}
        self.assertIn('citation_map_mismatch', self.codes(expected=expected))
    def test_missing_location(self):
        self.make()
        self.assertIn('citation_map_location_missing', self.codes(expected={'5:ReferenceFooter:1': []}))
    def test_missing_relationship(self):
        self.make(relation=False)
        self.assertIn('missing_link_target', self.codes())
    def test_comma_excluded(self):
        self.make(run_xml('Paper | ') + run_xml('Example Journal,', True))
        self.assertIn('extra_space_or_punctuation_linked', self.codes())
    def test_read_only(self):
        self.make()
        before = self.path.read_bytes()
        lint.audit(self.path)
        self.assertEqual(before, self.path.read_bytes())

if __name__ == '__main__':
    unittest.main()
