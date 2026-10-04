# TroyeXie_PPT_Style

一套面向中文答辩、学术成长、评奖与社会实践汇报的 Codex Skill。

核心是**真实素材支撑叙事，证据约束价值表达，统一网格组织视觉，逐轮精修验证成品**。它总结了国奖汇报多轮修订，以及社会实践答辩的设计、文案、配图和初稿制作经验；不附带个人经历材料，也不是固定页数的PPT模板。

## 使用

显示名与仓库名为 **TroyeXie_PPT_Style**。为兼容 Skill 命名规范，可调用标识为 **`troye-xie-ppt-style`**。

将本仓库内容放入 Codex 技能目录下的 `troye-xie-ppt-style` 文件夹，保证 `SKILL.md` 位于该文件夹根目录。例如：

```bash
git clone https://github.com/TroyeXie/TroyeXie_PPT_Style.git ~/.codex/skills/troye-xie-ppt-style
```

如果配置了其他 `CODEX_HOME`，使用其 `skills` 子目录；已有同名 Skill 时先比较版本，不直接覆盖本地修改。重新加载技能后，可这样提出任务：

> 请使用 $troye-xie-ppt-style，按我提供的最新PPT和本轮意见继续修改。保留指定母版，统一图组、图注和标题层级，并核验最终导出的文件。

> 请使用 $troye-xie-ppt-style，把这些原始材料组织成社会实践答辩。先梳理角色、行动和成果，再按参考图迁移配色、蒙版与布局。

## 内容

- [SKILL.md](SKILL.md)：适用范围、核心判断和工作流程。
- [叙事与证据](references/narrative-and-evidence.md)：内容取舍、标题价值、成果状态和原件呈现。
- [视觉语言与对齐](references/visual-language.md)：封面大字、配色、字体、母版导航、几何与光学对齐。
- [常见页面范式](references/layout-patterns.md)：课程、论文、会议、项目、临床、履职、社会实践、美育与体育页面。
- [修订与验收](references/revision-and-quality.md)：最小必要修改、脱敏、最终文件检查、按需音视频验证。
- [只读PPTX盘点工具](scripts/inspect_pptx.py)：文件指纹和结构概览，可选使用，不替代视觉与事实核查。

## 取舍

当前明确要求、品牌或模板优先。不会把某次字号、页数、配色、统计值、个人身份、脱敏名单、清空备注或背景音乐安排固化成全局规则。没有任何图片、字体、校标、论文、证书、私人聊天或本地路径随仓库分发。

盘点脚本仅依赖 Python 标准库，默认不导出正文文本，使用 `--include-text` 才包含文字。生成的清单可能含私人内容，应留在当前任务工作区。
