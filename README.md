# Hermes Daily Report

Hermes 服务器把 B 站原始字幕和已有结构化 JSON 同步到此私有仓库；ChatGPT 再按字幕技能生成独立研报。

## 目录

- `subtitles/YYYY-MM-DD/`：当日原始字幕与全量 `index.json`
- `data/`：Hermes 已生成的结构化 JSON（辅助来源）
- `reports/hermes/`：Hermes 自有报告
- `reports/chatgpt/YYYY-MM-DD/`：ChatGPT 生成的 `report.json` 与 `report.md`
- `scripts/bilibili-tracker.py`：追踪UP主并抓取B站AI字幕
- `scripts/sync.sh`：服务器同步脚本

## 推荐时序（北京时间）

1. 交易日收盘后，市场温度仓库更新一次腾讯行情宽度数据。
2. 22:00，Hermes 服务器运行 `scripts/bilibili-tracker.py`，追踪新视频并抓取AI字幕。
3. 22:15，Hermes 服务器运行 `scripts/sync.sh`，全量重建当天字幕索引并推送。
4. 22:35，ChatGPT 定时任务读取全部字幕、校验清单和 SHA-256，然后生成当日研报并同步网页。
5. 周日 22:35，任务合并读取周六、周日字幕，去重后生成周末版研报。

服务器 cron 需要单独配置；仅把脚本提交到仓库不会自动创建或修复服务器上的 cron。

## 字幕抓取配置

登录态只保存在服务器，不写入 GitHub。脚本按以下优先级读取：

1. 环境变量 `BILI_SESSDATA`
2. `~/.hermes/data/bilibili/cookies.json`
3. 服务器本机 Chrome Cookie（仅安装并可读取 `browser_cookie3` 时）

推荐的 Cookie 文件格式：

```json
{"SESSDATA":"在服务器本地填写，禁止提交到GitHub"}
```

脚本只把 Cookie 发送给 `api.bilibili.com`；下载独立字幕文件时不携带 Cookie。未生成字幕的视频不会被提前标记完成，后续运行会继续补抓。

## 手动运行

```bash
# 抓取新视频字幕
python3 scripts/bilibili-tracker.py

# 默认使用北京时间当天
bash scripts/sync.sh

# 补跑指定日期
bash scripts/sync.sh 2026-08-07
```

可用 `HERMES_REPO_DIR`、`HERMES_SOURCE_JSON`、`HERMES_SOURCE_SUB`、`HERMES_SSH_KEY` 覆盖服务器路径。

## 同步保证

- `git pull --ff-only` 失败时立即停止，避免盲目覆盖远端。
- 每次从当天全部有效字幕重建索引；未变化文件也会进入 `entries`。
- `repository_path` 使用仓库相对路径，标题和 UP 主兼容旧、新两种字幕格式。
- 字幕、JSON 与索引内容没有真实变化时不提交。
- 拒绝疑似密钥文件和超过 10 MB 的单个文件。
