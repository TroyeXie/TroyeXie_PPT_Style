(function () {
  'use strict';
  const Core = window.CampusPPT;
  const Export = window.CampusPPTExport;
  const STORAGE_KEY = 'qiushi-presentation-project-v1';
  const typeNames = {cover:'封面',section:'章节页',bullets:'要点页',comparison:'双栏对照',figure:'图文页'};
  const evidenceNames = {teaching:'教学内容',literature:'文献结果',analysis:'本项目分析',hypothesis:'待检验假说',plan:'后续计划'};
  const sourceKinds = {paper:'论文',data:'数据来源',official:'官方材料',synthetic:'教学示例'};
  const iconPaths = {
    download:'M8 2v8m-3-3 3 3 3-3M3 11v3h10v-3',
    spark:'m8 1 1.6 4.8L14 8l-4.4 1.6L8 15l-1.6-5.4L2 8l4.4-2.2L8 1Z',
    plus:'M8 3v10M3 8h10',
    upload:'M8 11V2M4 6l4-4 4 4M2 11v3h12v-3',
    close:'m3 3 10 10M13 3 3 13',
    copy:'M6 2h8v9H6zM3 5H2v9h9v-1',
    undo:'M5 3 2 6l3 3M2 6h7a4 4 0 0 1 0 8',
    arrowUp:'M8 13V3m-4 4 4-4 4 4',
    arrowDown:'M8 3v10m-4-4 4 4 4-4',
    file:'M3 1h6l4 4v10H3V1Zm6 0v4h4M5 8h6M5 11h4',
    check:'m3 8 3 3 7-7',
    trash:'M2 4h12M5 4V2h6v2M4 4l1 10h6l1-10M7 7v4M9 7v4',
    image:'M2 2h12v12H2V2Zm0 10 4-5 3 4 2-2 3 3M10 5h.01'
  };
  function icon(name) { return '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true"><path d="'+(iconPaths[name]||iconPaths.file)+'"/></svg>'; }
  const h = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clone = value => JSON.parse(JSON.stringify(value));
  function validColor(v, fallback) { return /^#[0-9a-f]{6}$/i.test(v||'') ? v : fallback; }
  function cleanFont(v) { return String(v||'华文楷体').replace(/[;{}<>"'\\]/g,''); }
  let savedProject = null;
  let saveState = '演示工作区';
  try { const raw = localStorage.getItem(STORAGE_KEY); if(raw){ savedProject = Core.normalizeProject(JSON.parse(raw)); saveState='已恢复上次编辑'; } } catch (_) { saveState='已载入示例'; }
  let project = savedProject || Core.createDemo('lab');
  let selected = 0, leftTab = 'style', editTab = 'text', outlineDraft = '', templateResult = null, toastTimer, exporting = false;
  const history = [];
  let modalOpen = false;
  function currentSlide() { return project.slides[selected]; }
  function remember() { history.push(clone(project)); if(history.length>25)history.shift(); }
  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(project)); saveState='已保存至当前浏览器'; }
    catch(_) { saveState='存储空间不足，请保存项目'; }
    const e=document.getElementById('save-state'); if(e)e.textContent=saveState;
  }
  function toast(message) { const t=document.getElementById('toast');t.textContent=message;t.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('visible'),5000); }
  function mutate(callback, light) { remember();callback();persist();if(light){renderPreview();renderList();renderStats();const undo=document.querySelector('[data-action="undo"]');if(undo)undo.disabled=false;if(leftTab==='check')renderSettings();}else renderAll(); }
  function selectSlide(index) { selected=Math.max(0,Math.min(index,project.slides.length-1));renderPreview();renderList();renderEditor(); }
  function options(values,current) { return Object.entries(values).map(([value,label])=>'<option value="'+h(value)+'"'+(value===current?' selected':'')+'>'+h(label)+'</option>').join(''); }
  function field(label,content,hint) { return '<label class="field"><span class="field-label">'+label+'</span>'+content+(hint?'<p class="hint">'+hint+'</p>':'')+'</label>'; }
  function inp(key,value,type='text',attributes='') { return '<input data-project="'+key+'" type="'+type+'" value="'+h(value)+'" '+attributes+'>'; }
  function slideInp(key,value,tag='input',attributes='') { return tag==='textarea'?'<textarea data-slide="'+key+'" '+attributes+'>'+h(value)+'</textarea>':'<input data-slide="'+key+'" value="'+h(value)+'" '+attributes+'>'; }
  function renderAll() {
    document.getElementById('app').innerHTML = `
      <header class="topbar">
        <div class="brand"><div class="brand-mark" aria-hidden="true">汇</div><div><div class="brand-title">求是·汇报</div><div class="brand-sub">CAMPUS PRESENTATION STUDIO</div></div></div>
        <nav class="toplinks" aria-label="工作区导航"><button class="text-button current" data-action="workbench">汇报工作台</button><button class="text-button" data-action="guide">使用指南</button><button class="text-button" data-action="roadmap">参赛推进</button></nav>
        <div class="top-actions"><button class="button" data-action="ai">${icon('spark')}AI 协作</button><button class="button primary" data-action="export" ${exporting?'disabled':''}>${icon('download')}${exporting?'正在导出…':'导出 PPTX'}</button></div>
      </header>
      <div class="workspace-heading"><div><div class="eyebrow">YOUR IDEAS, WELL PRESENTED</div><h1>把材料，整理成一次清楚的汇报</h1><p>选择汇报场景，调整整套风格，在每一页保留内容的依据。</p></div><div class="session-label"><span class="dot"></span><span id="save-state">${h(saveState)}</span><span class="pill-label">原型 v0.1</span></div></div>
      <main class="workspace">
        <aside class="left-column panel" aria-label="汇报设置"><div class="left-tabs" role="tablist"><button role="tab" aria-selected="${leftTab==='content'}" class="${leftTab==='content'?'active':''}" data-tab="content">01 内容</button><button role="tab" aria-selected="${leftTab==='style'}" class="${leftTab==='style'?'active':''}" data-tab="style">02 样式</button><button role="tab" aria-selected="${leftTab==='check'}" class="${leftTab==='check'?'active':''}" data-tab="check">03 自检</button></div><div id="settings-content" class="settings"></div></aside>
        <section class="center-column" aria-label="演示文稿预览"><div class="preview-toolbar"><h2>页面预览 <span id="page-indicator"></span></h2><div class="preview-actions"><button class="button small" data-action="undo" title="撤销上一次修改" ${history.length?'':'disabled'}>${icon('undo')}撤销</button><button class="button small" data-action="save-project">${icon('file')}保存项目</button></div></div><div class="preview-stage"><div id="preview" class="slide-shell"></div></div><div class="preview-caption"><span>文字可编辑 · 图片按比例显示</span><span>字体显示取决于当前电脑</span></div><div id="stats" class="stats"></div><div class="slide-list-header"><h3>汇报页面</h3><div class="preview-actions"><button class="button small" data-action="move-up" title="上移当前页" aria-label="上移当前页">${icon('arrowUp')}</button><button class="button small" data-action="move-down" title="下移当前页" aria-label="下移当前页">${icon('arrowDown')}</button><button class="button small" data-action="add-slide">${icon('plus')}添加页面</button></div></div><div id="slide-list" class="slide-list"></div><p class="demo-warning">内置内容为教学演示示例。可导入自己的提纲、图片和来源，也可通过 AI 协作生成内容初稿。</p></section>
        <aside class="right-column" aria-label="当前页编辑"><div class="panel"><div class="panel-header"><span>编辑当前页</span><button class="text-button" data-action="delete-slide" aria-label="删除当前页" title="删除当前页">${icon('trash')}</button></div><div class="edit-tabs" role="tablist"><button role="tab" aria-selected="${editTab==='text'}" class="${editTab==='text'?'active':''}" data-edit-tab="text">内容</button><button role="tab" aria-selected="${editTab==='sources'}" class="${editTab==='sources'?'active':''}" data-edit-tab="sources">来源</button><button role="tab" aria-selected="${editTab==='notes'}" class="${editTab==='notes'?'active':''}" data-edit-tab="notes">讲稿</button></div><div class="settings" id="slide-editor"></div><div class="editor-note">修改仅作用于当前页。章节、页码和导航根据页面顺序更新。</div></div></aside>
      </main>
      <footer class="project-footer"><span>由 TroyeXie_PPT_Style 制作规范发展而来 · 学生作品原型</span><span><button class="text-button" data-action="guide">帮助</button>　<a href="https://github.com/TroyeXie/TroyeXie_PPT_Style" target="_blank" rel="noopener noreferrer">项目仓库 ↗</a></span></footer>`;
    renderSettings();renderPreview();renderStats();renderList();renderEditor();
  }
  function renderSettings() {
    const box=document.getElementById('settings-content');
    if(leftTab==='content'){
      const scenes=Object.fromEntries(Object.entries(Core.sceneTemplates).map(([k,v])=>[k,v.label||v.name||k]));
      box.innerHTML = '<div class="section-label"><span>01</span> 这次要讲什么</div>'+field('汇报场景','<select data-project="scene">'+options(scenes,project.scene)+'</select>')+field('汇报名称',inp('title',project.title))+field('汇报人',inp('presenter',project.presenter)) + field('预计汇报时长（分钟）',inp('duration',project.duration,'number','min="1" max="120" step="1"'))+'<button class="button full" data-action="load-demo">载入该场景示例</button><p class="hint">示例将替换当前内容，可用“撤销”恢复。</p><hr><div class="section-label"><span>02</span> 导入已有材料</div>'+field('粘贴分节提纲','<textarea id="outline-draft" rows="7" placeholder="# 汇报题目\n## 研究问题\n- 第一条要点\n- 第二条要点">'+h(outlineDraft)+'</textarea>','使用 # 题名、## 页标题、- 要点。提纲排版不会自动补写事实。')+'<button class="button primary full" data-action="apply-outline">将提纲排成页面</button><button class="button full" data-action="import-project" style="margin-top:9px">'+icon('upload')+'导入 TXT / MD / 项目 JSON</button><hr><p class="quiet-note">材料在当前浏览器处理。生成内容初稿可使用右上角“AI 协作”，复制任务包到你正在使用的助手。</p>';
    }else if(leftTab==='style'){
      const paletteButtons=Core.palettes.map(p=>'<button class="palette-option '+(project.theme.palette===p.id?'active':'')+'" data-palette="'+h(p.id)+'"><span class="swatch" style="background:'+validColor(p.accent,'#074591')+'"></span>'+h(p.label||p.name)+'</button>').join('');
      box.innerHTML = '<div class="section-label"><span>01</span> 模板与字体</div><div class="template-zone">'+icon('upload')+'<strong>使用自己的 PPT 模板</strong><p>提取主题字体、配色与页面尺寸<br>应用于本工作台的标准版式</p><button class="button small" data-action="import-template">选择 PPTX 模板</button></div>'+(templateResult?'<div class="template-result"><strong>'+h(templateResult.fileName)+'</strong>已应用样式参数。母版、校标和动画未迁入。</div>':'')+'<div style="margin-top:17px">'+field('正文与标题字体','<select data-theme="font">'+options({'华文楷体':'华文楷体','STKaiti':'STKaiti','楷体':'楷体','微软雅黑':'微软雅黑','宋体':'宋体',...(project.theme.font && !['华文楷体','STKaiti','楷体','微软雅黑','宋体'].includes(project.theme.font)?{[project.theme.font]:project.theme.font}:{})},project.theme.font)+'</select>','电脑需安装所选字体；原始图片中的字形保持不变。')+'</div>'+field('页面比例','<select id="aspect-ratio">'+options({'wide':'16:9 宽屏','standard':'4:3 标准','custom':'来自导入模板'},Math.abs(project.theme.width/project.theme.height-16/9)<.02?'wide':Math.abs(project.theme.width/project.theme.height-4/3)<.02?'standard':'custom')+'</select>')+'<hr><div class="section-label"><span>02</span> 全稿主题色</div><div class="palette-grid">'+paletteButtons+'</div><label class="custom-color">自定主色<input type="color" id="custom-color" value="'+validColor(project.theme.accent,'#074591')+'"><code>'+h(project.theme.accent.toUpperCase())+'</code></label><hr><div class="section-label"><span>03</span> 章节导航</div><div class="nav-options">'+[['top','顶部横排'],['left','左侧竖排'],['none','无导航']].map(([v,l])=>'<button class="nav-option '+(project.theme.nav===v?'active':'')+'" data-nav="'+v+'"><div class="nav-sketch '+v+'" aria-hidden="true"></div>'+l+'</button>').join('')+'</div><p class="hint">导航取自当前页面的章节。调整顺序后，当前章节与页码同步更新。</p><hr><div class="quiet-note">样式应用于整份汇报。原图始终按比例放置，导出后仍可在 PowerPoint 中修改文字与图片。</div>';
    }else renderChecks(box);
  }
  function renderChecks(box) {
    const report=Core.validateProject(project);
    const errors=report.errors||[], warnings=report.warnings||[];
    const issues=[...errors.map(x=>({...x,level:'error'})),...warnings.map(x=>({...x,level:'warn'}))];
    box.innerHTML = '<div class="section-label">版式与材料自检</div><div class="checks-summary">'+(errors.length?'需要处理 '+errors.length+' 项错误。':'未发现已实现检查项的错误。')+'<br>'+warnings.length+' 项提醒可在导出前查看。</div>'+ (issues.length?issues.map(x=>'<div class="check-item"><span class="check-symbol '+x.level+'">!</span><div>'+h(x.message||String(x))+(x.slideId?'<br><button data-jump-id="'+h(x.slideId)+'">查看对应页面 →</button>':'')+'</div></div>').join(''):'<div class="check-item"><span class="check-symbol">✓</span><div>目前未发现需要提示的项目。</div></div>')+'<hr><div class="quiet-note">自检检查已实现的长度、来源字段、图片与时间等规则。来源与结论是否相符，以及 Office 中的实际字形和排版，需要人工确认。</div>';
  }
  function getSections(){return [...new Set(project.slides.filter(s=>s.type!=='cover').map(s=>s.section).filter(Boolean))];}
  function renderPreview() {
    const shell=document.getElementById('preview'); if(!shell)return;
    const slide=currentSlide();if(!slide){shell.innerHTML='';return;}
    const t=project.theme;const width=Number(t.width)||13.3333,height=Number(t.height)||7.5;
    shell.style.setProperty('--slide-ratio',width+' / '+height);
    shell.style.setProperty('--slide-accent',validColor(t.accent,'#074591'));
    shell.style.setProperty('--slide-bg',validColor(t.background,'#ffffff'));
    shell.style.setProperty('--slide-text',validColor(t.text,'#182333'));
    shell.style.setProperty('--slide-font','"'+cleanFont(t.font)+'", "STKaiti", "KaiTi", "Microsoft YaHei", serif');
    const g=Export.geometry(project),sections=getSections(),parts=[];
    function box(content,x,y,w,bh,size,extra='') { return '<div class="ppt-box" style="left:'+(x/width*100)+'%;top:'+(y/height*100)+'%;width:'+(w/width*100)+'%;height:'+(bh/height*100)+'%;font-size:'+(size/(width*72)*100)+'cqw;'+extra+'">'+content+'</div>'; }
    function text(value,x,y,w,bh,size,extra=''){return box(h(value),x,y,w,bh,size,extra);}
    function line(x1,y1,x2,y2,color,pt=.75){parts.push('<div class="ppt-line" style="left:'+(x1/width*100)+'%;top:'+(y1/height*100)+'%;width:'+Math.max(0,(x2-x1)/width*100)+'%;height:'+Math.max(0,(y2-y1)/height*100)+'%;'+(x1===x2?'border-left':'border-top')+':'+Math.max(.5,pt*.8)+'px solid '+color+'"></div>');}
    function bullets(body,x,y,w,bh,size){if(body?.length)parts.push(box('<ul>'+body.map(v=>'<li>'+h(v)+'</li>').join('')+'</ul>',x,y,w,bh,size));}
    const accent='color:'+validColor(t.accent,'#074591')+';',bold='font-weight:700;';
    if(t.nav!=='none'&&slide.type!=='cover'){
      if(t.nav==='top'){
        const gap=.22*g.sx,each=(g.right-g.left-(sections.length-1)*gap)/Math.max(1,sections.length);
        sections.forEach((s,i)=>{const x=g.left+i*(each+gap);parts.push(box('<button data-jump-section="'+h(s)+'">'+h(s)+'</button>',x,.27*g.sy,each,.26*g.sy,g.fontSize.nav,'text-align:center;'+(s===slide.section?accent+bold:'color:#6F7C8C;')));if(s===slide.section)line(x,.68*g.sy,x+each,.68*g.sy,t.accent,2);});
        line(g.left,.72*g.sy,g.right,.72*g.sy,'#DEE4EC',.5);
      }else{
        line(1.49*g.sx,.43*g.sy,1.49*g.sx,g.height-.49*g.sy,'#D8E0E9',.65);
        const step=Math.min(.93*g.sy,4.7*g.sy/Math.max(1,sections.length)),y0=(g.height-sections.length*step)/2;
        sections.forEach((s,i)=>{parts.push(box('<button data-jump-section="'+h(s)+'">'+h(s)+'</button>',.15*g.sx,y0+i*step,1.2*g.sx,.58*g.sy,g.fontSize.nav,'display:flex;align-items:center;justify-content:center;text-align:center;'+(s===slide.section?accent+bold:'color:#768396;')));if(s===slide.section)line(.29*g.sx,y0+i*step+.63*g.sy,1.18*g.sx,y0+i*step+.63*g.sy,t.accent,2);});
      }
    }
    const capacity=(g.right-g.left-.7*g.sx)*72/g.fontSize.citation;
    const nLines=(slide.citations||[]).reduce((n,c)=>n+Math.max(1,Math.ceil((c.title.length+c.venue.length+c.year.length+c.status.length+10)/capacity)),0);
    const footH=Math.max(.35*g.sy,Math.min(1.55*g.sy,nLines*g.fontSize.citation*1.3/72));
    const bottom=Math.min(g.contentBottom,g.height-footH-.47*g.sy),contentW=g.right-g.left;
    if(slide.type==='cover'){
      const x=.95*g.sx,w=width-2*x;
      parts.push(text(Core.sceneTemplates[project.scene]?.label||'校园汇报',x,1.20*g.sy,w,.4*g.sy,14*g.scale,accent));
      parts.push(text(slide.title||project.title,x,2.1*g.sy,w,1.53*g.sy,g.fontSize.cover,accent+bold));
      parts.push(text(slide.subtitle||project.subtitle,x,3.88*g.sy,w,.8*g.sy,19*g.scale));
      line(x,5.12*g.sy,width-x,5.12*g.sy,'#C5D0DE',.8);
      parts.push(text(project.presenter,x,5.6*g.sy,w,.4*g.sy,16*g.scale,'color:#5E6D7F;'));
    }else if(slide.type==='section'){
      parts.push(text(String(Math.max(1,sections.indexOf(slide.section)+1)).padStart(2,'0'),g.left,2.15*g.sy,1.1*g.sx,.75*g.sy,35*g.scale,'color:'+validColor(t.secondary,'#8C9CAD')+';'));
      parts.push(text(slide.title,g.left+1.35*g.sx,2.16*g.sy,contentW-1.35*g.sx,1.1*g.sy,32*g.scale,accent+bold));
      parts.push(text(slide.subtitle,g.left+1.35*g.sx,3.53*g.sy,contentW-1.35*g.sx,1*g.sy,20*g.scale));
      bullets(slide.body,g.left+1.35*g.sx,4.63*g.sy,contentW-1.35*g.sx,bottom-4.63*g.sy,18*g.scale);
    }else{
      parts.push(text(slide.title,g.left,g.titleY,contentW,.68*g.sy,g.fontSize.title,accent+bold));
      line(g.left,g.titleY+.79*g.sy,g.right,g.titleY+.79*g.sy,'#D8E1EC',.7);
      let y=g.contentY;
      if(slide.subtitle){parts.push(text(slide.subtitle,g.left,y,contentW,.46*g.sy,g.fontSize.subtitle,'color:#68778A;'));y+=.64*g.sy;}
      if(slide.evidence){parts.push(text(Core.evidenceLabels[slide.evidence]||evidenceNames[slide.evidence],g.left,y,contentW,.28*g.sy,11*g.scale,accent));y+=.44*g.sy;}
      if(slide.type==='comparison'){
        const gap=.57*g.sx,colW=(contentW-gap)/2;
        if(slide.body?.length){bullets(slide.body,g.left,y,contentW,.7*g.sy,g.fontSize.subtitle);y+=.83*g.sy;}
        (slide.columns||[]).slice(0,2).forEach((c,i)=>{const x=g.left+i*(colW+gap);parts.push(text(c.title,x,y,colW,.57*g.sy,22*g.scale,accent+bold));line(x,y+.72*g.sy,x+colW,y+.72*g.sy,'#D5DFE9',.65);bullets(c.body,x,y+1*g.sy,colW,Math.max(.3,bottom-y-1*g.sy),g.fontSize.body);});
      }else if(slide.type==='figure'){
        const hasBody=slide.body?.length>0,figW=hasBody?contentW*.61:contentW,captionH=slide.caption ? .85*g.sy : 0;
        const rect={x:g.left,y,w:figW,h:Math.max(.4,bottom-y-captionH)};
        if(slide.image&&Core.isSafeImageDataUrl(slide.image.dataUrl)){
          const pos=Export.fitImage(slide.image.width,slide.image.height,rect);
          parts.push(box('<img class="ppt-image" src="'+h(slide.image.dataUrl)+'" alt="'+h(slide.image.alt||slide.caption)+'">',pos.x,pos.y,pos.w,pos.h,12*g.scale));
        }else{
          parts.push(text('添加本页图像',rect.x,rect.y+rect.h/2-.4*g.sy,rect.w,.45*g.sy,20*g.scale,'text-align:center;color:#6D7E94;'));
          parts.push(text('在应用中选择 PNG 或 JPEG',rect.x,rect.y+rect.h/2+.12*g.sy,rect.w,.4*g.sy,12*g.scale,'text-align:center;color:#6D7E94;'));
        }
        if(slide.caption)parts.push(text(slide.caption,rect.x,bottom-captionH+.11*g.sy,rect.w,captionH-.11*g.sy,g.fontSize.caption,'text-align:center;'));
        if(hasBody)bullets(slide.body,g.left+figW+.43*g.sx,y+.15*g.sy,contentW-figW-.43*g.sx,bottom-y-.15*g.sy,18*g.scale);
      }else bullets(slide.body,g.left,y+.12*g.sy,contentW,Math.max(.4,bottom-y-.12*g.sy),g.fontSize.body);
    }
    const prefix={data:'数据来源：',official:'官方来源：',synthetic:'教学示例：',paper:''};
    const citations=(slide.citations||[]).map(c=>'<div>'+h(prefix[c.kind]||'')+h(c.title)+(c.venue?' | ':'')+(Core.safeUrl(c.url)?'<a href="'+h(Core.safeUrl(c.url))+'" target="_blank" rel="noopener noreferrer">'+h(c.venue)+'</a>':'<strong>'+h(c.venue)+'</strong>')+(c.year?', '+h(c.year):'')+(c.status?' '+h(c.status):'')+'.</div>').join('');
    if(citations)parts.push(box(citations,g.left,height-.26*g.sy-footH,contentW-.7*g.sx,footH,g.fontSize.citation,'display:flex;flex-direction:column;justify-content:flex-end;line-height:1.35;'));
    parts.push(text(String(selected+1).padStart(2,'0')+' / '+String(project.slides.length).padStart(2,'0'),g.right-.65*g.sx,height-.50*g.sy,.65*g.sx,.22*g.sy,9*g.scale,'text-align:right;color:#738196;'));
    shell.innerHTML='<article class="slide ppt-precise">'+parts.join('')+'</article>';
    const indicator=document.getElementById('page-indicator');if(indicator)indicator.textContent=' / '+String(selected+1).padStart(2,'0')+' — '+String(project.slides.length).padStart(2,'0');
  }
  function renderStats(){
    const report=Core.validateProject(project);const count=(report.errors||[]).length+(report.warnings||[]).length;
    document.getElementById('stats').innerHTML='<div class="stat"><strong>'+project.slides.length+'</strong><span>页内容</span></div><div class="stat" title="按各页预计用时相加；字数估算约 '+Number(report.minutes||0).toFixed(1)+' 分钟"><strong>'+Number(report.scheduledMinutes||0).toFixed(1)+'</strong><span>已分配 / '+h(project.duration)+' 分钟</span></div><div class="stat"><strong>'+getSections().length+'</strong><span>个章节</span></div><div class="stat"><strong>'+count+'</strong><button data-tab="check">项自检提醒 →</button></div>';
  }
  function renderList(){document.getElementById('slide-list').innerHTML=project.slides.map((s,i)=>'<button class="slide-item '+(i===selected?'active':'')+'" data-slide-index="'+i+'" aria-label="第'+(i+1)+'页 '+h(s.title)+'" aria-current="'+(i===selected?'true':'false')+'"><span class="slide-number">'+String(i+1).padStart(2,'0')+'</span><div><div class="slide-item-title">'+h(s.title||'未命名页面')+'</div><div class="slide-item-section">'+h(typeNames[s.type]||'内容页')+' / '+h(s.section||'未设章节')+'</div></div></button>').join('');}
  function renderEditor(){
    const s=currentSlide(),box=document.getElementById('slide-editor');if(!s){box.innerHTML='<div class="empty-state">添加一页开始编辑。</div>';return;}
    if(editTab==='notes'){
      box.innerHTML=field('本页讲稿与图号备注',slideInp('notes',s.notes||'','textarea','rows="12"'),'备注随 PPTX 导出，可在 PowerPoint 备注区查看。')+field('本页预计用时（秒）',slideInp('durationSec',s.durationSec??60,'input','type="number" min="0" max="1800"'))+'<div class="quiet-note">“已分配”按逐页预计用时相加。另按字数估计讲述时间，约 '+h(Core.estimateProject(project).minutes)+' 分钟。请结合实际试讲调整。</div>';
    }else if(editTab==='sources'){
      box.innerHTML=field('内容性质','<select data-slide="evidence">'+options(evidenceNames,s.evidence||'teaching')+'</select>')+(s.citations||[]).map((c,i)=>'<div class="source-card"><div class="source-card-header"><span>来源 '+(i+1)+'</span><button class="text-button" data-remove-source="'+i+'" style="padding:0">移除</button></div>'+field('来源类型','<select data-citation="kind" data-source-index="'+i+'">'+options(sourceKinds,c.kind||'paper')+'</select>')+field('完整题名','<input data-citation="title" data-source-index="'+i+'" value="'+h(c.title)+'">')+field('期刊 / 机构（链接锚点）','<input data-citation="venue" data-source-index="'+i+'" value="'+h(c.venue)+'">')+field('年份','<input data-citation="year" data-source-index="'+i+'" value="'+h(c.year)+'">')+field('来源网址 / DOI 链接','<input data-citation="url" data-source-index="'+i+'" value="'+h(c.url)+'" placeholder="https://doi.org/…">')+field('发表状态（选填）','<input data-citation="status" data-source-index="'+i+'" value="'+h(c.status)+'" placeholder="如 Reviewed Preprint v2">')+'</div>').join('')+'<button class="button full" data-action="add-source">'+icon('plus')+'添加来源</button><p class="hint">只让期刊或机构名可点击。题名、年份和发表状态保持完整。保留链接不代表已经核实证据。</p>';
    }else{
      box.innerHTML=field('页面类型','<select data-slide="type">'+options(typeNames,s.type)+'</select>')+field('本页标题',slideInp('title',s.title))+field('所属章节',slideInp('section',s.section||'','input','list="section-options"'))+'<datalist id="section-options">'+getSections().map(x=>'<option value="'+h(x)+'">').join('')+'</datalist>';
      if(s.type==='cover'||s.type==='section')box.innerHTML+=field('副标题',slideInp('subtitle',s.subtitle||'','textarea','rows="3"'));
      else if(s.type==='comparison'){
        const columns=[0,1].map(i=>s.columns?.[i]||{title:i?'右栏':'左栏',body:[]});
        box.innerHTML+=columns.slice(0,2).map((c,i)=>field((i===0?'左':'右')+'栏标题','<input data-column="'+i+'" data-column-key="title" value="'+h(c.title)+'">')+field((i===0?'左':'右')+'栏要点（一行一条）','<textarea data-column="'+i+'" data-column-key="body" rows="4">'+h((c.body||[]).join('\n'))+'</textarea>')).join('');
      }else{
        if(s.type==='figure')box.innerHTML+='<button class="button full" data-action="add-image">'+icon('image')+(s.image?'替换图片':'添加原始图片')+'</button><p class="hint">PNG / JPEG / WebP，单张不超过 8 MB。导出时保留比例。</p><div style="margin-top:14px">'+field('图注',slideInp('caption',s.caption||'','textarea','rows="2"'))+'</div>';
        box.innerHTML+=field('本页要点（一行一条）',slideInp('body',(s.body||[]).join('\n'),'textarea','rows="7"'));
      }
      box.innerHTML+='<hr>'+field('内容性质','<select data-slide="evidence">'+options(evidenceNames,s.evidence||'teaching')+'</select>');
    }
  }
  function download(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  function safeFilename(v){return String(v||'校园汇报').replace(/[\\/:*?"<>|\x00-\x1f]/g,'_').slice(0,80);}
  function saveProject(){download(new Blob([JSON.stringify(project,null,2)],{type:'application/json'}),safeFilename(project.title)+'.json');toast('项目文件已导出，可在下次导入继续编辑。');}
  async function exportPptx(){if(exporting)return;const r=Core.validateProject(project);if(r.errors?.length){leftTab='check';renderAll();toast('请先处理自检中列出的错误。');return;}exporting=true;renderAll();try{const blob=await Export.exportPptx(clone(project));download(blob,safeFilename(project.title)+'.pptx');toast('PPTX 已导出。请在 PowerPoint 中检查字体与实际排版。');}catch(e){toast('导出失败：'+(e.message||e));}finally{exporting=false;renderAll();}}
  function closeModal(){document.getElementById('modal-root').innerHTML='';modalOpen=false;}
  function openModal(kind){
    let title='',sub='',body='';
    if(kind==='ai'){
      title='与正在使用的 AI 助手协作';sub='把任务、材料与输出结构一起交给助手，再将结果带回工作台。';
      body='<div class="modal-grid"><section><div class="ai-step">01 / 复制任务包</div><h3>到 ChatGPT 或千问整理内容</h3><p>任务包包含当前汇报内容、场景要求和返回格式。按你的材料补充事实，让助手保留来源与待核实项。</p><textarea class="ai-text" id="ai-prompt" readonly>'+h(Core.buildPrompt(project))+'</textarea><div class="modal-row"><button class="button primary" data-action="copy-prompt">'+icon('copy')+'复制任务包</button><button class="button" data-action="download-prompt">下载 TXT</button></div></section><section><div class="ai-step">02 / 导入返回结果</div><h3>继续调整结构与版式</h3><p>粘贴助手返回的项目 JSON，或导入下载的 JSON 文件。导入后可以撤销，再逐页修改。</p><textarea class="ai-text" id="ai-result" placeholder="粘贴 JSON 内容，支持带 ```json 标记的回复"></textarea><div class="modal-row"><button class="button primary" data-action="apply-ai">导入 AI 结果</button><button class="button" data-action="import-project">选择 JSON 文件</button></div></section></div><hr><p class="quiet-note">当前版本通过任务包与外部助手协作，未内置大模型调用。本应用不要求提供 API 密钥。复制任务包后由你决定将材料交给哪个助手。</p>';
    }else if(kind==='roadmap'){
      title='参赛推进';sub='先用真实任务验证，再按实际完成的功能准备材料。';
      body='<h3>建议方向：教育教学</h3><p>服务课程汇报与研究生学术训练，重点检验材料组织、来源保留、样式一致与后续修改。工作名“求是·汇报”可在试用后确定。</p><table><thead><tr><th>时间</th><th>主要产出</th></tr></thead><tbody><tr><td>10月12—13日</td><td>原型试用，确认场景、页面结构与导出结果</td></tr><tr><td>10月14—15日</td><td>两个外部模板与真实材料测试，修复关键排版问题</td></tr><tr><td>10月16—17日</td><td>六项任务对照及少量同学试用，记录用时与返工</td></tr><tr><td>10月18日前</td><td>按实际功能完成报名，落实原创承诺书</td></tr><tr><td>10月19—20日</td><td>固定演示版本，制作介绍PDF、录制演示视频</td></tr><tr><td>10月21日</td><td>检查提交材料、视频大小与命名，留出提交缓冲</td></tr></tbody></table><p class="hint">赛程与材料要求依据本项目提供的通知摘录。这里的评测安排为作品开发建议。</p><hr><h3>可验证的应用成效</h3><p>用相同源材料比较通用助手、原有 Skill 和应用，记录达到可交付状态的总时间、来源正确性、版式问题与修改成功率。成果展示只使用实测数据。</p><h3>演示视频建议</h3><p>概述 ≤2 分钟；完整操作 ≤6 分钟，包含 AI 协作、模板导入、导航切换、当前页修改与 PPTX 导出；成效与反思 ≤2 分钟。总文件 ≤200 MB，不含第三方水印。</p>';
    }else{
      title='一次汇报的完整流程';sub='首版工作台围绕课程、组会和文献分享制作。';
      body='<ol><li><strong>选择场景。</strong>在“内容”页选择场景，载入示例或粘贴分节提纲。已有项目 JSON 可随时恢复。</li><li><strong>整理内容。</strong>提纲可以直接排成页。需要 AI 整理时，使用“AI 协作”生成任务包，再导入助手返回的内容。</li><li><strong>应用风格。</strong>选择内置主题色或自定义主色；可上传 PPTX 提取字体、配色、页面尺寸，切换顶部或左侧导航。</li><li><strong>逐页编辑。</strong>右侧修改标题、要点、图注、来源和讲稿。点击页面列表切换页面，可上移、下移、添加、删除与撤销。</li><li><strong>自检并导出。</strong>检查信息量、来源和时间提醒。导出可编辑 PPTX 后，在实际汇报电脑中确认字形、图像与页脚。</li></ol><hr><div class="modal-grid"><section><h3>当前支持</h3><p>五种页面类型；三类场景示例；全稿主题与导航；TXT/Markdown/JSON导入；图片按比例放置；来源链接；讲稿备注；浏览器保存与项目导出。</p></section><section><h3>模板导入的范围</h3><p>当前提取样式参数，并使用本工作台版式重新排版。复杂母版、校标、动画与原文件页面不会一起迁入。已有整份 PPT 的精准续改仍需原有 Skill 与桌面演示软件配合。</p></section></div><hr><h3>文件与保存</h3><p>内容在当前浏览器处理并尝试自动保存。清除浏览器数据或换设备后无法自动恢复，请使用“保存项目”导出 JSON 备份。字体由使用电脑提供，应用不分发字体、校标或论文原图。</p><p>页面自检只覆盖程序已实现的规则，不核实文献事实。参考来源需与原材料对应。内置内容为合成教学示例，不代表真实科研结果。</p>';
    }
    document.getElementById('modal-root').innerHTML='<div class="modal-backdrop" data-modal-backdrop="true"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">'+title+'</h2><p>'+sub+'</p></div><button class="close-button" data-action="close-modal" aria-label="关闭">'+icon('close')+'</button></header><div class="modal-content">'+body+'</div></section></div>';
    modalOpen=true;document.querySelector('.close-button').focus();
  }
  function parseProjectText(text){
    if(text.length>Core.limits.projectBytes)throw new Error('项目内容过大，请压缩图片后导入。');
    const trimmed=text.trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'');
    const obj=JSON.parse(trimmed);if(!obj||!Array.isArray(obj.slides)||!obj.slides.length)throw new Error('JSON 需要包含非空 slides 数组。');
    if(obj.slides.length>Core.limits.slides)throw new Error('首版最多支持 '+Core.limits.slides+' 页。');
    return Core.normalizeProject(obj);
  }
  function applyProject(next,message){remember();project=next;selected=0;persist();closeModal();renderAll();toast(message);}
  async function copyPrompt(){const value=document.getElementById('ai-prompt').value;try{await navigator.clipboard.writeText(value);toast('任务包已复制。请粘贴到你正在使用的 AI 助手。');}catch(_){const area=document.getElementById('ai-prompt');area.focus();area.select();try{if(document.execCommand('copy'))toast('任务包已复制。');else toast('请按 Ctrl/Cmd+C 复制，或下载 TXT。');}catch(_){toast('请按 Ctrl/Cmd+C 复制，或下载 TXT。');}}}
  async function handleAction(action){
    switch(action){
      case 'workbench':closeModal();window.scrollTo({top:0,behavior:'smooth'});break;
      case 'guide':case 'roadmap':case 'ai':openModal(action);break;
      case 'close-modal':closeModal();break;
      case 'undo':if(history.length){project=history.pop();selected=Math.min(selected,project.slides.length-1);persist();renderAll();toast('已撤销上一次修改。');}break;
      case 'load-demo':applyProject(Core.createDemo(project.scene),'已载入场景示例，可继续修改。');break;
      case 'save-project':saveProject();break;
      case 'import-project':document.getElementById('project-file').click();break;
      case 'import-template':document.getElementById('template-file').click();break;
      case 'add-image':document.getElementById('image-file').click();break;
      case 'export':await exportPptx();break;
      case 'add-slide':mutate(()=>{const section=currentSlide()?.section||getSections()[0]||'主要内容';const s={id:'slide-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,6),type:'bullets',section,title:'新页面',body:['在这里填写本页要点'],columns:[{title:'左栏',body:[]},{title:'右栏',body:[]}],citations:[],notes:'',evidence:'teaching',durationSec:60};project.slides.splice(selected+1,0,s);selected++;});break;
      case 'delete-slide':if(project.slides.length<=1){toast('请至少保留一页。');break;}mutate(()=>{project.slides.splice(selected,1);selected=Math.min(selected,project.slides.length-1);});break;
      case 'move-up':if(selected>0)mutate(()=>{[project.slides[selected-1],project.slides[selected]]=[project.slides[selected],project.slides[selected-1]];selected--;});break;
      case 'move-down':if(selected<project.slides.length-1)mutate(()=>{[project.slides[selected+1],project.slides[selected]]=[project.slides[selected],project.slides[selected+1]];selected++;});break;
      case 'add-source':mutate(()=>{currentSlide().citations=currentSlide().citations||[];currentSlide().citations.push({title:'',venue:'',year:'',url:'',kind:'paper',status:''});});break;
      case 'apply-outline':if(!outlineDraft.trim()){toast('请先粘贴分节提纲。');break;}try{const next=Core.parseMarkdown(outlineDraft,project.scene);const warnings=next.importWarnings||[];next.theme=clone(project.theme);next.presenter=project.presenter;next.duration=project.duration;applyProject(Core.normalizeProject(next),'提纲已排成页面。'+(warnings.length?warnings.join('；'):'请补充来源和图像。'));}catch(e){toast('提纲读取失败：'+e.message);}break;
      case 'copy-prompt':await copyPrompt();break;
      case 'download-prompt':download(new Blob([Core.buildPrompt(project)],{type:'text/plain;charset=utf-8'}),'AI汇报任务包.txt');break;
      case 'apply-ai':try{const next=parseProjectText(document.getElementById('ai-result').value);let kept=0;next.slides.forEach(s=>{const old=project.slides.find(o=>o.id===s.id);if(!s.image&&old?.image){s.image=clone(old.image);kept++;}});applyProject(Core.normalizeProject(next),'AI 内容已导入'+(kept?'，已保留 '+kept+' 张原图':'')+'。请核对事实与来源。');}catch(e){toast('无法导入：'+e.message);}break;
    }
  }
  document.addEventListener('click',async event=>{
    const b=event.target.closest('button');
    if(b){
      if(b.dataset.action){try{await handleAction(b.dataset.action);}catch(e){toast(e.message||'操作失败，请重试。');}return;}
      if(b.dataset.tab){leftTab=b.dataset.tab;renderAll();return;}
      if(b.dataset.editTab){editTab=b.dataset.editTab;renderAll();return;}
      if(b.dataset.slideIndex!==undefined){selectSlide(Number(b.dataset.slideIndex));return;}
      if(b.dataset.nav){mutate(()=>project.theme.nav=b.dataset.nav);return;}
      if(b.dataset.palette){const p=Core.palettes.find(p=>p.id===b.dataset.palette);if(p)mutate(()=>{Object.assign(project.theme,{palette:p.id,accent:p.accent,secondary:p.secondary,background:p.background,text:p.text});});return;}
      if(b.dataset.removeSource!==undefined){mutate(()=>currentSlide().citations.splice(Number(b.dataset.removeSource),1));return;}
      if(b.dataset.jumpId){const idx=project.slides.findIndex(s=>s.id===b.dataset.jumpId);if(idx>=0)selectSlide(idx);return;}
      if(b.dataset.jumpSection){const idx=project.slides.findIndex(s=>s.section===b.dataset.jumpSection);if(idx>=0)selectSlide(idx);return;}
    }
    if(event.target.dataset.modalBackdrop)closeModal();
  });
  document.addEventListener('change',event=>{
    const e=event.target;
    if(e.dataset.project){const key=e.dataset.project;mutate(()=>project[key]=key==='duration'?Math.max(1,Math.min(120,Number(e.value)||10)):e.value);}
    else if(e.dataset.theme){mutate(()=>project.theme[e.dataset.theme]=e.value);}
    else if(e.dataset.slide){const key=e.dataset.slide;mutate(()=>{currentSlide()[key]=key==='body'?e.value.split('\n').map(x=>x.trim()).filter(Boolean):key==='durationSec'?Math.max(0,Math.min(1800,Number(e.value)||0)):e.value;if(key==='type'&&e.value==='comparison'&&(!currentSlide().columns||currentSlide().columns.length<2))currentSlide().columns=[{title:'左栏',body:[]},{title:'右栏',body:[]}];},key!=='type');if(key==='type')renderEditor();}
    else if(e.dataset.column!==undefined){mutate(()=>{if(!currentSlide().columns||currentSlide().columns.length<2)currentSlide().columns=[0,1].map(i=>currentSlide().columns?.[i]||{title:i?'右栏':'左栏',body:[]});const c=currentSlide().columns[Number(e.dataset.column)];c[e.dataset.columnKey]=e.dataset.columnKey==='body'?e.value.split('\n').filter(x=>x.trim()):e.value;},true);}
    else if(e.dataset.citation){mutate(()=>currentSlide().citations[Number(e.dataset.sourceIndex)][e.dataset.citation]=e.value,true);}
    else if(e.id==='custom-color'){mutate(()=>{project.theme.accent=e.value;project.theme.palette='custom';});}
    else if(e.id==='aspect-ratio'){if(e.value!=='custom')mutate(()=>{project.theme.width=e.value==='standard'?10:13.333333;project.theme.height=7.5;});}
  });
  document.addEventListener('input',e=>{if(e.target.id==='outline-draft')outlineDraft=e.target.value;});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&modalOpen){closeModal();return;}if(modalOpen&&e.key==='Tab'){const controls=[...document.querySelectorAll('.modal button,.modal a,.modal textarea,.modal input,.modal select')].filter(x=>!x.disabled);if(!controls.length)return;const first=controls[0],last=controls[controls.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
  document.getElementById('project-file').addEventListener('change',async e=>{
    const f=e.target.files[0];e.target.value='';if(!f)return;
    try{if(f.size>Core.limits.projectBytes)throw new Error('项目不能超过 '+Math.round(Core.limits.projectBytes/1024/1024)+' MB。');const text=await f.text();let next,warnings=[];if(/\.json$/i.test(f.name)){next=parseProjectText(text);}else{next=Core.parseMarkdown(text,project.scene);warnings=next.importWarnings||[];next.theme=clone(project.theme);next.presenter=project.presenter;next.duration=project.duration;next=Core.normalizeProject(next);}applyProject(next,'已导入 '+f.name+'。'+warnings.join('；'));}catch(err){toast('导入失败：'+err.message);}
  });
  document.getElementById('template-file').addEventListener('change',async e=>{
    const f=e.target.files[0];e.target.value='';if(!f)return;
    try{if(f.size>Core.limits.templateBytes)throw new Error('首版模板文件限制为 '+Math.round(Core.limits.templateBytes/1024/1024)+' MB，请使用精简模板副本。');toast('正在读取模板样式…');const result=await Export.readTemplate(await f.arrayBuffer(),f.name);mutate(()=>{templateResult=result;Object.assign(project.theme,result.theme,{palette:'custom'});});toast('已应用字体、主题色与页面尺寸。复杂母版元素未迁入。');}catch(err){toast('模板读取失败：'+err.message);}
  });
  document.getElementById('image-file').addEventListener('change',async e=>{
    const f=e.target.files[0];e.target.value='';if(!f)return;const targetId=currentSlide()?.id;
    try{if(f.size>8*1024*1024)throw new Error('单张图片不能超过 8 MB。');if(!/^image\/(png|jpeg|webp)$/.test(f.type))throw new Error('请选择 PNG、JPEG 或 WebP 图片。');const dataUrl=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(new Error('图片无法读取。'));r.readAsDataURL(f);});const img=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('图片格式损坏。'));im.src=dataUrl;});if(img.width*img.height>40000000)throw new Error('图片像素过大，请先缩小至 4000 万像素以内。');let output=dataUrl;if(f.type==='image/webp'){const canvas=document.createElement('canvas');canvas.width=img.width;canvas.height=img.height;canvas.getContext('2d').drawImage(img,0,0);output=canvas.toDataURL('image/png');}if(!Core.isSafeImageDataUrl(output))throw new Error('转换后的图片超过 8 MB，请缩小图片后重试。');const next=clone(project);const s=next.slides.find(s=>s.id===targetId);if(!s)throw new Error('目标页面已不存在。');s.image={dataUrl:output,width:img.width,height:img.height,alt:f.name};const checked=Core.normalizeProject(next);mutate(()=>{project=checked;});toast('图片已加入，保持原始比例。');}catch(err){toast(err.message);}
  });
  window.CampusPPTWorkbench={getProject:()=>clone(project),loadProject:value=>applyProject(Core.normalizeProject(value),'项目已载入。')};
  renderAll();
})();
