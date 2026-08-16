---
name: up-prediction-ledger
version: 1.0.0
description: >-
  用于把财经UP主的原始字幕转化为可审计的预测事件台账，并用真实行情验证T+1/T+3/T+5/T+10表现，计算准确率、风控能力、关键位能力和阶段画像。适用于“复盘某UP全部字幕”“统计预测准确率”“建立长期预测台账”“比较多个UP谁在哪个环节更有用”“筛选下一批值得跟踪的UP”等任务。原始字幕是最高级证据，严禁用事后复盘、日报摘要或UP主自述替代原始预测证据。
---

# UP主预测复盘与准确率台账

## 1. 目标

把财经UP主历史内容转换为**可追溯、可证伪、可重复计算**的长期预测数据库。核心统计单位是 `Prediction Event / 独立预测事件`，不是视频、字幕文件或直播场次。

最终必须回答：

1. UP当时到底预测了什么；
2. 在原定时间窗口内是否实现；
3. 哪类任务可靠、哪类容易错；
4. 对交易而言应该承担大盘拐点、关键位、板块节奏、风控、仓位或其他什么角色。

## 2. 证据优先级

固定顺序：

1. 原始字幕正文
2. 原视频/直播原始发布时间与页面信息
3. 已建立事件台账
4. 阶段报告
5. 总进度台账
6. 日报/研报/网页摘要

硬规则：

- 日报只能作为索引，不能替代原始预测证据。
- “我之前就说过”“我早就提醒过”不能补记为历史预测，除非找到当时原始字幕。
- 后来行情不能反向修改UP当时的时间窗口、目标或方向。

## 3. GitHub字幕发现标准路径

仓库字幕通常按日期组织：

```text
subtitles/
  YYYY-MM-DD/
    index.json
    xxx.txt
```

### 首选方法

1. 获取 `subtitles/` 日期目录；
2. 逐日读取 `subtitles/YYYY-MM-DD/index.json`；
3. 按 `author`、`title`、`text_file` 筛候选；
4. 再读取对应原始字幕正文确认说话人和实际日期。

典型索引字段：

```text
id
page_url
source_url
title
author
author_uid
published_at
fetched_at
archive_date
video_date
text_file
subtitle_char_count
subtitle_duration_sec
```

### 禁止的主检索方式

不要把“全仓 recursive tree + 在巨大JSON里搜中文文件名”作为主要发现方法。仓库较大时返回内容过长，中文路径搜索容易漏命中。

正确策略是先扫几十个小 `index.json`，再按 `text_file` 定向读字幕。

同一次全库扫描顺手统计所有作者：文件数、覆盖天数、总字幕字数、未来预测密度，用于下一批UP筛选。

## 4. Raw Inventory

提取预测前先建立原始文件清单：

```text
archive_date
author
title
published_at
video_date
text_file
subtitle_char_count
subtitle_duration_sec
```

此阶段只回答“有什么素材”，不判断预测对错。

后续正文确认后增加：

```text
archive_account
actual_speaker
```

## 5. actual_date校正

绝不能默认目录日期等于预测日期。必须分别保存：

```text
archive_date
actual_date
publish_time
```

因为：

```text
归档日期 ≠ 发布时间 ≠ 直播日期 ≠ 预测实际发生日期
```

优先根据正文中的日期、星期、“明天不开盘”“下周一”“昨天市场……”等时间锚，结合 `published_at`、`video_date`、交易日日历和行情校正实际日期。

若归档日明显晚于实际内容日：

```text
historical_backfill = YES
```

禁止用归档日验证历史补档，否则会产生未来函数。

## 6. archive_account与actual_speaker分离

上传账号可能只是搬运、切片、转载、录播或补档账号。必须分别记录：

```text
archive_account
actual_speaker
```

只有正文、原视频来源或明确上下文能够确认说话人时，才能并入对应UP。不能因为标题带UP名字就直接归类。

搬运号也不能因为文件多就自动作为独立UP候选。

## 7. 去重与Prediction Chain

### 文件级重复

完全重复或大面积重复字幕只保留一个主证据文件，其他标记重复来源。

### 同场切片

同一直播拆成第一篇/第二篇/第三篇时，不直接删除；共享：

```text
source_session
duplicate_group
```

预测仍按内容提取。

### 连续重复观点

连续多日重复相同观点，如果没有新增目标、方向、时间窗或触发条件，不得重复增加分母。

建立：

```text
prediction_chain_id
chain_action = initial / confirmation / update / reversal
```

只有预测结构真正改变时才形成新独立事件。

## 8. 有效预测标准

进入 `prediction_eligible = YES` 的内容通常同时满足：

1. 面向未来；
2. 目标明确；
3. 方向或状态明确；
4. 有可解释的时间范围；
5. 可被未来行情证伪。

常见有效类型：

```text
明天继续跌
下周会反弹
3700-3750是重要支撑
科技短期难恢复主升
成交额达到2.5万亿后科技会反弹
这里不要追高，应降低仓位
```

最后一类属于风控/仓位事件，不与纯方向事件混算。

## 9. 必须排除的内容

通常 `prediction_eligible = NO`：

- 教学：技术指标一般规律；
- 复盘：描述已经发生的行情；
- 事后认领：找不到原始预测证据的“我早就说过”；
- 营销/情绪表达；
- 没有明确方向的提醒；
- 无法证伪的长期口号。

事后认领标：

```text
unsupported_retrospective_claim
```

## 10. 复合预测必须拆子事件

一句话可能包含多个 `target × horizon × prediction_type`。

例：

> 上证基本见底，下周会反弹，但创业板还要再杀一下。

拆为：

```text
上证 / 阶段见底
上证 / 下周上涨
创业板 / 短期下跌
```

例：

> 周五先跌一下，周一会起来，然后还能延续两三天。

拆为：

```text
周五下跌 / T+1
周一反弹 / 指定日
反弹延续2-3天 / T+3~T+5
```

硬规则：**后面的正确不能洗掉前面的错误。**

## 11. 不同目标必须拆开

如果“市场基本见底”后续正文明确：

```text
上证差不多见底
创业板可能还没有
```

必须拆为独立目标，例如：

```text
SHCOMP
CHINEXT
STAR50
```

不能用“市场整体后来上涨”模糊验证。

## 12. prediction_type分类

至少使用：

```text
direction
level
sector_rotation
risk_control
position
conditional_plan
state_switch
```

禁止把“不要追高”直接解释成“明天必跌”，也禁止把“风险较高”直接解释成方向性看空。

方向、风险和仓位分别记账、分别评分。

## 13. 条件预测Trigger规则

例如：

> 如果明天成交额达到2.5-3万亿，科技会反弹。

记录：

```text
trigger = turnover >= 2.5T
```

验证时先判断 `trigger_status`。

若条件未发生：

```text
result = UNTRIGGERED
```

不进入准确率分母。只有条件发生后才验证后半句方向。

## 14. Horizon与验证窗口

默认保存：

```text
T+1
T+3
T+5
T+10
```

但主评分窗口必须尊重原话。

- “明天反弹”主要验证T+1；T+1跌、T+5涨不能算命中。
- “未来一周震荡向上”主要看T+3/T+5。
- “中期行情没走完”主要看T+10及更长窗口，并明确规则。

若原话时间模糊，可结合上下文设 `horizon` 与 `horizon_confidence`，但不得事后挑最有利窗口。

## 15. Pending制度

尚未走完原定验证窗口：

```text
result = PENDING
```

PENDING不进入分母。禁止为了给最新准确率而提前判近期事件。

## 16. 行情验证

行情证据优先级：

1. 已有台账中可审计行情数据；
2. 交易所/指数公司/官方行情源；
3. 可靠金融行情源。

至少记录：

```text
actual_return_1d
actual_return_3d
actual_return_5d
actual_return_10d
```

推荐增加：

```text
MFE
MAE
```

### 关键位事件

`prediction_type = level` 时不能只看T+5涨跌，应验证：

1. 是否进入目标区间；
2. 是否有效跌破/突破；
3. 到达后是否发生预期反应；
4. 最大越界幅度；
5. 随后反向/顺向幅度。

## 17. 结果与计分

```text
HIT = 1
PARTIAL = 0.5
MISS = 0
```

以下不进入分母：

```text
PENDING
UNTRIGGERED
EXCLUDED
NO_SCORE
```

加权准确率：

```text
(HIT + 0.5 * PARTIAL) / (HIT + PARTIAL + MISS)
```

必须独立做sanity check：

```text
denominator == HIT + PARTIAL + MISS
weighted_score == HIT + 0.5*PARTIAL
weighted_accuracy == weighted_score / denominator
```

不要只相信Excel公式显示值。

## 18. Partial边界

PARTIAL只用于预测核心方向基本实现、但有中等偏差，例如方向对但时间轻度偏移，或目标大体达到但幅度明显不足。

不能用Partial救明显错位的次日预测：

```text
“明天涨”
实际明天跌、第五天涨
```

主事件应为MISS。

## 19. 标准事件字段

### 来源/身份

```text
archive_date
actual_date
publish_time
archive_account
actual_speaker
source_file
source_session
duplicate_group
prediction_chain_id
historical_backfill
```

### 内容

```text
content_type
raw_quote
context_note
```

### 预测结构

```text
prediction_eligible
prediction_type
target
direction
horizon
horizon_confidence
trigger
trigger_status
level
position_advice
falsifiable
target_confidence
```

### 验证

```text
validation_window
actual_return_1d
actual_return_3d
actual_return_5d
actual_return_10d
MFE
MAE
```

### 结果

```text
result
score
confidence
validation_evidence
validation_source
review_note
```

## 20. 每个UP的标准产物

### A. 事件主账

```text
prediction_event_ledger_<UP>_vN.xlsx
prediction_event_ledger_<UP>_vN.csv
```

Excel推荐工作表：

1. 事件账本
2. 阶段汇总
3. 原始文件扫描
4. 验证行情
5. 口径说明

### B. 阶段报告

```text
UP主阶段报告_<UP>_vN.md
```

至少包含：

- 样本日期范围
- 原始字幕文件数
- 可计预测数
- Mature / Pending / Untriggered
- Hit / Partial / Miss
- 加权准确率
- Direction Score
- Risk Control Score
- 强项、弱项
- 最佳时间尺度
- 最可靠目标类型
- 典型命中/失败案例
- 对实际交易的功能定位

### C. 总进度台账

总账只保存UP名称、当前canonical版本、最新样本日期、主要统计和文件路径。

总账不是原始证据，不得覆盖单UP主账。

## 21. Canonical与版本管理

避免产生混乱的 `v4(1)`、`v5(2)` 等副本。

推荐：

```text
ledgers/
  <UP>/
    prediction_event_ledger.csv
    prediction_event_ledger.xlsx
    summary.md
    archive/
      prediction_event_ledger_v1.csv
      prediction_event_ledger_v2.csv
```

网站、日报、自动化只读取canonical。更新前把旧canonical归档。

## 22. UP能力画像

禁止只按总准确率排名。至少拆：

```text
index_direction
next_day_timing
medium_term
sector_rotation
key_levels
risk_control
position_management
```

还可按上证、创业板、科创、港股、美股、行业板块、个股继续拆分。

最终必须说明：**这个UP最值得在哪个决策节点被参考。**

## 23. 候选UP筛选

全库筛选下一批UP按：

1. 原始字幕文件数；
2. 覆盖交易日和时间跨度；
3. 去重后独立内容量；
4. 可证伪未来预测密度；
5. 明确时间窗/点位/条件频率；
6. 是否已有足够后续行情；
7. 是否对现有UP组合有功能增量；
8. 是否大量为教学、复盘、营销、转载。

输出：

```text
Tier A：立即建账
Tier B：先抽样10-20份
Skip：样本太少 / 复盘为主 / 搬运为主 / 难以证伪
```

不得根据印象虚构候选名单。

## 24. 标准SOP

```text
STEP 1   扫描全部日期 index.json
STEP 2   建立全库作者/文件清单
STEP 3   筛选目标UP候选字幕
STEP 4   逐份读取原始字幕正文
STEP 5   校正 actual_date
STEP 6   确认 actual_speaker
STEP 7   标记 historical_backfill
STEP 8   建立 duplicate_group / source_session
STEP 9   建立 prediction_chain
STEP 10  排除教学/复盘/营销/事后认领
STEP 11  抽取所有可证伪未来判断
STEP 12  按 target × horizon × prediction_type 拆事件
STEP 13  条件预测先验证 trigger
STEP 14  写入事件主账
STEP 15  拉取对应市场行情
STEP 16  按原始 horizon 验证 T+1/T+3/T+5/T+10
STEP 17  未成熟标 PENDING
STEP 18  HIT=1 / PARTIAL=.5 / MISS=0
STEP 19  分母与公式 sanity check
STEP 20  计算方向/关键位/风控/板块等能力
STEP 21  生成阶段报告
STEP 22  更新 canonical
STEP 23  更新总进度索引
STEP 24  网页/日报只读取 canonical
```

## 25. 强制终检

- [ ] 原始字幕是否为唯一主证据
- [ ] 是否扫描完整日期范围
- [ ] archive_date / actual_date是否分离
- [ ] archive_account / actual_speaker是否分离
- [ ] 是否识别历史补档
- [ ] 同场切片是否去重
- [ ] 重复观点是否形成Prediction Chain
- [ ] “我之前说过”是否找到原始证据
- [ ] 教学/复盘/营销是否排除
- [ ] 条件预测是否先检查trigger
- [ ] 不同指数/板块/个股是否拆开
- [ ] 不同时间窗是否拆开
- [ ] 风控/仓位与方向是否拆开
- [ ] T+1错误是否被后续行情洗掉
- [ ] 未成熟预测是否标PENDING
- [ ] denominator是否等于HIT+PARTIAL+MISS
- [ ] 加权准确率是否独立复算
- [ ] 是否保留典型命中和失败案例
- [ ] 是否形成能力画像而不是单一百分比
- [ ] canonical是否为网站唯一读取入口

## 26. 常见错误与修复

### 全仓中文搜索漏文件
修复：逐日期扫描 `index.json`，按索引拿 `text_file`。

### 少量样本先算最终准确率
修复：先做Raw Inventory和完整时间范围确认。

### 目录日期当实际预测日
修复：正文校正 `actual_date`，保留 `archive_date` 审计。

### 搬运账号直接当UP
修复：正文确认 `actual_speaker`。

### 一场直播只记一个对错
修复：按 `target × horizon × prediction_type` 拆独立事件。

### 同一观点连续几天重复加分
修复：Prediction Chain，只把结构变化作为新事件。

### 用后续上涨洗掉“明天涨”的错
修复：主评分严格服从原始horizon。

### 条件没触发仍判错
修复：`UNTRIGGERED`，不进分母。

### 近期预测提前判
修复：`PENDING`。

### 风控提示当方向预测
修复：按prediction_type分开记账和评分。

### 只看收盘
修复：加入MFE/MAE；关键位采用专门验证逻辑。

### 总账版本混乱
修复：单UP建立canonical + archive，网站只读canonical。

## 27. 五条铁律

1. **只认当时原始字幕，不认事后自述。**
2. **目录日期不是预测日期，必须校正 `actual_date`。**
3. **一个视频不是一个预测，必须拆成独立 `target × horizon` 事件。**
4. **后来的正确不能洗掉原时间窗口内的错误。**
5. **最终评价必须回答“这个UP在哪个决策环节值得参考”，不能只给一个准确率。**

## 28. 执行要求

- 用户要求完整复盘时，不要先拿少量样本给最终准确率。
- 数据源不完整时明确标注阶段性，但优先继续实际扫描，不停留在流程说明。
- 用户要求执行时，优先产生真实文件、真实事件数和可核验结论，避免只汇报“正在做”。
- 不得为了结果好看而扩大Partial、延长验证窗口或事后更改预测含义。
- 每个最终判断都应能回溯到：

```text
raw_quote + source_file + validation_source
```
