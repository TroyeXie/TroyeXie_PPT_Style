/* Editable PPTX export and bounded, local theme-parameter import. */
(function (root) {
  'use strict';
  const C = root.CampusPPT;
  const EMU = 914400;
  const mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
  const hex = c => c.replace('#', '');

  function geometry(project) {
    const t = project.theme, scale = Math.min(t.width / 13.333333, t.height / 7.5);
    const sx = t.width / 13.333333, sy = t.height / 7.5;
    const left = t.nav === 'left' ? 1.91 * sx : .69 * sx;
    return { width: t.width, height: t.height, sx, sy, scale, left, right: t.width - .65 * sx,
      titleY: (t.nav === 'top' ? .96 : .43) * sy, contentY: (t.nav === 'top' ? 2.0 : 1.53) * sy,
      contentBottom: t.height - 1.0 * sy, footerY: t.height - .66 * sy,
      fontSize: { title: 28 * scale, body: 20 * scale, subtitle: 16 * scale, nav: 12 * scale, citation: 9 * scale, caption: 13 * scale, cover: 37 * scale } };
  }
  function line(pptx, slide, x1, y1, x2, y2, color, width) {
    slide.addShape(pptx.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color, width: width || .75 } });
  }
  function baseText(project, extra) {
    return { fontFace: project.theme.font, color: hex(project.theme.text), margin: 0, breakLine: false,
      lang: 'zh-CN', valign: 'top', fit: 'none', ...extra };
  }
  function putText(slide, project, text, x, y, w, h, size, extra) {
    slide.addText(text || '', baseText(project, { x, y, w, h, fontSize: size, ...extra }));
  }
  function putBody(slide, project, lines, x, y, w, h, size, objectName) {
    if (!lines || !lines.length) return;
    const runs = lines.map((text, i) => ({ text, options: { bullet: { indent: size * .76 },
      hanging: size * .18, breakLine: i < lines.length - 1, paraSpaceAfterPt: size * .8 } }));
    putText(slide, project, runs, x, y, w, h, size, { paraSpaceAfterPt: size * .7, lineSpacingMultiple: 1.15, objectName });
  }
  function drawNavigation(pptx, slide, project, model, g, sections) {
    const t = project.theme;
    if (t.nav === 'none' || model.type === 'cover') return;
    if (t.nav === 'top') {
      const gap = .22 * g.sx, navW = g.right - g.left, each = (navW - (sections.length - 1) * gap) / Math.max(1, sections.length);
      sections.forEach((section, i) => {
        const current = section === model.section, x = g.left + i * (each + gap);
        putText(slide, project, section, x, .27 * g.sy, each, .26 * g.sy, g.fontSize.nav, {
          color: current ? hex(t.accent) : '6F7C8C', bold: current, align: 'center', objectName: 'Navigation ' + (i + 1) });
        if (current) line(pptx, slide, x, .68 * g.sy, x + each, .68 * g.sy, hex(t.accent), 2);
      });
      line(pptx, slide, g.left, .72 * g.sy, g.right, .72 * g.sy, 'DEE4EC', .5);
    } else {
      line(pptx, slide, 1.49 * g.sx, .43 * g.sy, 1.49 * g.sx, g.height - .49 * g.sy, 'D8E0E9', .65);
      const step = Math.min(.93 * g.sy, 4.7 * g.sy / Math.max(1, sections.length));
      const y0 = (g.height - sections.length * step) / 2;
      sections.forEach((section, i) => {
        const current = section === model.section;
        putText(slide, project, section, .15 * g.sx, y0 + i * step, 1.2 * g.sx, .58 * g.sy, g.fontSize.nav,
          { color: current ? hex(t.accent) : '768396', bold: current, align: 'center', valign: 'mid', objectName: 'Navigation ' + (i + 1) });
        if (current) line(pptx, slide, .29 * g.sx, y0 + i * step + .63 * g.sy, 1.18 * g.sx, y0 + i * step + .63 * g.sy, hex(t.accent), 2);
      });
    }
  }
  function citationRuns(citations, project) {
    const runs = [];
    citations.forEach((c, i) => {
      const prefix = c.kind === 'data' ? '数据来源：' : c.kind === 'official' ? '官方来源：' : c.kind === 'synthetic' ? '教学示例：' : '';
      if (prefix) runs.push({ text: prefix, options: { color: hex(project.theme.accent), bold: c.kind !== 'synthetic' } });
      if (c.title) runs.push({ text: c.title + (c.venue ? ' | ' : ''), options: {} });
      if (c.venue) {
        const options = { bold: true, underline: { style: 'none' }, color: hex(project.theme.accent) };
        if (C.safeUrl(c.url)) options.hyperlink = { url: C.safeUrl(c.url), tooltip: c.venue };
        runs.push({ text: c.venue, options });
      }
      const suffix = [c.year ? ', ' + c.year : '', c.status ? ' ' + c.status : '', (c.year || c.venue || c.title) ? '.' : ''].join('');
      runs.push({ text: suffix, options: { breakLine: i < citations.length - 1 } });
    });
    return runs;
  }
  function citationHeight(model, g) {
    if (!model.citations.length) return .35 * g.sy;
    const capacity = (g.right - g.left - .7 * g.sx) * 72 / g.fontSize.citation;
    const lines = model.citations.reduce((n, c) => n + Math.max(1, Math.ceil((c.title.length + c.venue.length + c.year.length + c.status.length + 10) / capacity)), 0);
    return Math.max(.35 * g.sy, Math.min(1.55 * g.sy, lines * g.fontSize.citation * 1.3 / 72));
  }
  function drawFooter(pptx, slide, project, model, g, index, total) {
    const footerHeight = citationHeight(model, g);
    const bottom = g.height - .26 * g.sy;
    if (model.citations.length) {
      putText(slide, project, citationRuns(model.citations, project), g.left, bottom - footerHeight,
        g.right - g.left - .7 * g.sx, footerHeight, g.fontSize.citation, { valign: 'bottom', objectName: 'ReferenceFooter',
          paraSpaceAfterPt: 1.5 * g.scale, lineSpacingMultiple: 1.05 });
    }
    putText(slide, project, String(index + 1).padStart(2, '0') + ' / ' + String(total).padStart(2, '0'),
      g.right - .65 * g.sx, bottom - .24 * g.sy, .65 * g.sx, .22 * g.sy, 9 * g.scale,
      { align: 'right', color: '738196', objectName: 'PageNumber' });
  }
  function fitImage(width, height, box) {
    const factor = Math.min(box.w / width, box.h / height);
    const w = width * factor, h = height * factor;
    return { x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h };
  }
  async function imageDimensions(image) {
    if (!C.isSafeImageDataUrl(image.dataUrl)) throw new Error('图片格式无效，导出仅支持本地 PNG/JPEG。');
    if (typeof root.Image === 'function') {
      return new Promise((resolve, reject) => {
        const img = new root.Image();
        img.onload = () => img.naturalWidth > 0 && img.naturalHeight > 0
          ? resolve({ width: img.naturalWidth, height: img.naturalHeight }) : reject(new Error('图片尺寸无效。'));
        img.onerror = () => reject(new Error('图片无法解码，请重新选择 PNG/JPEG。'));
        img.src = image.dataUrl;
      });
    }
    // Node-only checks use explicitly supplied dimensions; browser export always decodes pixels.
    if (image.width > 0 && image.height > 0) return { width: image.width, height: image.height };
    throw new Error('图片缺少尺寸信息。');
  }

  async function exportPptx(raw) {
    if (typeof root.PptxGenJS !== 'function') throw new Error('离线导出组件未加载，请保留 vendor 文件夹后重新打开。');
    const review = C.validateProject(raw);
    if (review.errors.length) throw new Error(review.errors.map(e => e.message).join('\n'));
    const project = C.normalizeProject(raw), pptx = new root.PptxGenJS(), g = geometry(project);
    const sections = [...new Set(project.slides.filter(s => s.type !== 'cover' && s.section).map(s => s.section))];
    pptx.defineLayout({ name: 'CAMPUS', width: g.width, height: g.height });
    pptx.layout = 'CAMPUS';
    pptx.author = project.presenter || '求是·汇报用户'; pptx.subject = C.sceneTemplates[project.scene].label;
    pptx.title = project.title; pptx.company = '求是·汇报'; pptx.lang = 'zh-CN';
    pptx.theme = { headFontFace: project.theme.font, bodyFontFace: project.theme.font, lang: 'zh-CN' };
    for (let i = 0; i < project.slides.length; i++) {
      const model = project.slides[i], slide = pptx.addSlide();
      slide.background = { color: hex(project.theme.background) };
      drawNavigation(pptx, slide, project, model, g, sections);
      const footerHeight = citationHeight(model, g), bottom = Math.min(g.contentBottom, g.height - footerHeight - .47 * g.sy);
      const contentW = g.right - g.left;
      if (model.type === 'cover') {
        const coverLeft = .95 * g.sx;
        putText(slide, project, C.sceneTemplates[project.scene].label, coverLeft, 1.20 * g.sy, g.width - 2 * coverLeft,
          .4 * g.sy, 14 * g.scale, { color: hex(project.theme.accent), objectName: 'CoverScene' });
        putText(slide, project, model.title || project.title, coverLeft, 2.1 * g.sy, g.width - 2 * coverLeft,
          1.53 * g.sy, g.fontSize.cover, { bold: true, color: hex(project.theme.accent), objectName: 'CoverTitle' });
        putText(slide, project, model.subtitle || project.subtitle, coverLeft, 3.88 * g.sy, g.width - 2 * coverLeft,
          .8 * g.sy, 19 * g.scale, { objectName: 'CoverSubtitle' });
        line(pptx, slide, coverLeft, 5.12 * g.sy, g.width - coverLeft, 5.12 * g.sy, 'C5D0DE', .8);
        putText(slide, project, project.presenter, coverLeft, 5.6 * g.sy, g.width - 2 * coverLeft,
          .4 * g.sy, 16 * g.scale, { color: '5E6D7F', objectName: 'Presenter' });
      } else if (model.type === 'section') {
        const n = Math.max(1, sections.indexOf(model.section) + 1);
        putText(slide, project, String(n).padStart(2, '0'), g.left, 2.15 * g.sy, 1.1 * g.sx, .75 * g.sy,
          35 * g.scale, { color: hex(project.theme.secondary), objectName: 'SectionNumber' });
        putText(slide, project, model.title, g.left + 1.35 * g.sx, 2.16 * g.sy, contentW - 1.35 * g.sx,
          1.1 * g.sy, 32 * g.scale, { color: hex(project.theme.accent), bold: true, objectName: 'SectionTitle' });
        putText(slide, project, model.subtitle, g.left + 1.35 * g.sx, 3.53 * g.sy, contentW - 1.35 * g.sx,
          1.0 * g.sy, 20 * g.scale, { objectName: 'SectionSubtitle' });
        if (model.body.length) putBody(slide, project, model.body, g.left + 1.35 * g.sx, 4.63 * g.sy,
          contentW - 1.35 * g.sx, bottom - 4.63 * g.sy, 18 * g.scale, 'SectionBody');
      } else {
        putText(slide, project, model.title, g.left, g.titleY, contentW, .68 * g.sy,
          g.fontSize.title, { color: hex(project.theme.accent), bold: true, objectName: 'SlideTitle' });
        line(pptx, slide, g.left, g.titleY + .79 * g.sy, g.right, g.titleY + .79 * g.sy, 'D8E1EC', .7);
        let y = g.contentY;
        if (model.subtitle) {
          putText(slide, project, model.subtitle, g.left, y, contentW, .46 * g.sy, g.fontSize.subtitle, { color: '68778A', objectName: 'Subtitle' });
          y += .64 * g.sy;
        }
        if (model.evidence) {
          putText(slide, project, C.evidenceLabels[model.evidence], g.left, y, contentW, .28 * g.sy, 11 * g.scale,
            { color: hex(project.theme.accent), objectName: 'EvidenceStatus' }); y += .44 * g.sy;
        }
        if (model.type === 'comparison') {
          const gap = .57 * g.sx, colW = (contentW - gap) / 2;
          if (model.body.length) {
            putBody(slide, project, model.body, g.left, y, contentW, .7 * g.sy, g.fontSize.subtitle, 'ComparisonIntro'); y += .83 * g.sy;
          }
          const columns = model.columns.length ? model.columns : [{ title: '左侧栏目', body: [] }, { title: '右侧栏目', body: [] }];
          columns.forEach((c, idx) => {
            const x = g.left + idx * (colW + gap);
            putText(slide, project, c.title, x, y, colW, .57 * g.sy, 22 * g.scale,
              { bold: true, color: hex(project.theme.accent), objectName: 'ColumnTitle ' + (idx + 1) });
            line(pptx, slide, x, y + .72 * g.sy, x + colW, y + .72 * g.sy, 'D5DFE9', .65);
            putBody(slide, project, c.body, x, y + 1.0 * g.sy, colW, Math.max(.3, bottom - y - 1.0 * g.sy),
              g.fontSize.body, 'ColumnBody ' + (idx + 1));
          });
        } else if (model.type === 'figure') {
          const hasBody = model.body.length > 0, figW = hasBody ? contentW * .61 : contentW;
          const captionH = model.caption ? .85 * g.sy : 0;
          const box = { x: g.left, y, w: figW, h: Math.max(.4, bottom - y - captionH) };
          if (model.image) {
            const dimensions = await imageDimensions(model.image);
            slide.addImage({ data: model.image.dataUrl, ...fitImage(dimensions.width, dimensions.height, box),
              altText: model.image.alt || model.caption || '汇报图像', objectName: 'EvidenceFigure' });
          } else {
            putText(slide, project, '添加本页图像', box.x, box.y + box.h / 2 - .4 * g.sy, box.w, .45 * g.sy,
              20 * g.scale, { align: 'center', color: '6D7E94', objectName: 'ImagePlaceholder' });
            putText(slide, project, '在应用中选择 PNG 或 JPEG', box.x, box.y + box.h / 2 + .12 * g.sy, box.w, .4 * g.sy,
              12 * g.scale, { align: 'center', color: '6D7E94', objectName: 'ImagePlaceholderHint' });
          }
          if (model.caption) putText(slide, project, model.caption, box.x, bottom - captionH + .11 * g.sy, box.w,
            captionH - .11 * g.sy, g.fontSize.caption, { align: 'center', objectName: 'FigureCaption' });
          if (hasBody) putBody(slide, project, model.body, g.left + figW + .43 * g.sx, y + .15 * g.sy,
            contentW - figW - .43 * g.sx, bottom - y - .15 * g.sy, 18 * g.scale, 'FigureExplanation');
        } else {
          putBody(slide, project, model.body, g.left, y + .12 * g.sy, contentW, Math.max(.4, bottom - y - .12 * g.sy),
            g.fontSize.body, 'BodyText');
        }
      }
      drawFooter(pptx, slide, project, model, g, i, project.slides.length);
      const sources = model.citations.map(c => [c.kind === 'synthetic' ? '合成教学材料' : '来源', c.title, c.venue, c.year, c.status, c.url].filter(Boolean).join('；'));
      slide.addNotes([model.notes, sources.length ? '\n来源记录：\n' + sources.join('\n') : ''].filter(Boolean).join('\n'));
    }
    const result = await pptx.write({ outputType: 'blob', compression: true });
    return result instanceof Blob ? result : new Blob([result], { type: mime });
  }

  function zipPreflight(buffer) {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
    if (!bytes.length || bytes.length > C.limits.templateBytes) throw new Error('模板须小于 25 MB。');
    const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), min = Math.max(0, bytes.length - 65557);
    let eocd = -1;
    for (let p = bytes.length - 22; p >= min; p--) if (v.getUint32(p, true) === 0x06054b50 && p + 22 + v.getUint16(p + 20, true) === bytes.length) { eocd = p; break; }
    if (eocd < 0) throw new Error('文件不是可识别的 PPTX 压缩包。');
    const count = v.getUint16(eocd + 10, true), size = v.getUint32(eocd + 12, true), offset = v.getUint32(eocd + 16, true);
    if (count === 65535 || offset === 0xffffffff || size === 0xffffffff) throw new Error('当前原型不支持 ZIP64 模板。');
    if (v.getUint16(eocd + 4, true) || v.getUint16(eocd + 6, true) || count !== v.getUint16(eocd + 8, true)) throw new Error('不支持分卷压缩的模板。');
    if (!count || count > 4000 || offset + size > eocd) throw new Error('模板内部结构过大或损坏。');
    let p = offset, total = 0; const names = new Set();
    for (let i = 0; i < count; i++) {
      if (p + 46 > bytes.length || v.getUint32(p, true) !== 0x02014b50) throw new Error('模板目录损坏。');
      const compressed = v.getUint32(p + 20, true), expanded = v.getUint32(p + 24, true), nameLength = v.getUint16(p + 28, true);
      const extraLength = v.getUint16(p + 30, true), commentLength = v.getUint16(p + 32, true), flags = v.getUint16(p + 8, true), method = v.getUint16(p + 10, true);
      if (p + 46 + nameLength + extraLength + commentLength > offset + size) throw new Error('模板目录范围无效。');
      const name = new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(p + 46, p + 46 + nameLength));
      if (flags & 1 || ![0, 8].includes(method)) throw new Error('不支持加密或特殊压缩方式的模板。');
      if (name.includes('\\') || name.startsWith('/') || name.split('/').includes('..') || name.includes('\0') || names.has(name)) throw new Error('模板包含不安全或重复的内部文件名。');
      names.add(name); total += expanded;
      if (compressed === 0xffffffff || expanded === 0xffffffff || total > 200 * 1024 * 1024) throw new Error('模板解压尺寸过大。');
      if (/\.(xml|rels)$/i.test(name) && (expanded > 2 * 1024 * 1024 || expanded > Math.max(1, compressed) * 400)) throw new Error('模板 XML 结构过大，请使用精简模板。');
      p += 46 + nameLength + extraLength + commentLength;
    }
    return bytes;
  }
  function readBounded(entry) {
    return new Promise((resolve, reject) => {
      const chunks = []; let total = 0, failed = false;
      const stream = entry.internalStream('uint8array');
      stream.on('data', chunk => {
        if (failed) return; total += chunk.length;
        if (total > 2 * 1024 * 1024) { failed = true; stream.pause(); reject(new Error('模板 XML 解压超过安全大小。')); return; }
        chunks.push(chunk);
      }).on('error', err => { if (!failed) reject(err); }).on('end', () => {
        if (failed) return; const all = new Uint8Array(total); let offset = 0;
        chunks.forEach(c => { all.set(c, offset); offset += c.length; });
        try { resolve(new TextDecoder('utf-8', { fatal: true }).decode(all)); } catch (_) { reject(new Error('模板 XML 编码无效。')); }
      }).resume();
    });
  }
  async function xmlPart(zip, path, optional) {
    const entry = zip.file(path);
    if (!entry) { if (optional) return null; throw new Error('模板缺少必要结构：' + path); }
    const text = await readBounded(entry);
    if (/<!DOCTYPE|<!ENTITY/i.test(text)) throw new Error('模板包含不支持的 XML 实体声明。');
    const doc = new root.DOMParser().parseFromString(text, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length || doc.documentElement.localName === 'parsererror') throw new Error('模板 XML 无法解析。');
    return doc;
  }
  function node(parent, local) { return parent && parent.getElementsByTagNameNS('*', local)[0] || null; }
  function resolvePart(base, target) {
    if (!target || /[\\:\u0000]/.test(target) || target.startsWith('/')) throw new Error('模板关系指向不支持的路径。');
    const bits = base.split('/').slice(0, -1);
    target.split('/').forEach(b => { if (b === '..') { if (!bits.length) throw new Error('模板关系超出包内范围。'); bits.pop(); } else if (b !== '.' && b) bits.push(b); });
    return bits.join('/');
  }
  async function readTemplate(arrayBuffer, fileName) {
    if (typeof root.JSZip !== 'function' || typeof root.DOMParser !== 'function') throw new Error('模板读取组件未加载。');
    if (fileName && !/\.pptx$/i.test(fileName)) throw new Error('请选择 .pptx 格式模板。');
    const bytes = zipPreflight(arrayBuffer), zip = await root.JSZip.loadAsync(bytes);
    if (Object.keys(zip.files).some(x => /vbaproject\.bin$/i.test(x))) throw new Error('请使用不包含宏的 PPTX 模板。');
    const presentation = await xmlPart(zip, 'ppt/presentation.xml'), rels = await xmlPart(zip, 'ppt/_rels/presentation.xml.rels');
    const size = node(presentation, 'sldSz');
    if (!size) throw new Error('模板未定义页面尺寸。');
    const width = Number(size.getAttribute('cx')) / EMU, height = Number(size.getAttribute('cy')) / EMU;
    if (!Number.isFinite(width) || !Number.isFinite(height) || width < 6 || width > 20 || height < 4 || height > 15) throw new Error('当前原型支持宽 6–20 英寸、高 4–15 英寸的幻灯片。');
    const warnings = ['本版读取主题字体、主题色和页面尺寸。母版布局、校标、背景图、占位符及动画需后续适配。'];
    const masterId = node(presentation, 'sldMasterId');
    const rid = masterId && (masterId.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id') || masterId.getAttribute('r:id'));
    const masterRel = Array.from(rels.getElementsByTagNameNS('*', 'Relationship')).find(r => r.getAttribute('Id') === rid && r.getAttribute('TargetMode') !== 'External');
    let themePath;
    if (masterRel) {
      const master = resolvePart('ppt/presentation.xml', masterRel.getAttribute('Target'));
      const parts = master.split('/'), base = parts.pop();
      const mr = await xmlPart(zip, parts.join('/') + '/_rels/' + base + '.rels', true);
      const tr = mr && Array.from(mr.getElementsByTagNameNS('*', 'Relationship')).find(r => /\/theme$/.test(r.getAttribute('Type') || '') && r.getAttribute('TargetMode') !== 'External');
      if (tr) themePath = resolvePart(master, tr.getAttribute('Target'));
    }
    if (!themePath) {
      themePath = Object.keys(zip.files).filter(x => /^ppt\/theme\/[^/]+\.xml$/.test(x)).sort()[0];
      warnings.push('未能关联首个母版，改取包内首个主题。请核对提取结果。');
    }
    if (!themePath) throw new Error('模板没有可读取的主题。');
    const theme = await xmlPart(zip, themePath), scheme = node(theme, 'clrScheme'), fonts = node(theme, 'fontScheme');
    function colorAt(name, fallback) {
      const parent = node(scheme, name), srgb = node(parent, 'srgbClr'), sys = node(parent, 'sysClr');
      const value = srgb && srgb.getAttribute('val') || sys && sys.getAttribute('lastClr');
      return /^[0-9a-fA-F]{6}$/.test(value || '') ? '#' + value.toUpperCase() : fallback;
    }
    const minor = node(fonts, 'minorFont'), major = node(fonts, 'majorFont');
    function fontAt(fontRoot) {
      if (!fontRoot) return '';
      const hans = Array.from(fontRoot.getElementsByTagNameNS('*', 'font')).find(n => n.getAttribute('script') === 'Hans');
      const ea = node(fontRoot, 'ea'), latin = node(fontRoot, 'latin');
      return hans && hans.getAttribute('typeface') || ea && ea.getAttribute('typeface') || latin && latin.getAttribute('typeface') || '';
    }
    const font = fontAt(minor) || fontAt(major) || '华文楷体';
    if (font.length > 100 || /[<>"'&\u0000-\u001F]/.test(font)) throw new Error('模板字体名称无效。');
    if (Object.keys(zip.files).filter(x => /^ppt\/theme\/[^/]+\.xml$/.test(x)).length > 1) warnings.push('模板含多个主题，本次只读取首个母版对应主题。');
    warnings.push('读取字体名称不代表设备已安装该字体，实际显示与导出需在本机核对。');
    return { fileName: String(fileName || 'template.pptx').replace(/[\u0000-\u001F]/g, ''), scope: 'style-parameters',
      theme: { font, accent: colorAt('accent1', '#074591'), secondary: colorAt('accent2', '#8C9CAD'), width, height }, warnings };
  }
  root.CampusPPTExport = { exportPptx, readTemplate, geometry, fitImage, citationRuns, zipPreflight };
})(typeof window !== 'undefined' ? window : globalThis);
