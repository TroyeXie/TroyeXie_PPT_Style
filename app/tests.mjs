// Offline regression tests. Run with Node 20+ : node app/tests.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
globalThis.window = globalThis;
for (const f of ['vendor/jszip.min.js', 'vendor/pptxgen.min.js', 'core.js', 'demo.js', 'pptx.js']) {
  vm.runInThisContext(fs.readFileSync(path.join(directory, f), 'utf8'), { filename: f, importModuleDynamically: vm.constants.USE_MAIN_CONTEXT_DEFAULT_LOADER });
}
const C = globalThis.CampusPPT, E = globalThis.CampusPPTExport;
let checks = 0;
function check(name, task) { return Promise.resolve().then(task).then(() => { checks++; process.stdout.write('PASS ' + name + '\n'); }); }

await check('All scene demos contain editable supported layouts and no private data', () => {
  for (const scene of ['course', 'lab', 'journal']) {
    const p = C.createDemo(scene), review = C.validateProject(p);
    assert.equal(p.slides.length, 6); assert.deepEqual(review.errors, []);
    assert.deepEqual(new Set(p.slides.map(s => s.type)), new Set(['cover', 'section', 'bullets', 'comparison', 'figure']));
    assert(p.slides.every(s => s.citations.every(c => c.kind === 'synthetic')));
    assert(p.slides.every(s => s.evidence === 'teaching' || s.evidence === 'plan'));
    assert(p.slides.find(s => s.image).image.alt.includes('合成'));
  }
});
await check('Markdown directives retain exact source fields and independent notes', () => {
  const p = C.parseMarkdown('# 课堂主题\n## 对比页\n@section 阅读\n@evidence literature\n### 已知\n- 实验结果\n### 未知\n- 待检验问题\n@source paper | A & B | Example Journal | 2026 | https://example.org/paper | Reviewed Preprint v2\n> 独立备注', 'journal');
  assert.equal(p.title, '课堂主题'); assert.equal(p.slides[0].type, 'comparison');
  assert.equal(p.slides[0].columns[1].body[0], '待检验问题');
  assert.equal(p.slides[0].citations[0].venue, 'Example Journal');
  assert.equal(p.slides[0].citations[0].status, 'Reviewed Preprint v2');
  assert.equal(p.slides[0].notes, '独立备注');
  assert.deepEqual(C.parseMarkdown(C.projectToMarkdown(p), 'journal').slides[0].citations, p.slides[0].citations);
});
await check('Untrusted imports reject executable URLs, fake images and excessive size', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,test', 'file:///etc/passwd', 'https://user:password@example.org', 'https://example.org/\n']) assert.equal(C.safeUrl(url), '');
  assert(C.safeUrl('https://example.org/?a=1&b=2'));
  assert(!C.isSafeImageDataUrl('data:image/svg+xml;base64,PHN2Zy8+'));
  assert(!C.isSafeImageDataUrl('data:image/png;base64,aGVsbG8='));
  const p = C.createDemo('course'); p.slides[2].citations = [{ title: 'A', venue: 'B', year: '2026', url: 'javascript:alert(1)' }];
  assert.throws(() => C.normalizeProject(p), /http\/https/);
  p.slides[2].citations = []; p.theme.font = '"/><bad/>';
  assert.throws(() => C.normalizeProject(p), /字体/);
  assert.throws(() => C.parseMarkdown('A'.repeat(C.limits.outlineChars + 1)), /120,000/);
});
await check('Manual timing can be zero and custom palette stays selected', () => {
  const p = C.createDemo('course'); p.theme.palette = 'custom'; p.theme.accent = '#123456';
  p.slides.forEach(s => { s.durationSec = 0; });
  const clean = C.normalizeProject(p);
  assert.equal(clean.theme.palette, 'custom'); assert.equal(clean.theme.accent, '#123456');
  assert.equal(C.estimateProject(clean).scheduledMinutes, 0);
  clean.slides[0].durationSec = 1800;
  assert(C.validateProject(clean).warnings.some(w => w.code === 'scheduled-duration'));
});
await check('References exceeding the export area block export rather than disappear', async () => {
  const p = C.createDemo('course'); p.slides[2].citations = Array.from({ length: 4 }, () => ({ kind: 'synthetic', title: 'Test', venue: '', year: '', url: '' }));
  assert(C.validateProject(p).errors.some(e => e.code === 'citation-count'));
  await assert.rejects(E.exportPptx(p), /最多保留 3/);
});

for (const nav of ['top', 'left', 'none']) {
  await check('Actual PPTX export: ' + nav + ' navigation, native text, notes, exact hyperlink and image ratio', async () => {
    const p = C.createDemo('course'); p.theme.nav = nav; p.theme.accent = '#675985';
    p.slides[2].citations = [{ kind: 'paper', title: 'A < B & C', venue: 'Example Journal', year: '2026',
      url: 'https://example.org/paper', status: 'Reviewed Preprint v2' }];
    p.slides[2].notes = '备注中的关键限制保持完整。';
    const blob = await E.exportPptx(p); assert(blob.size > 5000);
    const archive = await globalThis.JSZip.loadAsync(await blob.arrayBuffer());
    const files = Object.keys(archive.files);
    assert.equal(files.filter(f => /^ppt\/slides\/slide\d+\.xml$/.test(f)).length, 6);
    assert.equal(files.filter(f => /^ppt\/notesSlides\/notesSlide\d+\.xml$/.test(f)).length, 6);
    assert(!files.some(f => /\.fntdata$/.test(f)));
    const third = await archive.file('ppt/slides/slide3.xml').async('string');
    assert(third.includes('A &lt; B &amp; C'));
    assert(third.includes('675985')); assert(third.includes('<p:sp>'));
    const runs = third.match(/<a:r>.*?<\/a:r>/gs) || [];
    const linked = runs.filter(r => r.includes('<a:hlinkClick'));
    assert.equal(linked.length, 1); assert(linked[0].includes('<a:t>Example Journal</a:t>'));
    assert(linked[0].includes('b="1"')); assert(linked[0].includes('u="none"'));
    assert(!linked[0].includes('2026')); assert(!linked[0].includes('Preprint')); assert(!linked[0].includes('A &lt;'));
    const shapeProperties = third.match(/<p:cNvPr\b[^>]*?(?:\/>|>[\s\S]*?<\/p:cNvPr>)/g) || [];
    assert(shapeProperties.every(x => !x.includes('<a:hlinkClick')));
    const rels = await archive.file('ppt/slides/_rels/slide3.xml.rels').async('string');
    assert(rels.includes('https://example.org/paper'));
    const note = await archive.file('ppt/notesSlides/notesSlide3.xml').async('string');
    assert(note.includes('备注中的关键限制保持完整')); assert(note.includes('https://example.org/paper'));
    const fifth = await archive.file('ppt/slides/slide5.xml').async('string');
    const picture = fifth.match(/<p:pic>.*?<\/p:pic>/s)[0];
    const ext = picture.match(/<a:ext cx="(\d+)" cy="(\d+)"/);
    assert(ext); assert(Math.abs(Number(ext[1]) / Number(ext[2]) - 1185 / 704) < .0001);
    const navObjects = (third.match(/name="Navigation /g) || []).length;
    assert.equal(navObjects, nav === 'none' ? 0 : 4);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    assert.doesNotThrow(() => E.zipPreflight(bytes));
  });
}

await check('Template preflight rejects invalid ZIP and inflated XML declarations', async () => {
  assert.throws(() => E.zipPreflight(new Uint8Array([1, 2, 3])), /PPTX/);
  const zip = new globalThis.JSZip(); zip.file('ppt/presentation.xml', '<p/>');
  const bytes = await zip.generateAsync({ type: 'uint8array' });
  assert.doesNotThrow(() => E.zipPreflight(bytes));
  const bad = bytes.slice(), view = new DataView(bad.buffer);
  for (let i = 0; i < bad.length - 46; i++) if (view.getUint32(i, true) === 0x02014b50) {
    const nameLength = view.getUint16(i + 28, true);
    const name = new TextDecoder().decode(bad.subarray(i + 46, i + 46 + nameLength));
    if (name.endsWith('.xml')) { view.setUint32(i + 24, 3 * 1024 * 1024, true); break; }
  }
  assert.throws(() => E.zipPreflight(bad), /XML/);
});

process.stdout.write('\n' + checks + ' regression checks passed. Browser rendering and template DOM parsing require browser verification.\n');
