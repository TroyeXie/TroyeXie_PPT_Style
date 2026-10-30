# TroyeXie_PPT_Style

**v2.2.0** · 用于中文学术组会、论文解读、基金评审、答辩、成长展示与社会实践PPT的可复用制作规范。

核心是**真实素材支撑叙事，围绕问题组织证据，沿用已确认模板，统一图组与光学对齐，逐轮精修并核验最终文件**。本仓库不是研究结论库，也不分发个人PPT、字体或校标。

## 使用

仓库/显示名为`TroyeXie_PPT_Style`，Skill调用标识为`troye-xie-ppt-style`。仓库根目录的`SKILL.md`是入口，配套目录应一并保留。

```bash
git clone https://github.com/TroyeXie/TroyeXie_PPT_Style.git ./troye-xie-ppt-style
```

上面仅将仓库复制到本地，不自动完成安装。按当前使用端的技能加载配置添加该目录；不把某个客户端的隐藏目录当作所有环境的统一路径。已有副本先检查`git status`及本地修改，再使用`git pull --ff-only`更新并重新加载。有关Skill概念可参考[官方说明](https://developers.openai.com/plugins/concepts/skills)。也可直接要求助手读取仓库规范，并提供本轮实际PPT模板。

### 沿用蓝白学术模板

> 请使用 $troye-xie-ppt-style。以我上传的最新PPT为基线，采用clinical-academic profile，落实本轮修改并保留其他已认可内容。引用只链接期刊/机构名，更新重排后的页码、导航和备注，交付核验过的PPTX与PDF。

### 使用其他模板

> 请使用 $troye-xie-ppt-style 的叙事、图组和验收原则，但保留我本次活动模板；不要应用clinical-academic的数字参数。

**规则优先级：本轮要求 > 最新文件/指定模板 > 明确选用的profile > 通用建议。**明确选择profile后才采用导航14 pt、引用9 pt等设置；不会把某次页数、时长、人物、日期或科学结论变成全局规则。

## 文件导航

| 文件 | 作用 |
|---|---|
| [SKILL.md](SKILL.md) | 工作流入口与任务路由 |
| [叙事与证据](references/narrative-and-evidence.md) | 事实—贡献—价值、状态和素材选择 |
| [基金评审PPT](references/grant-review-presentations.md) | 重要性—缺口—用途、原申请书图件、短引和最新提交版 |
| [学术汇报](references/academic-presentations.md) | 原文/再分析/计划区分、来源、图注与模型页 |
| [视觉语言](references/visual-language.md) | 字体、正文边界、导航、光学对齐和多面板 |
| [常见页面范式](references/layout-patterns.md) | 成长、会议、实践、美育等既有页面范式 |
| [修订与验收](references/revision-and-quality.md) | 最小修改、页序、真实点击范围、渲染和素材保护 |
| [渲染后边界检查](references/rendered-layout-checks.md) | 区分文本框与可见边界，核对成组对齐、分布和留白 |
| [媒体与渲染](references/media-and-rendering.md) | 字体异常、时间剪辑与画面裁剪、音轨衔接和目标软件试播 |
| [模板参数说明](references/template-profile.md) | 三层复用方式与脚本使用范围 |
| [clinical-academic.json](profiles/clinical-academic.json) | 可选蓝白学术模板的字体、字号及几何配置 |
| [inspect_pptx.py](scripts/inspect_pptx.py) | 原有只读结构盘点，默认不导出正文 |
| [lint_pptx_style.py](scripts/lint_pptx_style.py) | 逻辑页序、页脚锚点及显式样式检查 |
| [check_rendered_layout.py](scripts/check_rendered_layout.py) | 只读核对已有边界测量与排版约束，不负责渲染或识别字形 |
| [引用映射示例](examples/citation-map.example.json) | 用合成名称示范精确文本/目标核对 |
| [边界测量](examples/rendered-layout.measurements.example.json) / [约束示例](examples/rendered-layout.contracts.example.json) | 无真实文字或素材的合成坐标示例 |
| [结构测试](tests/test_lint_pptx_style.py) / [边界测试](tests/test_rendered_layout.py) | 纯合成OOXML与坐标回归测试 |
| [CHANGELOG.md](CHANGELOG.md) | 版本与迁移说明 |

## 核心规范

**内容**：以科学问题组织，不按文件夹编号罗列；原文已完成、本人再分析和待检验问题分开；图下用一句清楚结论；模型页说明病理状态、构建方式和拟测表型。

**引用**：文献精读保留完整题名；基金评审可沿用认可的作者—期刊—年份短引，本人分析可突出数据登录号。期刊/机构名加粗无下划线，只有名称或约定的数据编号可点击；年份、前缀、标点及发表状态不进入点击范围。

**排版**：标题与横线左对齐；在适用模板中内容右界对齐校标右界、引用末行对齐页码底部；图与图注共享中心；先去掉多余强制换行和孤字，再考虑调整字号。

**续改**：从最新文件继续，只做必要改动；移页同步更新导航、小节、页码、备注及PDF。原始图像和有效分析不因换字体被重算或重绘成假原件。

**模板与间距**：美化保留背景、形状、重点色、字体层级及封尾；混合字号按实际字形底端检查。数字与说明先统一组内间距，再按整组分布；承托色块要有上下留白，并与页脚元素保持净距，不能压成贴字的细条。

**证据与媒体**：叙述突出执行者真实贡献，保留专业指导和分工；奖项信息顺序一致，标题与图片新顺序相符。正式反馈展示关键正文及必要上下文。音视频分别检查时间剪辑、画面裁剪、音轨、循环和翻页；字体错映、可见裁切及播放效果须实际验证。

## 只读检查与测试

检查器使用Python 3.10+标准库，无需联网或安装PPT库：

```bash
python scripts/lint_pptx_style.py presentation.pptx
python scripts/lint_pptx_style.py presentation.pptx --profile profiles/clinical-academic.json
python scripts/lint_pptx_style.py presentation.pptx --citation-map local/citation-map.json
python scripts/check_rendered_layout.py examples/rendered-layout.measurements.example.json examples/rendered-layout.contracts.example.json
python -m unittest discover -s tests -v
```

检查器不修改输入。退出码0/1/2分别表示无已实现项错误/发现错误/读取失败。精确映射按最终逻辑页码填写；示例中的假期刊不能直接用于真实文档。

边界检查器接收已归一为pt的对象框与可见边界，核对底端对齐、并集中心、成对间距、整组分布、内边距和净距。它不会自动从PPTX、图片或PDF提取测量；使用方法与限制见[边界检查说明](references/rendered-layout-checks.md)。

**结构检查不是视觉或事实认证。**母版继承、实际字体、图像裁剪、公式缺字、PDF点击矩形和媒体播放需要另行核查。测试仅覆盖脚本逻辑，仓库没有上传真实演示作为测试样本。

## 资源与隐私

数值profile不是模板文件。实际使用时仍需用户提供最新PPT及授权素材；独立字体文件不随仓库或交付ZIP分发；用户文档可按许可嵌入，并在最后一次保存后核对真实部件与字形。私人分析、论文PDF、Figure截图、校标、原始数据和含敏感文本的QA留在项目工作区。修改风格规范不自动授权访问或公开其他资料。

## 社会实践总结册子技能

新增可独立安装的 [social-practice-booklet](skills/social-practice-booklet/SKILL.md)，用于社会实践图文总结册。包含真实材料取舍、内容精炼、字体与重点色、媒体与奖项展示、局部精修方法，以及可运行的两页矢量PDF初稿构建器、合成示例和预检工具。独立选择该目录作为技能目录，保留全部配套文件；不影响仓库根目录的PPT技能。

> 请使用 $social-practice-booklet，依据最新材料和参考册制作社会实践总结册，精炼文案、丰富图文，交付可复现源和核验后的PDF。

两页红金版式是可选起点，不覆盖本轮模板。字体、校标和真实团队素材由使用者在本地提供，公共包不包含本次私人材料。

## 自然科学基金申请书子技能

新增可独立安装的 [natural-science-grant](skills/natural-science-grant/SKILL.md)，用于国家、省级及研究生自然科学基金申请书的起草、修订、模板排版与提交前复核。包含科学逻辑、摘要/关键词、AI方法定位、前期基础归属、图注首行随图、字数统计口径、字体便携及最后保存后的核验。

> 请使用 $natural-science-grant，以当年指南、空白模板和我指定的最新稿为准，完善科学问题与研究内容，并保持模板、核对摘要字数和图文分页。

独立安装时仅选择`skills/natural-science-grant`并保留其配套文件。字体、具体研究结论、真实申请书和个人信息不随技能分发。默认自动发现，不要求每次显式调用。只读结构盘点与合成测试：

```bash
python skills/natural-science-grant/scripts/audit_docx.py application.docx --output local/audit.json
python -m unittest discover -s skills/natural-science-grant/tests -v
```

盘点器默认不导出正文，不认证真实分页、字数合规、字体许可或科学事实；这些仍需实际文档及来源复核。某次400字、20页、具体字体或数据图语言属于本轮配置，不作为所有基金的硬规则。
