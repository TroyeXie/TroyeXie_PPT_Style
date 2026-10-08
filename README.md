# TroyeXie_PPT_Style

**v2.0.0** · 用于中文学术组会、论文解读、答辩、成长展示与社会实践PPT的可复用制作规范。

核心是**真实素材支撑叙事，围绕问题组织证据，沿用已确认模板，统一图组与光学对齐，逐轮精修并核验最终文件**。本仓库不是研究结论库，也不分发个人PPT、字体或校标。

## 使用

仓库/显示名为`TroyeXie_PPT_Style`，Skill调用标识为`troye-xie-ppt-style`。将仓库放入技能目录并确保根目录存在`SKILL.md`。已有本地副本时先检查差异，再更新；不要覆盖尚未提交的本地修改。

```bash
git clone https://github.com/TroyeXie/TroyeXie_PPT_Style.git ~/.codex/skills/troye-xie-ppt-style
```

已有副本可在检查`git status`后使用`git pull --ff-only`，重新加载后使用。其他安装位置应按实际配置调整。

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
| [学术汇报](references/academic-presentations.md) | 原文/再分析/计划区分、来源、图注与模型页 |
| [视觉语言](references/visual-language.md) | 字体、正文边界、导航、光学对齐和多面板 |
| [常见页面范式](references/layout-patterns.md) | 成长、会议、实践、美育等既有页面范式 |
| [修订与验收](references/revision-and-quality.md) | 最小修改、页序、真实点击范围、渲染和素材保护 |
| [模板参数说明](references/template-profile.md) | 三层复用方式与脚本使用范围 |
| [clinical-academic.json](profiles/clinical-academic.json) | 可选蓝白学术模板的字体、字号及几何配置 |
| [inspect_pptx.py](scripts/inspect_pptx.py) | 原有只读结构盘点，默认不导出正文 |
| [lint_pptx_style.py](scripts/lint_pptx_style.py) | 新增逻辑页序、页脚锚点及显式样式检查 |
| [引用映射示例](examples/citation-map.example.json) | 用合成名称示范精确文本/目标核对 |
| [测试](tests/test_lint_pptx_style.py) | 纯合成OOXML回归测试 |
| [CHANGELOG.md](CHANGELOG.md) | 版本与迁移说明 |

## 本次新增的核心规则

**内容**：以科学问题组织，不按文件夹编号罗列；原文已完成、本人再分析和待检验问题分开；图下用一句清楚结论；模型页说明病理状态、构建方式和拟测表型。

**引用**：完整题名保留在页底；本人分析加“数据来源：”；期刊/机构名加粗无下划线，只有名称可点击。题名、年份、前缀、标点及Reviewed Preprint/v2不进入点击范围。

**排版**：标题与横线左对齐；在适用模板中内容右界对齐校标右界、引用末行对齐页码底部；图与图注共享中心；先去掉多余强制换行和孤字，再考虑调整字号。

**续改**：从最新文件继续，只做必要改动；移页同步更新导航、小节、页码、备注及PDF。原始图像和有效分析不因换字体被重算或重绘成假原件。

## 只读检查与测试

新检查器使用Python 3.10+标准库，无需联网或安装PPT库：

```bash
python scripts/lint_pptx_style.py presentation.pptx
python scripts/lint_pptx_style.py presentation.pptx --profile profiles/clinical-academic.json
python scripts/lint_pptx_style.py presentation.pptx --citation-map local/citation-map.json
python -m unittest discover -s tests -v
```

检查器不修改输入。退出码0/1/2分别表示无已实现项错误/发现错误/读取失败。精确映射按最终逻辑页码填写；示例中的假期刊不能直接用于真实文档。

**结构检查不是视觉或事实认证。**母版继承、实际字体、图像裁剪、公式缺字、PDF点击矩形和媒体播放需要另行核查。测试仅覆盖脚本逻辑，仓库没有上传真实演示作为测试样本。

## 资源与隐私

数值profile不是模板文件。实际使用时仍需用户提供最新PPT及授权素材；字体只在本地使用，不随仓库、快照或交付ZIP分发。私人分析、论文PDF、Figure截图、校标、原始数据和含敏感文本的QA留在项目工作区。修改风格规范不自动授权访问或公开其他资料。
