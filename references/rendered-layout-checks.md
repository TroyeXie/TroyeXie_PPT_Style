# 渲染后对齐检查

用于混合字号底端、数字与说明分组、整组居中、底带留白等需要反复量取的局部精修。不要求每次修改都准备约束文件；简单页面直接看图即可。

## 测量来源与边界

`scripts/check_rendered_layout.py`只读两份JSON，不读取或修改PPTX，不渲染、识字或验证字体。它检查**已有测量是否满足本轮明确的几何关系**，不能证明文本正确、主体完整或媒体正常播放。

所有坐标使用同一页面原点的**磅（pt）**。OOXML通常用EMU，编辑库可能用像素，PowerPoint原生对象常用磅，必须先明确换算；脚本拒绝直接把`px`当`pt`。从截图量取时，应按已知页面尺寸和渲染分辨率换算，不猜测屏幕DPI。

每个对象有唯一`id`、逻辑页码`page`和`frame: [x, y, width, height]`。`frame`是容器框；`ink`是同坐标系下的实际文字或可见图形边界。字体内边距、透明图边、描边和阴影是否纳入，应在本轮测量方法中保持一致。

可在原生PowerPoint中记录`TextFrame2.TextRange`的`BoundLeft`、`BoundTop`、`BoundWidth`、`BoundHeight`，并与实际导出图核对。这些是文本范围测量，未必等同于逐像素墨迹或包含阴影。组合对象先换算至页面坐标；不要把组内局部坐标直接与页内其他对象比较。对象标识优先由逻辑页和形状ID建立；仅名称不一定唯一。

矩形色块可只提供`frame`以作为居中/内边距的参照。需要检查它与其他可见图形的间隔时，另提供经核对的`ink`。曲线页脚的变换框可能覆盖整页，不能拿这个大框代替曲线实际占据区域。没有可靠可见边界时保留人工检查，不补造数据。缺少`ink`不会自动回退到`frame`。

## 两份输入

[测量示例](../examples/rendered-layout.measurements.example.json)与[约束示例](../examples/rendered-layout.contracts.example.json)完全由合成矩形构成，不代表任何模板参数。

测量格式：

```json
{
  "schema_version": 1,
  "unit": "pt",
  "objects": [
    {"id": "text", "page": 1, "frame": [10, 10, 100, 30], "ink": [12, 15, 92, 20]},
    {"id": "band", "page": 1, "frame": [0, 0, 120, 50]}
  ]
}
```

约束文件中的`checks`列出需要验证的关系；`tolerance_pt`按测量精度选择，可在单项中覆盖。示例的容差与距离不是全局规范。

容差边界包含在内，比较时只额外吸收十亿分之一pt的浮点舍入差；这不是新增的排版宽限。输入和计算结果都必须为有限数值，`schema_version`须为整数1。

| kind | 关键字段 | 核对内容 |
|---|---|---|
| `align` | `groups`、`edge` | 各组联合可见框的left/right/top/bottom/center_x/center_y一致 |
| `center` | `members`、`container`、`axis` | 整组联合可见框相对容器框在x/y/both方向居中 |
| `pair_gaps` | `pairs`、`axis`、`min_pt` | 至少两对before/after的内部边缘间距一致且不低于下限 |
| `distribute` | `groups`、`axis`、`mode`、`min_pt` | 至少三组按gaps或centers均匀分布；同时检查组间不重叠 |
| `padding` | `members`、`container`、`min_pt` | 四侧可见内边距达到本轮明确下限 |
| `clearance` | `before`、`after`、`axis`、`min_pt` | 两组之间沿指定方向保留足够间距 |

`groups`是对象ID列表的列表，例如`[["number_a", "label_a"], ["number_b", "label_b"]]`；`members`、`before`和`after`是一个组的ID列表。`pairs`为`[{"before": ["number_a"], "after": ["label_a"]}, ...]`。`container`是单个对象ID，读取它的`frame`。同一项检查不能跨页；均匀分布遵循约束文件中给定的顺序，不替用户自动排序。

数字与说明先检查组内间距，再比较完整组的分布。组高相等时，等中心距与等净间距一致；组高不等时要按当前意图明确`mode`，不能把两者混称。整组中心采用联合边界，不是所有对象中心的简单平均。

## 运行与解释

```bash
python scripts/check_rendered_layout.py \
  examples/rendered-layout.measurements.example.json \
  examples/rendered-layout.contracts.example.json

python scripts/check_rendered_layout.py \
  private/rendered-measurements.json private/layout-contracts.json \
  --output private/layout-report.json
```

退出码0/1/2分别表示约束全部满足、存在不满足项、输入或读取错误。检查器不更改输入，并拒绝以任一输入作为输出；诊断默认只含检查ID、类型和数值，不复制正文。实际测量和报告留在私有工作区，不提交到公共仓库。

字体错映可能在无溢出、所有约束都通过时仍然出现。最后仍须查看真实字形、图片主体、图注对应与实际播放；通过本脚本不等于演示验收。
