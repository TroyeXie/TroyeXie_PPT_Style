"""Synthetic integration checks; set BOOKLET_TEST_FONT to a local CJK TTF.

No font, photograph or private example is distributed with these tests.
"""
from pathlib import Path
import copy, json, os, subprocess, sys, tempfile, unittest
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('BOOKLET_TEST_FONT'), 'Set BOOKLET_TEST_FONT to a local CJK .ttf')
class BuildBooklet(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.brief=json.loads((ROOT/'examples/brief.example.json').read_text(encoding='utf-8'))
        self.font=str(Path(os.environ['BOOKLET_TEST_FONT']).resolve())

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, brief=None, out=None, extra=()):
        source=self.base/'brief.json'
        source.write_text(json.dumps(brief or self.brief,ensure_ascii=False),encoding='utf-8')
        output=out or self.base/'draft.pdf'
        completed=subprocess.run([sys.executable,str(ROOT/'scripts/build_booklet.py'),str(source),
            '--font-body',self.font,'--output',str(output),*extra],capture_output=True,text=True,encoding='utf-8')
        return source,output,completed

    def test_two_pages_with_extractable_text(self):
        _,out,result=self.build()
        self.assertEqual(result.returncode,0,result.stderr)
        pages=PdfReader(out).pages
        self.assertEqual(len(pages),2)
        self.assertTrue(all(p.extract_text().strip() for p in pages))
        self.assertTrue(all(abs(float(p.mediabox.width)-595.276)<.01 for p in pages))

    def test_long_copy_fails_without_partial_file(self):
        brief=copy.deepcopy(self.brief);brief['intro']['body']='基层需求与实践收获。'*100
        _,out,result=self.build(brief)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(out.exists())

    def test_missing_font_fails(self):
        _,out,result=self.build(extra=('--font-body',str(self.base/'absent.ttf')))
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(out.exists())

    def test_existing_output_is_preserved(self):
        out=self.base/'existing.pdf';out.write_bytes(b'unchanged sentinel')
        _,_,result=self.build(out=out)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(out.read_bytes(),b'unchanged sentinel')

    def test_force_does_not_overwrite_brief(self):
        source=self.base/'brief.json'
        _,_,result=self.build(out=source,extra=('--force',))
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(source.read_text(encoding='utf-8')),self.brief)

if __name__=='__main__':
    unittest.main()
