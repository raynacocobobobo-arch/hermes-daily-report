# YAN DESK 日报规范

目标：把字幕观点压缩成可执行、可证伪、可复盘的机构战术简报。页面不展示方法论解释，先给决策，再给证据。

## 固定顺序

1. 首席结论：一句明确方向，禁止“可能、也许、或许”堆叠。
2. 行动台：DO / WAIT / STOP，每项必须有条件。
3. 三情景：主情景、上行情景、防守情景；每项包含触发、行动、失效。
4. 方向矩阵：方向、评级、入场条件、执行、失效条件、周期。
5. 前瞻账本：预测、期限、依据、验证信号、失效条件。
6. 风险雷达：按高 / 中高 / 中 / 低排序，不输出无证据的数字概率。
7. 关键位与催化时间表。
8. 每位分析师核心观点：姓名、立场、关注方向、一句话核心判断、对应字幕文件。
9. 共识强度、关键分歧、重要原话和来源审计。

## JSON 扩展字段

保留技能既有字段，并增加：

- `desk_brief`: `call`, `summary`, `regime`, `action_bias`, `conviction`, `actions[]`
- `scenarios[]`: `type`, `name`, `thesis`, `trigger`, `action`, `invalidation`
- `trade_setups[]`: `name`, `rating`, `entry`, `action`, `invalidation`, `horizon`
- `forecast[]`: `horizon`, `call`, `reason`, `proof`, `invalidation`
- `risk_dashboard[]`: `risk`, `level`, `trigger`
- `analyst_distribution`: `signal`, `positive`, `mixed`, `cautious`, `summary`
- `catalyst_clock[]`: `time`, `event`, `watch`
- `analysts[]`: `speaker`, `stance`, `focus`, `view`, `source_files[]`

## 研究纪律

- 预测必须是条件式；不能从单一UP主推导为市场事实。
- 不编造概率、仓位比例、目标价或实时行情。
- 所有关键位保留来源；冲突观点必须并列。
- 当日每位有有效字幕的分析师都必须单独列出；不得只写共识后省略个人观点。
- 字幕与行情日期不同，页面顶部必须显示数据滞后。
- 没有足够证据时写“等待确认”，不填充模板。
- 结论不超过18字，摘要不超过80字，单条行动不超过45字。
