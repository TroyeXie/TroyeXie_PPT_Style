# Brief与工具

## 初稿构建器

`scripts/build_booklet.py`使用Python 3.10+及ReportLab，照片需要Pillow，PDF校标合并需要pypdf。`requirements.txt`固定本次实际测试的版本，建议在独立环境安装；不要为使用技能覆盖用户已有项目依赖。

复制合成JSON至项目内部再填真实信息；JSON和构建脚本共同构成可复现的可编辑源。不是Word或PPTX二进制编辑文件；用户指定这些格式时需另外制作。

| 字段 | 用途与限制 |
|---|---|
| `preset` | `formal-red`或`university-blue`；用户指定模板优先 |
| `fonts` | `body_regular`必需；`body_bold`与`title`可选。CLI的`--font-body/--font-bold/--font-title`优先 |
| `title` | `text`为单行，或`groups`恰好两组，形成纵向重叠的假两行；不自动插中点 |
| `team` / `second_title` | 团队全名与第二页标题；完整标题不重复写入团队名 |
| `hero` | `path`及`caption`；无图片时`placeholder`只用于草稿 |
| `intro` | `heading`和精简`body` |
| `teachers` | 最多3张姓名、职务`role`、专业`expertise`卡，数组顺序即展示顺序；不用则省略 |
| `leaders` | 最多2张`name`/`message`卡；寄语按已有材料转述，不用则省略 |
| `media` | `total/national/provincial`明确数值；最多3张代表报道`cards`，含`path/label` |
| `modules` | 两页起点要求4模块，每个`title/value/body`及最多2张`photos`（含`path/caption`） |
| `highlights` / `bold_phrases` | 模块中完整匹配词组的字符串数组，分别控制重点色/加粗；两者同时指定即红色加粗，跨行持续生效 |
| `keep_together` | 模块中的短结论整组不拆行；整组超宽则失败，不压字距 |
| `awards` | 最多2张`context/name`卡，奖项名突出；过长则精简，不静默缩字 |
| `logo` | 可选本地`path`；`width/height`为同尺寸容纳框，PDF可指定1起始`page`；预先裁除无关画布与白底 |
| `colors` | 按脚本`PRESETS`键覆盖六位HEX；修改后检查正文与底板对比度 |

相对资源路径以JSON所在目录为基准。输出路径以当前工作目录为基准，已有文件默认拒绝覆盖；审核后才用`--force`。CLI字体相对路径也按JSON目录解析，推荐给绝对本地字体路径。

图片仅支持等比完整适配。若设计确需局部裁剪，先在项目内生成另一个保留必要上下文的授权图片副本，再将该路径传入。构建器不自动裁掉人像来填满容器。

脚本提供起点，不承诺任意长度和图片比例都自动变得美观。缺字、缺字体、指定重点词不存在、过宽不拆行词组和内容溢出会明确报错。先改brief，再按确有必要调整源布局；不要删除错误检查或批量缩小字体来掩盖问题。

需要验证本地环境时，设置`BOOKLET_TEST_FONT`为本地中文TTF路径，再运行`python -m unittest discover -s tests -v`。测试使用临时合成材料，检查双页输出、溢出拒绝、缺字体及源文件保护；未设置字体时会明确跳过，不应称为测试通过。

## PDF预检

```bash
python scripts/preflight_pdf.py local-review/draft.pdf --expected-pages 2 --render-dir local-review/previews --report local-review/qa.json
```

预检需要pypdf；渲染额外用pypdfium2和Pillow。退出码0表示已实现结构项通过（仍可能有警告），1表示检查失败，2表示输入/依赖/读取错误。JSON是内部记录，不包含全文或完整URL。

精修时可加`--baseline previous.pdf --require-same-text`核查文字、图像payload及链接URI/矩形。当前操作若需要改文，不加严格文字开关；改图或改链接时按有意变化单独复核，不把预期差异称为“完全相同”。图像哈希和矢量运算符数量不能代替实际视觉检查。
